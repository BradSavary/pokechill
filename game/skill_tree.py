"""
The skill tree: what the research points (and the zones' resources) buy.

There are several trees, side by side in the lab: the Ranch (general), the
Feeder, and one per zone. A tree reads from left to right: each node sits in
a column (`col`) and a lane (`lane`, its row on screen). A node needs the
nodes it `requires`, possibly in another tree: this is how a late step of a
zone waits for the Ranch to reach a level. Branches join again on milestones
(`milestone`), which bring the big rewards.

A tree may itself be locked until a node is unlocked (`requires` of the
tree): the Feeder tree opens with the Ranch's level 2.

The trees are data (data/skill_tree.json): adding a node needs no code. Its
cost comes from a formula of its column (balance.SKILL_COST_*), unless the
file gives one, so that the whole economy is tuned with a few numbers.

    tree = load(path)
    tree.can_unlock("meadow-yield-1", unlocked)
    tree.cost("meadow-yield-1")              # {"berry": 30}
    tree.bonuses(unlocked).welcome_places    # what the unlocked nodes add
"""

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from . import balance
from .zones import ZONE_OF_RESOURCE, ZONES

RESEARCH = "research"  # the currency of research points
CURRENCIES = {RESEARCH} | set(ZONE_OF_RESOURCE)

# What a node may do. Ranch-wide effects, then the effects of a zone (the
# zone of the node's tree, or every zone with "zone": "all").
RANCH_EFFECTS = {
    "welcome_places",  # places of the Welcome area
    "feeder_slots",  # slots of the feeder
    "feeder_max_units",  # units a slot holds
    "feeder_unit_tenths",  # what a unit adds to the lure, in tenths of a point
    "research_percent",  # more research points per challenge claimed
    "candy_xp_percent",  # more experience per candy
}
ZONE_EFFECTS = {
    "zone_slots",  # Pokémon the zone holds
    "zone_storage_hours",  # hours of work its storage holds
    "zone_yield_percent",  # more resources
    "zone_xp_percent",  # more experience for its workers
    "zone_level",  # its level (arrival conditions may ask for it)
}
EFFECTS = RANCH_EFFECTS | ZONE_EFFECTS


class SkillTreeError(ValueError):
    """Raised when the data of the skill tree is malformed."""


@dataclass(frozen=True)
class Tree:
    id: str
    name: str
    zone: str | None  # the zone a zone tree improves
    requires: str | None  # the node that opens the tree (None: open at the start)
    currencies: tuple[str, ...]  # what its nodes cost
    milestone_currencies: tuple[str, ...]  # what its milestones cost
    description: str = ""  # one sentence, under its name in the lab


@dataclass(frozen=True)
class Node:
    id: str
    tree: str
    name: str
    col: int  # 1, 2, 3... from the left: the cost grows with it
    lane: int  # its row on screen (0 at the top)
    effects: Mapping[str, int]
    requires: tuple[str, ...] = ()
    milestone: bool = False
    zone: str | None = None  # "all" for a zone effect on every zone
    cost_override: Mapping[str, int] | None = None


@dataclass
class Bonuses:
    """What the unlocked nodes add, all together."""

    welcome_places: int = 0
    feeder_slots: int = 0
    feeder_max_units: int = 0
    feeder_unit_tenths: int = 0
    research_percent: int = 0
    candy_xp_percent: int = 0
    # By zone slug
    zone_slots: dict[str, int] = field(default_factory=dict)
    zone_storage_hours: dict[str, int] = field(default_factory=dict)
    zone_yield_percent: dict[str, int] = field(default_factory=dict)
    zone_xp_percent: dict[str, int] = field(default_factory=dict)
    zone_level: dict[str, int] = field(default_factory=dict)  # 1 + the levels gained

    def of_zone(self, effect: str, zone: str) -> int:
        return getattr(self, effect).get(zone, 0)


def nice_round(value: float) -> int:
    """A price a player reads easily: to 5 below 100, to 10 above."""
    step = 5 if value < 100 else 10
    return max(step, int(round(value / step)) * step)


@dataclass(frozen=True)
class SkillTree:
    trees: Mapping[str, Tree]
    nodes: Mapping[str, Node]

    def cost(self, node_id: str) -> dict[str, int]:
        """
        What a node costs: from its file if given, else from the formula
        base x growth^(col - 1) of each currency of its tree, times
        SKILL_MILESTONE_FACTOR for a milestone.
        """
        node = self.nodes[node_id]
        if node.cost_override is not None:
            return dict(node.cost_override)
        tree = self.trees[node.tree]
        currencies = tree.milestone_currencies if node.milestone else tree.currencies
        factor = balance.SKILL_MILESTONE_FACTOR if node.milestone else 1
        growth = balance.SKILL_COST_GROWTH ** (node.col - 1)
        return {
            currency: nice_round(balance.SKILL_COST_BASE[_kind(currency)] * growth * factor)
            for currency in currencies
        }

    def is_open(self, tree_id: str, unlocked: Iterable[str]) -> bool:
        """Is a tree open (its opening node unlocked, if it has one)?"""
        requires = self.trees[tree_id].requires
        return requires is None or requires in set(unlocked)

    def can_unlock(self, node_id: str, unlocked: Iterable[str]) -> bool:
        """Can a node be unlocked now (costs apart): its tree open, its needs met."""
        unlocked = set(unlocked)
        node = self.nodes[node_id]
        return (
            node_id not in unlocked
            and self.is_open(node.tree, unlocked)
            and all(needed in unlocked for needed in node.requires)
        )

    def bonuses(self, unlocked: Iterable[str]) -> Bonuses:
        """What the unlocked nodes add, all together."""
        total = Bonuses()
        for node_id in unlocked:
            node = self.nodes[node_id]
            zones = list(ZONES) if node.zone == "all" else [node.zone or self.trees[node.tree].zone]
            for effect, value in node.effects.items():
                if effect in RANCH_EFFECTS:
                    setattr(total, effect, getattr(total, effect) + value)
                else:
                    by_zone = getattr(total, effect)
                    for zone in zones:
                        by_zone[zone] = by_zone.get(zone, 0) + value
        for zone in ZONES:
            total.zone_level[zone] = 1 + total.zone_level.get(zone, 0)
        return total

    def total_cost(self) -> dict[str, int]:
        """What every node costs together, by currency (for the budget check)."""
        total: dict[str, int] = {}
        for node_id in self.nodes:
            for currency, amount in self.cost(node_id).items():
                total[currency] = total.get(currency, 0) + amount
        return total


def _kind(currency: str) -> str:
    """The cost base of a currency: research points, or a zone's resource."""
    return RESEARCH if currency == RESEARCH else "resource"


# --- Reading the data file -------------------------------------------------------------


def _frozen(mapping):
    return MappingProxyType(dict(mapping)) if mapping is not None else None


def parse(raw: Any) -> SkillTree:
    """Validate the content of data/skill_tree.json. Raises SkillTreeError on any problem."""
    if not isinstance(raw, dict) or set(raw) != {"trees", "nodes"}:
        raise SkillTreeError('the file holds {"trees": [...], "nodes": [...]}')
    trees: dict[str, Tree] = {}
    for item in raw["trees"]:
        tree = Tree(
            id=item["id"],
            name=item["name"],
            zone=item.get("zone"),
            requires=item.get("requires"),
            currencies=tuple(item["currencies"]),
            milestone_currencies=tuple(item.get("milestone_currencies", item["currencies"])),
            description=item.get("description", ""),
        )
        if tree.id in trees:
            raise SkillTreeError(f"two trees are called {tree.id!r}")
        if tree.zone is not None and tree.zone not in ZONES:
            raise SkillTreeError(f"tree {tree.id!r}: unknown zone {tree.zone!r}")
        if unknown := set(tree.currencies + tree.milestone_currencies) - CURRENCIES:
            raise SkillTreeError(f"tree {tree.id!r}: unknown currencies {sorted(unknown)}")
        trees[tree.id] = tree

    nodes: dict[str, Node] = {}
    for item in raw["nodes"]:
        node = Node(
            id=item["id"],
            tree=item["tree"],
            name=item["name"],
            col=item["col"],
            lane=item.get("lane", 0),
            effects=_frozen(item["effects"]),
            requires=tuple(item.get("requires", ())),
            milestone=item.get("milestone", False),
            zone=item.get("zone"),
            cost_override=_frozen(item.get("cost")),
        )
        if node.id in nodes:
            raise SkillTreeError(f"two nodes are called {node.id!r}")
        if node.tree not in trees:
            raise SkillTreeError(f"node {node.id!r}: unknown tree {node.tree!r}")
        if unknown := set(node.effects) - EFFECTS:
            raise SkillTreeError(f"node {node.id!r}: unknown effects {sorted(unknown)}")
        zone_effect = bool(set(node.effects) & ZONE_EFFECTS)
        if zone_effect and node.zone != "all" and trees[node.tree].zone is None:
            raise SkillTreeError(f'node {node.id!r}: a zone effect needs a zone tree or "all"')
        if not isinstance(node.col, int) or node.col < 1:
            raise SkillTreeError(f"node {node.id!r}: col starts at 1")
        nodes[node.id] = node

    for node in nodes.values():
        for needed in node.requires:
            if needed not in nodes:
                raise SkillTreeError(f"node {node.id!r} requires an unknown node {needed!r}")
            other = nodes[needed]
            # Within a tree, a node needs nodes on its left: no loop is possible
            if other.tree == node.tree and other.col >= node.col:
                raise SkillTreeError(f"node {node.id!r} requires {needed!r}, not on its left")
    for tree in trees.values():
        if tree.requires is not None and tree.requires not in nodes:
            raise SkillTreeError(f"tree {tree.id!r} opens with an unknown node {tree.requires!r}")
    return SkillTree(trees=MappingProxyType(trees), nodes=MappingProxyType(nodes))


def load(path: Path) -> SkillTree:
    """Read and validate the skill tree file."""
    return parse(json.loads(Path(path).read_text(encoding="utf-8")))


# --- What a node does, in words (for the lab page) ----------------------------------------


def describe(tree: SkillTree, node_id: str) -> list[str]:
    """The effects of a node in English, one line each, e.g. "+5 % berries in the Meadow"."""
    node = tree.nodes[node_id]
    zone_slug = node.zone or tree.trees[node.tree].zone
    where = (
        "in every zone"
        if node.zone == "all"
        else f"in the {ZONES[zone_slug].name}"
        if zone_slug
        else ""
    )
    lines = []
    for effect, value in node.effects.items():
        if effect == "welcome_places":
            lines.append(f"+{value} place{'s' if value > 1 else ''} in the Welcome area")
        elif effect == "feeder_slots":
            lines.append(f"+{value} feeder slot{'s' if value > 1 else ''}")
        elif effect == "feeder_max_units":
            lines.append(f"+{value} units per feeder slot")
        elif effect == "feeder_unit_tenths":
            lines.append(f"Each unit in the feeder lures +{value / 10:g} point more")
        elif effect == "research_percent":
            lines.append(f"+{value} % research points")
        elif effect == "candy_xp_percent":
            lines.append(f"+{value} % experience from candies")
        elif effect == "zone_slots":
            lines.append(f"+{value} Pokémon {where}")
        elif effect == "zone_storage_hours":
            lines.append(f"+{value} h of storage {where}")
        elif effect == "zone_yield_percent":
            what = ZONES[zone_slug].resource_plural.lower() if node.zone != "all" else "resources"
            lines.append(f"+{value} % {what} {where}")
        elif effect == "zone_xp_percent":
            lines.append(f"+{value} % experience {where}")
        elif effect == "zone_level":
            lines.append(f"The {ZONES[zone_slug].name} levels up: new Pokémon may come")
    lines += [f"Opens the {t.name} tree" for t in tree.trees.values() if t.requires == node_id]
    return lines
