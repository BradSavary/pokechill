# PokéChill

[![CI](https://github.com/BradSavary/pokechill/actions/workflows/ci.yml/badge.svg)](https://github.com/BradSavary/pokechill/actions/workflows/ci.yml)

An idle + roguelike web game set in the Kanto region. You take over an abandoned Pokémon ranch: every hour a wild Pokémon shows up, attracted by what you built, what you put in the feeder, the time of day and the Pokémon already living there. The goal is to complete the 151-species research Pokédex, in the spirit of *Pokémon Legends: Arceus*.

**Live: [pokechill.bradsavary.dev](https://pokechill.bradsavary.dev)**

![Pokédex page](docs/images/pokedex.png)

> Personal learning project (Python and Django) built for my portfolio.
> Unofficial, non-commercial fan game. Not affiliated with Nintendo, Game Freak or The Pokémon Company.

## Status

The game is built in 8 playable steps, each one deployed (full design in [docs/concept.md](docs/concept.md), in French).

| Step | Content | Status |
| --- | --- | --- |
| 0 | Foundations: Django on Vercel, PokéAPI import, browsable Pokédex | Done |
| 1 | Hourly arrivals, guest mode and accounts | Next |
| 2 | Harvest zones and the feeder | Planned |
| 3 | Research: challenges, skill tree, mastery | Planned |
| 4 | Daily and weekly quests | Planned |
| 5 | Full ranch content (8 zones, TMs, natures, shinies) | Planned |
| 6 | Roguelike expeditions (2D, Phaser) | Planned |
| 7 | Legendaries and 3D dungeons (Three.js) | Planned |

## Tech stack

- **Back end:** Python 3.13, Django 5.2 (LTS)
- **Front end:** Django templates, [HTMX](https://htmx.org) for partial page updates, Tailwind CSS v4
- **Database:** SQLite locally, PostgreSQL ([Neon](https://neon.tech)) in production, selected by `DATABASE_URL`
- **Hosting:** Vercel (serverless Python functions, static files on the CDN)
- **Tooling:** [uv](https://docs.astral.sh/uv/) (Python and dependencies), Ruff (lint and format), pytest, GitHub Actions

## Technical highlights

- **One-off data import.** A Django command (`import_pokeapi`) fetches species, types, moves and FireRed/LeafGreen learnsets from [PokéAPI](https://pokeapi.co). Responses are cached on disk, parsing is done by pure functions, and everything is written in a single transaction, so a failed import never leaves half-written data. The import is idempotent: running it again updates rows instead of duplicating them.
- **Progressive enhancement with HTMX.** Every Pokédex entry has its own URL and works without JavaScript. With HTMX, a click only swaps the entry pane, and the same view returns either a fragment or the full page depending on the `HX-Request` header.
- **Query-conscious views.** A full Pokédex page takes 5 SQL queries and an entry 3, whatever the number of moves, thanks to `select_related` and `prefetch_related`.
- **Serverless-first design.** No process runs permanently: game time will be recomputed on each visit from timestamps, with per-hour random seeds so the result doesn't depend on when it is computed.
- **Tested without the network.** The PokéAPI client is injected, so tests use a fake client or `httpx.MockTransport`. CI checks formatting, lint, Django checks, missing migrations, tests, and that the committed CSS matches the templates.

## Run it locally

Requirements: [uv](https://docs.astral.sh/uv/getting-started/installation/) (it installs Python 3.13 by itself).

```bash
git clone https://github.com/BradSavary/pokechill.git
cd pokechill
uv sync                                       # create .venv and install dependencies
uv run python manage.py migrate               # create the local SQLite database
uv run python manage.py import_pokeapi --no-media   # import the 151 species (~2 min the first time)
uv run python manage.py runserver
```

Then open <http://127.0.0.1:8000>. Sprites and cries are already in the repository, hence `--no-media`.

Useful commands:

| Task | Command |
| --- | --- |
| Run the tests | `uv run pytest` |
| Format and lint | `uv run ruff format .` then `uv run ruff check .` |
| Rebuild the CSS on template changes | `uv run python scripts/build_css.py --watch` |
| Admin account (then visit `/admin/`) | `uv run python manage.py createsuperuser` |

## Project structure

```
config/              Django settings (read from environment variables) and root URLs
pokedex/             Pokédex app: models, views, templates, admin
  pokeapi/           PokéAPI client (with cache), parsers and importer
  management/        The import_pokeapi command
templates/           Shared base layout
assets/css/          Tailwind source, compiled into static/css/main.css
static/              Compiled CSS, HTMX, sprites, cries and type icons
scripts/             CSS build script
tests/               pytest suite
docs/                Game design document
```

## Credits

- Game data from [PokéAPI](https://pokeapi.co); sprites, cries and type icons from the [PokeAPI/sprites](https://github.com/PokeAPI/sprites) and [PokeAPI/cries](https://github.com/PokeAPI/cries) repositories.
- Pokémon and all related names and images are trademarks and © of Nintendo, Game Freak and The Pokémon Company. This project is not affiliated with or endorsed by them.
