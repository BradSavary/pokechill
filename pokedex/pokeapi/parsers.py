"""
Pure functions turning raw PokéAPI JSON into plain Python values.

No database and no network here: these functions only reshape data, which
makes them trivial to test with small hand-written dictionaries.
"""

# Learnsets come from FireRed/LeafGreen; other learn methods (tutor, egg...) are ignored
LEARN_METHODS = {"level-up", "machine"}

# PokéAPI stat names -> Species field names
STAT_FIELDS = {
    "hp": "hp",
    "attack": "attack",
    "defense": "defense",
    "special-attack": "special_attack",
    "special-defense": "special_defense",
    "speed": "speed",
}


def english(entries: list[dict], field: str = "name") -> str:
    """Pick the English value in a list of translated entries."""
    for entry in entries:
        if entry["language"]["name"] == "en":
            return entry[field]
    raise ValueError(f"No English entry found for {field!r}")


def clean_flavor_text(text: str) -> str:
    """Flatten line breaks and fix the all-caps "POKéMON" of old games."""
    return " ".join(text.split()).replace("POKéMON", "Pokémon")


def pick_flavor_text(species: dict, versions: tuple[str, ...] = ("firered", "leafgreen")) -> str:
    """English Pokédex description, preferably from the given game versions."""
    english_entries = [e for e in species["flavor_text_entries"] if e["language"]["name"] == "en"]
    for version in versions:
        for entry in english_entries:
            if entry["version"]["name"] == version:
                return clean_flavor_text(entry["flavor_text"])
    # Fallback: the most recent English description, if any
    return clean_flavor_text(english_entries[-1]["flavor_text"]) if english_entries else ""


def parse_species(pokemon: dict, species: dict) -> dict:
    """
    Merge the /pokemon and /pokemon-species resources into Species field values.

    Types are returned as slugs ("primary_type", "secondary_type"): the
    importer resolves them to database rows.
    """
    types = sorted(pokemon["types"], key=lambda t: t["slot"])
    stats = {STAT_FIELDS[s["stat"]["name"]]: s["base_stat"] for s in pokemon["stats"]}
    return {
        "number": species["id"],
        "slug": species["name"],
        "name": english(species["names"]),
        "genus": english(species["genera"], field="genus"),
        "flavor_text": pick_flavor_text(species),
        "is_legendary": species["is_legendary"],
        "is_mythical": species["is_mythical"],
        "primary_type": types[0]["type"]["name"],
        "secondary_type": types[1]["type"]["name"] if len(types) > 1 else None,
        "height_dm": pokemon["height"],
        "weight_hg": pokemon["weight"],
        **stats,
    }


def parse_learnset(pokemon: dict, version_group: str) -> list[tuple[str, str, int]]:
    """List the (move slug, learn method, level) entries for one game version."""
    entries = set()  # a set removes exact duplicates
    for move in pokemon["moves"]:
        for detail in move["version_group_details"]:
            method = detail["move_learn_method"]["name"]
            if detail["version_group"]["name"] == version_group and method in LEARN_METHODS:
                entries.add((move["move"]["name"], method, detail["level_learned_at"]))
    return sorted(entries)


def parse_move(move: dict) -> dict:
    """Move field values; the type is returned as a slug."""
    return {
        "slug": move["name"],
        "name": english(move["names"]),
        "type": move["type"]["name"],
        "damage_class": move["damage_class"]["name"],
        "power": move["power"],
        "accuracy": move["accuracy"],
        "pp": move["pp"],
    }


def evolution_family(chain: dict, allowed: set[str]) -> dict[str, tuple[int, str | None]]:
    """
    Compute (evolution stage, previous stage slug) for each allowed species of a chain.

    Species outside `allowed` (e.g. Pichu, added in a later generation) are
    skipped: Pikachu is then a base form (stage 1) and Raichu stage 2.
    """
    family: dict[str, tuple[int, str | None]] = {}

    def walk(node: dict, parent: str | None, stage: int) -> None:
        slug = node["species"]["name"]
        if slug in allowed:
            family[slug] = (stage, parent)
            parent, stage = slug, stage + 1
        for child in node["evolves_to"]:
            walk(child, parent, stage)

    walk(chain["chain"], parent=None, stage=1)
    return family


def media_urls(pokemon: dict) -> dict[str, str | None]:
    """Black/White sprites (normal and shiny) and the original cry."""
    black_white = pokemon["sprites"]["versions"]["generation-v"]["black-white"]
    cries = pokemon["cries"]
    return {
        "sprite": black_white["front_default"],
        "shiny_sprite": black_white["front_shiny"],
        "cry": cries["legacy"] or cries["latest"],
    }
