"""
Import of the Kanto Pokédex from PokéAPI into the database.

The import runs in three phases:
1. fetch every resource (network or cache) and parse it, without touching the database;
2. write everything in a single transaction: on any error nothing is saved;
3. download the media files (sprites and cries) into the static folder.

Every write uses `update_or_create`, so the import is idempotent: running it
twice gives the same result, and re-running it updates changed data.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from pokedex.models import EvolutionChain, Move, Species, SpeciesMove, Type

from . import parsers
from .client import PokeAPIClient, id_from_url

KANTO_SPECIES_COUNT = 151
VERSION_GROUP = "firered-leafgreen"


@dataclass
class ImportReport:
    species: int = 0
    moves: int = 0
    types: int = 0
    learnset_entries: int = 0
    media_downloaded: int = 0


def run_import(
    client: PokeAPIClient,
    *,
    limit: int = KANTO_SPECIES_COUNT,
    media_dir: Path | None = None,
    log: Callable[[str], None] = print,
) -> ImportReport:
    """Import species #1 to #`limit`. Media are skipped when `media_dir` is None."""
    report = ImportReport()

    # --- Phase 1: fetch and parse ------------------------------------------
    log(f"Fetching {limit} species...")
    pokemons = {n: client.get("pokemon", n) for n in range(1, limit + 1)}
    species_data = {n: client.get("pokemon-species", n) for n in pokemons}
    parsed_species = {n: parsers.parse_species(pokemons[n], species_data[n]) for n in pokemons}

    log("Fetching evolution chains...")
    imported_slugs = {s["slug"] for s in parsed_species.values()}
    chain_ids = {id_from_url(s["evolution_chain"]["url"]) for s in species_data.values()}
    family: dict[str, tuple[int, str | None]] = {}
    for chain_id in chain_ids:
        family |= parsers.evolution_family(client.get("evolution-chain", chain_id), imported_slugs)
    chain_of = {
        species_data[n]["name"]: id_from_url(species_data[n]["evolution_chain"]["url"])
        for n in pokemons
    }

    log("Fetching moves...")
    learnsets = {n: parsers.parse_learnset(pokemons[n], VERSION_GROUP) for n in pokemons}
    move_slugs = {entry[0] for learnset in learnsets.values() for entry in learnset}
    parsed_moves = [parsers.parse_move(client.get("move", slug)) for slug in sorted(move_slugs)]

    log("Fetching types...")
    type_slugs = {m["type"] for m in parsed_moves}
    for s in parsed_species.values():
        type_slugs |= {s["primary_type"], s["secondary_type"]} - {None}
    type_data = {slug: client.get("type", slug) for slug in type_slugs}
    type_names = {slug: parsers.english(data["names"]) for slug, data in type_data.items()}

    # --- Phase 2: write to the database -------------------------------------
    log("Saving to the database...")
    with transaction.atomic():
        types = {
            slug: Type.objects.update_or_create(slug=slug, defaults={"name": name})[0]
            for slug, name in type_names.items()
        }
        chains = {
            chain_id: EvolutionChain.objects.get_or_create(pokeapi_id=chain_id)[0]
            for chain_id in chain_ids
        }

        species_rows = {}
        for data in parsed_species.values():
            # Copy the dict before replacing type slugs by Type rows
            values = dict(data)
            slug = values.pop("slug")
            values["primary_type"] = types[values["primary_type"]]
            values["secondary_type"] = types.get(values["secondary_type"])
            values["evolution_chain"] = chains[chain_of[slug]]
            values["evolution_stage"] = family[slug][0]
            species_rows[slug] = Species.objects.update_or_create(slug=slug, defaults=values)[0]

        # Second pass: `evolves_from` needs every species row to exist first
        for slug, row in species_rows.items():
            previous = family[slug][1]
            row.evolves_from = species_rows[previous] if previous else None
            row.save(update_fields=["evolves_from"])

        move_rows = {}
        for data in parsed_moves:
            values = dict(data)
            slug = values.pop("slug")
            values["type"] = types[values["type"]]
            move_rows[slug] = Move.objects.update_or_create(slug=slug, defaults=values)[0]

        # Learnsets are replaced as a whole: simpler than diffing entries
        SpeciesMove.objects.filter(species__in=species_rows.values()).delete()
        entries = [
            SpeciesMove(
                species=species_rows[parsed_species[n]["slug"]],
                move=move_rows[move_slug],
                learn_method=method,
                level=level,
            )
            for n, learnset in learnsets.items()
            for move_slug, method, level in learnset
        ]
        # One INSERT for thousands of rows instead of one query per row
        SpeciesMove.objects.bulk_create(entries)

    report.species = len(species_rows)
    report.moves = len(move_rows)
    report.types = len(types)
    report.learnset_entries = len(entries)

    # --- Phase 3: media files -------------------------------------------------
    if media_dir is not None:
        log("Downloading sprites, icons, cries, type icons and candies...")
        for n, pokemon in pokemons.items():
            urls = parsers.media_urls(pokemon)
            targets = {
                "sprite": media_dir / "sprites" / f"{n}.png",
                "shiny_sprite": media_dir / "sprites" / "shiny" / f"{n}.png",
                "cry": media_dir / "cries" / f"{n}.ogg",
                "icon": media_dir / "icons" / f"{n}.png",
            }
            for kind, destination in targets.items():
                if urls[kind] and client.download(urls[kind], destination):
                    report.media_downloaded += 1
        for slug, data in type_data.items():
            url = parsers.type_icon_url(data)
            if url and client.download(url, media_dir / "types" / f"{slug}.png"):
                report.media_downloaded += 1
        # One candy per family, named after its base form (stage 1)
        for slug, (stage, _previous) in family.items():
            if stage == 1:
                destination = media_dir / "candies" / f"{slug}.png"
                if client.download(parsers.candy_url(slug), destination):
                    report.media_downloaded += 1

    return report
