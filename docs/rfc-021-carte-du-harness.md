# RFC-021 — La carte du harness (le lien vers Omoikane)

**Statut :** scellée (décisions validées une à une par le propriétaire du produit, 31 octobre 2026) — **en cours d'application** (§9-10)
**Dépend de :** RFC-005 (le harness courant — appliqué) ; RFC-009 D9.4 (souveraineté) ; RFC-012 (un harness, un dépôt) ; RFC-006 (export et import de harness) ; HDS v0
**En regard de :** Omoikane-kun, l'outil de cartes de connaissance de l'écosystème — son ADR 18 (« un lien désigne une carte », `?carte=<id>`) est le prérequis de celle-ci.

---

## 1. Motivation

Kokaji tient une méthode : il la sert étape par étape, en vérifie la forme,
et en garde la pratique au corpus pour qu'on apprenne à mieux travailler
ensemble au fil des sessions. Son axe est **horizontal** : un kata après
l'autre, dans l'ordre que la chaîne déclare.

Un harness est aussi un **savoir** : la manière de résoudre un type de
problème. Ce savoir a une forme que le manifest ne montre pas. Pourquoi ces
kata-là, pourquoi dans cet ordre, ce que chacun décompose du problème, ce
qui émerge de leur enchaînement. Le manifest dit **comment jouer** la
méthode ; il ne dit pas **pourquoi elle est faite ainsi**.

Omoikane construit ce genre de savoir pas à pas, dans une vue à deux axes.
Verticalement, l'émergence et la décomposition : une proposition plus
générale au-dessus, ses parties plus concrètes en dessous. Horizontalement,
la chronologie : ce qui vient avant, à gauche de ce qui suit. Et cette
chronologie est précisément un **pré-ordre**, celui que la relation `amont`
d'une chaîne de kata définit déjà (réflexive et transitive : un kata hérite
de tout ce qui le précède).

Les deux outils se rejoignent donc sur un objet : **chaque harness peut être
modélisé dans une carte Omoikane**, où ceux qui le conçoivent (un humain et
Claude, en designers) pensent la méthode avant et pendant qu'ils la forgent.
Cette RFC pose le premier pont entre les deux : Kokaji sait quelle carte
modélise un harness, et y mène depuis le harness courant.

## 2. La correspondance : un harness se lit en carte

Une carte d'harness suit une forme fixe. Kokaji ne la fabrique pas (D21.4),
mais il l'énonce, pour que deux cartes de deux harness se lisent de la même
manière.

| Dans le harness | Dans la carte | Axe |
|---|---|---|
| le harness lui-même (`nom`, `domaine`) | une proposition, au sommet | — |
| chaque kata (`nom`, `livrable`) | une proposition, un niveau sous le harness ; « le harness **généralise** le kata » | vertical, décomposition |
| chaque champ de `produit` (`<kata>.<champ>`) | une proposition, un niveau sous son kata ; « le kata **généralise** le champ » | vertical, décomposition |
| chaque arête de la chaîne `de: A, vers: B` | « B **dépend de** A », justifiée par le `label` de l'arête | horizontal, pré-ordre |
| un nœud `externe` de la chaîne | une proposition au niveau des kata, reliée comme eux | horizontal |

Deux lectures de l'axe horizontal sont équivalentes, et la carte n'en pose
qu'une :

- **précéder**, c'est être à gauche d'un autre. « B dépend de A » se lit
  « A précède B ». C'est la relation posée.
- **suivre** est le duo inverse : « A implique B » se lit « B suit A ».
  Elle se déduit de la première, et la poser aussi doublerait chaque arête.

Omoikane n'a donc pas besoin d'une relation « précède » nouvelle : ses
relations « dépend de » et « implique » forment déjà le couple
précède / suit.

La carte peut aller **plus loin que le manifest**. On peut y poser les
raisons d'un kata, les hypothèses sur lesquelles la méthode repose, les
objections qu'on lui fait. C'est même sa raison d'être. La forme ci-dessus
n'en est que le squelette.

## 3. Décisions scellées

### D21.1 — Le lien vit dans le manifest, à `harness.carte`

Une clé facultative de l'en-tête, à côté de `domaine` :

```yaml
harness:
  id: mon-harness
  nom: Mon harness
  domaine: …
  carte: https://omoikane/?carte=<id-de-la-carte>
```

- **Facultative.** Un harness sans carte est un harness complet. Rien
  d'autre ne change pour lui.
- **Une adresse web, et rien d'autre.** La valeur est un texte non vide qui
  commence par `http://` ou `https://`. Tout autre schéma (`javascript:`,
  `data:`, `file:`, `ftp:`) est une faute de manifest, refusée par
  `kokaji valider`. La page en fait un lien cliquable, et un lien cliquable
  qui exécute du code est une faille.
- **Documentaire, comme `domaine`.** Kokaji la transporte et la montre. Il ne
  la suit jamais, ne l'interroge pas, ne vérifie pas que la carte existe.
- **Elle voyage avec le harness.** Le manifest est versionné dans le dépôt
  du harness (RFC-012) et passe à l'export et à l'import (RFC-006). Une
  instance qui importe le harness reçoit le lien. C'est assumé : un lien ne
  porte aucun droit, il n'ouvre la carte que là où elle est lisible (ADR 18
  d'Omoikane). L'instance qui reçoit le lien peut le retirer ou le changer
  comme n'importe quelle clé du manifest.

L'autre emplacement envisagé était un réglage propre à l'instance, posé
depuis le QG. Il a été écarté : la carte modélise **la méthode**, et la
méthode, c'est le manifest. Un réglage d'instance séparerait le harness de
sa carte dès le premier export.

### D21.2 — Le manifest fait foi ; la carte est l'espace de conception

`harness.yaml` reste ce que Kokaji exécute. La carte est l'endroit où l'on
pense la méthode. **Aucune synchronisation dans un premier temps** : changer
le manifest ne change pas la carte, et réciproquement.

Les deux peuvent donc diverger, et c'est assumé pour l'instant. Il revient
aux designers de reporter dans l'un ce qu'ils ont décidé dans l'autre. Si la
divergence devient un problème observé, une RFC ultérieure tranchera, avec
cette pratique pour matière.

### D21.3 — La correspondance du §2 est la forme d'une carte d'harness

Une carte créée pour un harness suit le squelette du §2 : décomposition
verticale harness → kata → champs produits, pré-ordre horizontal par
« dépend de ». Les altitudes ne sont pas fixées dans l'absolu, seulement
relativement : chaque niveau un cran sous le précédent.

### D21.4 — La carte se crée à la demande d'un designer

Ni Kokaji ni la forge ne créent de carte. Quand un designer le demande,
Claude crée la carte par le MCP d'Omoikane : `create_map` ouvre la carte
sur la question du harness, puis `suggest` y dépose le squelette du §2.
Le designer accepte ou rejette les suggestions dans Omoikane. Claude écrit
ensuite l'adresse de la carte à `harness.carte`, dans le dépôt du harness.

Kokaji ne gagne donc **aucune émission réseau** (D9.4) : il ne connaît
d'Omoikane qu'une adresse qu'on lui a écrite.

### D21.5 — Un lien par harness, dans le flanc, sous le harness courant

- La page montre un lien **« Carte »** dans le territoire *Harness* du flanc,
  après les sous-vues Design et QG, quand le harness courant déclare une
  carte. Le lien s'ouvre dans un nouvel onglet : la carte n'est pas une vue
  de Kokaji.
- Il apparaît aussi quand l'instance ne sert qu'un harness, donc quand le
  sélecteur est caché : ce qui commande l'affichage est le harness courant,
  pas le nombre de harness.
- Sans carte déclarée, rien ne s'affiche : pas de lien vide, pas
  d'invitation à en créer une.
- L'offre des harness (`GET /harness`) porte la carte de chacun, `null` sans
  carte. La page n'a rien d'autre à lire.
- **Pas de lien par kata**, et **rien dans le chat**. La carte est celle du
  harness entier.

## 4. Souveraineté

Un lien n'est pas une émission : la page le montre, la personne choisit de
le suivre, et c'est son navigateur qui va vers Omoikane, jamais Kokaji.

La trempe du produit refuse toute adresse en dur dans le dépôt du produit.
Elle continue de le faire : la carte d'un harness vit dans **le dépôt du
harness** (RFC-009 D9.1), jamais dans celui du produit. L'Atelier ne déclare
donc pas de carte. Les tests du produit utilisent des adresses que la
trempe tolère (`localhost`, un hôte sans domaine).

## 5. Modèle (extrait de manifest)

```yaml
harness:
  id: resolution
  nom: Résolution d'un problème ouvert
  version: 0.1.0
  langue: fr
  domaine: >-
    Mener un problème ouvert de son énoncé jusqu'à une décision argumentée.
  carte: https://omoikane/?carte=<id-de-la-carte>
```

Et ce que l'offre en dit :

```json
{ "id": "resolution", "nom": "Résolution d'un problème ouvert", "version": "0.1.0",
  "role": "proprietaire", "archive_le": null, "depot": "à jour",
  "carte": "https://omoikane/?carte=<id-de-la-carte>" }
```

## 6. Changements et non-objectifs

**Changements de documents :**

- **SPECS §2** : le squelette du manifest gagne `carte`, commenté.
- **HDS v0** (`docs/hds-v0.md`) : la table de `harness` gagne la ligne
  `carte`.

**Non-objectifs :**

- **La synchronisation** dans un sens ou dans l'autre (D21.2).
- **La génération automatique** du squelette par Kokaji (une commande
  `kokaji carte`, par exemple). Elle ferait de Kokaji un client d'Omoikane,
  ou au moins un producteur de son format. Elle n'est envisagée qu'une fois
  que plusieurs cartes faites à la main auront montré ce qui se répète.
- **Un lien par kata**, vers la proposition qui le modélise. Omoikane ne sait
  pas encore désigner une proposition par son adresse.
- **Le lien dans le chat.**
- **Le MCP de Kokaji** (SPECS R7.4, ultérieur). Il permettrait à Claude de
  lire un harness et sa pratique pour le cartographier sans copier le
  manifest à la main. C'est un autre geste, et une autre RFC.

---

## 7. Critère « juste assez » et sabotages

1. **Nominal — le lien suit le harness courant** : deux harness, l'un avec
   carte, l'autre sans. Choisir le premier montre « Carte », qui mène à son
   adresse dans un nouvel onglet. Choisir le second fait disparaître le lien.
2. **Nominal — un seul harness** : une instance mono-harness dont le harness
   déclare une carte montre le lien, sans sélecteur.
3. **Nominal — l'offre** : `GET /harness` porte `carte` pour chaque harness,
   `null` sans carte.
4. **Sabotage — le schéma** : `carte: javascript:alert(1)`, `carte: data:…`,
   `carte: ftp://hote/x` sont **refusés** par la validation du manifest, avec
   la clé fautive nommée (`harness.carte`).
5. **Sabotage — la forme** : une carte vide, faite d'espaces, ou qui n'est pas
   un texte (`carte: 12`, `carte: [a]`) est **refusée** de même.
6. **Sabotage — la souveraineté** : une adresse en dur glissée dans l'Atelier
   fait **rougir** la trempe du produit. Le vérificateur existe déjà ; il
   doit être vu refuser une `carte` comme une autre adresse.

---

## 8. Note d'établi

Cette RFC est née d'une remarque faite en concevant l'écosystème : la
flèche du temps, celle qui range les kata de gauche à droite, est
exactement la notion de pré-ordre de l'analyse entropique. La chaîne d'un
harness portait déjà ce pré-ordre sous le nom d'`amont` ; Omoikane en
faisait son axe horizontal sans le nommer ainsi. Les deux outils avaient le
même axe, et rien ne les reliait.

Les cinq décisions ont été posées une à une, question par question, avant
toute ligne de code. Elles sont volontairement minces : un lien, une
correspondance, et rien de ce qui ferait de Kokaji un client d'Omoikane.
On saura ce qu'il faut synchroniser une fois qu'on aura vu, sur de vraies
cartes, où le manifest et la carte divergent.

---

## 9. Plan d'implémentation

Trois lots côté produit, un côté instance. Chaque lot porte ses sabotages.

- **Lot 0 — les documents.** Cette RFC dans `docs/` ; SPECS §2 et
  `docs/hds-v0.md` amendés.
- **Lot A — le manifest et l'offre** (`kokaji/hds/modele.py`,
  `kokaji/hds/manifest.py`, `kokaji/middleware/exploitation.py`). La clé
  `harness.carte`, lue et validée (sabotages 4 et 5) ; `carte` dans l'offre
  (critère 3).
- **Lot B — la page** (`kokaji/qg/vue.html`). Le lien « Carte » du flanc,
  qui suit le harness courant (critères 1 et 2).
- **Lot C — l'instance.** À la première demande d'un designer : créer la
  carte d'un harness par le MCP d'Omoikane, écrire son adresse dans le dépôt
  du harness, voir le lien dans le QG en service.

## 10. Tableau d'application

| Lot | État |
|---|---|
| 0 — les documents | appliqué (31 octobre 2026) — RFC dans le produit ; SPECS §2 et `docs/hds-v0.md` amendés |
| A — le manifest et l'offre | à faire |
| B — la page | à faire |
| C — l'instance | à faire — attend la première demande |
