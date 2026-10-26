"""
Species data files: reading and validation of data/species/*.json.

Each file describes how one species behaves in the game (rarity, level on
arrival, arrival conditions). Adding a species to the game means adding a
file, never code. Validation is strict and reports every problem at once,
so a typo in a file is caught before anything reaches the database.
"""

import json
from dataclasses import dataclass
from pathlib import Path

from game import balance
from game.conditions import ConditionError, validate

REQUIRED_KEYS = {"species", "rarity", "min_level"}
OPTIONAL_KEYS = {"conditions", "notes"}


class SpeciesFileError(ValueError):
    """One or more species files are invalid; `errors` lists every problem."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("\n".join(errors))


@dataclass(frozen=True)
class SpeciesData:
    """The validated content of one species file."""

    slug: str
    rarity: str
    min_level: int
    conditions: dict | None


def parse_species_data(raw: object) -> SpeciesData:
    """Validate the content of one file. Raises SpeciesFileError listing all problems."""
    if not isinstance(raw, dict):
        raise SpeciesFileError(["the file must contain a JSON object"])

    errors = []
    if missing := REQUIRED_KEYS - raw.keys():
        errors.append(f"missing keys: {', '.join(sorted(missing))}")
    # Unknown keys are rejected: this catches typos such as "rarety"
    if unknown := raw.keys() - REQUIRED_KEYS - OPTIONAL_KEYS:
        errors.append(f"unknown keys: {', '.join(sorted(unknown))}")

    rarity = raw.get("rarity")
    if "rarity" in raw and rarity not in balance.RARITY_WEIGHTS:
        errors.append(f"rarity must be one of {', '.join(balance.RARITY_WEIGHTS)}, got {rarity!r}")

    level = raw.get("min_level")
    # bool is a subclass of int in Python: exclude it explicitly
    if "min_level" in raw and (
        not isinstance(level, int) or isinstance(level, bool) or not 1 <= level <= 100
    ):
        errors.append(f"min_level must be an integer from 1 to 100, got {level!r}")

    conditions = raw.get("conditions")
    if conditions is not None:
        try:
            validate(conditions)
        except ConditionError as error:
            errors.append(f"invalid conditions: {error}")

    if errors:
        raise SpeciesFileError(errors)
    return SpeciesData(slug=raw["species"], rarity=rarity, min_level=level, conditions=conditions)


def read_species_files(directory: Path) -> list[SpeciesData]:
    """
    Read and validate every *.json file of `directory`.

    Errors are collected across all files and raised together, each prefixed
    with its file name, so the whole data set can be fixed in one go.
    """
    results, errors, seen = [], [], {}
    for path in sorted(directory.glob("*.json")):
        try:
            data = parse_species_data(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as error:
            errors.append(f"{path.name}: invalid JSON ({error})")
            continue
        except SpeciesFileError as error:
            errors.extend(f"{path.name}: {message}" for message in error.errors)
            continue
        if data.slug in seen:
            errors.append(f"{path.name}: {data.slug!r} is already described in {seen[data.slug]}")
            continue
        seen[data.slug] = path.name
        results.append(data)

    if errors:
        raise SpeciesFileError(errors)
    return results
