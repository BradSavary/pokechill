"""
Balance values of the game, gathered in one place.

Tuning the game (production, costs, caps, odds) should only require editing
this file, never the logic that uses these values.
"""

# --- Arrivals ----------------------------------------------------------------

# Relative weight of each rarity in the hourly draw: among eligible species,
# a common one is 100 / 12 ≈ 8 times more likely than a rare one.
# Rarity is a gameplay setting. In this game Mew counts as a legendary too:
# a separate "mythical" tier would only ever contain one species.
RARITY_WEIGHTS = {
    "common": 100,
    "uncommon": 40,
    "rare": 12,
    "very_rare": 3,
    "legendary": 0.2,
}

# Places of the Welcome area at the start of the game. Once full, new
# arrivals are lost: this is the game's offline cap. Research (skill tree,
# step 3) will add places on top of this base value.
WELCOME_CAPACITY_BASE = 8

# One passive arrival in SHINY_ODDS is shiny. The Shiny Charm (step 5) will
# halve these odds, to 1 in 512.
SHINY_ODDS = 1024

# --- Start of the game ---------------------------------------------------

# Species owned by every new player
STARTER_SPECIES = ("bulbasaur", "charmander", "squirtle")

# Species given at the end of the tutorial
TUTORIAL_GIFT_SPECIES = "pikachu"

# --- Duplicates ------------------------------------------------------------

# Candies of the evolution family given when an owned species arrives again
CANDIES_PER_DUPLICATE = {
    "common": 3,
    "uncommon": 5,
    "rare": 10,
    "very_rare": 20,
    "legendary": 50,
}

# --- Zones -------------------------------------------------------------------

# Zones every player has from the start (the skill tree unlocks the others)
STARTING_ZONES = ("meadow", "orchard")

# Pokémon a zone can hold at the start (the skill tree will add more)
ZONE_SLOTS_BASE = 3

# Hours the Pokémon of a zone work between two collections. Then its storage
# is full: they stop (no resource, no experience) until the player collects.
# Like the Welcome area, it gives a reason to come back without punishing.
ZONE_WORK_HOURS_CAP = 8

# Production of one Pokémon per hour, in hundredths of a resource (integers
# keep the sums exact): 100 = 1 resource. A Pokémon whose types don't match
# the zone still works, at OFF_TYPE_PRODUCTION_PERCENT of the rate. Each
# level adds PRODUCTION_BONUS_PER_LEVEL_PERCENT: a level 50 makes 1.5 per hour.
PRODUCTION_PER_HOUR_CENTI = 100
OFF_TYPE_PRODUCTION_PERCENT = 25
PRODUCTION_BONUS_PER_LEVEL_PERCENT = 1

# Experience of a working Pokémon per hour: XP_PER_HOUR_BASE plus
# XP_PER_HOUR_PER_LEVEL per level (the games give more experience at higher
# levels, where the curves are steeper), plus XP_TYPE_BONUS_PERCENT in a zone
# that matches its type. E.g. a level 10 earns 50 per hour, 62 in its zone.
XP_PER_HOUR_BASE = 20
XP_PER_HOUR_PER_LEVEL = 3
XP_TYPE_BONUS_PERCENT = 25

# --- Feeder ------------------------------------------------------------------

# Slots of the feeder at the start (the skill tree will add more). A slot
# holds units of one zone's resource.
FEEDER_SLOTS_BASE = 1

# Each unit in a slot adds FEEDER_BONUS_PER_UNIT_PERCENT points to the chance
# that the Pokémon who arrives has one of that zone's types, up to
# FEEDER_MAX_UNITS units (+50 %): 13 apricorns, +13 points for Grass and Bug.
# The next Pokémon to arrive eats the whole first slot: it alone gets the
# bonus, the next one eats the next slot. No arrival (e.g. a full Welcome
# area), nothing eaten.
FEEDER_BONUS_PER_UNIT_PERCENT = 1
FEEDER_MAX_UNITS = 50

# --- Time ------------------------------------------------------------------

# Day/night cycle, in Paris local time: night from 21:00 to 06:00
GAME_TIMEZONE = "Europe/Paris"
NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6
