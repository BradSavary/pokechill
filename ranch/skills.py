"""
The skill tree of the player: Professor Oak's lab, and the nodes it buys.

The tree itself (its nodes, costs, effects) is game.skill_tree, read from
data/skill_tree.json (ranch.skill_data). This module saves what the player
unlocked, makes them pay, and prepares what the lab page shows. The effects
are read where they apply, through Player.skill_bonuses.
"""

from django.db import transaction
from django.db.models import F
from django.templatetags.static import static

from game.skill_tree import RESEARCH, describe
from game.zones import ZONES

from .models import Player, ResourceStock, UnlockedNode
from .skill_data import skill_tree


class SkillError(ValueError):
    """Raised when a node can't be unlocked (locked, too dear...)."""


def lab_is_open(player: Player) -> bool:
    """The lab opens once the Pokédex holds enough species (see Player.lab_open)."""
    return player.lab_open


def unlocked_of(player: Player) -> set[str]:
    return set(player.unlocked_nodes.values_list("node", flat=True))


def wallet_of(player: Player) -> dict[str, int]:
    """What the player can spend: research points and the zones' resources."""
    stocks = dict(player.resources.values_list("resource", "amount"))
    return {RESEARCH: player.research_points, **stocks}


@transaction.atomic
def unlock_node(player: Player, node_id: str) -> None:
    """
    Buy a node of the skill tree: its tree open, the nodes it needs
    unlocked, its cost paid (research points and resources), once.
    """
    tree = skill_tree()
    if node_id not in tree.nodes:
        raise SkillError("This node doesn't exist.")
    locked = Player.objects.select_for_update().get(pk=player.pk)
    if not tree.can_unlock(node_id, unlocked_of(locked)):
        raise SkillError("Unlock the nodes before it first.")
    # Each payment is a conditional UPDATE: the database refuses to go below
    # zero, so two purchases at once can't spend the same points. Raising
    # inside the transaction cancels the payments already made.
    for currency, amount in tree.cost(node_id).items():
        if currency == RESEARCH:
            paid = Player.objects.filter(pk=locked.pk, research_points__gte=amount).update(
                research_points=F("research_points") - amount
            )
        else:
            paid = ResourceStock.objects.filter(
                player=locked, resource=currency, amount__gte=amount
            ).update(amount=F("amount") - amount)
        if not paid:
            raise SkillError("You can't afford it yet.")
    UnlockedNode.objects.create(player=locked, node=node_id)
    # The caller's player sees the new bonuses and points from now on
    player.__dict__.pop("skill_bonuses", None)
    player.refresh_from_db(fields=["research_points"])


# --- What the lab page shows ---------------------------------------------------------------

# The sprite of a node: the item of its first effect (a zone's yield: its resource)
EFFECT_ICONS = {
    "welcome_places": "pokemon/poke-ball.png",
    "research_percent": "pokemon/items/research-points.png",
    "candy_xp_percent": "pokemon/items/rare-candy.png",
    "zone_storage_hours": "pokemon/items/honey.png",
    "zone_xp_percent": "pokemon/items/lucky-egg.png",
    "zone_slots": "pokemon/items/poke-doll.png",
    "feeder_max_units": "pokemon/items/berry-pouch.png",
    "feeder_unit_tenths": "pokemon/items/lure.png",
    "feeder_slots": "pokemon/items/max-lure.png",
}


def node_icon(node, zone_resource: str | None) -> str:
    effect = next(iter(node.effects))
    if effect == "zone_yield_percent" and zone_resource:
        return static(f"pokemon/resources/{zone_resource}.png")
    return static(EFFECT_ICONS.get(effect, "pokemon/poke-ball.png"))


def node_label(node) -> str:
    """A few characters under the node: "+5 %", "+1 h", "+2"..."""
    effect, value = next(iter(node.effects.items()))
    if effect.endswith("_percent"):
        return f"+{value} %"
    if effect == "zone_storage_hours":
        return f"+{value} h"
    if effect == "feeder_unit_tenths":
        return f"+{value / 10:g}"
    return f"+{value}"


def tree_cards(player: Player) -> list[dict]:
    """The trees of the lab, for its first page: open or not, how far the player got."""
    tree, unlocked = skill_tree(), unlocked_of(player)
    cards = []
    for spec in tree.trees.values():
        nodes = [node for node in tree.nodes.values() if node.tree == spec.id]
        opener = tree.nodes[spec.requires] if spec.requires else None
        cards.append(
            {
                "tree": spec,
                "open": tree.is_open(spec.id, unlocked),
                "opener": opener.name if opener else None,
                "done": sum(node.id in unlocked for node in nodes),
                "total": len(nodes),
                "icon": node_icon(nodes[0], _resource_of(spec)),
            }
        )
    return cards


def _resource_of(spec) -> str | None:
    """The resource of a zone tree (None for the others)."""
    return ZONES[spec.zone].resource if spec.zone else None


def tree_view(player: Player, tree_id: str) -> dict:
    """
    One tree for its page: its nodes on a grid (column, lane), their state,
    and the lines between a node and those it needs in the same tree.
    """
    tree, unlocked, wallet = skill_tree(), unlocked_of(player), wallet_of(player)
    spec = tree.trees[tree_id]
    resource = _resource_of(spec)
    nodes = sorted(
        (node for node in tree.nodes.values() if node.tree == tree_id), key=lambda n: n.col
    )
    cells = []
    for node in nodes:
        cost = tree.cost(node.id)
        affordable = all(wallet.get(currency, 0) >= amount for currency, amount in cost.items())
        if node.id in unlocked:
            state = "unlocked"
        elif not tree.can_unlock(node.id, unlocked):
            state = "locked"
        else:
            state = "available" if affordable else "expensive"
        cells.append(
            {
                "node": node,
                "state": state,
                "cost": [
                    {
                        "currency": currency,
                        "amount": amount,
                        "enough": wallet.get(currency, 0) >= amount,
                    }
                    for currency, amount in cost.items()
                ],
                "effects": describe(tree, node.id),
                "icon": node_icon(node, resource),
                "label": node_label(node),
                # What it still waits for, in this tree or another one
                "missing": [
                    tree.nodes[needed].name
                    + (
                        ""
                        if tree.nodes[needed].tree == tree_id
                        else f" ({tree.trees[tree.nodes[needed].tree].name})"
                    )
                    for needed in node.requires
                    if needed not in unlocked
                ],
            }
        )
    by_id = {node.id: node for node in nodes}
    # The lines between nodes, in the units of the grid's SVG: 100 per cell,
    # from the centre of one cell to the centre of the other
    edges = [
        {
            "x1": (by_id[needed].col - 0.5) * 100,
            "y1": (by_id[needed].lane + 0.5) * 100,
            "x2": (node.col - 0.5) * 100,
            "y2": (node.lane + 0.5) * 100,
            "done": needed in unlocked,
        }
        for node in nodes
        for needed in node.requires
        if needed in by_id
    ]
    return {
        "tree": spec,
        "open": tree.is_open(tree_id, unlocked),
        "opener": tree.nodes[spec.requires].name if spec.requires else None,
        "cells": cells,
        "edges": edges,
        "cols": max(node.col for node in nodes),
        "lanes": max(node.lane for node in nodes) + 1,
        "done": sum(node.id in unlocked for node in nodes),
        "total": len(nodes),
    }
