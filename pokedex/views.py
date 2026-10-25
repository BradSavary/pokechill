from django.shortcuts import render


def index(request):
    """Pokédex main page (placeholder until species are imported)."""
    return render(request, "pokedex/index.html", {"active_tab": "pokedex"})
