# PokéChill

Jeu web idle + roguelike sur l'univers Pokémon (151 espèces de Kanto). Objectif du joueur : compléter le Pokédex en 3 stades par espèce, à la manière de Légendes Arceus.

Le concept complet (gameplay, systèmes, interface, feuille de route) est dans `docs/concept.md`. Le lire avant toute tâche de conception.

## Contexte

- Projet personnel d'apprentissage de Python et Django, destiné à un portfolio. Pense donc a bien commenter le code et expliquer tes choix dans tes réponses.
- Fan-game non officiel, non monétisé. Une mention « non affilié à Nintendo, Game Freak ou The Pokémon Company » doit figurer dans le pied de page.

## Stack

- Back-end : Django, avec Django REST Framework ou Django Ninja pour l'API du jeu.
- Base de données : SQLite en local, PostgreSQL (Neon) en production, choisi selon la variable `DATABASE_URL`.
- Hébergement : Vercel (runtime Python, région `fra1`), fichiers statiques servis par le CDN de Vercel. Production : https://pokechill.bradsavary.dev (domaine géré par Vercel). Les migrations s'appliquent au build (`[tool.vercel.scripts]` dans `pyproject.toml`) ; les données s'importent depuis le poste local avec `DATABASE_URL` pointant vers Neon.
- Interface : templates Django + HTMX + Tailwind CSS v4 pour les menus. Source CSS dans `assets/css/input.css`, compilée vers `static/css/main.css` (commité, minifié) par `uv run python scripts/build_css.py` (`--watch` en développement). Recompiler après toute modification de classes dans les templates. Phaser (2D) puis Three.js (3D) pour les expéditions, plus tard.
- Données : importées une fois depuis PokéAPI via une commande Django. Sprites et cris copiés dans les fichiers statiques.

## Règles d'architecture

- La logique du jeu est en Python pur, dans un module indépendant de Django, testée avec pytest :
  - moteur de conditions (conditions d'arrivée stockées en JSON sur chaque espèce, arbre ET/OU) ;
  - moteur d'objectifs (défis Pokédex et quêtes sont le même objet, alimenté par des événements de jeu) ;
  - rattrapage du temps (calcul paresseux, heure par heure, dans l'ordre chronologique).
- Pas de processus permanent : tout ce qui dépend du temps est recalculé à la visite, à partir d'horodatages.
- Chaque créneau horaire utilise une graine aléatoire dérivée de l'identifiant du joueur et de l'heure : le résultat doit être identique quel que soit le moment du recalcul.
- Dates stockées en UTC. L'heure de Paris ne sert qu'au cycle jour/nuit et à la remise à zéro des quêtes.
- Un Pokémon a un seul statut à la fois : libre, en zone, en expédition, en soins. Tout changement passe par une fonction unique, dans une transaction.
- Les espèces sont pilotées par les données : un fichier par espèce (conditions, défis, rareté, niveau minimal), chargé par une commande Django. Ajouter une espèce ne doit demander aucun code.
- Les valeurs d'équilibrage (production, coûts, plafonds) sont regroupées dans un seul fichier de configuration.

## Règles de gameplay à respecter

- Un seul Pokémon par espèce (151 places). Une recapture donne des bonbons de la lignée, peut débloquer une nature, et débloque l'apparence shiny si elle est shiny.
- Pas d'évolution : chaque espèce s'obtient uniquement par capture.
- Bonbons partagés par lignée, coût croissant selon le stade d'évolution.
- 6 natures (une par statistique), chacune débloque un bonus une seule fois par espèce.
- Pas de sexe, pas de Boîte : le Pokédex sert d'interface de gestion.
- Les déblocages passent par des nœuds de l'arbre de compétences.

## Feuille de route

Le développement suit les étapes 0 à 7 de `docs/concept.md`. Chaque étape doit aboutir à une version déployée et jouable. Ne pas anticiper le code des étapes suivantes au-delà de ce que le concept demande.

## Conventions

- Tout en anglais : code, noms de variables et textes du jeu (noms des Pokémon, attaques, objets, interface). Le concept reste rédigé en français ; les noms français qu'il cite se traduisent par leurs noms anglais officiels.
- Sprites : style Noir/Blanc (génération 5). Attaques apprises par niveau : version Rouge Feu/Vert Feuille. Types modernes (PokéAPI).
- Dépendances et Python gérés avec uv (`uv run ...`). Sprites et cris commités dans `static/`, cache JSON de PokéAPI non commité.
- Formatage et lint avec Ruff.
- Mode invité disponible : un compte n'est jamais obligatoire pour jouer.