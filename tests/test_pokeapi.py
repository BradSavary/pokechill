"""
Tests of the PokéAPI import: parsers, cache client and full import.

No test touches the network: responses are small hand-written dictionaries
that mimic the shape of the real PokéAPI resources.
"""

import json

import httpx
import pytest

from pokedex.models import Species, SpeciesMove
from pokedex.pokeapi import parsers
from pokedex.pokeapi.client import PokeAPIClient, id_from_url
from pokedex.pokeapi.importer import run_import

# --- Fake PokéAPI resources ------------------------------------------------


def en(value, field="name"):
    """A translated entry list with an English and a French value."""
    return [
        {field: value, "language": {"name": "en"}},
        {field: f"{value} (fr)", "language": {"name": "fr"}},
    ]


def fake_pokemon(number, slug, types, moves=()):
    return {
        "id": number,
        "name": slug,
        "height": 7,
        "weight": 69,
        "types": [{"slot": i + 1, "type": {"name": t}} for i, t in enumerate(types)],
        "stats": [
            {"stat": {"name": name}, "base_stat": 50}
            for name in parsers.STAT_FIELDS  # the six stat names
        ],
        "moves": [
            {
                "move": {"name": move},
                "version_group_details": [
                    {
                        "version_group": {"name": "firered-leafgreen"},
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": level,
                    },
                    # Same move in another game: must be ignored
                    {
                        "version_group": {"name": "red-blue"},
                        "move_learn_method": {"name": "level-up"},
                        "level_learned_at": 99,
                    },
                ],
            }
            for move, level in moves
        ],
        "sprites": {
            "versions": {
                "generation-v": {
                    "black-white": {
                        "front_default": f"https://img/{number}.png",
                        "front_shiny": f"https://img/shiny/{number}.png",
                    }
                }
            }
        },
        "cries": {"legacy": f"https://cry/{number}.ogg", "latest": None},
    }


def fake_species(number, slug, name, chain_id=1):
    return {
        "id": number,
        "name": slug,
        "names": en(name),
        "genera": en("Seed Pokémon", field="genus"),
        "flavor_text_entries": [
            {
                "flavor_text": "A strange seed was\nplanted on its\fback.",
                "language": {"name": "en"},
                "version": {"name": "firered"},
            }
        ],
        "is_legendary": False,
        "is_mythical": False,
        "evolution_chain": {"url": f"https://pokeapi.co/api/v2/evolution-chain/{chain_id}/"},
    }


def fake_type(slug, name):
    return {
        "names": en(name),
        "sprites": {
            "generation-vii": {
                "lets-go-pikachu-lets-go-eevee": {"symbol_icon": f"https://icons/{slug}.png"}
            }
        },
    }


def chain_node(slug, *children):
    return {"species": {"name": slug}, "evolves_to": list(children)}


class FakeClient:
    """Stands in for PokeAPIClient: serves resources from a dictionary."""

    def __init__(self, resources):
        self.resources = resources
        self.downloads = []

    def get(self, endpoint, key):
        return self.resources[(endpoint, key)]

    def download(self, url, destination):
        self.downloads.append(url)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake")
        return True


@pytest.fixture
def fake_client():
    """Bulbasaur and Ivysaur, one move, two types."""
    return FakeClient(
        {
            ("pokemon", 1): fake_pokemon(1, "bulbasaur", ["grass", "poison"], [("tackle", 1)]),
            ("pokemon", 2): fake_pokemon(2, "ivysaur", ["grass", "poison"], [("tackle", 1)]),
            ("pokemon-species", 1): fake_species(1, "bulbasaur", "Bulbasaur"),
            ("pokemon-species", 2): fake_species(2, "ivysaur", "Ivysaur"),
            ("evolution-chain", 1): {
                "chain": chain_node("bulbasaur", chain_node("ivysaur", chain_node("venusaur")))
            },
            ("move", "tackle"): {
                "name": "tackle",
                "names": en("Tackle"),
                "type": {"name": "normal"},
                "damage_class": {"name": "physical"},
                "power": 40,
                "accuracy": 100,
                "pp": 35,
            },
            ("type", "grass"): fake_type("grass", "Grass"),
            ("type", "poison"): fake_type("poison", "Poison"),
            ("type", "normal"): fake_type("normal", "Normal"),
        }
    )


# --- Parsers -----------------------------------------------------------------


def test_id_from_url():
    assert id_from_url("https://pokeapi.co/api/v2/evolution-chain/10/") == 10


def test_english_ignores_other_languages():
    assert parsers.english(en("Grass")) == "Grass"


def test_clean_flavor_text():
    raw = "When several of these POKéMON\ngather,\ftheir electricity"
    assert (
        parsers.clean_flavor_text(raw) == "When several of these Pokémon gather, their electricity"
    )


def test_parse_species_merges_both_resources():
    data = parsers.parse_species(
        fake_pokemon(1, "bulbasaur", ["grass", "poison"]),
        fake_species(1, "bulbasaur", "Bulbasaur"),
    )
    assert data["name"] == "Bulbasaur"
    assert data["primary_type"] == "grass"
    assert data["secondary_type"] == "poison"
    assert data["special_attack"] == 50
    assert data["flavor_text"] == "A strange seed was planted on its back."


def test_parse_learnset_keeps_only_the_chosen_game():
    pokemon = fake_pokemon(1, "bulbasaur", ["grass"], [("tackle", 1), ("vine-whip", 10)])
    assert parsers.parse_learnset(pokemon, "firered-leafgreen") == [
        ("tackle", "level-up", 1),
        ("vine-whip", "level-up", 10),
    ]


def test_evolution_family_skips_species_not_imported():
    # Pichu (generation 2) comes before Pikachu in the real chain
    chain = {"chain": chain_node("pichu", chain_node("pikachu", chain_node("raichu")))}
    family = parsers.evolution_family(chain, allowed={"pikachu", "raichu"})
    assert family == {"pikachu": (1, None), "raichu": (2, "pikachu")}


def test_evolution_family_with_branches():
    chain = {"chain": chain_node("eevee", chain_node("vaporeon"), chain_node("jolteon"))}
    family = parsers.evolution_family(chain, allowed={"eevee", "vaporeon", "jolteon"})
    assert family["vaporeon"] == (2, "eevee")
    assert family["jolteon"] == (2, "eevee")


# --- Cache client ----------------------------------------------------------


def test_client_caches_responses(tmp_path):
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"name": "pikachu"})

    # MockTransport answers requests locally instead of using the network
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = PokeAPIClient(tmp_path, http)

    assert client.get("pokemon", 25) == {"name": "pikachu"}
    assert client.get("pokemon", 25) == {"name": "pikachu"}

    assert calls == ["/api/v2/pokemon/25/"]  # second call served from cache
    assert json.loads((tmp_path / "pokemon" / "25.json").read_text()) == {"name": "pikachu"}


def test_client_raises_on_http_error(tmp_path):
    http = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(404)))
    with pytest.raises(httpx.HTTPStatusError):
        PokeAPIClient(tmp_path, http).get("pokemon", 9999)


# --- Full import -------------------------------------------------------------


@pytest.mark.django_db
def test_import_creates_species_with_family_and_learnset(fake_client):
    report = run_import(fake_client, limit=2, log=lambda message: None)

    assert (report.species, report.types, report.moves) == (2, 3, 1)
    ivysaur = Species.objects.get(slug="ivysaur")
    assert ivysaur.evolution_stage == 2
    assert ivysaur.evolves_from.slug == "bulbasaur"
    assert ivysaur.evolution_chain == Species.objects.get(slug="bulbasaur").evolution_chain
    assert [t.slug for t in ivysaur.types] == ["grass", "poison"]
    assert ivysaur.learnset.get().move.name == "Tackle"


@pytest.mark.django_db
def test_import_is_idempotent(fake_client):
    run_import(fake_client, limit=2, log=lambda message: None)
    run_import(fake_client, limit=2, log=lambda message: None)

    assert Species.objects.count() == 2
    assert SpeciesMove.objects.count() == 2


@pytest.mark.django_db
def test_import_downloads_media(fake_client, tmp_path):
    report = run_import(fake_client, limit=2, media_dir=tmp_path, log=lambda message: None)

    # 2 species x (sprite, shiny sprite, cry) + 3 type icons
    assert report.media_downloaded == 9
    assert (tmp_path / "types" / "poison.png").exists()
    assert (tmp_path / "sprites" / "shiny" / "2.png").exists()
    assert (tmp_path / "cries" / "1.ogg").exists()


def test_mythical_species_count_as_legendary():
    species = fake_species(151, "mew", "Mew")
    species["is_mythical"] = True
    data = parsers.parse_species(fake_pokemon(151, "mew", ["psychic"]), species)
    assert data["is_legendary"] is True
