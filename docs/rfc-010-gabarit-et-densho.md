# RFC-010 — Écrire la définition à la main : le gabarit, les densho, la coupe qu'on voit

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : HDS v0.1 (template, source d'un kata), SPECS §4 (forge), RFC-002 (les adjonctions : `herite` / `produit`), RFC-004 §3 (éditer la définition est un droit de tout co-auteur), RFC-006 (proposition, épreuve, scellement). Objet : donner aux co-auteurs, depuis le QG, la main sur **le texte** qui définit chaque étape — et leur montrer ce que la forge en fait.

---

## 1. Motivation

Le module « Design du harness » édite aujourd'hui trois choses, toutes dans le manifest : le partitionnement, les contrats f♯, la trempe. Il ne touche jamais au **texte du prompt**. Or c'est le texte qui fait l'étape : la posture, les interdits, les questions, ce qu'on livre et quand on passe la main.

Ce texte vit en deux endroits que le module ignore :

- `template.md` — le gabarit commun, où sont écrits les invariants demandés à toute la chaîne. Le HDS le dit déjà : « les blocs fixes portent la doctrine du harness ». C'est le **ryū** rendu en texte.
- `kata/<id>.yaml` — la source d'un kata : ce qu'il reçoit de l'amont, ce qu'il doit réunir pour l'aval, avec les niveaux exigés, et sa trempe locale. C'est le **densho** du kata : le rouleau de transmission qui, mêlé au gabarit, donne la coupe.

Aujourd'hui, écrire l'un ou l'autre demande un éditeur de fichiers et un `git push`. Et personne ne voit la coupe forgée avant qu'elle ne soit servie au chat. Un forgeron qui ne voit pas sa lame règle son geste à l'aveugle.

Le modèle de proposition sait pourtant déjà porter les variables d'un kata (`source`) et le scellement les écrit. Ce qui manque n'est pas une mécanique : c'est **une surface**, et une pièce — le gabarit — que la proposition ne connaît pas.

## 2. Ce que le vocabulaire dit, et ce qu'il gagne

Trois niveaux, reliés par les adjonctions du RFC-002 :

```
GABARIT (template.md)        — la doctrine du ryū : ce que toute étape doit tenir
   │  + densho du kata
   ▼
DENSHO (kata/<id>.yaml)      — l'étape : rôle, questions, interdits, livrable, passage,
   │  + adjonctions             ce qu'elle hérite (amont), ce qu'elle produit (aval)
   ▼
COUPE (dist/coupes/…)        — le kiri : le prompt tel que le chat le reçoit, par cible
```

Les adjonctions ne s'écrivent pas dans le texte : elles **y entrent à la forge**. Le bloc « ce que tu reçois de l'amont » vient de `herite` ; le bloc d'état et le passage viennent de `produit`, de la chaîne et de la cible. Éditer le densho, c'est donc éditer les variables ; éditer les adjonctions, c'est l'axe « Contrats » qui existe déjà. Ce RFC ne déplace rien : il complète.

**Le mot « densho » entre au registre d'imagerie** (SPECS §1.2) pour « la source d'un kata ». Le registre technique reste `source` — code, manifest, API n'en connaissent pas d'autre.

## 3. Décisions scellées

### D10.1 — Le gabarit entre à la proposition

La proposition gagne une clé `template` : le texte entier du gabarit. Même régime que tout le reste — partielle (absente, le gabarit ne bouge pas), éprouvée sur une copie, écrite au scellement seulement si l'ensemble tient.

Le gabarit s'édite **comme texte brut, variables comprises**. En v1 la page n'assiste pas la pose des `{{ variables }}` ; elle les montre, et la forge refuse un gabarit dont une variable n'a pas de valeur — comme aujourd'hui. Une assistance à la pose (choisir une variable dans la liste du HDS) est envisagée, pas décidée.

Un gabarit modifié change l'empreinte de **toutes** les coupes du harness. La version du harness monte en **mineure** : la doctrine change, aucun contrat ne bouge. Si un co-auteur veut marquer une refonte du ryū comme majeure, il le fait par le motif du scellement, pas par une mécanique.

### D10.2 — Le densho s'édite par ses variables

Ce que la page édite d'un kata est exactement ce que la forge lit dans sa source : `role`, `interdits`, `questions`, `livrable_nom`, `livrable_structure`, `passage`, `natures`. Rien de plus, rien d'inventé. La proposition porte déjà ces variables (`source`) ; le scellement les écrit déjà, sans perdre les commentaires du fichier (RFC-006, « le manifest est une source »).

Les niveaux exigés sur chaque donnée — `herite` avec ses statuts minimaux, `produit` avec ses statuts garantis — restent sur l'axe « Contrats ». Un densho ne redit pas son contrat.

### D10.3 — La coupe se voit, s'exporte, et la lecture n'écrit rien

Une route rend la coupe d'un kata pour une cible, **forgée en mémoire** depuis la définition en place ou depuis une proposition non scellée. C'est la forge ordinaire, sur une copie, comme l'épreuve : rien n'est écrit dans `dist/`, rien n'est servi. On voit la lame avant de la tremper.

L'export est cette même coupe, remise telle quelle — le texte avec son estampille. Versionner ces exports est un **non-objectif** de ce RFC (§6) : la coupe est un dérivé, régénérable, et son empreinte suffit à la reconnaître.

### D10.4 — Un harness adopté se lit, ne s'édite pas par cet axe

Un harness exogène (RFC-008) n'a ni gabarit ni densho : ses kata sont des textes servis tels quels. Cet axe montre leurs coupes, et refuse d'y écrire — le RFC-011 dit comment un texte importé devient éditable.

### D10.5 — Rien ne s'enregistre qui ne tient

Reconduit du RFC-006 : le gabarit et les densho passent par l'épreuve. Un gabarit qui casse une variable, un densho qui vide une variable obligatoire, un texte qui contient un mot du vocabulaire interdit — le verdict le dit, et rien n'est écrit.

## 4. La surface

### 4.1 Lecture — `GET /conception`

La réponse gagne :

```yaml
template:
  chemin: template.md
  texte: "…"
  variables: [en_tete, kata_nom, role, …]   # celles que le gabarit cite
cibles: [{ id: sobre, etat_structure: false, en_tete: Atelier }, …]
kata:
  - id: idee
    …                                      # inchangé
    source:                                # le densho, tel que la forge le lit
      version: 1.0.0
      role: "…"
      interdits: []
      questions: []
      livrable_nom: ""
      livrable_structure: []
      passage: "…"
      natures: []
```

Pour un harness exogène, `template` est absent et `source` porte `{ texte: "…" }`.

### 4.2 Rendu — `POST /conception/coupe`

```yaml
kata: idee
cible: sobre
proposition: { … }     # facultatif — la même proposition que l'épreuve
```

Rend `{ texte, estampille }`, ou un verdict de forge (`ForgeImpossible`) en 422 avec sa raison. Réservé aux co-auteurs, comme `/conception`.

### 4.3 Écriture — l'épreuve et le scellement, inchangés

`/conception/epreuve` et `/conception/scellement` acceptent `template` dans la proposition. Le verdict liste `template` parmi les changements ; les versions annoncées avant le scellement disent quels kata montent (aucun pour un gabarit seul : c'est le harness qui monte).

### 4.4 La page — un quatrième axe : « 4 · Coupes »

Dans « Design du harness », à côté de Partitionnement, Contrats et Trempe. Deux colonnes :

- **à gauche, ce qu'on écrit** — le gabarit, texte brut avec ses variables ; puis le kata choisi et son densho, une zone par variable (rôle et passage en texte, interdits et questions et structure du livrable en listes, natures en cases) ;
- **à droite, ce qu'on obtient** — la coupe rendue, une vue par cible, rafraîchie à la demande depuis le brouillon courant. Un bouton la copie ou la télécharge telle quelle.

Le brouillon suit la règle de la page : il vit dans la page, l'épreuve retombe à la moindre retouche, rien n'est retenu entre deux visites. Le flux ensuite est celui d'aujourd'hui : éprouver, puis sceller et signer.

Le handoff de design réservait le module 3 sans en dessiner la forme ; les trois axes existants ont posé une forme depuis. Le quatrième la suit, et n'invente rien d'autre.

## 5. Ce qui change, et ce qui ne change pas

| Document | Changement |
|---|---|
| SPECS §1.2 | « densho » au registre d'imagerie, pour la source d'un kata |
| SPECS §4 | R4.4 (proposée) : la coupe d'un kata se rend en mémoire depuis une définition non scellée, sans rien écrire |
| HDS v0.1 | inchangé — le gabarit et la source d'un kata y sont déjà décrits |
| RFC-004 §3 | inchangé — « éditer la définition (template, kata, …) » était déjà un droit de tout co-auteur ; ce RFC le rend possible |
| RFC-006 | la proposition gagne `template` ; le scellement l'écrit |
| docs/qg.md | le quatrième axe |

## 6. Non-objectifs

- Versionner ou archiver les exports de coupes : la coupe est un dérivé (R4.1), son empreinte la nomme.
- Assister la pose des variables dans le gabarit (envisagé, §D10.1).
- Réécrire un texte importé en gabarit ou en densho — la rétro-ingénierie est le N4 du RFC-008, il aura sa RFC.
- Toute évolution de la trempe, du chat ou des comptes — chacune aura la sienne.

## 7. Critère « juste assez » — avec sabotages

**Nominal**, sur l'Atelier : depuis le QG, modifier une question du densho de `idee`, voir la coupe `idee@sobre` la porter avant tout scellement ; modifier le gabarit, voir les trois coupes changer ; éprouver, sceller ; `kokaji forge` régénère les coupes à l'identique de ce que la page montrait ; le chat sert la nouvelle coupe.

**Sabotages** — chacun doit être vu refuser :

1. Un gabarit qui cite `{{ inconnue }}` → l'épreuve refuse, nomme la variable, rien n'est écrit.
2. Un densho dont `questions` est vidé → refusé : variable obligatoire vide.
3. Un mot du vocabulaire interdit du harness glissé dans le gabarit → la trempe statique refuse dans l'épreuve.
4. `POST /conception/coupe` avec une proposition → `dist/coupes/` et `kata/` sont inchangés après l'appel, octet pour octet.
5. Un contributeur non membre → 403 sur la coupe comme sur le reste (R12.3).
6. Un harness exogène → la coupe se lit ; une proposition qui porte `template` ou `source` → refusée, nommée.

## 8. Plan d'implémentation

Trois lots, chacun livrable seul, dans cet ordre.

**Lot 1 — le modèle et la lecture** (`kokaji/conception/`, `kokaji/middleware/service.py`, tests)
- `Proposition.template` ; `_changements` le nomme ; `juger` le pose sur la copie ; `sceller` écrit le fichier que `harness.template` désigne.
- `/conception` renvoie `template`, `cibles` et `source` par kata.
- Tests : `test_conception.py` — le gabarit tient / ne tient pas, s'écrit au scellement, monte le harness en mineure ; la lecture expose gabarit et densho ; un exogène expose le texte et refuse l'écriture.

**Lot 2 — le rendu** (`kokaji/conception/brouillon.py`, `service.py`, tests)
- Extraire de `juger` la construction de la copie éprouvée, réutilisable ; `rendre_coupe(racine, kata, cible, proposition)` qui forge en mémoire.
- `POST /conception/coupe`, 422 sur `ForgeImpossible`, 403 hors ACL.
- Tests : la coupe rendue égale celle que `kokaji forge` écrit ; rien n'est écrit ; la proposition se voit dans le rendu.

**Lot 3 — la page** (`kokaji/qg/vue.html`, `tests/test_vue.py`, `tests/test_rendu.py`, `docs/qg.md`)
- L'axe « 4 · Coupes », le brouillon étendu (`template`, `source` par kata), `proposition()` qui ne renvoie que ce qui bouge, la coupe rendue par cible, copier et télécharger.
- La vigie mesure le rendu de l'axe aux trois largeurs, comme les autres.

Puis les six sabotages du §7, joués et consignés dans la carte de conviction.

---
*Note d'établi : la forge savait tout faire, et le forgeron n'en voyait rien. Ce RFC ne lui donne pas un nouvel outil ; il lui rend la vue sur sa lame, et la main sur le rouleau qui la décrit.*
