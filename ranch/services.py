"""Operations on the player's game state, used by the views."""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from game import balance
from game.arrivals import NATURES
from game.clock import floor_to_hour
from game.collection import Obtention, OwnedState, resolve_obtention
from pokedex.models import Species

from .models import CandyStock, OwnedPokemon, Player


def ensure_player(user) -> Player:
    """
    The game save of `user`, created on first use with the three starters.

    A new save starts at the current hour: arrivals begin with the next one.
    """
    with transaction.atomic():  # the save and its starters, or nothing
        player, created = Player.objects.get_or_create(
            user=user, defaults={"last_slot": floor_to_hour(timezone.now())}
        )
        if created:
            give_starters(player)
    return player


def give_starters(player: Player) -> None:
    """The three Kanto starters, with a nature drawn from the player's own seed."""
    rng = random.Random(f"starters:{player.pk}")
    for species in Species.objects.filter(slug__in=balance.STARTER_SPECIES).order_by("number"):
        receive_pokemon(player, species, nature=rng.choice(NATURES), is_shiny=False)


@transaction.atomic
def receive_pokemon(player: Player, species: Species, *, nature: str, is_shiny: bool) -> Obtention:
    """
    The single entry point for obtaining a Pokémon (starter, arrival, gift...).

    The game rule lives in game.collection.resolve_obtention; this function
    loads the current state, asks the rule, and saves its outcome.
    """
    # select_for_update locks the row until the end of the transaction, so two
    # simultaneous requests can't both convert the same catch
    owned = OwnedPokemon.objects.select_for_update().filter(player=player, species=species).first()
    state = OwnedState(frozenset(owned.unlocked_natures), owned.shiny_unlocked) if owned else None
    outcome = resolve_obtention(state, species.rarity, nature, is_shiny)

    if outcome.is_new:
        OwnedPokemon.objects.create(
            player=player,
            species=species,
            level=species.min_level,
            unlocked_natures=[nature],
            shiny_unlocked=is_shiny,
        )
        return outcome

    if outcome.new_nature:
        owned.unlocked_natures = sorted([*owned.unlocked_natures, outcome.new_nature])
    owned.shiny_unlocked = owned.shiny_unlocked or outcome.new_shiny
    owned.save(update_fields=["unlocked_natures", "shiny_unlocked"])

    stock, _ = CandyStock.objects.get_or_create(player=player, family=species.evolution_chain)
    # F() makes the database do the addition: no lost update if two requests race
    CandyStock.objects.filter(pk=stock.pk).update(amount=F("amount") + outcome.candies)
    return outcome


def mark_seen(player: Player) -> None:
    """Record a visit (one small UPDATE, without reloading the player)."""
    player.last_seen_at = timezone.now()
    Player.objects.filter(pk=player.pk).update(last_seen_at=player.last_seen_at)


def inactive_guests(days: int):
    """
    Guest users who haven't played for `days` days.

    A guest's password starts with Django's "unusable" marker. Registered
    players and staff are never selected, however long their absence.
    A guest without a save (none created yet) is judged on its sign-up date.
    """
    cutoff = timezone.now() - timedelta(days=days)
    return get_user_model().objects.filter(
        Q(player__last_seen_at__lt=cutoff) | Q(player__isnull=True, date_joined__lt=cutoff),
        password__startswith=UNUSABLE_PASSWORD_PREFIX,
        is_staff=False,
    )
