"""
The player's game state.

Django's User handles identity (username, password); Player holds the game
save attached to it. Every table of the game state points to a Player.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from game import balance
from game.zones import ZONES

# Zones and resources as choices for the database: ("meadow", "Meadow")...
ZONE_CHOICES = [(zone.slug, zone.name) for zone in ZONES.values()]
RESOURCE_CHOICES = [(zone.resource, zone.resource_name) for zone in ZONES.values()]


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
    # Current step of the tutorial (see ranch/tutorial.py); finished at the end
    tutorial_step = models.PositiveSmallIntegerField(default=0)
    # The feeder's slots, in the order they will be eaten: a list of
    # [resource, units], e.g. [["apricorn", 13], ["berry", 5]]. A list, not an
    # object: the order matters, and PostgreSQL doesn't keep the order of an
    # object's keys. A small JSON value rather than a table: the engine works
    # on this very list (see game.arrivals.catch_up).
    feeder = models.JSONField(default=list, blank=True)
    # Earned by the Pokédex challenges, spent in the skill tree
    research_points = models.PositiveIntegerField(default=0)
    # False for the saves made before the research (step 3): their challenges
    # are set up from their current state at their next visit (ranch.research)
    research_synced = models.BooleanField(default=True)
    # Rewards of the research waiting to be claimed (a challenge completed, a
    # stage reached): the "!" of the Pokédex menu, read without any query.
    # Set by ranch.research.record, recomputed after each claim.
    has_rewards = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f"Player of {self.user.username}"

    @property
    def welcome_capacity(self) -> int:
        """Places of the Welcome area (research bonuses will be added in step 3)."""
        return balance.WELCOME_CAPACITY_BASE

    @property
    def feeder_capacity(self) -> int:
        """Slots of the feeder (the skill tree will add more)."""
        return balance.FEEDER_SLOTS_BASE


class PlayerZone(models.Model):
    """
    A harvest zone of the player (a row exists once the zone is unlocked).

    Its work since the last collection piles up here (see ranch.zones): the
    resource made, and the hours worked, capped by the storage.
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="zones")
    zone = models.CharField(max_length=20, choices=ZONE_CHOICES)
    # Hours worked since the last collection (at most balance.ZONE_WORK_HOURS_CAP)
    hours_worked = models.PositiveSmallIntegerField(default=0)
    # Resource made since the last collection, in hundredths (100 = 1 resource)
    stock_centi = models.PositiveIntegerField(default=0)
    collected_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["id"]
        constraints = [models.UniqueConstraint(fields=["player", "zone"], name="one_row_per_zone")]

    def __str__(self) -> str:
        return f"{self.spec.name} of {self.player.user.username}"

    @property
    def spec(self):
        """The zone's definition in the engine (types, resource): game.zones.Zone."""
        return ZONES[self.zone]

    @property
    def capacity(self) -> int:
        """Pokémon it can hold (the skill tree will add slots)."""
        return balance.ZONE_SLOTS_BASE

    @property
    def stock(self) -> int:
        """Whole resources waiting to be collected."""
        return self.stock_centi // 100

    @property
    def is_full(self) -> bool:
        """The storage is full: its Pokémon have stopped working."""
        return self.hours_worked >= balance.ZONE_WORK_HOURS_CAP


class OwnedPokemon(models.Model):
    """
    A Pokémon of the player's collection: one per species at most.

    Owning a species means its Pokédex entry reached stage 1 ("Encountered").
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="pokemon")
    # PROTECT: a species with owners can't be deleted from the catalogue
    species = models.ForeignKey("pokedex.Species", on_delete=models.PROTECT, related_name="owners")
    level = models.PositiveSmallIntegerField(default=1)
    # Experience earned since the current level was reached (the blue bar of
    # the games), see game.experience.add_experience
    experience = models.PositiveIntegerField(default=0)
    # Experience earned in a zone, applied when the zone is collected
    pending_experience = models.PositiveIntegerField(default=0)

    # --- Status: a Pokémon is in one place at a time ---------------------------
    # Changed only by ranch.zones.move_pokemon. Expedition and care come later.
    FREE, IN_ZONE = "free", "zone"
    STATUS_CHOICES = [(FREE, "Free"), (IN_ZONE, "In a zone")]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=FREE)
    # The zone it works in (only when its status is IN_ZONE). PROTECT: a zone
    # with workers can't be deleted.
    zone = models.ForeignKey(
        PlayerZone, on_delete=models.PROTECT, null=True, blank=True, related_name="workers"
    )
    # Its spot on the zone's map (0, 1, 2... see ranch/zone_maps.py): kept as
    # long as it works there, so the others never move when one comes or goes
    spot = models.PositiveSmallIntegerField(null=True, blank=True)

    # Natures obtained at least once for this species (e.g. ["attack", "speed"]).
    # Their stat bonuses arrive with step 5; they are recorded from the start.
    unlocked_natures = models.JSONField(default=list)
    shiny_unlocked = models.BooleanField(default=False)
    obtained_at = models.DateTimeField(auto_now_add=True)
    # Research stage of its species whose reward was claimed (0 to 3). The
    # stage reached comes from its challenges; the player claims each stage's
    # reward in turn (ranch.research.claim_stage).
    research_stage = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["species__number"]
        constraints = [
            # The database itself forbids a second Pokémon of the same species
            models.UniqueConstraint(fields=["player", "species"], name="one_pokemon_per_species"),
            # A zone and a spot if and only if the status says so: no
            # half-assigned Pokémon
            models.CheckConstraint(
                condition=(
                    models.Q(status="zone", zone__isnull=False, spot__isnull=False)
                    | (~models.Q(status="zone") & models.Q(zone__isnull=True, spot__isnull=True))
                ),
                name="zone_and_spot_match_status",
            ),
            # One Pokémon per spot of a zone (free Pokémon have no zone: NULLs
            # never collide in a unique constraint)
            models.UniqueConstraint(fields=["zone", "spot"], name="one_pokemon_per_spot"),
        ]

    def __str__(self) -> str:
        return f"{self.species.name} of {self.player.user.username}"


class ObjectiveProgress(models.Model):
    """
    The player's progress on one objective (a Pokédex challenge for now).

    A row only exists once the objective moved. The objectives themselves are
    not stored: they are built from the species data (game.challenges), and
    found here by their key, e.g. "dex:pidgey:obtain-10".
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="objectives")
    key = models.CharField(max_length=80)
    progress = models.PositiveIntegerField(default=0)
    # When it was completed (null: not yet). Kept even if its target changes.
    completed_at = models.DateTimeField(null=True, blank=True)
    # When its research points were claimed (null: waiting for the player)
    claimed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "key"], name="one_progress_per_objective")
        ]

    def __str__(self) -> str:
        return f"{self.key}: {self.progress}"


class ResourceStock(models.Model):
    """The player's stock of one resource (berries, apricorns...)."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="resources")
    resource = models.CharField(max_length=20, choices=RESOURCE_CHOICES)
    amount = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "resource"], name="one_stock_per_resource")
        ]

    def __str__(self) -> str:
        return f"{self.amount} {self.get_resource_display()}"


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


class Arrival(models.Model):
    """
    A Pokémon waiting at the Welcome area, until the player reveals it.

    Created by the hourly catch-up (see ranch.services.catch_up_player).
    """

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="arrivals")
    species = models.ForeignKey("pokedex.Species", on_delete=models.PROTECT)
    # The hourly slot it arrived at (UTC, on the hour)
    slot = models.DateTimeField()
    nature = models.CharField(max_length=20)
    is_shiny = models.BooleanField(default=False)

    class Meta:
        ordering = ["slot"]
        constraints = [
            # One arrival per hour and per player: even if two catch-ups ran at
            # the same time, the database would refuse the duplicate
            models.UniqueConstraint(fields=["player", "slot"], name="one_arrival_per_slot")
        ]

    def __str__(self) -> str:
        return f"{self.species.name} for {self.player.user.username} at {self.slot:%Y-%m-%d %H:00}"
