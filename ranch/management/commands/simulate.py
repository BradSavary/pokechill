"""
Django command: `uv run python manage.py simulate [--days 60] [--visits 7,12,19] [--seed 1]`.

Plays a simulated player for weeks (game.simulation), with the species of
the game and the skill tree, and prints its progress day by day: species
owned and mastered, research points earned and left, nodes unlocked. Run it after any
change of the balance (game/balance.py) or of the tree
(data/skill_tree.json), to check that the progress stays smooth.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count

from game.simulation import SimSpecies, longest_wait, simulate
from game.skill_tree import load
from pokedex.models import Species

TREE_FILE = settings.BASE_DIR / "data" / "skill_tree.json"


def catalog() -> list[SimSpecies]:
    """The species of the game, as the simulation needs them (from the database)."""
    species = list(
        Species.objects.filter(is_available=True)
        .exclude(rarity="")
        .select_related("primary_type", "secondary_type")
    )
    sizes = dict(Species.objects.values_list("evolution_chain_id").annotate(size=Count("id")))
    return [
        SimSpecies(
            slug=s.slug,
            rarity=s.rarity,
            min_level=s.min_level,
            types=tuple(t.slug for t in s.types),
            growth_rate=s.growth_rate,
            evolution_stage=s.evolution_stage,
            family=str(s.evolution_chain_id),
            family_size=sizes[s.evolution_chain_id],
            conditions=s.arrival_conditions,
            custom_challenges=s.custom_challenges,
        )
        for s in species
    ]


class Command(BaseCommand):
    help = "Simulate a regular player for weeks, to check the economy of the game."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=60)
        parser.add_argument("--visits", default="7,12,19", help="Hours of the visits (UTC).")
        parser.add_argument("--seed", type=int, default=1)

    def handle(self, *args, days, visits, seed, **options):
        tree = load(TREE_FILE)
        hours = tuple(int(hour) for hour in visits.split(","))
        reports = simulate(catalog(), tree, days=days, visit_hours=hours, seed=seed)
        names = {node_id: node.name for node_id, node in tree.nodes.items()}

        self.stdout.write(
            f"{'day':>4} {'owned':>5} {'mast.':>5} {'earned':>7} {'left':>6} {'nodes':>6}  bought"
        )
        for report in reports:
            bought = ", ".join(names[node_id] for node_id in report.bought)
            self.stdout.write(
                f"{report.day:>4} {report.owned:>5} {report.mastered:>5} "
                f"{report.research_earned:>7} {report.research_left:>6} "
                f"{report.nodes:>3}/{len(tree.nodes):<3} {bought}"
            )
        last = reports[-1]
        self.stdout.write("")
        self.stdout.write(f"Longest wait without any unlock: {longest_wait(reports)} days")
        self.stdout.write(f"Resources at the end: {last.resources}")
