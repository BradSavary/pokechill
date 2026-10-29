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
    "uncommon": 60,
    "rare": 25,
    "very_rare": 8,
    "legendary": 1,
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

# Resources given once the tutorial's first Pokémon works in a zone, to try
# the feeder at once (resource, amount)
TUTORIAL_FEEDER_GIFT = ("berry", 10)

# --- Duplicates ------------------------------------------------------------

# Candies of the evolution family given when an owned species arrives again
CANDIES_PER_DUPLICATE = {
    "common": 5,
    "uncommon": 10,
    "rare": 20,
    "very_rare": 50,
    "legendary": 100,
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

# --- Candies ------------------------------------------------------------------

# A candy is worth CANDY_WORK_HOURS hours of zone work at the Pokémon's
# level (without the type bonus), divided by its evolution stage: candies
# stay useful at every level, and cost more for evolved forms. Charmander
# level 10: 2 x 50 = 100 experience; Charizard level 50: 2 x 170 / 3 = 113.
CANDY_WORK_HOURS = 2

# --- Research: the Pokédex challenges (game.challenges) ------------------------

# "Obtain it N times": two tiers, fewer for rarer species (a very rare one
# arrives a few times a month at best). No "once": the stage 1 rewards the
# first obtention already.
CHALLENGE_OBTAIN_TIERS = {
    "common": (10, 20),
    "uncommon": (8, 15),
    "rare": (5, 10),
    "very_rare": (3, 5),
    "legendary": (2, 3),
}

# "Reach level N": two targets above its arrival level (min_level + offset,
# rounded up to a multiple of 5). Pidgey (level 1): 15 and 30.
CHALLENGE_LEVEL_OFFSETS = (10, 25)

# "Unlock N natures" (6 in all, one per stat)
CHALLENGE_NATURE_TIERS = (3, 6)

# "Gather N resources" (while working in a zone) and "Work N hours"
CHALLENGE_HARVEST_RESOURCES = 100
CHALLENGE_WORK_HOURS = 48

# Challenges completed for stage 2 ("studied"); stage 3 needs all of them
STAGE_2_CHALLENGES = 5

# Research points per challenge completed, by the species' rarity
RESEARCH_POINTS_PER_CHALLENGE = {
    "common": 5,
    "uncommon": 8,
    "rare": 12,
    "very_rare": 20,
    "legendary": 40,
}

# Rewards of the stages: research points, and candies of the family at stage 2
# (stage 3 gives the species its mastery bonuses)
STAGE_1_RESEARCH_POINTS = 10
STAGE_2_RESEARCH_POINTS = 50
STAGE_2_CANDIES = 50

# --- Skill tree (game.skill_tree, data/skill_tree.json) -------------------------

# A node costs base x growth^(col - 1) of each currency of its tree (its
# column: the further right, the dearer), times SKILL_MILESTONE_FACTOR for a
# milestone. "resource": the resource of a zone (berries, apricorns...).
# Tuning the whole economy = these few numbers (check with the simulation:
# uv run python manage.py simulate).
SKILL_COST_BASE = {"research": 70, "resource": 20}
SKILL_COST_GROWTH = 1.2
SKILL_MILESTONE_FACTOR = 2.5

# The nodes of all the trees together should cost this share of the research
# points the species of the game can give (the rest: room for the nodes of
# later steps, and other sources of points will come: quests, expeditions).
# Checked by a test, to see at once when content and costs drift apart.
SKILL_BUDGET_SHARE = (0.50, 0.70)

# --- Time ------------------------------------------------------------------

# Day/night cycle, in Paris local time: night from 21:00 to 06:00
GAME_TIMEZONE = "Europe/Paris"
NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6
