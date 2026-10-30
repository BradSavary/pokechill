"""Tests of Professor Oak's lab: opening, nodes bought, their effects, the pages."""

import pytest
from django.urls import reverse

from game import balance
from pokedex.models import EvolutionChain
from ranch.models import OwnedPokemon, Player, ResourceStock
from ranch.services import receive_pokemon
from ranch.skill_data import skill_tree
from ranch.skills import SkillError, unlock_node
from tests.conftest import make_species

pytestmark = pytest.mark.django_db

HTMX = {"HTTP_HX_REQUEST": "true"}


@pytest.fixture
def guest(client, grass):
    """A guest at the end of the tutorial."""
    client.get(reverse("ranch:index"))
    Player.objects.update(tutorial_step=6)
    return client, Player.objects.get()


def give_species(player, grass, count):
    """`count` species owned (the lab opens with enough of them, like receive_pokemon does)."""
    for number in range(100, 100 + count):
        chain = EvolutionChain.objects.create(pokeapi_id=number)
        species = make_species(number, f"Mon{number}", chain, grass)
        OwnedPokemon.objects.create(player=player, species=species, level=5)
    if count >= balance.LAB_SPECIES_REQUIRED:
        Player.objects.filter(pk=player.pk).update(lab_open=True)


@pytest.fixture
def lab(guest, grass):
    """A guest whose lab is open, with research points and resources to spend."""
    client, player = guest
    give_species(player, grass, balance.LAB_SPECIES_REQUIRED)
    Player.objects.filter(pk=player.pk).update(research_points=5000, lab_intro_seen=True)
    for resource in ("berry", "apricorn"):
        ResourceStock.objects.update_or_create(
            player=player, resource=resource, defaults={"amount": 5000}
        )
    player.refresh_from_db()
    return client, player


def cost(node_id, currency="research"):
    return skill_tree().cost(node_id)[currency]


# --- Opening -----------------------------------------------------------------------------


def test_the_lab_stays_shut_until_enough_species(guest):
    client, _ = guest
    response = client.get(reverse("lab:index"), follow=True)
    assert response.redirect_chain[-1][0] == reverse("ranch:index")
    assert "The lab opens once your Pokédex holds" in response.content.decode()
    # On the map: the lab's door shows how many species are still needed
    html = client.get(reverse("ranch:index")).content.decode()
    assert 'class="lab-sign"' in html
    # In the menu: the flask is greyed out, with the reason
    reason = f"opens when your Pokédex holds {balance.LAB_SPECIES_REQUIRED} species"
    assert f'title="Professor Oak\'s Lab ({reason})"' in html


def test_the_species_that_reaches_the_count_opens_the_lab(guest, grass):
    client, player = guest
    give_species(player, grass, balance.LAB_SPECIES_REQUIRED - 1)  # one short
    player.refresh_from_db()
    assert not player.lab_open
    chain = EvolutionChain.objects.create(pokeapi_id=999)
    last = make_species(999, "Lastmon", chain, grass)
    receive_pokemon(player, last, nature="attack", is_shiny=False)
    assert player.lab_open
    player.refresh_from_db()
    assert player.lab_open
    # The menu now leads to the lab
    html = client.get(reverse("ranch:index")).content.decode()
    assert 'href="/lab/"' in html and 'class="lab-sign"' not in html


def test_professor_oak_introduces_the_lab_once(guest, grass):
    client, player = guest
    give_species(player, grass, balance.LAB_SPECIES_REQUIRED)
    html = client.get(reverse("lab:index")).content.decode()
    assert "Professor Oak" in html and "data-auto-open" in html
    assert 'href="/lab/"' in client.get(reverse("ranch:index")).content.decode()  # its door
    client.post(reverse("lab:intro_seen"))
    assert "data-auto-open" not in client.get(reverse("lab:index")).content.decode()


# --- Unlocking a node --------------------------------------------------------------------


def test_unlocking_a_node_pays_its_cost(lab):
    _, player = lab
    unlock_node(player, "ranch-welcome-1")
    assert player.research_points == 5000 - cost("ranch-welcome-1")
    assert player.unlocked_nodes.filter(node="ranch-welcome-1").exists()
    with pytest.raises(SkillError):
        unlock_node(player, "ranch-welcome-1")  # once


def test_a_node_needs_the_nodes_before_it(lab):
    _, player = lab
    with pytest.raises(SkillError, match="before it"):
        unlock_node(player, "ranch-research-1")


def test_a_node_too_dear_is_refused_and_nothing_is_paid(lab):
    _, player = lab
    Player.objects.filter(pk=player.pk).update(research_points=1)
    with pytest.raises(SkillError, match="afford"):
        unlock_node(player, "ranch-welcome-1")
    assert Player.objects.get(pk=player.pk).research_points == 1


def test_a_zone_node_is_paid_with_its_resource(lab):
    _, player = lab
    unlock_node(player, "meadow-yield-1")
    berries = ResourceStock.objects.get(player=player, resource="berry").amount
    assert berries == 5000 - cost("meadow-yield-1", "berry")


def test_the_feeder_tree_opens_with_the_ranch_level_2(lab):
    _, player = lab
    with pytest.raises(SkillError):
        unlock_node(player, "feeder-units-1")
    for node_id in ("ranch-welcome-1", "ranch-research-1", "ranch-candy-1", "ranch-welcome-2"):
        unlock_node(player, node_id)
    unlock_node(player, "ranch-storage-1")
    unlock_node(player, "ranch-level-2")
    unlock_node(player, "feeder-units-1")


# --- The effects in the game ------------------------------------------------------------


def test_the_nodes_change_the_game(lab):
    _, player = lab
    meadow = player.zones.get(zone="meadow")
    assert (player.welcome_capacity, meadow.work_cap) == (
        balance.WELCOME_CAPACITY_BASE,
        balance.ZONE_WORK_HOURS_CAP,
    )
    for node_id in ("ranch-welcome-1", "ranch-research-1", "ranch-candy-1", "ranch-storage-1"):
        unlock_node(player, node_id)
    player = Player.objects.get(pk=player.pk)  # bonuses are read once per object
    meadow = player.zones.get(zone="meadow")
    assert player.welcome_capacity == balance.WELCOME_CAPACITY_BASE + 1
    assert meadow.work_cap == balance.ZONE_WORK_HOURS_CAP + 1  # every zone
    assert player.skill_bonuses.research_percent == 5
    assert player.skill_bonuses.candy_xp_percent == 10


def test_a_zone_milestone_adds_a_spot_and_a_level(lab):
    _, player = lab
    for node_id in ("meadow-yield-1", "meadow-storage-1", "meadow-xp-1", "meadow-yield-2"):
        unlock_node(player, node_id)
    unlock_node(player, "meadow-yield-3")
    unlock_node(player, "meadow-level-2")
    meadow = Player.objects.get(pk=player.pk).zones.get(zone="meadow")
    assert meadow.capacity == balance.ZONE_SLOTS_BASE + 1
    assert meadow.level == 2
    assert meadow.yield_percent == 15  # its three yield nodes


# --- The pages -----------------------------------------------------------------------------


def test_the_lab_shows_its_trees(lab):
    client, _ = lab
    html = client.get(reverse("lab:index")).content.decode()
    assert "Ranch" in html and "Meadow" in html
    assert "Opens with Ranch level 2" in html  # the Feeder tree is locked


def test_a_tree_page_shows_its_nodes_and_lines(lab):
    client, _ = lab
    html = client.get(reverse("lab:tree", args=["ranch"])).content.decode()
    assert html.count("data-skill-node") == len(
        [n for n in skill_tree().nodes.values() if n.tree == "ranch"]
    )
    assert "<line" in html
    detail = client.get(reverse("lab:node", args=["ranch", "ranch-level-2"]), **HTMX).content
    assert "Opens the Feeder tree" in detail.decode()


def test_unlocking_from_the_page_refreshes_the_tree_and_the_wallet(lab):
    client, player = lab
    url = reverse("lab:unlock", args=["ranch", "ranch-welcome-1"])
    html = client.post(url, **HTMX).content.decode()
    assert "✔ Unlocked" in html
    assert 'id="lab-wallet" hx-swap-oob="true"' in html
    assert player.unlocked_nodes.filter(node="ranch-welcome-1").exists()
    assert client.get(url).status_code == 405  # POST only


def test_an_unknown_tree_is_not_found(lab):
    client, _ = lab
    assert client.get(reverse("lab:tree", args=["moon"])).status_code == 404


def test_the_lab_needs_no_new_queries_on_the_game_pages(lab, django_assert_max_num_queries):
    client, _ = lab
    client.get(reverse("zones:index"))
    # The skill tree's bonuses add one query (the nodes unlocked), read once
    with django_assert_max_num_queries(11):
        client.get(reverse("zones:index"))
