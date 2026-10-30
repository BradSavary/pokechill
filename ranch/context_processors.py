"""Values of the game every template may need (the menu, on every page)."""

from game import balance


def game(request) -> dict:
    """The species the Pokédex needs to open the lab (the menu, the Ranch map)."""
    required = balance.LAB_SPECIES_REQUIRED
    return {
        "lab_required": required,
        # Why the lab's entry of the menu is greyed out (its title, on hover)
        "lab_locked_reason": f"opens when your Pokédex holds {required} species",
    }
