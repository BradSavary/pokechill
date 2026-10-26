"""Template filters of the ranch pages: {% load ranch_extras %}."""

from django import template

register = template.Library()

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
