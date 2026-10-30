"""
A simulated player, to tune the economy of the game (manage.py simulate).

The whole game logic is pure Python (game/), so a script can play weeks of
the game in a few seconds, with the real species data and the real rules:
the hourly arrivals and their conditions, the zones, the feeder, the
challenges and their rewards, the candies and the skill tree. What it
plays like is a regular player:

    a few visits a day; at each one:
      catch up the hours (arrivals, zones' work) and collect the zones,
      reveal the arrivals, claim every reward, give the candies,
      buy the cheapest node it can afford, put its best Pokémon to work,
      fill the free slots of the feeder

The result is a report per day (species owned, research points earned and
left, nodes unlocked): it shows whether the progress is smooth, or where
the player waits too long, or gets everything too soon.

It is a model, not the game: the player is greedy and never forgets to
come back. The point is to compare settings, not to predict a real player.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from . import balance, experience
from .arrivals import SpeciesRule, catch_up
from .challenges import ChallengeSpecies, challenge_points, challenges_for, stage
from .clock import ONE_HOUR, floor_to_hour
from .collection import OwnedState, resolve_obtention
from .mastery import candy_percent, is_mastered
from .objectives import FAMILY, HARVESTED, LEVEL, NATURES, OBTAINED, WORKED, Event, apply
from .skill_tree import RESEARCH, SkillTree
from .zones import ZONES, Worker, production_per_hour, work


@dataclass(frozen=True)
class SimSpecies:
    """What the simulation knows of a species (from the catalogue and its data file)."""

    slug: str
    rarity: str
    min_level: int
    types: tuple[str, ...]
    growth_rate: str
    evolution_stage: int
    family: str
    family_size: int
    conditions: dict | None = None
    custom_challenges: dict | None = None

    @property
    def rule(self) -> SpeciesRule:
        return SpeciesRule(self.slug, self.rarity, self.conditions, self.types)

    @property
    def challenge_species(self) -> ChallengeSpecies:
        return ChallengeSpecies(
            self.slug, self.rarity, self.min_level, self.family, self.family_size
        )


@dataclass
class Mon:
    """A Pokémon of the simulated player."""

    species: SimSpecies
    level: int
    xp: int = 0  # since its current level
    pending: int = 0  # earned in its zone, applied when the zone is collected
    natures: set[str] = field(default_factory=set)
    shiny: bool = False


@dataclass(frozen=True)
class DayReport:
    day: int
    owned: int
    research_earned: int  # since the start
    research_left: int  # not spent yet
    nodes: int  # unlocked since the start
    bought: tuple[str, ...]  # the nodes unlocked this day
    resources: dict[str, int]
    mastered: int = 0  # species at their stage 3 (their mastery bonuses work)


class Player:
    """The state of the simulated player, and what it does at each visit."""

    def __init__(self, catalog: list[SimSpecies], tree: SkillTree, seed: int, start: datetime):
        self.catalog = {species.slug: species for species in catalog}
        self.rules = [species.rule for species in catalog]
        self.tree = tree
        self.seed = seed
        self.last_slot = floor_to_hour(start)
        self.mons: dict[str, Mon] = {}
        self.candies: dict[str, int] = defaultdict(int)  # by family
        self.resources: dict[str, int] = defaultdict(int)
        self.zone_hours = {zone: 0 for zone in balance.STARTING_ZONES}
        self.zone_centi = {zone: 0 for zone in balance.STARTING_ZONES}
        self.assignment: dict[str, list[str]] = {zone: [] for zone in balance.STARTING_ZONES}
        self.feeder: list[tuple[str, int]] = []
        self.progress: dict[str, int] = {}
        self.claimed: set[str] = set()
        self.claimed_stage: dict[str, int] = defaultdict(int)
        self.research = 0
        self.research_earned = 0
        self.unlocked: set[str] = set()
        self.bonuses = tree.bonuses(())
        self.events: list[Event] = []
        # The challenges of every species, built once
        self.challenges = {
            slug: challenges_for(species.challenge_species, species.custom_challenges)
            for slug, species in self.catalog.items()
        }
        self.family_members: dict[str, list[str]] = defaultdict(list)
        for species in catalog:
            self.family_members[species.family].append(species.slug)

    # --- The start of the game (as ranch.services and ranch.tutorial do) --------------

    def start(self) -> None:
        for slug in (*balance.STARTER_SPECIES, balance.TUTORIAL_GIFT_SPECIES):
            if slug in self.catalog:
                self.receive(slug, "hp", False)
        resource, amount = balance.TUTORIAL_FEEDER_GIFT
        self.resources[resource] += amount
        self.flush_events()

    # --- One visit -------------------------------------------------------------------------

    def visit(self, now: datetime) -> list[str]:
        """Play one visit; returns the names of the nodes bought."""
        hours = self.catch_up(now)
        self.work_zones(hours)
        self.collect()
        for arrival in self.arrivals:
            self.receive(arrival.slug, arrival.nature, arrival.is_shiny)
        self.flush_events()
        self.claim_all()
        self.give_candies()
        self.flush_events()
        self.claim_all()
        bought = self.buy_nodes()
        self.assign_workers()
        self.fill_feeder()
        return bought

    def catch_up(self, now: datetime) -> int:
        bonuses = self.bonuses
        result = catch_up(
            player_id=self.seed,
            rules=self.rules,
            last_slot=self.last_slot,
            now=now,
            free_places=balance.WELCOME_CAPACITY_BASE + bonuses.welcome_places,
            feeder=self.feeder,
            owned=frozenset(self.mons),
            workers=frozenset(
                (zone, slug) for zone, slugs in self.assignment.items() for slug in slugs
            ),
            max_units=balance.FEEDER_MAX_UNITS + bonuses.feeder_max_units,
            unit_tenths=bonuses.feeder_unit_tenths,
            zone_levels={zone: bonuses.zone_level[zone] for zone in self.assignment},
        )
        hours = (result.last_slot - self.last_slot) // ONE_HOUR
        self.last_slot = result.last_slot
        self.feeder = list(result.feeder)
        self.arrivals = result.arrivals
        return hours

    def worker(self, mon) -> Worker:
        """A Pokémon as the zones see it (mastered once its stage 3 is claimed)."""
        mastered = is_mastered(self.claimed_stage[mon.species.slug])
        return Worker(mon.species.types, mon.level, mastered)

    def work_zones(self, hours: int) -> None:
        for zone_slug, slugs in self.assignment.items():
            zone, mons = ZONES[zone_slug], [self.mons[slug] for slug in slugs]
            done = work(
                zone,
                [self.worker(mon) for mon in mons],
                self.zone_hours[zone_slug],
                hours,
                cap_hours=balance.ZONE_WORK_HOURS_CAP
                + self.bonuses.of_zone("zone_storage_hours", zone_slug),
                yield_percent=self.bonuses.of_zone("zone_yield_percent", zone_slug),
                xp_percent=self.bonuses.of_zone("zone_xp_percent", zone_slug),
            )
            self.zone_hours[zone_slug] += done.hours
            self.zone_centi[zone_slug] += done.resource_centi
            for mon, gained, made in zip(mons, done.experience, done.resources, strict=False):
                mon.pending += gained
                details = {"species": mon.species.slug, "zone": zone_slug}
                self.events.append(Event(WORKED, done.hours, details))
                self.events.append(Event(HARVESTED, made, {**details, "resource": zone.resource}))

    def collect(self) -> None:
        for zone_slug in self.assignment:
            whole, self.zone_centi[zone_slug] = divmod(self.zone_centi[zone_slug], 100)
            self.resources[ZONES[zone_slug].resource] += whole
            self.zone_hours[zone_slug] = 0
            for slug in self.assignment[zone_slug]:
                mon = self.mons[slug]
                self.raise_mon(mon, mon.pending)
                mon.pending = 0

    def raise_mon(self, mon: Mon, gained: int) -> None:
        old = mon.level
        mon.level, mon.xp = experience.add_experience(
            mon.species.growth_rate, mon.level, mon.xp, gained
        )
        if mon.level > old:
            self.events.append(Event(LEVEL, mon.level, {"species": mon.species.slug}))

    def receive(self, slug: str, nature: str, shiny: bool) -> None:
        species, mon = self.catalog[slug], self.mons.get(slug)
        state = OwnedState(frozenset(mon.natures), mon.shiny) if mon else None
        outcome = resolve_obtention(state, species.rarity, nature, shiny)
        events = [Event(OBTAINED, details={"species": slug, "shiny": shiny})]
        if outcome.is_new:
            mon = self.mons[slug] = Mon(species, species.min_level, natures={nature}, shiny=shiny)
            owned_in_family = sum(
                member in self.mons for member in self.family_members[species.family]
            )
            events += [
                Event(LEVEL, mon.level, {"species": slug}),
                Event(FAMILY, owned_in_family, {"family": species.family}),
            ]
        else:
            self.candies[species.family] += outcome.candies
            mon.natures.add(nature)
            mon.shiny = mon.shiny or shiny
        events.append(Event(NATURES, len(mon.natures), {"species": slug}))
        self.events += events

    def flush_events(self) -> None:
        """Feed the events of the visit to the challenges of the species they concern."""
        if not self.events:
            return
        slugs = set()
        for event in self.events:
            if "species" in event.details:
                slugs.add(event.details["species"])
            if "family" in event.details:
                slugs.update(self.family_members[event.details["family"]])
        objectives = [c.objective for slug in slugs for c in self.challenges[slug]]
        changed, _ = apply(objectives, self.progress, self.events)
        self.progress.update(changed)
        self.events = []

    def claim_all(self) -> None:
        """Claim every reward waiting (challenges, then stages), as ranch.research does."""
        percent = 100 + self.bonuses.research_percent
        for slug, mon in self.mons.items():
            found, species = self.challenges[slug], mon.species
            for challenge in found:
                key = challenge.objective.key
                if (
                    key not in self.claimed
                    and self.progress.get(key, 0) >= challenge.objective.target
                ):
                    self.claimed.add(key)
                    self.earn(challenge_points(species.rarity) * percent // 100)
            claimed = sum(c.objective.key in self.claimed for c in found)
            reached = stage(True, claimed, len(found))
            while self.claimed_stage[slug] < reached:
                self.claimed_stage[slug] += 1
                if self.claimed_stage[slug] == 1:
                    self.earn(balance.STAGE_1_RESEARCH_POINTS * percent // 100)
                elif self.claimed_stage[slug] == 2:
                    self.earn(balance.STAGE_2_RESEARCH_POINTS * percent // 100)
                    self.candies[species.family] += balance.STAGE_2_CANDIES

    def earn(self, points: int) -> None:
        self.research += points
        self.research_earned += points

    def give_candies(self) -> None:
        """Raise the Pokémon one level at a time while the candies allow: workers first."""
        working = {slug for slugs in self.assignment.values() for slug in slugs}
        order = sorted(self.mons.values(), key=lambda m: (m.species.slug not in working, m.level))
        for mon in order:
            family = mon.species.family
            mastered = is_mastered(self.claimed_stage[mon.species.slug])
            bonus = self.bonuses.candy_xp_percent + candy_percent(mastered)
            while mon.level < experience.MAX_LEVEL:
                curve, stage_ = mon.species.growth_rate, mon.species.evolution_stage
                need = experience.candies_to_next_level(curve, mon.level, mon.xp, stage_, bonus)
                if need > self.candies[family]:
                    break
                old = mon.level
                mon.level, mon.xp, eaten = experience.feed_candies(
                    curve, mon.level, mon.xp, stage_, need, bonus
                )
                self.candies[family] -= eaten
                if mon.level > old:
                    self.events.append(Event(LEVEL, mon.level, {"species": mon.species.slug}))

    def wallet(self) -> dict[str, int]:
        return {RESEARCH: self.research, **self.resources}

    def buy_nodes(self) -> list[str]:
        """Buy the cheapest node it can afford, again and again."""
        bought = []
        while True:
            wallet = self.wallet()
            affordable = [
                node_id
                for node_id in self.tree.nodes
                if self.tree.can_unlock(node_id, self.unlocked)
                and all(wallet.get(c, 0) >= n for c, n in self.tree.cost(node_id).items())
            ]
            if not affordable:
                return bought
            node_id = min(affordable, key=lambda n: sum(self.tree.cost(n).values()))
            for currency, amount in self.tree.cost(node_id).items():
                if currency == RESEARCH:
                    self.research -= amount
                else:
                    self.resources[currency] -= amount
            self.unlocked.add(node_id)
            self.bonuses = self.tree.bonuses(self.unlocked)
            bought.append(node_id)

    def assign_workers(self) -> None:
        """Each zone takes the best producers left (the zones in turn)."""
        free = set(self.mons)
        for zone_slug in self.assignment:
            zone = ZONES[zone_slug]
            spots = balance.ZONE_SLOTS_BASE + self.bonuses.of_zone("zone_slots", zone_slug)
            best = sorted(
                free,
                key=lambda slug: -production_per_hour(zone, self.worker(self.mons[slug])),
            )[:spots]
            self.assignment[zone_slug] = best
            free -= set(best)

    def fill_feeder(self) -> None:
        """A quarter of its richest stock in each free slot (it keeps the rest for nodes)."""
        slots = balance.FEEDER_SLOTS_BASE + self.bonuses.feeder_slots
        max_units = balance.FEEDER_MAX_UNITS + self.bonuses.feeder_max_units
        while len(self.feeder) < slots:
            resource = max(self.resources, key=self.resources.get, default=None)
            units = min(max_units, self.resources[resource] // 4) if resource else 0
            if units < 5:
                return
            self.resources[resource] -= units
            self.feeder.append((resource, units))


def simulate(
    catalog: list[SimSpecies],
    tree: SkillTree,
    *,
    days: int = 60,
    visit_hours: tuple[int, ...] = (7, 12, 19),
    seed: int = 1,
    start: datetime = datetime(2026, 1, 1, tzinfo=UTC),
) -> list[DayReport]:
    """Play `days` days (visits at `visit_hours`, UTC) and report each day."""
    player = Player(catalog, tree, seed, start)
    player.start()
    reports = []
    for day in range(1, days + 1):
        bought: list[str] = []
        for hour in visit_hours:
            bought += player.visit(start + timedelta(days=day - 1, hours=hour))
        reports.append(
            DayReport(
                day=day,
                owned=len(player.mons),
                mastered=sum(is_mastered(stage) for stage in player.claimed_stage.values()),
                research_earned=player.research_earned,
                research_left=player.research,
                nodes=len(player.unlocked),
                bought=tuple(bought),
                resources=dict(player.resources),
            )
        )
    return reports


def longest_wait(reports: list[DayReport]) -> int:
    """The longest run of days without any node unlocked, before the last unlock."""
    days = [report.day for report in reports if report.bought]
    if not days:
        return len(reports)
    gaps = [later - earlier - 1 for earlier, later in zip([0, *days], days, strict=False)]
    return max(gaps)
