"""Tests of the species data files and the load_species command."""

import json

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command

from pokedex.models import Species
from pokedex.species_files import SpeciesFileError, parse_species_data, read_species_files

VALID = {"species": "bulbasaur", "rarity": "rare", "min_level": 1, "conditions": None}


def write(directory, name, content):
    """Write a species file; `content` is a dict (dumped to JSON) or raw text."""
    text = content if isinstance(content, str) else json.dumps(content)
    (directory / name).write_text(text, encoding="utf-8")


# --- Validation of one file ------------------------------------------------


def test_valid_data_is_parsed():
    data = parse_species_data(VALID | {"notes": "Starter", "conditions": {"time_of_day": "day"}})
    assert data.slug == "bulbasaur"
    assert data.conditions == {"time_of_day": "day"}


def test_conditions_are_optional():
    data = parse_species_data({"species": "rattata", "rarity": "common", "min_level": 1})
    assert data.conditions is None


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"rarity": "mythical"}, "rarity must be one of"),
        ({"min_level": 0}, "min_level must be an integer"),
        ({"min_level": "5"}, "min_level must be an integer"),
        ({"min_level": True}, "min_level must be an integer"),
        ({"conditions": {"weather": "rain"}}, "invalid conditions"),
        ({"rarety": "rare"}, "unknown keys: rarety"),  # the classic typo
    ],
)
def test_invalid_values_are_reported(change, message):
    with pytest.raises(SpeciesFileError) as raised:
        parse_species_data(VALID | change)
    assert message in str(raised.value)


def test_every_problem_is_reported_at_once():
    with pytest.raises(SpeciesFileError) as raised:
        parse_species_data({"species": "bulbasaur", "rarity": "epic", "extra": 1})
    assert len(raised.value.errors) == 3  # missing min_level, unknown key, bad rarity


# --- Reading a folder ---------------------------------------------------------


def test_errors_are_prefixed_with_the_file_name(tmp_path):
    write(tmp_path, "001-bulbasaur.json", VALID)
    write(tmp_path, "002-broken.json", "{not json")
    write(tmp_path, "003-dup.json", VALID)
    with pytest.raises(SpeciesFileError) as raised:
        read_species_files(tmp_path)
    errors = raised.value.errors
    assert any(e.startswith("002-broken.json: invalid JSON") for e in errors)
    assert any(e.startswith("003-dup.json:") and "already described" in e for e in errors)


def test_repository_species_files_are_valid():
    # Guards the hand-edited files of data/species: a mistake fails the CI
    files = read_species_files(settings.BASE_DIR / "data" / "species")
    assert len(files) >= 55


def species_named_in(node):
    """The species slugs a condition tree refers to (owns, works_in)."""
    if not node:
        return set()
    key, value = next(iter(node.items()))
    if key in ("all", "any"):
        return set().union(*(species_named_in(child) for child in value))
    if key == "not":
        return species_named_in(value)
    if key == "owns":
        return {value}
    if key == "works_in":
        return {value["species"]}
    return set()


def test_repository_conditions_only_name_species_of_the_game():
    # "owns": "nidoran-f" can only be met if Nidoran♀ can come (a file of its own)
    files = read_species_files(settings.BASE_DIR / "data" / "species")
    slugs = {data.slug for data in files}
    for data in files:
        assert species_named_in(data.conditions) <= slugs, data.slug


# --- The load_species command ---------------------------------------------


@pytest.mark.django_db
def test_command_loads_files_and_disables_the_others(tmp_path, bulbasaur, charmander):
    write(tmp_path, "001-bulbasaur.json", VALID | {"conditions": {"time_of_day": "night"}})
    call_command("load_species", directory=tmp_path)

    bulbasaur.refresh_from_db()
    charmander.refresh_from_db()
    assert bulbasaur.is_available
    assert bulbasaur.to_rule().conditions == {"time_of_day": "night"}
    assert not charmander.is_available


@pytest.mark.django_db
def test_removing_a_file_removes_the_species_from_the_game(tmp_path, bulbasaur):
    write(tmp_path, "001-bulbasaur.json", VALID)
    call_command("load_species", directory=tmp_path)
    (tmp_path / "001-bulbasaur.json").unlink()
    call_command("load_species", directory=tmp_path)

    bulbasaur.refresh_from_db()
    assert not bulbasaur.is_available
    assert bulbasaur.rarity == ""


@pytest.mark.django_db
def test_invalid_files_change_nothing(tmp_path, bulbasaur):
    write(tmp_path, "001-bulbasaur.json", VALID)
    call_command("load_species", directory=tmp_path)
    write(tmp_path, "002-bad.json", VALID | {"species": "ivysaur", "rarity": "epic"})

    with pytest.raises(CommandError, match="002-bad.json"):
        call_command("load_species", directory=tmp_path)
    assert Species.objects.get(slug="bulbasaur").is_available  # untouched


@pytest.mark.django_db
def test_unknown_species_are_refused(tmp_path, bulbasaur):
    write(tmp_path, "999-missingno.json", VALID | {"species": "missingno"})
    with pytest.raises(CommandError, match="missingno"):
        call_command("load_species", directory=tmp_path)
