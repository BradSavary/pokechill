"""
The skill tree of the game, read once from data/skill_tree.json.

A module of its own, without models: the models (Player reads its bonuses)
and the services (buying a node) both need the tree.
"""

from functools import cache

from django.conf import settings

from game.skill_tree import SkillTree, load

TREE_FILE = settings.BASE_DIR / "data" / "skill_tree.json"


@cache
def skill_tree() -> SkillTree:
    """The skill tree, read and validated at the first call, then kept in memory."""
    return load(TREE_FILE)
