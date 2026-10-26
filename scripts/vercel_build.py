"""
Build step run by Vercel on every deployment ([tool.vercel.scripts] in pyproject.toml).

1. Apply pending migrations to the production database.
2. Load the species data files (data/species/*.json): the files in the
   repository are the source of truth, so every deployment syncs them.

Species themselves come from PokéAPI (import_pokeapi, run once from a local
machine). On a database where they were never imported, step 2 is skipped
with a warning instead of failing the deployment.
"""

import os
import sys
from pathlib import Path

# Run as `python scripts/vercel_build.py`: make the project root importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402 (Django must be configured before importing models)

django.setup()

from django.core.management import call_command  # noqa: E402

from pokedex.models import Species  # noqa: E402


def main() -> None:
    call_command("migrate", interactive=False)
    if Species.objects.exists():
        call_command("load_species")
    else:
        print("No species in the database: run import_pokeapi, then redeploy.")


if __name__ == "__main__":
    main()
