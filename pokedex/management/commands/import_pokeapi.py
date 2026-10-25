"""
Django command: `uv run python manage.py import_pokeapi`.

Imports the Kanto Pokédex from PokéAPI. Raw responses are cached in
data/pokeapi_cache/, so only the first run needs the network.
"""

import httpx
from django.conf import settings
from django.core.management.base import BaseCommand

from pokedex.pokeapi.client import PokeAPIClient
from pokedex.pokeapi.importer import KANTO_SPECIES_COUNT, run_import

CACHE_DIR = settings.BASE_DIR / "data" / "pokeapi_cache"
MEDIA_DIR = settings.BASE_DIR / "static" / "pokemon"


class Command(BaseCommand):
    help = "Import species, types, moves, sprites and cries from PokéAPI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=KANTO_SPECIES_COUNT,
            help="Import species #1 to #LIMIT (default: 151).",
        )
        parser.add_argument(
            "--no-media",
            action="store_true",
            help="Skip downloading sprites and cries.",
        )

    def handle(self, *args, limit, no_media, **options):
        # A clear User-Agent is good manners towards a free public API
        headers = {"User-Agent": "PokeChill data importer (fan project)"}
        with httpx.Client(headers=headers, timeout=30, follow_redirects=True) as http:
            report = run_import(
                PokeAPIClient(CACHE_DIR, http),
                limit=limit,
                media_dir=None if no_media else MEDIA_DIR,
                log=self.stdout.write,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {report.species} species, {report.types} types, "
                f"{report.moves} moves ({report.learnset_entries} learnset entries), "
                f"downloaded {report.media_downloaded} media files."
            )
        )
