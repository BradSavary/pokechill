"""
Reference data of the Pokédex: types, species, evolution chains and moves.

These tables hold *static* game data imported once from PokéAPI (see the
`import_pokeapi` command). They describe what a species is, never what a
player owns: player data will live in other apps from step 1 onwards.
"""

from django.db import models
from django.templatetags.static import static

from game import balance
from game.arrivals import SpeciesRule

# Rarity values come from the game engine, the single source of truth:
# ("very_rare", "Very rare"), ("legendary", "Legendary")...
RARITY_CHOICES = [(key, key.replace("_", " ").capitalize()) for key in balance.RARITY_WEIGHTS]


class Type(models.Model):
    """One of the 18 elemental types (modern type chart, Fairy included)."""

    # PokéAPI identifier ("fire"), used as a stable key by the importer
    slug = models.SlugField(unique=True)
    # Display name ("Fire")
    name = models.CharField(max_length=20)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    @property
    def icon_url(self) -> str:
        return static(f"pokemon/types/{self.slug}.png")


class EvolutionChain(models.Model):
    """
    A family of species linked by evolution (e.g. Charmander → Charmeleon → Charizard).

    The game has no evolution, but the family still matters: candies are
    shared by the whole chain, and evolved species are attracted by their
    base form.
    """

    pokeapi_id = models.PositiveIntegerField(unique=True)

    def __str__(self) -> str:
        base = self.base_species
        return f"{base.name} family" if base else f"Chain #{self.pokeapi_id}"

    @property
    def base_species(self) -> "Species | None":
        """First form of the family among imported species (Pikachu, not Pichu)."""
        return self.species.order_by("evolution_stage", "number").first()

    @property
    def candy_url(self) -> str:
        """Candy icon of the family, named after its base form (see the importer)."""
        return static(f"pokemon/candies/{self.base_species.slug}.png")


class Species(models.Model):
    """A Pokémon species of the Kanto Pokédex (#1 to #151)."""

    # --- Identity ---------------------------------------------------------
    # National Pokédex number. Kept separate from the primary key `id` so the
    # database never depends on business data.
    number = models.PositiveSmallIntegerField(unique=True)
    slug = models.SlugField(unique=True)  # "bulbasaur"
    name = models.CharField(max_length=30)  # "Bulbasaur"
    genus = models.CharField(max_length=40)  # "Seed Pokémon"
    flavor_text = models.TextField(blank=True)
    # Mew is officially "mythical": this game counts it as a legendary
    is_legendary = models.BooleanField(default=False)

    # --- Types ------------------------------------------------------------
    # Two foreign keys rather than a many-to-many: a species has at most two
    # types and their order matters (Bulbasaur is Grass first, then Poison).
    # PROTECT forbids deleting a type still used by a species.
    primary_type = models.ForeignKey(Type, on_delete=models.PROTECT, related_name="primary_species")
    secondary_type = models.ForeignKey(
        Type,
        on_delete=models.PROTECT,
        related_name="secondary_species",
        null=True,
        blank=True,
    )

    # --- Base stats -------------------------------------------------------
    # One column per stat: these are also the six stats targeted by natures.
    hp = models.PositiveSmallIntegerField()
    attack = models.PositiveSmallIntegerField()
    defense = models.PositiveSmallIntegerField()
    special_attack = models.PositiveSmallIntegerField()
    special_defense = models.PositiveSmallIntegerField()
    speed = models.PositiveSmallIntegerField()

    # --- Body (raw PokéAPI units, converted by the properties below) -------
    height_dm = models.PositiveSmallIntegerField(help_text="Height in decimetres")
    weight_hg = models.PositiveIntegerField(help_text="Weight in hectograms")

    # --- Evolution family ---------------------------------------------------
    # Pokémon never evolve in this game: the family only drives shared candies,
    # candy costs and the lineage shown on the Pokédex entry.
    evolution_chain = models.ForeignKey(
        EvolutionChain, on_delete=models.PROTECT, related_name="species"
    )
    # 1 = base form, 2 = second form, 3 = third form (drives candy costs later)
    evolution_stage = models.PositiveSmallIntegerField(default=1)
    # SET_NULL: deleting a species must not delete its evolutions
    evolves_from = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="evolutions",
    )

    # --- Game data (from data/species/*.json, see the load_species command) -
    # Everything above comes from PokéAPI; these fields are game design.
    # A species without a data file is not available yet: it never arrives.
    is_available = models.BooleanField(default=False)
    rarity = models.CharField(max_length=10, choices=RARITY_CHOICES, blank=True)
    # Level of the Pokémon when it arrives at the ranch
    min_level = models.PositiveSmallIntegerField(default=1)
    # Condition tree evaluated by game.conditions; null = may arrive any time
    arrival_conditions = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["number"]
        verbose_name_plural = "species"

    def __str__(self) -> str:
        return f"#{self.number:03d} {self.name}"

    def to_rule(self) -> SpeciesRule:
        """What the game engine needs to know about this species."""
        return SpeciesRule(slug=self.slug, rarity=self.rarity, conditions=self.arrival_conditions)

    # --- Derived values -----------------------------------------------------

    @property
    def types(self) -> list[Type]:
        """Types in display order (one or two)."""
        return [t for t in (self.primary_type, self.secondary_type) if t is not None]

    @property
    def base_stat_total(self) -> int:
        return (
            self.hp
            + self.attack
            + self.defense
            + self.special_attack
            + self.special_defense
            + self.speed
        )

    @property
    def height_m(self) -> float:
        return self.height_dm / 10

    @property
    def weight_kg(self) -> float:
        return self.weight_hg / 10

    # Media files follow a naming convention based on the Pokédex number, so
    # no database field is needed (see the import command).

    @property
    def sprite_url(self) -> str:
        return static(f"pokemon/sprites/{self.number}.png")

    @property
    def shiny_sprite_url(self) -> str:
        return static(f"pokemon/sprites/shiny/{self.number}.png")

    @property
    def cry_url(self) -> str:
        return static(f"pokemon/cries/{self.number}.ogg")


class Move(models.Model):
    """An attack a species can learn."""

    class DamageClass(models.TextChoices):
        PHYSICAL = "physical", "Physical"
        SPECIAL = "special", "Special"
        STATUS = "status", "Status"

    slug = models.SlugField(unique=True)  # "flamethrower"
    name = models.CharField(max_length=30)  # "Flamethrower"
    type = models.ForeignKey(Type, on_delete=models.PROTECT, related_name="moves")
    damage_class = models.CharField(max_length=10, choices=DamageClass.choices)
    # Status moves have no power, some moves never miss: hence nullable
    power = models.PositiveSmallIntegerField(null=True, blank=True)
    accuracy = models.PositiveSmallIntegerField(null=True, blank=True)
    pp = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class SpeciesMove(models.Model):
    """
    Association table: how a species learns a move (FireRed/LeafGreen learnsets).

    A plain many-to-many could not store *how* and *when* the move is learned,
    hence this explicit "through" model.
    """

    class LearnMethod(models.TextChoices):
        LEVEL_UP = "level-up", "Level up"
        MACHINE = "machine", "TM / HM"

    species = models.ForeignKey(Species, on_delete=models.CASCADE, related_name="learnset")
    move = models.ForeignKey(Move, on_delete=models.CASCADE, related_name="learned_by")
    learn_method = models.CharField(max_length=10, choices=LearnMethod.choices)
    # Level at which the move is learned; 0 for TMs (no level involved)
    level = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["learn_method", "level", "move__name"]
        constraints = [
            # The same move can't be listed twice for the same method and level
            models.UniqueConstraint(
                fields=["species", "move", "learn_method", "level"],
                name="unique_species_move_entry",
            )
        ]

    def __str__(self) -> str:
        return f"{self.species.name} – {self.move.name} ({self.get_learn_method_display()})"
