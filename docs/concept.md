# PokéChill — Document de concept

Oct 25, 2026 · @Brad

## Vision

PokéChill est un jeu web de gestion idle où l'objectif est de compléter entièrement le Pokédex de Kanto (151 espèces), dans l'esprit de Légendes Arceus. Des expéditions roguelike jouables activement viennent compléter la gestion passive.

**Pitch.** Vous reprenez une pension Pokémon abandonnée. Chaque heure, un Pokémon sauvage s'y présente, attiré par ce que vous avez construit, ce que vous avez mis dans la mangeoire, l'heure qu'il est et les Pokémon qui vivent déjà chez vous. À vous de comprendre ce qui attire chaque espèce, de faire travailler vos pensionnaires et de les emmener en expédition pour étudier les 151 Pokémon jusqu'au bout.

### Piliers

### **La collection et l'étude** : chaque espèce se complète en trois stades, de la première rencontre à la maîtrise totale.

1. **La découverte** : les conditions d'arrivée sont cachées. Le joueur les déduit, guidé par des indices.
2. **Les choix d'affectation** : un Pokémon ne peut être qu'à un seul endroit à la fois (zone de récolte, expédition, repos).
3. **Le rendez-vous quotidien** : arrivées horaires et quêtes du jour donnent une raison de revenir chaque jour, sans punir l'absence.

### Boucle principale

1. Le joueur revient : les arrivées et les récoltes accumulées pendant son absence l'attendent.
2. Il accueille les nouveaux Pokémon et collecte les ressources.
3. Il réaffecte ses Pokémon, remplit la mangeoire et améliore ses zones.
4. Il avance ses défis Pokédex et ses quêtes du jour.
5. Il part éventuellement en expédition roguelike avec les Pokémon disponibles.
6. Les nouvelles conditions remplies attireront d'autres espèces aux prochaines heures.

### Le démarrage

Le joueur commence avec les 3 starters de Kanto : Bulbizarre, Salamèche et Carapuce. Un tutoriel guidé par quelques quêtes présente chaque menu et se termine par une première arrivée offerte, pour montrer le cœur du jeu dès la première minute. Chaque nouvelle fonctionnalité y ajoute ses étapes (les zones, puis la mangeoire, avec 10 baies offertes pour l'essayer). Un menu permettra plus tard de rejouer les tutoriels, sans leurs récompenses.

## Le Pokédex de recherche

Chaque espèce possède sa propre fiche de recherche, qui progresse en trois stades. Compléter les 151 fiches au stade 3 est l'objectif final du jeu.

### Les stades d'une espèce

| Stade | Condition | Ce que la fiche affiche | Récompense |
| --- | --- | --- | --- |
| 0 — Inconnu | Jamais rencontré | Silhouette noire et un premier indice | — |
| 1 — Rencontré | Avoir obtenu le Pokémon au moins une fois | Sprite, types, liste des défis | Points de recherche |
| 2 — Étudié | 5 défis complétés | Une étoile grise dans la liste et sur la fiche | Points de recherche et bonbons de sa lignée (les objets viendront plus tard) |
| 3 — Maîtrisé | Tous les défis complétés | Une étoile dorée | Bonus permanents propres à l'espèce, qui ne concernent que ce Pokémon |

**Les récompenses se réclament.** Un défi complété ou un stade atteint ne paie pas tout seul : un « ! » apparaît sur le Pokédex du menu, sur l'espèce dans la liste et sur le bouton « Challenges » de sa fiche. Le joueur réclame chaque récompense (ou toutes d'un coup) et voit ce qu'elle rapporte. La barre des stades montre un cadeau à chaque stade, avec sa récompense.

**La fiche d'une espèce** se concentre sur une action à la fois, choisie avec les boutons en bas : « Challenges » (les défis et la barre des stades) et « Level & candies » (le niveau, et les bonbons de sa lignée à lui donner). Les statistiques, les attaques, la description et le cri attendent qu'ils servent (expéditions).

**Le bonus de maîtrise** donne une raison concrète d'aller jusqu'au bout. Il est lié à l'identité du Pokémon : Leveinard maîtrisé accélère les soins après une expédition, Miaouss augmente les gains d'argent, Ronflex agrandit la mangeoire.

### Les défis

Chaque espèce a entre 8 et 10 défis, tirés de catégories communes. Certains défis sont à paliers (obtenir 1, 5, puis 10 fois), chaque palier comptant comme un défi.

| Catégorie | Exemples |
| --- | --- |
| Obtention | L'obtenir 10 fois, en obtenir un shiny, l'obtenir en expédition et passivement |
| Niveau | Atteindre le niveau 30 avec un Pokémon de cette espèce |
| Attaques | Lui faire apprendre Lance-Flammes, lui apprendre une CT |
| Lignée et natures | Obtenir toute sa lignée, débloquer ses 6 natures |
| Récolte | Récolter 500 ressources avec lui, trouver un objet rare dans une zone |
| Pension | Le garder 48 h dans une zone, le laisser libre 240h (ex: pour ronflex) |
| Expédition | Battre 3 boss avec lui, terminer un donjon avec lui dans l'équipe, en vaincre 20 en donjon |

Tout les pokemons ne seront pas disponible des le début, a définir la liste des pokemons intégré au jeu ou non en amont et la faire grandir au fur et a mesure. Définir également les statistiques de chaque pokemon avant son intégration.

Les défis de la catégorie Expédition n'apparaissent qu'une fois le mode roguelike disponible.

### L'arbre de compétences

Les points de recherche gagnés sont la colonne vertébrale à la progression. On peut les dépenser dans un "arbre de compétences " cela coute aussi les ressources de certaines zones, et permet de débloquer du contenu : une nouvelle zone, une place de pension supplémentaire, un emplacement de mangeoire, une quête quotidienne de plus, l'accès aux expéditions.

Toutes les conditions de déblocage du jeu (zones, quêtes supplémentaires, certaines arrivées) font référence à un nœud précis de l'arbre.

Il y a en fait plusieurs arbres, réunis dans un même menu d'améliorations. L'arbre **Zones** se divise en une branche par zone : ses nœuds améliorent les zones de diverses façons (emplacements, stockage, rendement, trouvailles, rencontres). Un nœud coûte la ressource de sa zone, ou celles de plusieurs zones pour un nœud commun ; les nœuds majeurs coûtent aussi des points de recherche. Les améliorations de zone arrivent donc avec l'arbre, à l'étape 3.

### Les indices

Les indices sont gratuits et affichés directement sur la fiche Pokédex. Une espèce jamais obtenue montre un indice sur ses conditions d'arrivée, par exemple : « On l'aperçoit parfois près de l'étang, après le coucher du soleil. »

Une fois l'espèce obtenue, la fiche affiche à la place toutes ses méthodes d'obtention.

## Les arrivées de Pokémon

À chaque heure pile, un Pokémon se présente à la pension. Le jeu tire une espèce parmi toutes celles dont les conditions sont remplies à ce moment-là, en tenant compte de leur rareté.

### Le déroulement d'une arrivée

1. Le jeu liste les espèces dont toutes les conditions sont remplies à cette heure.
2. Il tire au sort l'une d'elles, pondérée par sa rareté et par les bonus actifs (ressource dans la mangeoire, événements).
3. Le Pokémon arrive à son niveau minimal : niveau 1 pour une forme de base, sinon le niveau auquel sa pré-évolution évolue. Sa nature et la chance de shiny sont tirées aléatoirement.
4. Le Pokémon attend à l'**Accueil**, où il sera révélé au joueur avec sa fiche et une animation.

**L'Accueil** a un nombre limité de places, par exemple 8 au départ. Une fois plein, les nouvelles arrivées sont perdues. C'est le plafond hors ligne du jeu : il peut s'agrandir (via un nœud de l'arbre de compétences), et il rend les retours réguliers intéressants sans punir lourdement une absence.

**Un seul Pokémon par espèce.** La pension contient au plus un exemplaire de chaque espèce, soit 151 places, et le Pokédex sert d'interface pour les gérer. Une première obtention ajoute l'espèce. Une nouvelle obtention d'une espèce déjà possédée se convertit automatiquement : elle donne des bonbons de sa lignée, débloque sa nature si elle est nouvelle et, si elle est shiny, débloque l'apparence shiny. Obtenir plusieurs fois la même espèce reste donc toujours utile.

### Les types de conditions

Chaque espèce a une ou plusieurs conditions, combinées avec des ET et des OU.

| Condition | Exemple |
| --- | --- |
| Moment de la journée | Fantominus : seulement la nuit (21 h – 6 h) |
| Zone débloquée | Magicarpe : l'étang doit exister |
| Ressource dans la mangeoire | Rondoudou : des baies sont dans la mangeoire |
| Présence d'une espèce | Nidoran♂ : un Nidoran♀ vit à la pension |
| Espèce au travail dans une zone | Parasect : un Paras travaille au Verger, la nuit |
| Niveau d'un pensionnaire | Onix : un Pokémon Roche de niveau 25 ou plus travaille à la carrière |
| Nombre de pensionnaires | Pikachu : au moins 3 Pokémon Électrik à la centrale |
| Nœud de l'arbre | Lokhlass : nœud « Grand large » débloqué |
| Jour de la semaine | M. Mime : seulement le week-end |
| Exclusif aux expéditions | Artikodin, Électhor, Sulfura, Mewtwo : jamais en arrivée passive |
| Autre méthode | Amonita, Kabuto, Ptéra : seulement par fossile ranimé |

Une condition combinée donne les espèces les plus satisfaisantes à trouver. Par exemple, Minidraco : la nuit ET étang de niveau 5 ET des perles dans la mangeoire.

### Les raretés

| Rareté | Poids indicatif | Exemples |
| --- | --- | --- |
| Commun | 100 | Rattata, Roucool, Chenipan |
| Peu commun | 50 | Abo, Psykokwak, Caninos |
| Rare | 20 | Évoli, Tauros, Kangourex |
| Très rare | 5 | Lokhlass, Minidraco, Ronflex |
| Légendaire | 1 | Mew, lors d'un événement très rare (Mew est considéré comme légendaire dans ce jeu) |

Les espèces évoluées ne s'obtiennent que par capture, avec des conditions plus exigeantes que leur forme de base, souvent liées à celle-ci (son niveau, une pierre placée à la pension). Voir la progression des Pokémon.

### La mangeoire

La mangeoire est le principal levier du joueur sur les arrivées. Elle compte d'abord 1 emplacement, puis davantage grâce à l'arbre (4 et au-delà). Chaque emplacement contient une seule ressource, celle de n'importe quelle zone débloquée, de 1 à 50 unités. Deux emplacements peuvent contenir la même ressource. La mangeoire produit deux effets :

- Elle **oriente l'arrivée suivante** vers les types efficaces dans la zone de la ressource : des baies de la Prairie attirent les types Normal, Vol et Fée ; des noigrumes du Verger, les types Plante et Insecte. Chaque unité ajoute 1 point de pourcentage à la chance habituelle que le Pokémon qui arrive ait l'un de ces types, jusqu'à +50 points avec 50 unités. Par exemple, si les types Plante et Insecte représentent d'habitude 30 % des arrivées possibles, 13 noigrumes portent cette chance à 43 %. Parmi les espèces attirées (ou les autres), le tirage reste pondéré par la rareté. Pour attirer un type, il suffit donc d'avoir débloqué sa zone et d'en mettre la ressource dans la mangeoire.
- Elle **remplit une condition** pour certaines espèces (des baies dans la mangeoire pour Rondoudou).

**Consommation** : le Pokémon qui arrive mange tout le premier emplacement, et lui seul profite de son bonus ; le suivant mange l'emplacement suivant, et ainsi de suite. Il le mange même si aucune espèce attirée ne pouvait venir à cette heure (le tirage est alors normal). Rien n'est consommé quand personne n'arrive, par exemple quand l'Accueil est plein. Le joueur peut reprendre un emplacement tant qu'il n'a pas été mangé : ses unités retournent dans le stock. Quand la mangeoire est vide, les chances redeviennent normales.

Les ressources proviennent des zones de récolte, ce qui relie directement la gestion des zones à la collection.

## Les zones de récolte

La pension compte 8 zones, chacune liée à des types de Pokémon. Les Pokémon affectés produisent en continu une ressource principale et ont une chance de trouver des objets rares.

### Liste des zones

| Zone | Types efficaces | Ressource principale | Trouvailles rares | Déblocage |
| --- | --- | --- | --- | --- |
| Prairie | Normal, Vol, Fée | Baie | Plumes, CT de type Normal/Vol/Fée | Départ |
| Verger | Plante, Insecte | Noigrume | Pierre Plante, CT de type Plante/Insecte | Départ |
| Étang | Eau, Glace | Perles | Pierre Eau, CT de type Eau/Glace | Nœud de l'arbre |
| Carrière | Roche, Sol, Combat | Minerai | Pierre Lune, CT de type Roche/Sol/Combat, fossiles | Nœud de l'arbre |
| Volcan | Feu | Braise | Pierre Feu, CT de type Feu | Nœud de l'arbre |
| Centrale | Électrik, Acier | Énergie | Pierre Foudre, CT de type Électrik/Acier | Nœud de l'arbre |
| Marais | Poison, Sol | Racine | CT de type Poison/Sol | Nœud de l'arbre |
| Tour Ancienne | Psy, Spectre, Dragon | Poussière mystique | CT rares de type Psy/Spectre/Dragon | Nœud de l'arbre |

Les types suivent ceux de PokéAPI, qui utilise les types modernes : Mélofée est de type Fée, Magnéti de type Électrik et Acier.

Chaque zone produit **une seule ressource**, pour rester lisible : une seule sorte de baie dans la Prairie (sprite de la Baie Oran), un seul noigrume dans le Verger.

Une zone compte **3 emplacements** au départ ; l'arbre en ajoute.

### Le rendement

La production horaire d'une zone dépend de trois facteurs :

- **Le type** : un Pokémon d'un type efficace produit 100 %. Un Pokémon d'un autre type peut travailler, mais à 25 %.
- **Le niveau** : plus il est élevé, plus la production et la chance de trouvaille rare augmentent.
- **Le niveau de la zone** : l'améliorer (par l'arbre Zones) ajoute des emplacements, augmente le stockage et débloque de nouvelles trouvailles.
- **L****e**** ****n****o****m****b****re**** **: l'efficacité des pokemons est cumulé pour calculé les ressources récoltés (les points de recherche permettent d'augmenter le nombre de pokemons affectable par zone)

Les Pokémon au travail gagnent aussi un peu d'expérience chaque heure, **25 % de plus** dans une zone efficace pour leur type. Améliorer une zone augmente les chances de trouvailles rares et de rencontres avec les espèces liées à cette zone.

### Le stockage

Chaque zone stocke une quantité limitée de ressources, par exemple 12 heures de production. Au-delà, les Pokémon de la zone s'arrêtent de travailler jusqu'à la prochaine collecte : plus de ressource, et plus d'expérience non plus. Ce plafond est le même principe que l'Accueil : améliorable plus tard, par l'arbre.

La collecte rapporte d'un coup les ressources et l'expérience accumulées depuis la précédente.

### L'économie des ressources

Chaque zone produit sa propre ressource, qui sert à plusieurs choses :

- **améliorer les zones**, par les nœuds de l'arbre Zones (emplacements, stockage, chances de trouvailles rares et de rencontres) ;
- **débloquer** certains nœuds des autres arbres ;
- **remplir la mangeoire**, pour attirer les types de la zone ;
- **acheter à la boutique** (plus tard, voir ci-dessous) ;
- les baies et les noigrumes servent en plus à remplir le sac d'expédition.

### La boutique (plus tard)

Une boutique permettra d'acheter, avec les ressources des zones, un Pokémon au hasard, ou un Pokémon au hasard d'un type donné. Elle donne une utilité durable aux ressources, qui sinon deviendraient vite inutiles une fois les zones améliorées. Son étape reste à choisir.

### Les arrivées propres aux zones

Certaines espèces ne viennent que si une zone précise est active et occupée. Ces conditions passent par le système d'arrivées décrit plus haut, pour garder une seule logique. Exemples :

- Un Tentacool peut se présenter quand l'étang compte au moins 3 pensionnaires.
- Un Taupiqueur peut arriver quand la carrière est au niveau 3.
- Les fossiles trouvés dans la carrière sont ranimés au laboratoire et donnent Amonita, Kabuto ou Ptéra.

### La règle d'affectation

Un Pokémon a toujours un seul statut à la fois : **libre**, **en zone**, **en expédition** ou **en soins**. Un Pokémon affecté à une zone ne peut pas partir en expédition sans être d'abord retiré, ce qui stoppe sa production. Le joueur arbitre donc en permanence entre revenus passifs et expéditions.

## Le panneau de quêtes

Le panneau propose 3 quêtes par jour (jusqu'à 5 via l'arbre de compétences), renouvelées chaque jour à minuit, heure de Paris, plus une quête hebdomadaire plus ambitieuse.

### Les sources de quêtes

- **Défis Pokédex en cours** : le panneau reprend un défi non terminé d'une espèce possédée. Le réaliser compte à la fois pour la quête et pour le défi, ce qui guide le joueur vers sa progression principale.
- **Quêtes de pension** : « Récolte 200 perles », « Accueille 3 Pokémon de type Insecte », « Améliore une zone » (si possible).
- **Commandes de clients** : un dresseur demande un Pokémon précis à un niveau donné, que l'on relâche en échange d'une belle récompense.
- **Quêtes d'expédition**, une fois le roguelike disponible : « Atteins l'étage 5 », « Bats un boss avec un Pokémon Eau ».

### Les récompenses

Ressources pour la mangeoire, bonbons, points de recherche, et plus rarement une CT ou une pierre d'évolution.

### Les règles de confort

- Une quête peut être remplacée gratuitement une fois par jour.
- Les quêtes non terminées disparaissent sans pénalité.
- Une série de 7 jours avec au moins une quête terminée donne une récompense bonus. Une journée manquée met la série en pause plutôt que de la remettre à zéro.

Côté technique, quêtes et défis reposent sur le même système d'**objectifs** (voir les notes techniques) : une quête n'est qu'un objectif avec une date d'expiration.

## La progression des Pokémon

Un Pokémon progresse par son niveau et ses attaques. Ces deux axes nourrissent directement les défis du Pokédex.

### Les niveaux

Un Pokémon gagne de l'expérience de trois façons : en travaillant dans une zone (lent mais passif), en consommant des bonbons, et en expédition. Le niveau maximum est 100.

L'expérience nécessaire suit les **courbes des jeux** : chaque espèce a la sienne (fournie par PokéAPI). Les 151 de Kanto en utilisent quatre : rapide (5 espèces), moyenne (80), parabolique (40) et lente (26). Au niveau 50, il faut ainsi 100 000 points d'expérience en courbe rapide, contre 156 250 en courbe lente.

### Les bonbons

Chaque nouvelle obtention d'une espèce déjà possédée donne des bonbons de sa lignée : 3 pour une espèce commune, davantage pour une rare. Comme dans Pokémon GO, les bonbons sont partagés par toute la lignée : les bonbons Salamèche font monter de niveau Salamèche, Reptincel et Dracaufeu. Le coût augmente avec le stade d'évolution, par exemple ×1 pour la forme de base, ×2 pour la deuxième forme et ×3 pour la troisième. Il n'existe pas de bonbon d'expérience universel : les légendaires progressent grâce aux bonbons obtenus en les capturant de nouveau en expédition.

### Les attaques

Chaque Pokémon connaît jusqu'à 4 attaques. Il en apprend de nouvelles en montant de niveau, selon les listes officielles de PokéAPI, ou grâce aux CT trouvées dans les zones. En idle, les attaques servent surtout aux défis. En expédition, elles deviennent le cœur du combat.

### Pas d'évolution

Les Pokémon n'évoluent pas. La seule façon d'obtenir une nouvelle espèce est de la capturer : arrivée passive, expédition ou méthode spéciale comme les fossiles. Chaque espèce évoluée a donc ses propres conditions d'arrivée.

**L'esprit de l'évolution passe par les conditions.** Une espèce évoluée s'attire souvent grâce à sa forme de base : Reptincel peut se présenter si Salamèche est au niveau 16 ou plus dans la pension. Les pierres d'évolution deviennent des objets à placer à la pension : une Pierre Feu attire Arcanin si Caninos est présent, une Pierre Eau attire Aquali si Évoli est présent. Les anciennes évolutions par échange (Alakazam, Mackogneur, Grolem, Ectoplasma) deviennent simplement des espèces rares aux conditions exigeantes.

### La nature et le shiny

Il existe 6 natures, une par statistique : PV, Attaque, Défense, Attaque Spéciale, Défense Spéciale et Vitesse. Chaque obtention tire une nature au hasard. La première fois qu'une nature est obtenue pour une espèce, elle débloque un bonus permanent sur la statistique correspondante. Obtenir de nouveau la même nature n'apporte rien de plus : chaque espèce a donc au maximum 6 bonus, un par statistique, que la fiche Pokédex affiche.

La chance de shiny est de 1 sur 1024 en arrivée passive (1 sur 512 avec le charme chroma). Obtenir une espèce en shiny débloque sur sa fiche Pokédex un interrupteur pour l'afficher en shiny ou non dans tout le jeu. Le charme chroma, débloqué lorsque 100 espèces atteignent le stade 2, double le taux d'apparition des shiny. Seules certaines espèces ont un défi « l'obtenir en shiny » : un shiny doit rester rare.

## Les expéditions roguelike

Les expéditions sont des donjons au tour par tour sur grille, joués activement avec une équipe de 1 à 3 Pokémon de la pension. Elles arrivent après le cœur idle, mais tout le design idle est pensé pour les accueillir.

### Le principe

L'équipe descend des étages générés aléatoirement, combat des Pokémon sauvages, ramasse des objets et affronte un boss tous les 5 étages. Les Pokémon vaincus ne rejoignent pas l'équipe : à la fin de l'expédition, un écran de bilan révèle si une capture a réussi parmi les espèces affrontées. Si toute l'équipe est mise K.O., l'expédition échoue et une partie du butin est perdue.

### Les donjons prévus

| Donjon | Étages | Espèces rencontrées | Boss final |
| --- | --- | --- | --- |
| Forêt de Jade | 5 | Insecte, Plante, Pikachu | Papilusion |
| Mont Sélénite | 10 | Roche, Poison, Mélofée | Onix |
| Grotte Glacée | 15 | Eau, Glace | Artikodin |
| Centrale abandonnée | 15 | Électrik, Acier | Électhor |
| Route Victoire | 15 | Feu, Combat, Roche | Sulfura |
| Caverne Azurée | 25 | Toutes, niveaux élevés | Mewtwo |

### Les liens avec la pension

- **Préparation** : le joueur choisit son équipe parmi les Pokémon libres et remplit un sac à places limitées avec les baies et objets produits par les zones (améliorable avec des points de recherche).
- **Verrouillage** : les Pokémon partis ont le statut « en expédition » (et ne peuvent donc plus etre dans des zones).&#32;
- **Retour** : le bilan révèle les captures éventuelles, les objets et matériaux rares vont dans l'inventaire, l'expérience est appliquée.
- **Soins** : un Pokémon mis K.O. passe quelques heures « en soins » avant de redevenir disponible.
- **Défis** : les défis de la catégorie Expédition s'activent
- **Espèces exclusives** : les légendaires ne s'obtiennent qu'au bilan d'une expédition dans leur donjon, avec une faible chance de capture. Ils peuvent être capturés plusieurs fois : chaque nouvelle capture donne des bonbons et peut débloquer une nouvelle nature, comme pour toute espèce.
- **Déblocage passif** : terminer un donjon une fois peut débloquer de nouvelles espèces en arrivée passive, par exemple Lipoutou après la Grotte glacée.

## L'interface

Le jeu est une application web conçue comme un jeu mobile **en paysage**, installable sur l'écran d'accueil (PWA). Le format paysage facilite aussi l'adaptation sur ordinateur. Sur un téléphone tenu en portrait, un message invite à le tourner.

### La navigation

Une barre verticale sur le côté donne accès à 4 onglets : **Pension**, **Zones**, **Pokédex** et **Expéditions** (verrouillé jusqu'à l'étape 6). Une barre en haut affiche les ressources, les points de recherche et le compte à rebours de la prochaine arrivée. Sur ordinateur, la barre latérale peut afficher les libellés à côté des icônes.

### Les pages

| Page | Contenu | Actions |
| --- | --- | --- |
| Pension (page principale) | Scène illustrée où les Pokémon se promènent, résumé de l'absence, Accueil (x/8), état de la mangeoire | Révéler les arrivées, remplir la mangeoire, ouvrir Quêtes, Arbre, Inventaire et Profil |
| Zones | La liste des zones : Pokémon au travail, ressources à récupérer, depuis combien de temps ils travaillent, jauge de stockage | Choisir une zone : le clic récolte ressources et expérience accumulées (avec un résumé), puis ouvre la zone ; s'il n'y a rien à récolter, elle s'ouvre directement |
| Détail d'une zone | La carte de la zone (décor pixel art) avec ses Pokémon qui sautillent (icônes de 7e génération), leur efficacité, les trouvailles rares (découvertes ou « ??? ») | Affecter (clic sur un emplacement vide, puis choix parmi les Pokémon libres, ceux du bon type en premier), retirer (clic sur un Pokémon) |
| Pokédex | À gauche (1/3) : liste triable et filtrable des espèces (silhouette, sprite, fiche dorée). À droite (2/3) : fiche complète de l'espèce sélectionnée | Affecter, donner des bonbons, apprendre une CT, activer l'apparence shiny |
| Expéditions | Liste des donjons, choix de l'équipe et du sac, écran de jeu, bilan | Lancer, jouer, abandonner |
| Quêtes, Arbre, Inventaire, Profil | Panneaux ouverts depuis la Pension | Selon le panneau |

**La fiche espèce du Pokédex** regroupe tout : nom, types, niveau et expérience, statut, statistiques avec les bonus de nature, attaques, stade et défis, apparence shiny si débloquée. Une espèce non obtenue affiche son indice, une espèce obtenue ses méthodes d'obtention.

### Ergonomie et immersion

- **Résumé de retour** animé à chaque ouverture du jeu.
- **Pastilles de notification** sur les onglets et les boutons de la Pension : Accueil plein, zone pleine, quête terminée.
- **Révélation des arrivées** : chaque Pokémon apparaît avec sa fiche, avec une animation spéciale pour une nouvelle espèce ou un shiny, et le cri du Pokémon.
- **Animations de collecte** dans les zones.
- **Couleurs des types**, choisies pendant le développement selon les codes officiels.
- **Assets Pokémon au maximum** : sprites, cris et icônes d'objets fournis par PokéAPI. Les visuels et les sons s'enrichissent au fil des étapes.

### Les décors

Chaque page a un décor de fond en pixel art, cohérent avec le style des sprites :

- **Pension** : la pension elle-même, avec son enclos et sa mangeoire, en version jour ou nuit selon l'heure réelle.
- **Zones** : un biome par zone (prairie, verger, étang, carrière, volcan, centrale, marais, tour).
- **Pokédex** : un décor de laboratoire, discret pour laisser la place aux fiches.
- **Expéditions** : le décor du donjon en cours.

Source à privilégier : des packs de décors libres (CC0 ou licence permissive) sur OpenGameArt ou itch.io, en vérifiant la licence de chaque pack. Les décors extraits des jeux officiels existent, mais relèvent du même risque juridique que les sprites.

## Feuille de route

Le développement avance en 8 étapes. Chacune se termine par une version déployée et jouable, qui peut être montrée sur le portfolio.

&#91;embedded content: feuille de route · 8 étapes jouables\]

Les six premières étapes construisent toute la pension. Les expéditions n'arrivent qu'ensuite, sur un socle déjà complet.

### Étape 0 — Le socle

- Projet Django configuré pour le local (SQLite) et Vercel (Neon).
- Import des 151 espèces depuis PokéAPI : types, statistiques, attaques, lignées d'évolution, sprites.
- Un Pokédex consultable avec fiches et silhouettes.

**Jouable** : un Pokédex web, déjà présentable.

### Étape 1 — Les arrivées

- Mode invité et comptes.
- Le tick horaire avec calcul paresseux et graine aléatoire.
- Le moteur de conditions, avec les conditions simples : moment de la journée, rareté.
- L'Accueil, la révélation des arrivées et la conversion des doublons en bonbons ; le démarrage avec les 3 starters et le tutoriel ; un premier lot d'environ 30 espèces.
- Le Pokédex passe au stade 1 à la première obtention.

**Jouable** : on revient voir qui est arrivé et on remplit son Pokédex.

### Étape 2 — Les zones et la mangeoire

- Les deux zones de départ (Prairie, Verger) : affectation, production, stockage, expérience passive selon les courbes des jeux.
- La page Zones et la carte de chaque zone, avec ses Pokémon.
- Le statut unique du Pokémon (libre, en zone).
- La mangeoire, sur la carte de la Pension, et les conditions de ressource, de présence et de zone.
- Les espèces jusqu'à Golduck (#055) ; les formes évoluées demandent leur forme précédente.
- Les étapes du tutoriel pour les zones et la mangeoire.
- L'amélioration des zones attend l'arbre de compétences (étape 3).

**Jouable** : la boucle idle complète, avec de vrais choix.

### Étape 3 — La recherche

- Le moteur d'objectifs et les défis (hors expédition).
- Les stades 2 et 3, les bonus de maîtrise.
- L'arbre de compétences, qui débloque désormais le contenu, dont l'arbre Zones pour améliorer les zones.
- Les indices et les bonbons de lignée.

**Jouable** : un objectif à long terme et une progression guidée.

### Étape 4 — Le panneau de quêtes

- Quêtes quotidiennes et hebdomadaires, construites sur le moteur d'objectifs.
- Remplacement quotidien, série de 7 jours.

**Jouable** : une raison claire de revenir chaque jour.

### Étape 5 — Le contenu complet de la pension

- Les 8 zones et leurs trouvailles rares.
- Les CT et les attaques, les pierres à placer à la pension, les fossiles.
- Les conditions avancées (niveau, nombre, jour de la semaine, combinaisons), les natures et le shiny.
- Le réglage des conditions des quelque 140 espèces non légendaires.

**Jouable** : le jeu idle complet, presque tout le Pokédex obtenable.

### Étape 6 — Les expéditions

- Le moteur de donjon en Python pur, testé en console.
- L'API d'expédition et un rendu 2D avec Phaser.
- Les deux premiers donjons, le sac, les recrues, les soins, le verrouillage.
- Les défis de la catégorie Expédition et les quêtes d'expédition.

**Jouable** : le mélange idle et roguelike.

### Étape 7 — Les légendaires et la 3D

- Les donjons avancés, les trois oiseaux légendaires, Mewtwo, l'événement de Mew.
- Le passage du rendu des donjons en 3D avec Three.js et des sprites en billboard.

**Jouable** : le jeu complet, avec les 151 espèces obtenables.

## Notes techniques et décisions ouvertes

Quatre mécanismes techniques portent tout le jeu. Les construire proprement dès leur première étape évite de tout réécrire ensuite.

### Les mécanismes communs

- **Le moteur de conditions** : les conditions d'arrivée sont stockées en JSON sur chaque espèce, sous forme d'arbre (ET, OU, conditions simples), et évaluées par du Python pur. Ajouter une espèce revient à écrire des données, pas du code.
- **Le moteur d'objectifs** : défis Pokédex et quêtes sont le même objet (un type d'événement suivi, une cible, une progression). Chaque action du jeu émet un événement (« Pokémon obtenu », « ressource récoltée », « boss vaincu ») que ce moteur distribue aux objectifs concernés.
- **Le calcul paresseux du temps** : à chaque visite, le jeu rattrape les heures écoulées (arrivées, production, soins, consommation de la mangeoire) jusqu'aux plafonds. Chaque créneau horaire utilise une graine aléatoire dérivée du joueur et de l'heure : le résultat est identique quel que soit le moment où l'on recalcule.
- **Le statut unique du Pokémon** : libre, en zone, en expédition ou en soins. Toute affectation passe par une seule fonction qui vérifie et change ce statut dans une transaction.

Un point d'attention sur le calcul paresseux : les conditions dépendent de l'état de la pension, qui change pendant le rattrapage. Il faut rejouer les heures dans l'ordre chronologique, en appliquant les événements au fur et à mesure.

### Les décisions à trancher

- [ ] **Niveaux en expédition** : persistants, remis à zéro, ou mixte (départ au niveau 5 avec un bonus de potentiel venant de la pension). Recommandation : mixte.\
Choix: Niveau de base avec potentiel en fonction du niveau en pension.
- [ ] **Taille de l'équipe d'expédition** : 1 à 3 Pokémon, ou une équipe fixe de 3.\
Choix: de 1 à 3
- [ ] **Nombre exact de défis par espèce** : fixe (8) ou variable selon la rareté.\
Choix: de 8 à 10, données a définir a chaque ajout de chaque pokemon

* [ ] **Commandes de clients** : intégrées au panneau de quêtes ou système à part.\
Commande de client remplacée par le panneau de quetes (car plus parlant)
* [ ] **Compte obligatoire** : mode invité avec conversion en compte, ou compte dès le départ (recommandation pour le portfolio : mode invité).\
Choix: Compte non obligatoire
