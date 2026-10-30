"""
Professor Oak's lab: the skill tree (/lab/).

It opens once the Pokédex holds enough species (balance.LAB_SPECIES_REQUIRED);
until then its door on the Ranch map stays shut. Its first page shows the
trees as cards (like the zones); a tree's page shows its nodes, from left to
right. Clicking a node shows what it does and costs (HTMX), and unlocking it
answers with the tree again.
"""

from functools import wraps

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from game import balance

from .decorators import player_required
from .skill_data import skill_tree
from .skills import SkillError, lab_is_open, tree_cards, tree_view, unlock_node, wallet_of


def lab_required(view):
    """The lab's pages: back to the Ranch while the lab is still shut."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not lab_is_open(request.player):
            messages.info(
                request,
                f"The lab opens once your Pokédex holds {balance.LAB_SPECIES_REQUIRED} species.",
            )
            return redirect("ranch:index")
        return view(request, *args, **kwargs)

    return wrapper


def is_htmx(request) -> bool:
    return "HX-Request" in request.headers


def tree_or_404(tree_id: str):
    if tree_id not in skill_tree().trees:
        raise Http404("No such tree")
    return tree_id


@player_required
@lab_required
def index(request):
    """The trees of the lab, as cards; Professor Oak's introduction at the first visit."""
    return render(
        request,
        "lab/index.html",
        {
            "active_tab": "lab",
            "cards": tree_cards(request.player),
            "wallet": wallet_of(request.player),
            "intro": not request.player.lab_intro_seen,
        },
    )


@require_POST
@player_required
def intro_seen(request):
    """The player closed Professor Oak's introduction: it won't show again."""
    request.player.lab_intro_seen = True
    request.player.save(update_fields=["lab_intro_seen"])
    return redirect("lab:index")


def tree_context(request, tree_id: str, selected: str | None) -> dict:
    view = tree_view(request.player, tree_id)
    cells = {cell["node"].id: cell for cell in view["cells"]}
    return {
        "active_tab": "lab",
        "view": view,
        "wallet": wallet_of(request.player),
        # The node shown in the panel under the tree (the first one at the start)
        "selected": cells.get(selected) or view["cells"][0],
    }


@player_required
@lab_required
def tree(request, tree_id):
    """A tree of the lab, its nodes from left to right."""
    tree_or_404(tree_id)
    return render(request, "lab/tree.html", tree_context(request, tree_id, request.GET.get("node")))


@player_required
@lab_required
def node(request, tree_id, node_id):
    """What a node does and costs (HTMX: the panel under the tree)."""
    context = tree_context(request, tree_or_404(tree_id), node_id)
    return render(request, "lab/_node_detail.html", context)


@require_POST
@player_required
@lab_required
def unlock(request, tree_id, node_id):
    """Unlock a node, then show the tree again (with the wallet, out of band)."""
    tree_or_404(tree_id)
    error = ""
    try:
        unlock_node(request.player, node_id)
    except SkillError as problem:
        error = str(problem)
    if not is_htmx(request):
        if error:
            messages.error(request, error)
        return redirect(f"{reverse('lab:tree', args=[tree_id])}?node={node_id}")
    context = tree_context(request, tree_id, node_id) | {"error": error, "just_unlocked": not error}
    return render(request, "lab/_unlock_response.html", context)
