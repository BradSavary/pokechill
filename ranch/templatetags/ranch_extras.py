"""Template filters of the ranch pages: {% load ranch_extras %}."""

from django import template
from django.templatetags.static import static

from game.zones import ZONE_OF_RESOURCE

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


@register.filter
def resource_word(count, resource: str) -> str:
    """{{ 3|resource_word:"berry" }} -> "berries", {{ 1|resource_word:"berry" }} -> "berry"."""
    zone = ZONE_OF_RESOURCE[resource]
    return (zone.resource_name if count == 1 else zone.resource_plural).lower()


@register.filter
def resource_icon(resource: str) -> str:
    """{{ "berry"|resource_icon }} -> URL of its item sprite (static/pokemon/resources/)."""
    return static(f"pokemon/resources/{resource}.png")


@register.filter
def get_item(mapping, key):
    """{{ stages|get_item:species.id }}: a dict lookup by a variable key (None if absent)."""
    return mapping.get(key) if mapping else None


@register.filter
def balanced_rows(items, per_row) -> list[list]:
    """
    {% for row in balls|balanced_rows:10 %}: the items in as few rows as
    `per_row` allows, of even lengths (the first rows one longer when they
    can't all be equal): 13 balls -> 7 and 6, not 10 and 3.
    """
    items, per_row = list(items), int(per_row)
    if not items:
        return []
    count = -(-len(items) // per_row)  # rows needed (rounded up)
    size, longer = divmod(len(items), count)
    rows, start = [], 0
    for index in range(count):
        end = start + size + (1 if index < longer else 0)
        rows.append(items[start:end])
        start = end
    return rows
