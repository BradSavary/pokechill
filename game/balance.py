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

# --- Time ------------------------------------------------------------------

# Day/night cycle, in Paris local time: night from 21:00 to 06:00
GAME_TIMEZONE = "Europe/Paris"
NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6
