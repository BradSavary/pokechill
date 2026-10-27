"""Template filters of the ranch pages: {% load ranch_extras %}."""

from django import template
from django.templatetags.static import static

register = template.Library()

# The ball an arrival waits in tells its rarity before the reveal, from the
# plainest to the most precious. Five rarities, five official balls: the
# Cherish Ball, kept for event Pokémon in the games, marks the very rare ones.
# Sprites: PokéAPI item icons (30x30), in static/pokemon/.
RARITY_BALLS = {
    "common": ("poke-ball", "Poké Ball"),
    "uncommon": ("great-ball", "Great Ball"),
    "rare": ("ultra-ball", "Ultra Ball"),
    "very_rare": ("cherish-ball", "Cherish Ball"),
    "legendary": ("master-ball", "Master Ball"),
}
DEFAULT_BALL = RARITY_BALLS["common"]  # a species without rarity yet


@register.filter
def ball_sprite(rarity: str) -> str:
    """{{ "rare"|ball_sprite }} -> URL of the Ultra Ball sprite."""
    slug, _ = RARITY_BALLS.get(rarity, DEFAULT_BALL)
    return static(f"pokemon/{slug}.png")


@register.filter
def ball_name(rarity: str) -> str:
    """{{ "rare"|ball_name }} -> "Ultra Ball"."""
    return RARITY_BALLS.get(rarity, DEFAULT_BALL)[1]


NATURE_LABELS = {
    "hp": "HP",
    "attack": "Attack",
    "defense": "Defense",
    "special_attack": "Sp. Atk",
    "special_defense": "Sp. Def",
    "speed": "Speed",
}


@register.filter
def nature_label(nature: str) -> str:
    """{{ "special_attack"|nature_label }} -> "Sp. Atk"."""
    return NATURE_LABELS.get(nature, nature)
