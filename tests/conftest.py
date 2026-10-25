"""
Shared pytest fixtures.

pytest loads this file automatically: every fixture defined here can be used
by any test simply by naming it as a parameter.
"""

import pytest

from pokedex.models import EvolutionChain, Species, Type


@pytest.fixture
def grass(db):
    # The `db` fixture (from pytest-django) grants database access
    return Type.objects.create(slug="grass", name="Grass")


@pytest.fixture
def poison(db):
    return Type.objects.create(slug="poison", name="Poison")


@pytest.fixture
def fire(db):
    return Type.objects.create(slug="fire", name="Fire")


def make_species(number, name, chain, primary_type, secondary_type=None, **extra):
    """Create a species with default stats; `extra` overrides any field."""
    values = {
        "number": number,
        "slug": name.lower(),
        "name": name,
        "genus": "Test Pokémon",
        "primary_type": primary_type,
        "secondary_type": secondary_type,
        "hp": 45,
        "attack": 49,
        "defense": 49,
        "special_attack": 65,
        "special_defense": 65,
        "speed": 45,
        "height_dm": 7,
        "weight_hg": 69,
        "evolution_chain": chain,
    }
    return Species.objects.create(**(values | extra))


@pytest.fixture
def bulbasaur(grass, poison):
    chain = EvolutionChain.objects.create(pokeapi_id=1)
    return make_species(1, "Bulbasaur", chain, grass, poison, genus="Seed Pokémon")


@pytest.fixture
def ivysaur(bulbasaur):
    return make_species(
        2,
        "Ivysaur",
        bulbasaur.evolution_chain,
        bulbasaur.primary_type,
        bulbasaur.secondary_type,
        evolution_stage=2,
        evolves_from=bulbasaur,
    )


@pytest.fixture
def charmander(fire):
    chain = EvolutionChain.objects.create(pokeapi_id=2)
    return make_species(4, "Charmander", chain, fire)
