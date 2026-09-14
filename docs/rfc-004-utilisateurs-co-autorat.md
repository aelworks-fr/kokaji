# RFC-004 — Utilisateurs et co-autorat de harness
> **Statut : proposé, décisions structurantes scellées** (établi, août 2026).
> ⚠️ **Ce RFC renverse un non-objectif scellé** : « multi-utilisateurs » sort des non-objectifs de la SPECS (§0). Le renversement est partiel et nommé : le co-autorat entre au périmètre ; « l'hébergement pour des tiers » (service ouvert) reste hors. Entraîne SPECS v1.4 → v1.5 (§0, §12) et une nuance au `NOTICE` (les contributeurs sont des tiers consentants).

---

## 1. Motivation

Un harness se forge mieux à plusieurs marteaux. Il faut pouvoir inviter un co-auteur sur un harness — sans diluer la responsabilité : **un harness a toujours un et un seul propriétaire**, et autant de contributeurs que voulu. Un onglet « Profil » (design déjà réalisé) matérialise cette gestion.

## 2. Le modèle — deux relations, pas une

Kokaji lie l'utilisateur au système par **deux relations distinctes**, aux règles différentes :

**L'autorat** (ce RFC) — un utilisateur possède ou contribue à des *définitions* de harness : template, kata, cibles, trempe, registre, personas. Les assets héritent de l'ACL du harness — **pas d'ACL par asset en v1**.

**La pratique** — un utilisateur déroule des sessions sur ses *sujets* ; la capture par défaut produit ses ha. La pratique n'est pas l'autorat : contribuer à un harness ne donne aucun droit automatique sur la pratique des autres (§5).

### 2.1 Utilisateur
```
utilisateur { id (uuid stable), nom, email (vérifiable), cree_le }
```
Authentification v1 : **comptes locaux** (mot de passe hashé — argon2 — ou lien magique). **Prêt pour OAuth** sans le coder : l'id est stable et indépendant du fournisseur, l'email est la clé de rapprochement, une table `identites_externes (utilisateur_id, fournisseur, sujet_externe)` est réservée dans le schéma — vide en v1.

### 2.2 Autorat
```
harness_acl { harness_id, proprietaire: utilisateur_id, contributeurs: [utilisateur_id] }
```
**Invariants :** exactement un propriétaire, toujours ; le propriétaire n'apparaît pas dans la liste des contributeurs ; le **transfert** de propriété est un geste explicite du propriétaire (l'ancien propriétaire devient contributeur, sauf retrait explicite).

*Note d'architecture :* la source d'un harness reste un dossier (HDS) — éventuellement un repo git. L'ACL ne vit pas dans les fichiers : elle vit dans Kokaji, attachée au harness *enregistré dans le Dojo*. Le manifest ne change pas.

## 3. Les droits (décision scellée : co-auteurs pleins)

| Geste | Propriétaire | Contributeur |
|---|---|---|
| Éditer la définition (template, kata, personas, trempe, chaîne) | ✅ | ✅ |
| Forger, tremper, pratiquer, lancer le banc | ✅ | ✅ |
| **Sceller une version (y compris majeure, y compris f♯)** | ✅ | ✅ — *chaque scellement porte le nom de son auteur (traçabilité, pas goulot)* |
| Gérer les membres (ajouter/retirer un contributeur) | ✅ | ❌ |
| Transférer la propriété | ✅ | ❌ |
| Supprimer le harness | ✅ | ❌ |

Le RFC-002 disait « le forgeron du harness » au singulier : lire désormais « tout co-auteur », le versionnage signé assurant la responsabilité. La discipline remplace le goulot.

## 4. L'onglet Profil (le design existant fait foi pour la forme)

Contenu contractuel : **ma liste de harness** avec mon rôle badgé (propriétaire / contributeur) ; **mes activités accessibles** — les sujets que je peux observer ou pratiquer, et par quel harness ; mes informations de compte. Le design réalisé est la référence visuelle — versé au repo (`design/profil/`) ; toute divergence entre le design et ce modèle se résout par amendement de l'un ou de l'autre, explicitement.

> **Amendement du 14 août 2026** — le design versé a fait apparaître deux écarts, tranchés ici comme le paragraphe ci-dessus l'exige.
>
> 1. **La gestion des membres quitte le Profil** et rejoint le module « Design du harness » (encore à dessiner). Elle porte sur le harness, non sur la personne : ajouter un co-auteur, transférer la propriété, retirer quelqu'un sont des gestes qu'on fait *sur une œuvre*, au même endroit qu'on en édite les kata et qu'on en scelle les versions. Le Profil répond à « à quoi ai-je accès » ; le Design du harness répondra à « qui le forge avec moi ».
> 2. **Les activités accessibles entrent au contenu contractuel.** Le design les a nommées, le §5 les rendait déjà nécessaires — les sujets appartiennent à leur praticien, encore faut-il pouvoir lire les siens. Elles manquaient au RFC, pas au produit.
>
> Les routes de gestion des membres (`GET/POST /membres`, `DELETE /membres/{id}`, `POST /transfert`) restent en service et éprouvées par les sabotages du §8 : c'est leur surface qui se déplace, pas leur contrat. **Rien n'a été dessiné pour les accueillir** — le module 3 est un emplacement réservé, et inventer sa forme serait la faute que le handoff interdit expressément.

## 5. La pratique dans un harness partagé (décision scellée : au choix du praticien, par ha)

- Chaque session porte son **praticien** : l'identité de ha s'étend — `(harness, kata, version_kata, version_coupe, cible, moteur, date, praticien)`.
- **Un ha est privé par défaut** : visible de son praticien seul (transcript, kin, options, blocs d'état).
- Le praticien peut **verser** un ha au corpus commun (statut `verse`) — il devient visible des co-auteurs. Le versement est révocable ; les agrégats déjà calculés demeurent.
- **Le système n'est pas un tiers** : les checks (carré RFC-002, métriques de banc, justesse de diagnostic RFC-003) tournent sur *tous* les ha — mais les résultats exposés aux co-auteurs sont **agrégés**, sans révéler transcripts ni kin des ha privés.
- Les **sujets** appartiennent à leur praticien : le QG montre *mes* sujets. Le partage de sujet est hors périmètre v1.
- Le cycle de vie RFC-001 (`brut → anonymisé → annoté`) est orthogonal à la visibilité (`privé | versé`) — deux axes, pas un statut de plus sur le même axe.

## 6. Impacts infrastructure

- **Middleware** : authentifie (session token) ; attribue chaque session à son praticien.
- **Dojo** : les clés virtuelles LiteLLM passent de « par usage » à **« par utilisateur et usage »** (`chat-<qui>`, `banc-<qui>`…) — c'est le mécanisme d'attribution du praticien, sans toucher à LiteLLM. Un compte Open WebUI par utilisateur ; mapping clé ↔ utilisateur dans le middleware.
- **Sécurité (SPECS §12 amendée)** : isolation par ACL **testée par sabotage** (cf. §8) ; secrets d'auth hors git ; HTTPS déjà requis.

## 7. Non-objectifs de ce RFC

Organisations et équipes ; rôles fins par asset ; harness publics ou découvrables ; invitations par lien ouvert ; quotas et facturation ; édition concurrente (deux co-auteurs sur le même kata au même moment : non géré en v1 — git en amont si besoin, limitation assumée) ; partage de sujets.

## 8. Critère « juste assez » (avec sabotages, comme toujours)

1. **Nominal** : créer un second utilisateur ; l'ajouter contributeur d'un harness ; il édite un kata, scelle une version mineure signée de son nom ; il pratique une session → son ha est privé ; il le **verse** → le propriétaire le voit.
2. **Sabotages** (chacun doit produire un refus net) : le contributeur tente de gérer les membres → 403 ; un utilisateur *non membre* tente de lire la définition → 403 ; le propriétaire tente de lire un ha **non versé** du contributeur → 403 — *ce dernier sabotage est le plus important : il prouve que la propriété du harness ne donne pas la propriété de la pratique.*
3. **Invariant** : tenter de supprimer le propriétaire ou d'en avoir deux → impossible par construction.

## 9. Changements de documents

| Document | Changement |
|---|---|
| SPECS §0 | Non-objectifs : retirer « multi-utilisateurs », inscrire « co-autorat de harness (RFC-004) » au périmètre ; maintenir « hébergement pour des tiers » hors |
| SPECS §12 | Ajouter auth locale, ACL, sabotages d'isolation |
| RFC-001/002/003 | Identité de ha étendue (`praticien`) ; « le forgeron » → « tout co-auteur, scellement signé » |
| NOTICE | Nuance : projet personnel avec contributeurs invités, tiers consentants |
| Carte de conviction | Ajouter les preuves du §8 |

---
*Note d'établi : la décision la plus importante de ce RFC n'est pas visible dans l'onglet Profil — c'est le sabotage n°3 du §8. Un harness partagé où le propriétaire verrait la pratique d'autrui par défaut transformerait chaque kin en donnée exposée, et tuerait l'honnêteté des sessions (qui dirait « je ne sais pas » en sachant son patron lecteur ?). La pratique reste à celui qui pratique ; elle se verse, elle ne se prend pas.*

---

## État d'application

| Changement | Pas | État |
|---|---|---|
| §9 — SPECS §0, non-objectifs et périmètre | 1 | appliqué |
| §9 — SPECS §12, auth locale, ACL, sabotages | 1 | appliqué — R12.1 à R12.4 |
| §9 — `NOTICE`, contributeurs tiers consentants | 1 | appliqué |
| §9 — RFC-001 et RFC-002, identité étendue et « tout co-auteur » | 1 | appliqué |
| §9 — RFC-003 | 1 | **sans objet, vérifié** — le RFC-003 a été versé depuis ; il ne parle ni du forgeron au singulier, ni de l'identité de ha, donc rien à y amender |
| §9 — carte de conviction | 1 | appliqué — `docs/carte-de-conviction.md`, les preuves du §8 y sont |
| §2.1 — utilisateur, mot de passe argon2, `identites_externes` réservée | 2 | appliqué — `kokaji/comptes/` |
| §2.2 — `harness_acl` et ses trois invariants | 2 | appliqué |
| §3 — la matrice des droits | 2 | appliqué — `kokaji/comptes/droits.py` |
| §5 — praticien sur l'identité de ha, visibilité `privee \| verse` | 2 | appliqué |
| §8 — nominal, trois sabotages, invariants | 2 | appliqué — `tests/test_isolation.py` |
| §4 — l'onglet Profil | 3 | appliqué — design versé le 13/08, implémenté ; les deux divergences sont tranchées par l'amendement du §4 |
| §6 — clés LiteLLM par utilisateur et usage | 3 | pas construit |
| §3 — édition de la définition, scellement signé | 3 | appliqué — `kokaji concevoir`, `POST /conception/epreuve` et `/scellement`, module 3 du QG |
| §4 — gestion des membres | 3 | volet « qui forge avec moi » au module 3 — **lecture seule** ; ajout et transfert restent sans surface |

Décisions prises à l'application, hors du texte du RFC :

- **La SPECS passe de v1.3 à v1.4, non de v1.4 à v1.5.** Le RFC annonce une bascule
  depuis une v1.4 qui n'existe pas dans ce dépôt : la SPECS y était en v1.3, étendue
  par les RFC-001 et RFC-002. La numérotation suit l'état réel du document.
- **Les droits sont vérifiés, l'édition ne l'est pas.** Le §3 accorde aux co-auteurs
  l'édition de la définition et le scellement de versions. Ces gestes n'existent
  nulle part dans Kokaji — ils appartiennent au mode admin, esquissé et non
  construit. La matrice les déclare donc, et rien ne les appelle encore : c'est le
  contrat, prêt pour le jour où le geste existera.
- **La visibilité est portée par le ha, pas par le corpus.** Un corpus nommé (HDS
  v0.2) reste un lieu de rangement ; `privee | verse` est un attribut de chaque ha,
  orthogonal au corpus comme au cycle `brut → annoté`.
- **`verse` n'est pas `verser`.** Le verbe existait déjà dans Kokaji au sens « faire
  entrer un ha au corpus depuis le journal ». Le RFC lui donne un second sens :
  « rendre visible aux co-auteurs ». Les deux coexistent — un ha est *versé au
  corpus* dès sa capture, et *versé aux co-auteurs* par un geste distinct de son
  praticien. Le code nomme le second `visibilite`, jamais `verser`, pour que la
  confusion ne se propage pas.
