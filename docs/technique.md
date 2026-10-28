# PokéChill — Synthèse technique

État du projet à la fin de l'**étape 2 (les zones et la mangeoire)**, au 28 octobre 2026. Ce document décrit ce qui est construit, comment les pièces s'articulent et pourquoi elles ont été conçues ainsi. Il est mis à jour à chaque étape. Pour le gameplay, voir [concept.md](concept.md).

- **Production :** https://pokechill.bradsavary.dev
- **Dépôt :** https://github.com/BradSavary/pokechill
- **Contenu jouable :**
    - on joue sans compte (invité), puis on sauvegarde sa partie en créant un compte ;
    - chaque heure, un Pokémon arrive à la Pension. On le découvre à son retour dans une fenêtre de révélation, et les doublons rapportent des bonbons ;
    - le Pokédex personnel montre les espèces possédées et des silhouettes pour les autres ;
    - les Pokémon travaillent dans deux zones (Prairie, Verger) : ils récoltent une ressource et gagnent de l'expérience, même hors ligne ;
    - les ressources vont dans la mangeoire, qui attire les types de leur zone ;
    - 55 espèces (#001 à #055), dont certaines n'arrivent qu'à certaines conditions (posséder leur forme précédente, une ressource dans la mangeoire, une zone occupée) ;
    - un tutoriel présente la Pension, le Pokédex, les zones et la mangeoire, avec un Pikachu et 10 baies offerts.

## 1. Vue d'ensemble

| Couche | Technologie | Rôle |
| --- | --- | --- |
| Langage et outillage | Python 3.13, uv | Version de Python, environnement virtuel, dépendances figées dans `uv.lock` |
| Moteur de jeu | Python pur (package `game/`) | Règles du jeu, sans Django ni base de données |
| Framework | Django 5.2 LTS | URLs, vues, modèles, templates, admin, comptes, commandes |
| Interface | Templates Django, HTMX 2.0.4, Tailwind CSS v4.3.3 | Pages rendues côté serveur, mises à jour partielles sans framework JavaScript |
| Base de données | SQLite (local), PostgreSQL Neon (production) | Choisie par la variable `DATABASE_URL` |
| Hébergement | Vercel, région `fra1` (Francfort) | Une fonction serverless Python, fichiers statiques sur le CDN |
| Qualité | Ruff, pytest, GitHub Actions | Formatage, lint, 263 tests, intégration continue |

### Les trois couches

```
┌───────────────────────────────────────────────────────────┐
│ Interface : templates, HTMX, Tailwind (style Épée/Bouclier)│
├───────────────────────────────────────────────────────────┤
│ Couche Django                                             │
│   pokedex  : catalogue (espèces, types, attaques)         │
│   accounts : invité, inscription, connexion               │
│   ranch    : partie du joueur (collection, Accueil,       │
│              zones, mangeoire, tutoriel)                  │
├───────────────────────────────────────────────────────────┤
│ Moteur pur game/ : horloge, conditions, arrivées,         │
│                    obtention, attaques, expérience,       │
│                    zones, équilibrage                     │
└───────────────────────────────────────────────────────────┘
```

Les dépendances vont toujours vers le bas, jamais dans l'autre sens :
- `game/` ne connaît pas Django. Un test d'architecture fait échouer la CI si un fichier de `game/` importe Django ;
- les **modèles** de `pokedex` ne dépendent pas de `ranch` : pas de dépendance circulaire ;
- `accounts` ne dépend pas de `ranch` : c'est `ranch` qui demande à `accounts` de créer un invité ;
- seules les **vues** combinent les apps. Par exemple, la vue du Pokédex lit la collection du joueur dans `ranch`.

Une vue suit toujours le même schéma : elle charge l'état depuis la base, appelle une fonction pure de `game/`, puis enregistre le résultat. Toutes les règles de jeu se testent donc en quelques millisecondes, sans base de données.

## 2. Arborescence

```
game/                    Moteur de jeu en Python pur (aucun import Django)
  balance.py             Toutes les valeurs d'équilibrage
  clock.py               Créneaux horaires, jour/nuit à Paris, graine par heure
  conditions.py          Arbres de conditions ET/OU/NON et leur validation
  arrivals.py            Espèces éligibles, tirage pondéré, rattrapage
  collection.py          Ce que rapporte une capture (nouvelle espèce ou doublon)
  moves.py               Les 4 attaques connues à un niveau donné
  experience.py          Courbes d'expérience des jeux, montée de niveau
  zones.py               Les zones, leur production et l'expérience gagnée
config/                  Projet Django : réglages (lus dans l'environnement), URLs racines
pokedex/                 Catalogue : modèles, vues du Pokédex, admin
  pokeapi/               Import PokéAPI : client avec cache, parsers, importeur
  species_files.py       Lecture et validation des fichiers d'espèces
  management/commands/   import_pokeapi, load_species
accounts/                Invité, inscription (conversion), connexion (pas de modèle)
ranch/                   Partie du joueur
  models.py              Player, OwnedPokemon, CandyStock, Arrival, PlayerZone, ResourceStock
  services.py            Rattrapage, obtention, révélation, purge des invités
  zones.py               Travail des zones, récolte, statut du Pokémon, mangeoire
  zone_views.py          Pages Zones (cartes, carte d'une zone, affectation)
  zone_maps.py           Emplacements des Pokémon sur la carte de chaque zone
  tutorial.py            Étapes du tutoriel et cadeaux
  decorators.py          @player_required (invité automatique + rattrapage)
  management/commands/   purge_guests, players, rewind_clock, reset_player
data/species/            Un fichier JSON par espèce disponible (55 : #001 à #055)
templates/               base.html, _menu_item.html, icons/ (SVG Tabler, MIT)
assets/css/input.css     Source Tailwind (non servie)
static/                  CSS compilé, HTMX, JS, polices, sprites, cris, icônes, bonbons
scripts/                 build_css.py (Tailwind), vercel_build.py (build de production),
                         mapkit.py, build_ranch_map.py, build_zone_maps.py (cartes en tuiles)
assets/map/sources/      Planches de tuiles d'origine (FRLG, RSE) découpées par les scripts de cartes
tests/                   263 tests pytest
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
- **`TIME_ZONE = "UTC"`** : toutes les dates sont stockées en UTC. L'heure de Paris ne sert qu'au jour et à la nuit.
- **`SESSION_COOKIE_AGE` = 1 an** : pour un invité, le cookie de session est la seule clé de sa partie.
- **Sécurité en production :** proxy HTTPS de Vercel reconnu (`SECURE_PROXY_SSL_HEADER`), cookies réservés au HTTPS, HSTS d'un an. Trois avertissements de `check --deploy` sont volontairement désactivés, avec leur justification dans le code.

## 4. Le moteur de jeu (`game/`)

Le moteur ne reçoit que des valeurs simples (des dates, des règles d'espèces) et rend des résultats (des arrivées, une issue de capture). Il ne lit et n'écrit jamais rien en base.

| Module | Rôle | Point clé |
| --- | --- | --- |
| [clock.py](../game/clock.py) | Créneaux horaires en UTC, jour ou nuit selon l'heure de Paris | `slot_rng(joueur, heure)` : un générateur aléatoire dont la graine est un SHA-256 du joueur et de l'heure |
| [conditions.py](../game/conditions.py) | Évalue et valide les arbres de conditions | Un **registre de feuilles** : ajouter un type de condition revient à ajouter une entrée |
| [arrivals.py](../game/arrivals.py) | Espèces éligibles, tirage pondéré par la rareté, attrait de la mangeoire, nature, shiny, rattrapage | Les candidats sont triés avant le tirage : l'ordre de la liste reçue n'influe pas |
| [collection.py](../game/collection.py) | Ce que rapporte une capture | Une nouvelle espèce est ajoutée ; un doublon donne des bonbons, une nature et un shiny éventuels |
| [moves.py](../game/moves.py) | Les 4 attaques connues à un niveau | Comme dans les jeux : les 4 dernières apprises par niveau |
| [experience.py](../game/experience.py) | Courbes d'expérience (rapide, moyenne, parabolique, lente) et montée de niveau | Les formules des jeux ; la progression est gardée « depuis le niveau actuel » |
| [zones.py](../game/zones.py) | Les zones, leurs types, leur ressource, la production et l'expérience par heure | Le travail d'une période se calcule d'un coup (voir la section 9) |
| [balance.py](../game/balance.py) | Toutes les valeurs d'équilibrage | Voir le tableau ci-dessous |

**Le déterminisme est la propriété centrale.** Une même heure donne toujours le même Pokémon, la même nature et le même shiny, quel que soit le moment du calcul. Un test vérifie que rattraper 10 heures d'un coup donne exactement les mêmes arrivées que rattraper 4 heures, puis 6.

### Valeurs d'équilibrage

| Valeur | Réglage |
| --- | --- |
| Poids de rareté | commune 100, peu commune 50, rare 20, très rare 5, légendaire 1 (Mew compte comme légendaire) |
| Places de l'Accueil | 8 au départ (`WELCOME_CAPACITY_BASE`), augmentées plus tard par l'arbre de compétences |
| Shiny | 1/1024 (1/512 avec le Charme Chroma, à l'étape 5) |
| Bonbons par doublon | 3 / 5 / 10 / 20 / 50 selon la rareté |
| Nuit (heure de Paris) | 21 h – 6 h |
| Starters | Bulbasaur, Charmander, Squirtle ; cadeaux du tutoriel : Pikachu, puis 10 baies |
| Zones | 2 au départ (Prairie, Verger), 3 Pokémon chacune, 8 heures de travail entre deux récoltes |
| Production | 1 ressource par heure (100 centièmes), +1 % par niveau ; 25 % hors des types de la zone |
| Expérience en zone | 20 + 3 par niveau, par heure ; +25 % dans une zone de son type |
| Mangeoire | 1 emplacement ; +1 point de chance par unité, 50 unités au plus par emplacement |

## 5. Modèle de données

```
pokedex (catalogue, identique pour tous)       ranch (partie du joueur)
Type ◀── Species ──▶ EvolutionChain ◀──────── CandyStock (bonbons par lignée)
           ▲  │                                  │
           │  └── SpeciesMove ──▶ Move           │
           │                                     ▼
           ├──────────────── OwnedPokemon ──▶ Player ◀── Arrival (Accueil)
           │                                     │
           └──────────────────── Arrival         └──▶ User (Django)
```

| Modèle | App | Champs clés | Remarques |
| --- | --- | --- | --- |
| `Type` | pokedex | `slug`, `name` | 18 types modernes. Propriété `icon_url` |
| `EvolutionChain` | pokedex | `pokeapi_id` | Une famille. Propriétés `base_species` et `candy_url` |
| `Species` | pokedex | Données PokéAPI (numéro, nom, types, stats, famille, `is_legendary`, `growth_rate`) et **données de jeu** (`is_available`, `rarity`, `min_level`, `arrival_conditions` en JSON) | `to_rule()` la convertit pour le moteur. Propriété `icon_url` (icône de la 7e génération) |
| `Move`, `SpeciesMove` | pokedex | Attaques, et comment une espèce les apprend (Rouge Feu/Vert Feuille) | Contrainte d'unicité sur l'entrée de learnset |
| `Player` | ranch | `user` (un-à-un), `last_slot`, `last_seen_at`, `tutorial_step`, `feeder` (JSON) | `last_slot` est la dernière heure rattrapée. Propriétés `welcome_capacity`, `feeder_capacity` |
| `OwnedPokemon` | ranch | `player`, `species`, `level`, `experience`, `pending_experience`, `unlocked_natures` (JSON), `shiny_unlocked`, `status`, `zone`, `spot` | **Un seul par espèce**, garanti par une contrainte en base. Un statut à la fois (libre ou en zone) |
| `PlayerZone` | ranch | `player`, `zone` (slug), `hours_worked`, `stock_centi`, `collected_at` | Une zone débloquée et ce qu'elle a produit depuis la dernière récolte |
| `ResourceStock` | ranch | `player`, `resource`, `amount` | Un stock par ressource, comme les bonbons |
| `CandyStock` | ranch | `player`, `family`, `amount` | Un stock par lignée |
| `Arrival` | ranch | `player`, `species`, `slot`, `nature`, `is_shiny` | Un Pokémon qui attend à l'Accueil. **Une seule arrivée par heure**, garantie en base |

Choix de conception :
- **`User` et `Player` sont séparés.** `User` (Django) porte l'identité, et `Player` l'état de jeu. Modifier le `User` en cours de projet est délicat, et un compte peut exister sans partie, comme celui de l'administrateur.
- **Les natures et le shiny sont enregistrés dès l'étape 1**, mais leurs effets (bonus de stats, apparence) arrivent à l'étape 5.
- **Le stade de recherche 1 se déduit** de l'existence d'un `OwnedPokemon` : pas de champ supplémentaire.
- **Le statut du Pokémon est garanti en base.** Une `CheckConstraint` impose qu'un Pokémon en zone ait une zone et un emplacement, et qu'un Pokémon libre n'en ait aucun. Une contrainte d'unicité interdit deux Pokémon au même emplacement. Tout changement passe par `move_pokemon`, dans une transaction.
- **Les ressources sont comptées en centièmes** (`stock_centi`) : 3 Pokémon hors type produisent 0,75 par heure, et des entiers gardent les sommes exactes, là où des nombres à virgule accumuleraient des erreurs d'arrondi.
- **L'expérience est gardée « depuis le niveau actuel »** (`experience`), plus l'expérience gagnée en zone mais pas encore récoltée (`pending_experience`). Changer la courbe d'une espèce ne casse donc rien.
- **La mangeoire est une liste** `[[ressource, unités], ...]`, dans l'ordre où elle sera mangée. Un dictionnaire ne convenait pas : `jsonb` (PostgreSQL) ne garde pas l'ordre des clés.

## 6. Les données d'espèces

Chaque espèce disponible a un fichier dans [data/species/](../data/species/) :

```json
{
  "species": "pikachu",
  "rarity": "rare",
  "min_level": 1,
  "conditions": {"time_of_day": "day"},
  "notes": "Also given at the end of the tutorial."
}
```

- **La validation est stricte** ([species_files.py](../pokedex/species_files.py)). Une clé inconnue est refusée, ce qui attrape les fautes de frappe comme `rarety`. Une rareté inconnue, un niveau hors de 1 à 100 ou un arbre de conditions invalide le sont aussi. **Toutes les erreurs sont listées d'un coup**, avec le nom de leur fichier.
- **La commande `load_species` est tout ou rien**, dans une transaction. Une espèce dont le fichier est supprimé repasse en « non disponible ».
- **Un test valide les vrais fichiers du dépôt** : une erreur dans un JSON fait échouer la CI.
- **En production**, `load_species` tourne **à chaque déploiement** ([scripts/vercel_build.py](../scripts/vercel_build.py)). Les fichiers du dépôt font foi.
- Règle retenue pour les **évolutions par pierre** (Raichu, Nidoqueen, Ninetales...) : le niveau d'arrivée vaut le niveau minimal de la forme précédente plus 15.
- **Une forme évoluée demande de posséder sa forme précédente** (`owns`) : le Pokédex se remplit dans l'ordre des lignées. Un test vérifie que toute espèce citée dans une condition a son propre fichier, sans quoi la condition ne pourrait jamais être remplie.

Les conditions disponibles (les feuilles de l'arbre, déclarées dans le registre `LEAVES` de [conditions.py](../game/conditions.py)) :

| Feuille | Exemple | Vraie si... |
| --- | --- | --- |
| `time_of_day` | `{"time_of_day": "night"}` | il fait nuit à Paris (21 h – 6 h) |
| `feeder` | `{"feeder": "berry"}` | un emplacement de la mangeoire contient cette ressource |
| `owns` | `{"owns": "nidoran-f"}` | le joueur possède cette espèce |
| `zone_occupied` | `{"zone_occupied": "orchard"}` | au moins un Pokémon travaille dans cette zone |
| `works_in` | `{"works_in": {"species": "paras", "zone": "orchard"}}` | cette espèce travaille dans cette zone |

Une condition peut déjà citer une zone ou une ressource **prévue** par le concept mais pas encore construite (`PLANNED_ZONES` dans [zones.py](../game/zones.py) : `pond`, `quarry`, `volcano`, `power-plant`, `swamp`, `tower`, et leurs ressources). Elle est valide, mais jamais remplie avant l'arrivée de la zone. Blastoise attend ainsi un Squirtle à l'Étang, et Meowth des perles, du minerai ou de la poussière mystique.

Elles se combinent avec `all` (ET), `any` (OU) et `not`. Par exemple, Parasect : `{"all": [{"time_of_day": "night"}, {"works_in": {"species": "paras", "zone": "orchard"}}]}`.

## 7. Joueurs et comptes

- **Un invité est un `User` sans mot de passe utilisable** (`set_unusable_password`). Il n'a besoin d'aucun champ ni modèle supplémentaire, et personne ne peut se connecter à sa place.
- **`@player_required`** protège les pages de jeu. Il crée un invité à la première visite, crée sa partie avec les 3 starters, enregistre la visite, puis lance le rattrapage. Le Pokédex n'en a pas besoin : les robots d'indexation qui le parcourent ne créent donc aucun compte.
- **Créer un compte convertit l'invité** : le `UserCreationForm` de Django reçoit l'utilisateur existant (`instance=`), qui garde son identifiant et toute sa partie. `update_session_auth_hash` le garde connecté après le changement de mot de passe.
- **La connexion et la déconnexion** utilisent les vues de Django. La déconnexion se fait uniquement en POST, et un invité n'a pas de bouton de déconnexion, qui lui ferait perdre sa partie.
- **`purge_guests`** supprime les invités inactifs depuis 180 jours, avec leur partie. Un compte inscrit n'est jamais supprimé. La commande se lance à la main pour l'instant, et son automatisation par un Cron Vercel est prévue.

## 8. Les arrivées : rattrapage et révélation

```
Visite d'une page de jeu
  └─▶ catch_up_player(player)                              [transaction]
        ├─ verrouille le joueur (select_for_update)
        ├─ places libres = capacité de l'Accueil − arrivées en attente
        ├─ game.arrivals.catch_up(...)   ← rejoue chaque heure depuis last_slot,
        │                                  avec la mangeoire, la collection et qui travaille où
        ├─ bulk_create des Arrival       ← contrainte (joueur, heure) unique
        ├─ mangeoire = emplacements restants (chaque arrivée a mangé le premier)
        ├─ work_zones(player)            ← travail des zones depuis la dernière visite
        └─ last_slot = heure actuelle    (même si l'Accueil était plein)

Clic sur « Reveal » / « Next » / « Skip » (POST, HTMX)
  ├─▶ reveal_next / reveal_all                             [transaction]
  │     └─ receive_pokemon()  ← unique porte d'entrée pour obtenir un Pokémon
  │           └─ game.collection.resolve_obtention()
  └─▶ la série en cours est notée dans la session (remember)
        └─ fin de série à plusieurs → compte rendu (end_series)
```

- **Deux protections contre les visites simultanées**, par exemple deux onglets ouverts : le verrou sur le joueur, puis la contrainte d'unicité en dernier recours. SQLite ignore `select_for_update`, donc en local seule la contrainte joue.
- **L'Accueil plein arrête le rattrapage.** Le moteur compte alors les heures perdues (`hours_while_full`), que le résumé d'absence affiche.
- **La révélation** se fait une par une, présentée comme une fiche du Pokédex : sur la scène rouge, la Ball (sprite d'objet de PokéAPI) tremble puis disparaît dans un flash, le Pokémon apparaît devant des rayons de la couleur de sa rareté, et son cri est joué. Les détails (types, nature, bonbons) n'apparaissent qu'à ce moment, pour ne rien dévoiler avant.
- **La Ball annonce la rareté** avant la révélation : Poké Ball (commune), Super Ball (peu commune), Hyper Ball (rare), Mémoire Ball (très rare, la Ball des Pokémon d'événement dans les jeux) et Master Ball (légendaire). La correspondance est dans [ranch_extras.py](../ranch/templatetags/ranch_extras.py) ; la page ne reçoit que les raretés des arrivées, jamais leurs espèces.
- **Le compte rendu** termine toute série de plus d'un Pokémon, et « Skip » y mène directement. Chaque révélation étant une requête séparée, la série en cours est gardée dans la session Django (identifiants et valeurs simples, la session étant enregistrée en JSON), puis oubliée quand le compte rendu s'affiche. Elle survit ainsi à un rechargement de page entre deux révélations.
- **Verrou et PostgreSQL** : la révélation charge les types de l'espèce dans la même requête que l'arrivée verrouillée. Le type secondaire étant facultatif, cette jointure est externe, et PostgreSQL refuse `FOR UPDATE` sur son côté nullable : le verrou se limite donc aux arrivées (`select_for_update(of=("self",))`).
- Les actions qui modifient l'état n'acceptent que POST, et HTMX envoie le jeton CSRF sur toutes ses requêtes (`hx-headers` sur `<body>`).
- **Le tutoriel** ([tutorial.py](../ranch/tutorial.py)) a 6 étapes : la Pension et l'Accueil, le Pokédex, le cadeau (Pikachu), les zones, puis la mangeoire. Une étape peut s'afficher sur plusieurs pages (celle des zones va de la Pension à l'onglet Zones, puis à la carte d'une zone). Les premières se terminent par un bouton, qui envoie le numéro de l'étape qu'il termine : un double clic ne peut pas en sauter une. Les autres se terminent quand le joueur fait ce qu'elles demandent : révéler le cadeau, placer un Pokémon dans une zone (10 baies offertes), remplir la mangeoire. Les cadeaux ne sont donnés qu'une fois, sous verrou.
- **Les nouvelles étapes s'ajoutent toujours à la fin**, juste avant `DONE`, dont le numéro augmente. Un joueur qui avait fini le tutoriel se retrouve alors sur la première nouvelle étape et découvre les nouveautés à sa visite suivante, sans migration. C'est ainsi que les joueurs de l'étape 1 découvrent les zones.

## 9. Les zones et la mangeoire

```
Ouverture d'une zone (clic sur sa carte, POST)
  └─▶ collect(zone)                                        [transaction]
        ├─ work_zones : travail depuis le dernier calcul (au plus 8 h entre deux récoltes)
        ├─ ressources entières → ResourceStock (les centièmes restent pour la fois suivante)
        ├─ expérience en attente → montée de niveau (courbe de l'espèce)
        └─ compteur d'heures remis à zéro : les Pokémon reprennent le travail

Affectation (« + » sur la carte, puis choix du Pokémon)
  └─▶ move_pokemon(pokemon, zone, spot)                    [transaction]
        ├─ récolte d'abord la zone quittée et la zone rejointe (rien n'est perdu)
        └─ change le statut et l'emplacement (contraintes en base)
```

- **Le travail d'une zone se calcule d'un coup.** Pendant l'absence du joueur, rien ne change dans une zone (mêmes Pokémon, mêmes niveaux : l'expérience n'est appliquée qu'à la récolte). Le travail de 30 heures vaut donc `min(30, 8 − heures déjà faites) × production horaire`, sans rejouer les heures une à une. Le plafond de 8 heures joue le même rôle que l'Accueil : il donne une raison de revenir sans punir une absence.
- **Production** : 1 ressource par heure et par Pokémon, +1 % par niveau ; un Pokémon dont aucun type ne correspond à la zone travaille à 25 %. **Expérience** : 20 + 3 par niveau, par heure, avec 25 % de plus dans une zone de son type. Les courbes d'expérience sont celles des jeux, importées de PokéAPI (`growth_rate`).
- **Les emplacements** : chaque zone a ses emplacements sur sa carte ([zone_maps.py](../ranch/zone_maps.py), en tuiles). Le Pokémon garde le sien (`spot`) quand d'autres arrivent ou partent.
- **La mangeoire** est une liste d'emplacements. Chacun contient une seule ressource, de 1 à 50 unités. Le Pokémon qui arrive mange tout le premier emplacement, et lui seul en profite :
  1. le moteur calcule la part habituelle des espèces attirées, c'est-à-dire celles qui ont un type de la zone de la ressource (par exemple 30 %) ;
  2. il y ajoute 1 point par unité (13 noigrumes : 43 %), puis tire « attirée ou non » ;
  3. il tire l'espèce dans le groupe retenu, pondérée par sa rareté.

  S'il n'existe aucune espèce attirée éligible, ou aucune autre, le tirage est normal. Rien n'est mangé quand personne n'arrive (Accueil plein). Le moteur rejoue les heures dans l'ordre : c'est ce qui permet de savoir quelle arrivée a mangé quel emplacement, et le résultat reste identique quel que soit le moment du calcul.
- **Reprendre un emplacement** rend ses unités au stock. Le stock est débité par un `UPDATE` conditionnel (`amount >= unités`) : deux requêtes simultanées ne peuvent pas dépenser deux fois les mêmes baies.

## 10. Import depuis PokéAPI

Commande : `uv run python manage.py import_pokeapi [--limit N] [--no-media]`.

1. **Récupération et analyse, sans toucher à la base.** Le client lit d'abord le cache disque, et des fonctions pures transforment le JSON.
2. **Écriture dans une seule transaction**, avec `update_or_create` (l'import est idempotent) et `bulk_create` pour les 5 017 entrées de learnset.
3. **Médias :** sprites Noir/Blanc (normaux et shiny), cris d'origine, icônes de types et **bonbons par lignée** (objets de *Let's Go*). Un fichier présent n'est jamais retéléchargé.

Règles : seules les espèces importées comptent pour les stades d'évolution (Pikachu est au stade 1, Pichu étant ignoré). Les attaques viennent de Rouge Feu/Vert Feuille (par niveau ou CT/CS). Les espèces fabuleuses comptent comme légendaires.

Chiffres : 151 espèces, 18 types, 302 attaques, 5 017 entrées de learnset, environ 550 médias (2,3 Mo).

## 11. Interface

### Le style

Le style s'inspire des menus de **Pokémon Épée/Bouclier**, avec des polices pixel en clin d'œil aux anciens jeux :
- un fond rouge coupé en diagonale, des panneaux blancs arrondis ;
- des **bandeaux de titre en biais** (`.title-band`, `.section-title`) ;
- des **étiquettes de type** sombres avec l'icône du type (`.type-label`) ;
- des boutons et des champs en pilule.

**La police « PokeChill »** combine Pixelify Sans pour les lettres et Micro 5 pour les chiffres. Les deux sont libres (OFL) et hébergées dans `static/fonts/`. Le navigateur choisit le fichier caractère par caractère grâce à `unicode-range`, et `size-adjust` aligne les tailles. Sur les écrans de plus de 1 536 px, la taille de base passe à 125 %.

**Le menu latéral** se compose de disques blancs portant des icônes plates colorées (Tabler, MIT). Les icônes sont des SVG inclus directement dans la page, avec un trait épaissi et colorés en CSS (`currentColor`). Le nom de chaque onglet s'affiche au survol, et un texte invisible le garde lisible pour les lecteurs d'écran.

### Le Pokédex

- **Une espèce possédée** est affichée sur une scène rouge en diagonale, avec son numéro, son nom, ses types, le cri, un encadré joueur (stade, niveau, bonbons avec l'icône de la lignée, natures), la description, les stats et ses **4 attaques actuelles**.
- **Une espèce inconnue** apparaît en **silhouette noire** avec « ??? ». Si elle n'est pas encore dans le jeu, elle est grisée.
- **La recherche par nom** ne trouve que les espèces possédées : elle ne révèle rien.
- **Un visiteur sans partie** voit le catalogue complet.
- **Le modèle HTMX** : la même vue renvoie la page complète ou un fragment, selon l'en-tête `HX-Request` (en tenant compte de `HX-History-Restore-Request`). Chaque lien reste un vrai lien `href`, donc tout fonctionne sans JavaScript. La page complète fait 5 requêtes SQL.

### La Pension et les zones

- **Les cartes** sont dessinées en tuiles de 16 px par des scripts Python ([build_ranch_map.py](../scripts/build_ranch_map.py), [build_zone_maps.py](../scripts/build_zone_maps.py), outillage commun dans [mapkit.py](../scripts/mapkit.py)). Les tuiles sont découpées dans des rendus de cartes de Rouge Feu/Vert Feuille, puis recolorées avec la palette d'Or HeartGold/Argent SoulSilver. Le résultat est une simple image PNG commitée.
- **La carte couvre la page** comme un papier peint (`.map-view`, `.map-stage`, unités `cqw`/`cqh`) : elle garde ses proportions et ses bords de sapins sont rognés selon l'écran. Les points cliquables (la porte, la mangeoire, les emplacements) sont placés en pourcentages de la grille de 40 × 23 tuiles, donc toujours sur leur tuile.
- **La page Zones** montre une carte par zone : un bandeau (un extrait de son paysage) avec ses Pokémon, ses types, son stock et sa jauge de travail. Un clic la récolte et ouvre sa carte.
- **Le choix d'un Pokémon** se fait dans un tableau triable (nom, niveau, production par heure), trié par défaut du meilleur au moins bon.
- **Les bulles « i »** (`templates/_info_tip.html`) expliquent une règle au survol, ou au toucher sur mobile. Elles sont placées en `position: fixed` par JavaScript, pour ne jamais faire défiler la fenêtre qui les contient.
- **Les fenêtres** sont des `<dialog>` natifs : `data-open` les ouvre, `data-close` les ferme, et un clic sur le fond (hors du panneau) aussi ([app.js](../static/js/app.js)).

### Tailwind

- La source est [assets/css/input.css](../assets/css/input.css) : les couleurs dans `@theme`, les composants, les animations de la révélation, les variants `portrait-phone:` et `phone:` (téléphone tenu en paysage, repéré à sa faible hauteur) et l'utilitaire `pixelated`.
- Le scan est limité aux templates `.html` et `.svg` (`source(none)` et `@source`).
- La compilation passe par `scripts/build_css.py`, avec la version figée (v4.3.3) et un résultat toujours minifié.
- **Versionnement** : la balise `{% asset %}` ([config/assets.py](../config/assets.py)) ajoute `?v=<date de modification>` aux URL du CSS et des scripts. Sans elle, un navigateur peut garder l'ancien `main.css` en cache après une recompilation : les nouveaux templates s'affichent alors avec d'anciennes classes. En production, Vercel fait déjà revalider chaque fichier (`max-age=0, must-revalidate`) ; le problème touchait surtout le serveur de développement, qui n'envoie aucun en-tête de cache.

## 12. Tests et qualité

**263 tests**, exécutés en environ 4 secondes, sans réseau :

| Domaine | Fichiers | Tests |
| --- | --- | --- |
| Moteur pur | `test_game_clock`, `test_game_conditions`, `test_game_arrivals`, `test_game_collection`, `test_game_moves`, `test_game_experience`, `test_game_zones` | 88 |
| Catalogue et import | `test_models`, `test_pokeapi`, `test_species_files`, `test_views` | 53 |
| Joueurs | `test_accounts`, `test_purge_guests`, `test_collection`, `test_player_pokedex` | 30 |
| Arrivées | `test_catch_up`, `test_reveal`, `test_tutorial` | 40 |
| Zones et mangeoire | `test_zones`, `test_zone_views`, `test_feeder_views` | 42 |
| Outillage | `test_smoke`, `test_dev_commands`, `test_vercel_build` | 10 |

Quelques tests notables :
- le **déterminisme** du rattrapage, qu'il soit fait d'un coup ou en deux visites ;
- les **proportions** de rareté et de shiny sur des milliers de tirages. Les graines sont fixes, donc ces tests ne peuvent pas échouer au hasard ;
- la **règle d'architecture**, qui interdit d'importer Django dans `game/` ;
- les **vrais fichiers d'espèces**, validés à chaque exécution ;
- les actions de jeu, qui doivent refuser toute requête GET.

**L'intégration continue** ([ci.yml](../.github/workflows/ci.yml)) enchaîne `ruff format --check`, `ruff check`, `manage.py check`, `makemigrations --check`, `pytest`, puis la recompilation du CSS avec une comparaison au fichier commité.

## 13. Déploiement et procédures

| Élément | Où |
| --- | --- |
| Build de production | `scripts/vercel_build.py` : migrations, puis `load_species` (déclaré dans `[tool.vercel.scripts]`) |
| Fichiers statiques | `collectstatic` lancé par Vercel, servi par son CDN |
| Région des fonctions | `vercel.json` (`fra1`) |
| Base de données | Neon (Francfort), créée depuis l'onglet Storage de Vercel |
| Domaine | `pokechill.bradsavary.dev`, certificat Let's Encrypt automatique |

### Procédures courantes

- **Déployer :** `git push` sur `main`. Vercel construit (migrations et espèces) et déploie, et la CI tourne en parallèle.
- **Modifier une espèce :** éditer son fichier JSON. En local, lancer `load_species` ; en production, le déploiement suffit.
- **Relancer l'import PokéAPI en production :** depuis le poste local, dans PowerShell, avec l'URL **sans pooler** de Neon.
  ```
  $env:DATABASE_URL = "postgresql://...(URL sans pooler)..."
  uv run python manage.py import_pokeapi --no-media
  Remove-Item Env:DATABASE_URL
  ```
  La dernière ligne est importante : tant que la variable existe, toutes les commandes Django du terminal agissent sur la production. Le même principe sert pour `createsuperuser` ou `purge_guests`.
- **Quand une donnée PokéAPI nouvelle est ajoutée au modèle** (comme `growth_rate` à l'étape 2) : relancer l'import en production après le déploiement. Sinon, chaque espèce garde la valeur par défaut du champ.
- **Après une modification d'une variable d'environnement sur Vercel :** redéployer.

### Commandes de développement

| Besoin | Commande |
| --- | --- |
| Voir les joueurs locaux | `uv run python manage.py players` |
| Simuler une absence de 10 h (dernier joueur actif) | `uv run python manage.py rewind_clock 10` |
| Recommencer une partie (le compte est gardé) | `uv run python manage.py reset_player` |
| Supprimer les invités inactifs | `uv run python manage.py purge_guests [--days 180] [--dry-run]` |

Astuce : une fenêtre de navigation privée crée un nouvel invité.

### Performances observées

- Environ 0,2 à 0,3 s par page une fois la fonction chaude. Le rattrapage d'une absence tient en 7 requêtes SQL, quelle que soit sa durée.
- Environ 1,2 à 1,4 s après une période sans visite : c'est le démarrage à froid du serverless.

## 14. Pièges rencontrés

| Problème | Cause | Solution retenue |
| --- | --- | --- |
| Des commentaires s'affichaient dans la page | `{# … #}` ne fonctionne que sur une seule ligne en Django | `{% comment %}` pour plusieurs lignes, plus un test de non-régression |
| CSS commité non minifié | Un `--watch` lancé avec l'ancienne version du script | Minification aussi en `--watch`, plus un contrôle dans la CI |
| Version de Tailwind pas réellement figée | `pytailwindcss.run()` sans `version` utilise « latest » | `run(..., version=..., auto_install=True)` |
| Migration réécrite après avoir été poussée | Une migration déjà appliquée sur Neon avait été modifiée | La version poussée a été restaurée et le changement placé dans une nouvelle migration. Règle : une migration poussée ne se modifie plus jamais |
| Pokédex grisé et aucune arrivée en production | `load_species` n'avait jamais été lancé sur Neon | Le build de production charge maintenant les espèces à chaque déploiement |
| `{% with a=b or c %}` refusé | `with` et `include … with` n'acceptent pas d'expressions | Condition écrite dans le `{% if %}`, ou comparaison faite dans le template inclus |
| `FOR UPDATE cannot be applied to the nullable side of an outer join` | Verrou demandé sur une requête qui joint le type secondaire (facultatif) | `select_for_update(of=("self",))` : seul l'objet principal est verrouillé |
| Ordre de la mangeoire perdu en production | `jsonb` (PostgreSQL) réordonne les clés d'un objet ; SQLite les gardait | Une liste de paires au lieu d'un dictionnaire |
| Ancien CSS gardé par le navigateur | Le serveur de développement n'envoie aucun en-tête de cache | Balise `{% asset %}` (`?v=<date>`) |
| Template modifié sans effet en local | `runserver --noreload` garde les templates en cache | Redémarrer le serveur après une modification de template |
| Bouton qui passe à la ligne, mise en page cassée | Un `<form>` dans un `<p>` : HTML invalide, le navigateur ferme le paragraphe | `<div>` |
| Texte vide dans une bulle | Le filtre `add` ne mélange pas texte et nombre | Textes des bulles construits dans la vue |
| Chiffres illisibles (le 5 ressemble à un S) | Dessin de Pixelify Sans | Micro 5 pour les chiffres, par `unicode-range` |
| Les deux polices ne se combinaient pas | Des descripteurs différents (graisse) empêchent la combinaison par `unicode-range` | Même plage `font-weight` sur les deux déclarations |
| Police absente d'une page de test | Une page en `file://` ne peut pas charger une police servie en `http://` (CORS) | Page servie par le serveur de développement |
| Icône du menu qui glisse au survol | Agrandissement autour d'un centre placé sur un demi-pixel | Anneau au survol, sans changement de taille |
| Bonbons décalés par rapport au texte | Le dessin est placé 4 px sous le centre de l'image | Recadrage en CSS (`.candy-icon`) |
| Erreurs fantômes dans VS Code | Analyse périmée de Pylance | « Python: Restart Language Server » |
| Mesure de requêtes à 0 dans le shell | Hôte `testserver` refusé par `ALLOWED_HOSTS` | `Client(SERVER_NAME="localhost")` |

## 15. Points ouverts pour la suite

- **Étape 3 (la recherche)** : moteur d'objectifs, stades 2 et 3, arbre de compétences (dont l'arbre Zones : emplacements, plafond de travail, emplacements de mangeoire).
- **Rejouer les tutoriels** depuis un menu, sans leurs récompenses.
- **Passe UX** : mettre en évidence les éléments cliquables et importants (bonbons, attaques, expérience).
- **Gestion des attaques** : changer les 4 attaques, consulter celles déjà apprises et les CT. Elle viendra avec la montée de niveau.
- **Automatiser `purge_guests`** avec un Cron Vercel.
- **API du jeu** (DRF ou Ninja) : décision reportée à l'étape 6.
- **Relancer l'import en production** après le déploiement de l'étape 2 : courbes d'expérience (`growth_rate`) et Mew marqué légendaire.
