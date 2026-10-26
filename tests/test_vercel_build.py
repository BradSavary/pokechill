"""Tests of the Vercel build step (scripts/vercel_build.py)."""

import runpy

import pytest
from django.conf import settings

pytestmark = pytest.mark.django_db

SCRIPT = settings.BASE_DIR / "scripts" / "vercel_build.py"


@pytest.fixture
def build():
    """
    The script's main(), with management commands replaced by a recorder.

    The commands themselves are tested elsewhere: here we only check which
    ones the build runs, and in which order.
    """
    main = runpy.run_path(str(SCRIPT))["main"]
    calls = []
    main.__globals__["call_command"] = lambda name, **options: calls.append(name)
    return main, calls


def test_the_build_migrates_then_loads_the_species_files(build, bulbasaur):
    main, calls = build
    main()
    assert calls == ["migrate", "load_species"]


def test_the_build_skips_species_files_on_an_empty_database(build, capsys):
    main, calls = build
    main()
    assert calls == ["migrate"]
    assert "run import_pokeapi" in capsys.readouterr().out
