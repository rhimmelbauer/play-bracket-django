from django.db import models
from django.core.exceptions import ValidationError
from django.db.models.query import QuerySet
from django.conf import settings
from datetime import date
from typing import TypedDict


class PlayerEventResults(TypedDict):
    name: str
    won: int
    lost: int
    total: int
    win_ratio: float


def hit_ratio(hit: int, total: int) -> float:
    if not total:
        return 0

    return (hit / total) * 100


class Event(models.Model):
    place = models.CharField(max_length=200, blank=True, null=True)
    date = models.DateField(default=date.today(), null=False, blank=False)

    def __str__(self):
        if self.place:
            return f"{self.date} - {self.place}"
        return f"{self.date}"

    def matches_display(self) -> list[str]:
        return [m.__str__() for m in self.matches.all()]

    def players(self) -> set:
        return set(player for match in self.matches.all() for player in match.players())

    def players_display(self) -> list[str]:
        return [p.name for p in self.players()]

    def player_result(self, player) -> PlayerEventResults:
        won = self.matches.filter(winners__in=[player]).count()
        lost = self.matches.filter(losers__in=[player]).count()

        win_ration = hit_ratio(won, (won + lost))

        return PlayerEventResults(
            name=player.name,
            won=won,
            lost=lost,
            total=(won + lost),
            win_ratio=win_ration
        )

    def ranking(self) -> list[PlayerEventResults]:
        ranking: list[PlayerEventResults] = []

        for player in self.players():
            ranking.append(self.player_result(player))

        return sorted(ranking, key=lambda d: d["win_ratio"], reverse=True)


class Player(models.Model):
    name = models.CharField(max_length=80, blank=False, null=False, unique=True)

    def __str__(self):
        return self.name

    def sports_display(self) -> list[str]:
        return self.sports.all().values_list('name', flat=True)

    def sport_win_ratio(self, sport) -> float:
        won = self.winners.filter(league__sport=sport).count()
        lost = self.losers.filter(league__sport=sport).count()

        return hit_ratio(won, (won + lost))

    def league_win_ratio(self, league) -> float:
        won = self.winners.filter(league=league).count()
        lost = self.losers.filter(league=league).count()

        return hit_ratio(won, (won + lost))


class Sport(models.Model):
    name = models.CharField(max_length=80, blank=False, null=False, unique=True)
    players = models.ManyToManyField(Player, blank=True, related_name="sports")

    def __str__(self) -> str:
        return self.name
    
    def players_display(self) -> list[str]:
        return self.players.all().values_list('name', flat=True)


class League(models.Model):
    name = models.CharField(max_length=80, null=False, blank=False)
    admins = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="admins")
    sport = models.ForeignKey(Sport, blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return self.name

    def players(self) -> QuerySet[Player]:
        return self.sport.players.all()


class Match(models.Model):
    date = models.DateField(default=date.today(), null=False, blank=False)
    cleared = models.BooleanField(default=False)
    winners = models.ManyToManyField(Player, blank=True, related_name="winners")
    winner_score = models.IntegerField(blank=True, null=True)
    losers = models.ManyToManyField(Player, blank=True, related_name="losers")
    loser_score = models.IntegerField(blank=True, null=True)
    league = models.ForeignKey(League, related_name="matches", blank=True, null=True, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, related_name="matches", blank=True, null=True, on_delete=models.CASCADE)

    def __str__(self):
        return f"({self.pk} - {self.date}) " +\
            f"Winners: {[x for x in self.winners.all().values_list("name", flat=True)]}, " +\
            f"Losers: {[x for x in self.losers.all().values_list("name", flat=True)]}"

    def players(self) -> QuerySet[Player]:
        return self.winners.all() | self.losers.all()

    def players_display(self) -> list[str]:
        return [p.name for p in self.players()]

    def winners_display(self) -> list[str]:
        return [w.name for w in self.winners.all()]

    def losers_display(self) -> list[str]:
        return [l.name for l in self.losers.all()]

    def validate_winners_losers_fields(self):
        """No player can be both a winner and a loser

        """
        winner_in_loser = [True for winner in self.winners.all() if winner in self.losers.all()]
        loser_in_winner = [True for loser in self.losers.all() if loser in self.winners.all()]

        if winner_in_loser:
            raise ValidationError("You can't have a winner in the losers field")

        if loser_in_winner:
            raise ValidationError("You can't have a loser in the winners field")

    def save(self, *args, **kwargs):
        self.validate_winners_losers_fields()
        return super().save(*args, **kwargs)
