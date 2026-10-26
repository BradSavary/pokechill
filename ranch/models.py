"""
The player's game state.

Django's User handles identity (username, password); Player holds the game
save attached to it. Every table of the game state points to a Player.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Player(models.Model):
    # One user has at most one game save, and a save belongs to one user.
    # CASCADE: deleting a user deletes their save.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="player"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Last hourly slot processed by the catch-up (UTC, on the hour). The next
    # visit replays every hour after this one (see game.arrivals.catch_up).
    last_slot = models.DateTimeField()
    # Last visit to a game page: inactive guests are purged after a while
    last_seen_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return f"Player of {self.user.username}"


class OwnedPokemon(models.Model):
    """
    A Pokémon of the player's collection: one per species at most.

    Owning a species means its Pokédex entry reached stage 1 ("Encountered").
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="pokemon")
    # PROTECT: a species with owners can't be deleted from the catalogue
    species = models.ForeignKey("pokedex.Species", on_delete=models.PROTECT, related_name="owners")
    level = models.PositiveSmallIntegerField(default=1)
    # Natures obtained at least once for this species (e.g. ["attack", "speed"]).
    # Their stat bonuses arrive with step 5; they are recorded from the start.
    unlocked_natures = models.JSONField(default=list)
    shiny_unlocked = models.BooleanField(default=False)
    obtained_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["species__number"]
        constraints = [
            # The database itself forbids a second Pokémon of the same species
            models.UniqueConstraint(fields=["player", "species"], name="one_pokemon_per_species")
        ]

    def __str__(self) -> str:
        return f"{self.species.name} of {self.player.user.username}"


class CandyStock(models.Model):
    """Candies of one evolution family: shared by Bulbasaur, Ivysaur and Venusaur."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="candies")
    family = models.ForeignKey("pokedex.EvolutionChain", on_delete=models.PROTECT)
    amount = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "family"], name="one_stock_per_family")
        ]

    def __str__(self) -> str:
        return f"{self.amount} {self.family} candies"
