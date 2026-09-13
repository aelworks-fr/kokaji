# RFC-007 — L'Observation du harness : les cartos
> **Statut : proposé** (établi, août 2026). Dépend de : RFC-001 (capture), RFC-002 (carré, contrats), RFC-004 (praticien, versement) ; RFC-003 alimente une carto optionnelle.
> Nom d'imagerie proposé pour la page : **l'Épure** — le dessin technique exact du forgeron. À marteler.

---

## 1. Motivation

Le QG regarde les **sujets** (la pratique d'un kin le long de la chaîne). Rien ne regarde encore le **harness lui-même** — sa structure, ses contrats, sa santé mathématique sur le corpus. Or le forgeron a besoin de *voir* son harness, et la mathématique du projet s'y prête par nature : la théorie sous-jacente est la seule branche des maths dont la notation native est diagrammatique **au sens formel** (un diagramme commutatif *est* l'équation ; le raisonnement graphique y est prouvablement correct). Une page qui dessine le harness n'illustre pas le formalisme : elle **l'affiche**.

## 2. Principe d'architecture — trois espaces isolés (décision structurante)

Chaque harness s'expose désormais en **trois espaces distincts**, séparés dans la navigation, dans l'API et dans les droits :

| Espace | Contenu | Nature | Droits (RFC-004) |
|---|---|---|---|
| **Définition** | template, kata, contrats, personas, registre — le tamahagane | Édition | co-auteurs |
| **Observation** *(ce RFC)* | les cartos : analyses du harness sous divers angles | **Lecture seule stricte** | co-auteurs (règles de visibilité §5) |
| **Administration** | membres, transfert, scellements/versions, suppression | Gestes de gouvernance | propriétaire (sauf scellement : co-auteurs) |

**Règle d'isolation** : aucune action d'édition ni d'administration n'est accessible depuis l'Observation — c'est un miroir, comme le QG. Trois familles de routes API distinctes ; le sabotage §7 le vérifie. Cette séparation clarifie aussi rétroactivement l'existant : l'onglet Profil (RFC-004) appartient à l'Administration ; le QG est l'Observation *des sujets* ; l'Épure est l'Observation *du harness*.

## 3. Les cartos — des angles d'analyse en sous-onglets

Une **carto** = un angle de lecture du harness, en sous-onglet de l'Observation. Contrat commun à toute carto : lecture seule ; alimentée par l'API d'observation ; soumise aux règles de justesse (§4) et de visibilité (§5). L'architecture est **extensible** : une carto nouvelle est un module de lecture — elle s'ajoute sans RFC, tant qu'elle respecte le contrat.

### 3.1 · Carto structurelle — le diagramme du harness *(v1)*
La chaîne dessinée avec, **par kata, son carré de naturalité vivant** : pratique en bas, contrats en haut, α sur les flancs, f♯ en traverse — le carré **coloré par le corpus** (vert : tous les ha vérifient la loi de prudence ; marqué : violations, avec accès aux ha fautifs selon visibilité). Les contrats (`herite`/`produit`) lisibles sur les arêtes, le typage de chaîne visible. Un diagramme commutatif qui est en même temps un instrument de contrôle.

### 3.2 · Carto des certitudes et incertitudes *(v1)*
Où le harness **produit de la certitude, où il laisse de l'incertitude** : par kata × champ, la distribution des statuts observés sur le corpus (part de fait_établi / hypothèse / en_pause dans les états finaux). Complétée par la **vue du slack** : le diagramme de Hasse de D (treillis fini, dessinable exactement) avec `herite` et `produit` comme points et le nuage des α des ha réels entre les deux — **le slack devient une distance visible**. Répond aux questions du forgeron : quel champ reste systématiquement en pause ? quel kata sur-livre en silence ? où l'incertitude s'accumule-t-elle ?

### 3.3 · Carto des natures *(v1 si RFC-003 intégré, sinon différée)*
Distribution des natures diagnostiquées (évident / analysable / émergent / urgence / indéterminé) par kata, taux de révision en cours de session, et — quand le banc tourne — justesse du diagnostic contre les kin de banc.

### Cartos candidates (sans RFC, quand le besoin arrive)
Fécondité agrégée (options vivantes/fermées par kata, à travers les sujets — l'agrégat du RFC-001) · admissibilité des moteurs (le meet des contrats observés par moteur) · fraîcheur du corpus (âge des ha par kata) · tour des granularités (les adjonctions d'étage empilées).

## 4. Les trois règles de justesse mathématique (non négociables)

1. **Ne dessiner que le calculable.** D est un treillis fini : dessinable *en entier, exactement*. K ne l'est pas — l'ordre « justifie plus » n'est pas mécanisé : le côté K de tout diagramme ne montre que des **échantillons observés**, positionnés par leur ombre γα dans D. Jamais un poset inventé. (La règle « zéro invention » du QG, appliquée aux mathématiques.)
2. **Représenter la laxité comme telle.** Le carré commute à ≥ près : un rendu qui suggérerait une commutation stricte serait un diagramme **faux**. Le mou se dessine (jeu, double-flèche, zone — question de design ouverte), il ne s'efface pas.
3. **Trois encres pour trois régimes sémantiques.** Le *déclaré* (manifest, contrats — exact), l'*observé* (ha, états — échantillons), l'*idéalisé* (ex. monotonie de la pratique — intention ⚠). L'œil doit toujours savoir ce qu'il regarde.

## 5. Données et visibilité

L'API d'observation sert : la structure (manifest), les contrats, les résultats de checks (carré, typage), et les **agrégats** calculés sur *tous* les ha (le système n'est pas un tiers — RFC-004 §5). Le **détail** d'un ha (transcript, kin) n'est accessible depuis une carto que s'il est versé, ou sien. Toute carto est agrégée par défaut ; le passage au détail est un geste explicite, soumis à l'ACL.

**Garde-fou Goodhart (reconduit)** : la carto des certitudes est **descriptive** — « plus de fait_établi » n'est pas un objectif (un harness honnête sur un domaine émergent produit *légitimement* de l'hypothèse). Aucun score global de « santé du harness » ; les formules affichées en légende.

## 6. Non-objectifs (v1)

Édition depuis les cartos (jamais) · temps réel (un rafraîchissement à l'ouverture suffit) · export d'images · cartos personnalisées par utilisateur · diagrammes de ficelles et tout formalisme au-delà du chapitre 1 · comparaison inter-harness.

## 7. Critère « juste assez » — avec sabotages

- **Nominal** : ouvrir l'Épure de l'Atelier sur un corpus sain → carto structurelle : carrés verts, contrats lisibles ; carto des certitudes : la heatmap reflète la réalité du corpus (ex. `criteres_reussite` majoritairement en pause — conforme à la fixture).
- **Sabotage 1 (le grand)** : introduire le kata sur-prometteur de la preuve 6 (carte de conviction) → **son carré passe au rouge sur la carto structurelle**, visible sans ouvrir un log. Le jour où ce carré rougit à l'écran, les mathématiques du projet ont une interface.
- **Sabotage 2** : depuis une carto, tenter d'accéder au transcript d'un ha non versé d'autrui → 403 ; tenter tout geste d'édition ou d'admin depuis l'Observation → impossible par construction (pas de route).

## 8. Changements et suites

| Document / composant | Changement |
|---|---|
| SPECS | v1.5 → v1.6 : l'app web se structure en trois espaces (§2) ; l'Épure rejoint la brique QG (même app, deux pages d'observation : sujets / harness) |
| API middleware | Famille de routes « observation » (agrégats, checks, Hasse de D) — lecture seule |
| Carte de conviction | Ajouter la preuve « le carré rougit à l'écran » (sabotage 1) |
| Design | Un brief dédié à produire pour l'équipe design (Claude Design + Nicolas) — les questions ouvertes : rendu du mou (laxité), les trois encres, la lisibilité d'un carré par kata sans surcharge |

---
*Note d'établi : ce RFC ferme une boucle ouverte il y a longtemps — « je crois fermement à la puissance de la représentation visuelle ». Le QG montrait déjà le métal qui chauffe ; l'Épure montre la forge elle-même : ses gabarits, ses tolérances, et l'écart entre ce que les lames promettent et ce qu'elles coupent. Le forgeron qui voit ses carrés rougir n'a plus besoin de croire son outillage sur parole.*
