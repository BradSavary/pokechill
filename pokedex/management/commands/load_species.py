"""
Django command: `uv run python manage.py load_species`.

Loads the game data of each species from data/species/*.json into the
database. Run it after `import_pokeapi`, and again after editing a file.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from pokedex.models import Species
from pokedex.species_files import SpeciesFileError, read_species_files

DATA_DIR = settings.BASE_DIR / "data" / "species"


class Command(BaseCommand):
    help = "Load rarity, level, arrival conditions and challenges from data/species/*.json."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dir",
            dest="directory",
            type=Path,
            default=DATA_DIR,
            help="Folder of the species files.",
        )

    def handle(self, *args, directory, **options):
        try:
            files = read_species_files(directory)
        except SpeciesFileError as error:
            # CommandError prints the message and exits with an error code
            raise CommandError("Invalid species files:\n" + "\n".join(error.errors)) from error

        species_by_slug = Species.objects.in_bulk(field_name="slug")
        if unknown := [data.slug for data in files if data.slug not in species_by_slug]:
            raise CommandError(f"Unknown species (run import_pokeapi first?): {', '.join(unknown)}")

        # All or nothing: either every file is applied, or none
        with transaction.atomic():
            # A species whose file was removed is no longer available
            Species.objects.update(
                is_available=False,
                rarity="",
                min_level=1,
                arrival_conditions=None,
                custom_challenges={},
            )
            for data in files:
                species = species_by_slug[data.slug]
                species.is_available = True
                species.rarity = data.rarity
                species.min_level = data.min_level
                species.arrival_conditions = data.conditions
                species.custom_challenges = data.challenges
            Species.objects.bulk_update(
                [species_by_slug[data.slug] for data in files],
                ["is_available", "rarity", "min_level", "arrival_conditions", "custom_challenges"],
            )

        self.stdout.write(self.style.SUCCESS(f"Loaded {len(files)} available species."))
