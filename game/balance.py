"""
Balance values of the game, gathered in one place.

Tuning the game (production, costs, caps, odds) should only require editing
this file, never the logic that uses these values.
"""

# --- Arrivals ----------------------------------------------------------------

# Relative weight of each rarity in the hourly draw: among eligible species,
# a common one is 100 / 12 ≈ 8 times more likely than a rare one.
RARITY_WEIGHTS = {
    "common": 100,
    "uncommon": 40,
    "rare": 12,
    "very_rare": 3,
    "mythical": 0.2,
}

# Number of arrivals that can wait at the Welcome area. Once full, new
# arrivals are lost: this is the game's offline cap.
WELCOME_CAPACITY = 8

# One arrival in SHINY_ODDS is shiny (1 in 512 for passive arrivals).
SHINY_ODDS = 512

# --- Duplicates ------------------------------------------------------------

# Candies of the evolution family given when an owned species arrives again
CANDIES_PER_DUPLICATE = {
    "common": 3,
    "uncommon": 5,
    "rare": 10,
    "very_rare": 20,
    "mythical": 50,
}

# --- Time ------------------------------------------------------------------

# Day/night cycle, in Paris local time: night from 21:00 to 06:00
GAME_TIMEZONE = "Europe/Paris"
NIGHT_START_HOUR = 21
NIGHT_END_HOUR = 6
