# PokéChill — Synthèse technique

État du projet à la fin de l'**étape 0 (le socle)**, au 26 octobre 2026. Ce document décrit ce qui est construit, comment les pièces s'articulent et pourquoi elles ont été conçues ainsi. Il sera complété à chaque étape. Pour le gameplay, voir [concept.md](concept.md).

- **Production :** https://pokechill.bradsavary.dev
- **Dépôt :** https://github.com/BradSavary/pokechill
- **Contenu jouable :** un Pokédex consultable des 151 espèces de Kanto (fiches, recherche, filtre par type, silhouettes).

## 1. Vue d'ensemble

| Couche | Technologie | Rôle |
| --- | --- | --- |
| Langage et outillage | Python 3.13, uv | Version de Python, environnement virtuel, dépendances figées dans `uv.lock` |
| Framework | Django 5.2 LTS | URLs, vues, modèles, templates, admin, commandes |
| Interface | Templates Django, HTMX 2.0.4, Tailwind CSS v4.3.3 | Pages rendues côté serveur, mises à jour partielles sans framework JavaScript |
| Base de données | SQLite (local), PostgreSQL Neon (production) | Choisie par la variable `DATABASE_URL` |
| Hébergement | Vercel, région `fra1` (Francfort) | Une fonction serverless Python, fichiers statiques sur le CDN |
| Qualité | Ruff, pytest, GitHub Actions | Formatage, lint, tests, intégration continue |

### Le circuit d'une requête

```
Navigateur ──GET /pokedex/25/──▶ Vercel (HTTPS) ──▶ fonction Python (Django)
                                                        │
                       middlewares (sécurité, session, CSRF)
                                                        │
               config/urls.py ─▶ pokedex/urls.py ─▶ views.species_detail
                                                        │
                            modèles (ORM) ◀──▶ PostgreSQL Neon
                                                        │
                 template : page complète, ou fragment si requête HTMX
                                                        │
Navigateur ◀──────────────── HTML ◀─────────────────────┘
     └──▶ /static/... (CSS, JS, sprites, cris) servis directement par le CDN de Vercel
```

### L'architecture cible

Le projet vise trois couches. À la fin de l'étape 0, seules les deux premières existent :

1. **Interface** : templates, HTMX, Tailwind.
2. **Couche Django** : modèles, vues, commandes, comptes.
3. **Moteur de jeu en Python pur, sans import Django** : conditions d'arrivée, objectifs, rattrapage du temps. Il arrive à l'étape 1 et sera testé sans base de données.

## 2. Arborescence

```
config/                  Projet Django
  settings.py            Réglages lus depuis l'environnement
  urls.py                Aiguillage racine (/admin/, /pokedex/, / redirige vers le Pokédex)
pokedex/                 App Pokédex
  models.py              Type, EvolutionChain, Species, Move, SpeciesMove
  views.py               Pages et fragments HTMX
  urls.py                /pokedex/, /pokedex/list/, /pokedex/<numéro>/
  admin.py               Interface d'administration (vérification des données)
  pokeapi/               Import des données
    client.py            Client HTTP avec cache disque
    parsers.py           Fonctions pures JSON -> dictionnaires
    importer.py          Orchestration en 3 phases
  management/commands/
    import_pokeapi.py    Commande Django d'import
  templates/pokedex/     index.html, _species_list.html, _entry.html, _type_badge.html
templates/base.html      Gabarit commun : navigation, pied de page légal
assets/css/input.css     Source Tailwind (non servie)
static/                  Fichiers servis tels quels
  css/main.css           CSS compilé et minifié (commité)
  js/                    htmx.min.js, pokedex.js
  pokemon/               sprites/, sprites/shiny/, cries/, types/
scripts/build_css.py     Compilation Tailwind (version figée)
tests/                   conftest.py, test_smoke, test_models, test_pokeapi, test_views
.github/workflows/ci.yml Intégration continue
vercel.json              Région des fonctions
data/pokeapi_cache/      Cache des réponses PokéAPI (66 Mo, non commité)
```

## 3. Configuration et environnements

Le même code tourne partout : seules les variables d'environnement changent.

| Variable | Local | Production (Vercel) |
| --- | --- | --- |
| `DJANGO_DEBUG` | absente : debug activé | `0` |
| `DJANGO_SECRET_KEY` | absente : clé de développement | clé secrète (obligatoire, sinon l'application refuse de démarrer) |
| `DJANGO_ALLOWED_HOSTS` | absente : `localhost`, `127.0.0.1` | `.vercel.app,pokechill.bradsavary.dev` |
| `DATABASE_URL` | absente : `db.sqlite3` | URL Neon avec pooler (ajoutée par l'intégration Vercel) |

Réglages notables de [config/settings.py](../config/settings.py) :

- **`conn_max_age=0`** : chaque requête ouvre puis ferme sa connexion, ce qui convient à des fonctions de courte durée.
- **`DISABLE_SERVER_SIDE_CURSORS`** (PostgreSQL uniquement) : le pooler de Neon, en mode transaction, ne gère pas les curseurs serveur de Django.
- **`TIME_ZONE = "UTC"`** : toutes les dates sont stockées en UTC. L'heure de Paris ne servira qu'aux règles de jeu.
- **Sécurité en production :** proxy HTTPS de Vercel reconnu (`SECURE_PROXY_SSL_HEADER`), cookies réservés au HTTPS et HSTS d'un an. Trois avertissements de `check --deploy` sont volontairement désactivés, avec leur justification dans le code :
    - la redirection HTTPS, déjà assurée par Vercel ;
    - HSTS sur les sous-domaines ;
    - la liste de préchargement HSTS.

## 4. Modèle de données

Ces tables contiennent des **données de référence statiques**, importées depuis PokéAPI. Elles décrivent ce qu'est une espèce, jamais ce qu'un joueur possède : les données de joueur arriveront dans d'autres apps à partir de l'étape 1.

```
Type ◀──── primary_type / secondary_type ──── Species ────▶ EvolutionChain
 ▲                                            │   ▲
 │                                            │   └── evolves_from (vers une autre Species)
 └──── type ──── Move ◀──── SpeciesMove ──────┘
```

| Modèle | Champs clés | Remarques |
| --- | --- | --- |
| `Type` | `slug` (`"fire"`), `name` | 18 types modernes. Ténèbres n'existe que par les attaques. Propriété `icon_url` |
| `EvolutionChain` | `pokeapi_id` | Une famille. Sert aux bonbons partagés |
| `Species` | `number`, `slug`, `name`, `genus`, `flavor_text`, 2 types, 6 stats, `height_dm`, `weight_hg`, `evolution_chain`, `evolution_stage`, `evolves_from`, `is_legendary` (Mew inclus) | Propriétés : `types`, `base_stat_total`, `height_m`, `weight_kg`, `sprite_url`, `shiny_sprite_url`, `cry_url` |
| `Move` | `slug`, `name`, `type`, `damage_class`, `power`, `accuracy`, `pp` | `power` et `accuracy` peuvent être vides (attaques de statut, attaques qui ne ratent jamais) |
| `SpeciesMove` | `species`, `move`, `learn_method` (`level-up` ou `machine`), `level` | Table d'association explicite. Contrainte d'unicité sur les 4 champs |

Choix de conception :

- **Deux clés étrangères pour les types** plutôt qu'une relation plusieurs-à-plusieurs : une espèce a au plus 2 types, et leur ordre compte.
- **Une colonne par stat** : ce sont exactement les 6 stats ciblées par les natures du concept.
- **Pas de champ pour les médias** : le chemin se déduit du numéro (`pokemon/sprites/25.png`) ou du slug (`pokemon/types/fire.png`).
- **Unités brutes de PokéAPI** (décimètres, hectogrammes), converties à l'affichage.
- **La famille sans l'évolution.** Les Pokémon n'évoluent pas dans ce jeu. On garde la chaîne, le stade (1 à 3) et la pré-évolution, qui serviront aux bonbons, à leur coût et aux conditions d'arrivée. Les champs décrivant le déclencheur d'évolution (niveau, objet, échange) ont été retirés : ils relèvent des fichiers de données par espèce de l'étape 1.
- **`on_delete`** : `PROTECT` pour les types et les chaînes (pas de suppression d'une ligne encore utilisée), `CASCADE` pour le learnset, `SET_NULL` pour `evolves_from`.

## 5. Import depuis PokéAPI

Commande : `uv run python manage.py import_pokeapi [--limit N] [--no-media]`.

### Les trois phases ([importer.py](../pokedex/pokeapi/importer.py))

1. **Récupération et analyse, sans toucher à la base.** Les ressources `pokemon`, `pokemon-species`, `evolution-chain`, `move` et `type` passent par le client, qui lit d'abord le cache disque. Des fonctions pures ([parsers.py](../pokedex/pokeapi/parsers.py)) les transforment en dictionnaires.
2. **Écriture dans une seule transaction** (`transaction.atomic`). Si une erreur survient, rien n'est enregistré.
    - Toutes les écritures passent par `update_or_create`, ce qui rend l'import idempotent.
    - `evolves_from` est rempli dans une seconde passe, une fois toutes les espèces créées.
    - Le learnset est remplacé en bloc (`bulk_create`), soit 5 017 lignes en une requête.
3. **Médias :** sprites Noir/Blanc (normal et shiny), cris d'origine (`legacy`) et icônes de types de Let's Go. Un fichier déjà présent n'est jamais retéléchargé.

### Règles d'interprétation

- **Stade d'évolution :** seules les espèces importées sont comptées. Pichu, ajouté en génération 2, est ignoré : Pikachu est donc au stade 1 et Raichu au stade 2. La même règle s'applique à Clefairy, Jigglypuff, Jynx, Electabuzz, Magmar et Hitmonlee.
- **Attaques :** uniquement celles de Rouge Feu/Vert Feuille, apprises par niveau ou par CT/CS. Les attaques par tuteur ou par œuf sont ignorées. La puissance et le type des attaques viennent des données modernes.
- **Descriptions :** version Rouge Feu, à défaut Vert Feuille. Les retours à la ligne sont aplatis et « POKéMON » devient « Pokémon ».

### Chiffres

151 espèces, 18 types, 302 attaques, 5 017 entrées de learnset, 471 médias (2,1 Mo). Le premier import prend environ 2 minutes ; avec le cache, une relance prend environ 1 seconde.

## 6. Interface

### La page Pokédex

- **Panneau gauche** (1/3) : recherche par nom, filtre par type (limité aux 17 types portés par au moins une espèce), case « Silhouettes » et liste des espèces avec leurs icônes de types.
- **Panneau droit** (2/3) : la fiche. Elle comprend le sprite, le genre, les types, la taille et le poids, le cri, la description, les stats, la famille et les attaques par niveau et par CT/CS.

### Le modèle HTMX

| Action | Requête | Réponse |
| --- | --- | --- |
| Ouvrir `/pokedex/25/` directement | GET normal | Page complète |
| Cliquer sur une espèce | GET avec `HX-Request: true` | Fragment `_entry.html` inséré dans `#entry`, URL mise à jour (`hx-push-url`) |
| Taper dans la recherche, changer de type | GET `/pokedex/list/` | Fragment `_species_list.html` inséré dans `#species-list` |
| Bouton Précédent sans cache HTMX | GET avec `HX-History-Restore-Request` | Page complète |

Principes appliqués :

- **Amélioration progressive :** chaque lien a un vrai `href`, donc tout fonctionne sans JavaScript.
- **JavaScript minimal :** `pokedex.js`, une vingtaine de lignes, ne fait que synchroniser la surbrillance de la liste après une navigation HTMX.
- **Silhouettes en CSS pur :** une case à cocher, le variant Tailwind `group-has-[#silhouettes:checked]` et le filtre `brightness(0)`.
- **Peu de requêtes SQL :** la page complète en fait 5 et la fiche seule 3, grâce à `select_related` et `prefetch_related`.

### Tailwind

- La source est [assets/css/input.css](../assets/css/input.css). On y trouve :
    - les couleurs du jeu et des types, déclarées dans `@theme` ;
    - le variant `portrait-phone:`, qui affiche le message invitant à tourner le téléphone ;
    - l'utilitaire `pixelated`, qui garde le pixel art net ;
    - les composants `.tab` et `.type-badge`.
- **Le scan est limité aux templates** (`source(none)` et `@source`) : un scan automatique du projet prenait des mots du Python pour des classes.
- **Les classes dynamiques** `bg-type-{{ slug }}` sont déclarées explicitement avec `@source inline(...)`, faute de quoi Tailwind ne les génère pas.
- **La compilation** passe par `scripts/build_css.py`, avec la version figée (v4.3.3) et un résultat toujours minifié, y compris en `--watch`. Le binaire est fourni par pytailwindcss, sans Node.js.

## 7. Tests et qualité

**35 tests**, exécutés en environ 0,3 seconde, sans réseau :

| Fichier | Ce qui est testé |
| --- | --- |
| `test_smoke.py` | Redirection de l'accueil, présence de la mention légale |
| `test_models.py` | Valeurs calculées, contrainte d'unicité du learnset |
| `test_pokeapi.py` | Parsers, cache du client (`httpx.MockTransport`), import complet avec un faux client : famille, idempotence, médias |
| `test_views.py` | Page complète ou fragment selon les en-têtes HTMX, 404, filtres, surbrillance, types du filtre, absence de commentaires de template dans la page |

Les fixtures partagées (types, Bulbasaur, Ivysaur, Charmander) sont dans `tests/conftest.py`.

**L'intégration continue** ([ci.yml](../.github/workflows/ci.yml)) s'exécute à chaque push. Elle enchaîne : `ruff format --check`, `ruff check`, `manage.py check`, `makemigrations --check`, `pytest`, puis la recompilation du CSS suivie de `git diff --exit-code`. L'action `setup-uv` est figée par l'empreinte de son commit.

## 8. Déploiement

Vercel prend Django en charge sans configuration :
- il repère `manage.py` et utilise `WSGI_APPLICATION` comme point d'entrée ;
- il lance `collectstatic`, car `STATIC_ROOT` est défini.

| Élément | Où |
| --- | --- |
| Migrations à chaque build | `[tool.vercel.scripts] build` dans `pyproject.toml` |
| Région des fonctions | `vercel.json` (`fra1`) |
| Base de données | Neon (Francfort), créée depuis l'onglet Storage de Vercel |
| Domaine | `pokechill.bradsavary.dev`, géré par Vercel, certificat Let's Encrypt automatique |

### Procédures courantes

- **Déployer :** `git push` sur `main`. Vercel construit et déploie, et la CI tourne en parallèle.
- **Importer ou mettre à jour les données en production :** depuis le poste local, dans PowerShell, avec l'URL **sans pooler** de Neon.
  ```
  $env:DATABASE_URL = "postgresql://...(URL sans pooler)..."
  uv run python manage.py import_pokeapi --no-media
  Remove-Item Env:DATABASE_URL
  ```
  La dernière ligne est importante : tant que la variable existe, toutes les commandes Django du terminal agissent sur la production.
- **Créer un administrateur en production :** même principe, avec `createsuperuser`.
- **Après une modification d'une variable d'environnement sur Vercel :** redéployer, car les variables ne sont lues qu'au build.

### Performances observées

- Environ 0,2 à 0,3 s par page une fois la fonction chaude.
- Environ 1,2 à 1,4 s après une période sans visite : c'est le démarrage à froid du serverless.

## 9. Pièges rencontrés

| Problème | Cause | Solution retenue |
| --- | --- | --- |
| Des commentaires s'affichaient dans la page | `{# … #}` ne fonctionne que sur une seule ligne en Django | `{% comment %}` pour les commentaires multi-lignes, plus un test de non-régression |
| CSS commité non minifié, à deux reprises | Un `--watch` lancé avec l'ancienne version du script | Minification aussi en `--watch`, plus un contrôle CSS dans la CI |
| Version de Tailwind pas réellement figée | `pytailwindcss.run()` sans paramètre `version` utilise « latest » | `run(..., version=..., auto_install=True)` |
| Erreurs fantômes dans VS Code | Analyse périmée de Pylance après une modification du fichier depuis le terminal | « Python: Restart Language Server » |
| Grand sprite noirci en entier en mode silhouette | Le filtre s'appliquait aussi au fond de l'image | Fond déplacé sur un conteneur |
| Index SQL inutile | `SlugField` est indexé par défaut | `db_index=False` sur un champ jamais recherché (champ retiré depuis) |
| Mesure de requêtes à 0 dans le shell | Le client de test utilise l'hôte `testserver`, refusé par `ALLOWED_HOSTS` | `Client(SERVER_NAME="localhost")` |

## 10. Points ouverts pour l'étape 1

- **Fichiers de données par espèce :** conditions d'arrivée, défis, rareté et niveau minimal. Le niveau minimal et les conditions inspirées des évolutions pourront être pré-remplis à partir du cache PokéAPI.
- **Moteur de jeu en Python pur :** créer le module indépendant de Django (conditions, rattrapage horaire avec graine aléatoire).
- **API du jeu :** choisir entre Django REST Framework et Django Ninja. La recommandation est Ninja.
- **Comptes :** mode invité, puis conversion en compte, avec l'authentification de Django.
- **Interface du Pokédex :** réorganisation prévue (trop d'informations, mise en page à revoir), reportée volontairement.
