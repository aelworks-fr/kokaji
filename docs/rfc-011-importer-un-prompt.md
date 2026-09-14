# RFC-011 — Importer un prompt tel quel, comme gabarit ou comme kata

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : RFC-008 (l'échelle d'adoption, la coupe orpheline), RFC-010 (le gabarit et les densho s'éditent depuis le QG), RFC-006 (proposition, épreuve, scellement), RFC-004 §3. Objet : faire entrer dans un harness un texte écrit ailleurs, **sans le réécrire**, à l'une des deux places où un texte peut vivre.

---

## 1. Motivation

Le RFC-008 sait adopter un harness entier né hors de la forge : des prompts faits main deviennent des kata orphelins, servis tels quels. Il ne sait pas faire entrer **un** texte dans un harness qui existe déjà — et c'est le geste le plus fréquent : on a un prompt qui marche, on veut le mettre à l'épreuve dans un ryū, comme doctrine commune ou comme une de ses étapes.

Le RFC-008 §3 nomme la suite : la rétro-ingénierie d'un texte en tamahagane est son N4, différé. Ce RFC ne l'entame pas. Il pose le premier pas, celui que le RFC-008 §5 a déjà décidé pour un harness entier : **tel quel, avec sa provenance**.

## 2. Deux places pour un texte

Un prompt importé peut devenir :

- **le gabarit** d'un harness natif — il remplace `template.md`. Le texte n'a pas de `{{ variables }}` : la forge le rend alors identique pour chaque kata, et n'exige rien de leurs densho. Les variables se posent ensuite, à la main (RFC-010 D10.1), quand le forgeron décide ce qui varie d'une étape à l'autre.
- **la base d'un kata** — le texte devient la source de ce kata, servi tel quel. Le kata est **orphelin dans un harness natif** : il n'est pas assemblé depuis le gabarit, il porte sa provenance, et le forgeron le remplacera un jour par un densho.

Dans les deux cas, la promesse du RFC-008 §6 tient : le texte d'origine **n'est pas réécrit**. L'instrumentation (cible `etat_structure: true`) s'ajoute par enrichissement, jamais par retouche.

## 3. Décisions scellées

### D11.1 — Importer est une proposition, pas un geste à part

Un import passe par la proposition du RFC-006, éprouvée et scellée comme le reste :

```yaml
template: "…"                         # le texte, tel quel — RFC-010 D10.1
importe:                               # la provenance, estampillée une fois
  template: { source: "", version_source: "", date_import: "" }
```

ou, pour un kata :

```yaml
kata:
  - { id: devis, nom: Répondre à un devis, livrable: Devis }
source:
  devis: { texte: "…" }                # un texte, pas des variables
importe:
  devis: { source: "", version_source: "", date_import: "" }
```

Le scellement écrit le texte à sa place, calcule son empreinte, et pose la provenance au manifest. Un import qui ne tient pas — vocabulaire interdit, marqueur de gabarit résiduel — ne s'enregistre pas.

### D11.2 — L'orphelinat descend au niveau du kata

Le RFC-008 marque l'exogène au niveau du harness : tous ses kata sont des textes. Ce RFC le fait descendre : **un kata dont la source est un texte** (`source: kata/<id>.md`) est orphelin, dans un harness qui par ailleurs forge. La forge choisit par kata, non par harness ; la trempe statique applique au texte ce qu'elle applique à une coupe — vocabulaire, marqueurs, décomptes ; le registre n'est pas consulté pour lui.

La provenance, aujourd'hui « réservée aux harness `exogene: true` », devient déclarable **par kata** :

```yaml
kata:
  - id: devis
    source: kata/devis.md
    provenance: { source: "", version_source: "", checksum_import: "", date_import: "" }
```

Un harness `exogene: true` reste ce qu'il est : le cas où tous les kata sont ainsi. Rien n'est réécrit du RFC-008 ; sa règle devient un cas particulier.

### D11.3 — Un kata orphelin est un citoyen incomplet, et le QG le dit

Il se sert, se capture, se juge (N0) ; il se situe dans la chaîne (N1) ; il s'instrumente si le harness déclare ses champs (N2). Mais il n'a ni densho ni contrat propre tant qu'il n'a pas été **réécrit** — geste hors de ce RFC. L'axe « Coupes » le montre en lecture, avec sa provenance, et propose une seule action : *remplacer par un densho* — qui crée une source de forge vide (la semence du RFC-006) et laisse le texte à côté, pour référence, jusqu'au scellement suivant.

Le carré, l'Épure, la carto appliquent les trois encres du RFC-008 §8 à ce kata seul : ce qui n'est pas déclaré s'affiche absent, jamais simulé.

### D11.4 — Importer en gabarit périme les densho, et le dit

Remplacer le gabarit par un texte sans variables rend les densho **inertes** : leurs variables ne sont plus citées, la forge les ignore. Rien n'est perdu — les fichiers restent — mais l'épreuve le dit en clair : « le gabarit ne cite aucune variable ; N kata gardent un densho que rien ne lit ». C'est une information, pas un refus : c'est le premier pas attendu avant de poser les variables.

## 4. La surface

- `Proposition` gagne `importe` ; `source.<kata>.texte` est reconnu comme texte et non comme variables.
- La page (axe « 4 · Coupes », RFC-010) gagne un bouton « importer un texte » à chaque place : sur le gabarit, sur un kata. Il ouvre une zone de collage et trois champs de provenance. Rien ne part avant l'épreuve.
- L'adoption d'un harness entier (`kokaji adopter`, RFC-008) ne change pas ; elle devient un import multiple.

## 5. Ce qui change

| Document | Changement |
|---|---|
| HDS v0.1 → v0.2 | `provenance` déclarable par kata ; une source `.md` est un texte servi tel quel |
| SPECS §2 | R2.5 (proposée) : un kata est natif ou orphelin ; un harness est exogène quand tous ses kata sont orphelins |
| RFC-008 | §3 : l'échelle d'adoption vaut par kata ; §4 : `exogene: true` devient le cas où tous le sont |
| RFC-010 | l'axe « Coupes » porte l'import et le geste « remplacer par un densho » |
| Carnet de vigilances | + « un gabarit sans variable rend les densho inertes sans les effacer — l'épreuve doit le dire » |

## 6. Non-objectifs

- La rétro-ingénierie d'un texte en gabarit + densho (N4 du RFC-008) — RFC dédiée à venir.
- Importer depuis une URL ou un dépôt : le texte se colle, en v1.
- Fusionner un texte importé avec un densho existant.

## 7. Critère « juste assez » — avec sabotages

**Nominal**, sur une copie de l'Atelier : importer un texte comme kata `devis` → il apparaît dans la chaîne, sa coupe est le texte plus l'estampille, le chat le sert, un ha se capture avec sa provenance ; importer un texte comme gabarit → les trois kata natifs rendent le même texte, l'épreuve dit que les densho sont inertes ; poser `{{ role }}` dans le gabarit → les densho reprennent vie, une coupe par kata.

**Sabotages** :

1. Un texte avec un marqueur de gabarit (`[À COMPLÉTER]`, `TBD`) → la trempe statique refuse à l'épreuve.
2. Un texte qui cite un mot du vocabulaire interdit du harness → refusé.
3. Une provenance sans `source` → refusée : on ne sait pas d'où ça vient, on n'enregistre pas.
4. Un kata orphelin avec un `herite` déclaré → faute de manifest : un texte ne tient pas de contrat.
5. L'Épure d'un harness dont un seul kata est orphelin → **ce** carré éteint, les autres vivants.
6. Après import puis scellement, le fichier écrit est identique octet pour octet au texte collé.

## 8. Plan d'implémentation

À faire après le lot 2 du RFC-010, dont il dépend.

**Lot A — le kata orphelin dans un harness natif** (`kokaji/hds/`, `kokaji/forge/`, `kokaji/trempe/statique/`, tests)
- Le manifest accepte `provenance` par kata ; une source `.md` marque le kata orphelin ; validation : un orphelin sans contrat.
- La forge choisit par kata ; la trempe statique traite un texte comme une coupe.
- Tests : `test_hds.py`, `test_forge.py`, `test_trempe_statique.py` — un harness mixte se forge et se trempe ; sabotages 1, 2, 4.

**Lot B — l'import comme proposition** (`kokaji/conception/`, `service.py`, tests)
- `Proposition.importe`, `source.<kata>.texte` ; l'épreuve pose le texte sur la copie ; le scellement l'écrit, calcule l'empreinte, pose la provenance ; l'avertissement D11.4.
- Tests : `test_conception.py` — sabotages 3 et 6, le nominal.

**Lot C — la page et les observatoires** (`vue.html`, `kokaji/qg/`, `docs/qg.md`, `docs/hds-v0.md`)
- Les boutons d'import, le geste « remplacer par un densho », les trois encres par kata (sabotage 5).
- Mise à jour du HDS et des RFC touchées (§5).

## 9. Tableau d'application

| Lot | État (14 septembre 2026) |
|---|---|
| A — le kata orphelin dans un harness natif | appliqué — `Kata.orphelin` et `Kata.provenance` ; une source `.md` fait l'orphelin ; sa provenance est exigée, un contrat refusé (sabotage 4), la provenance interdite à un natif ; la forge choisit par kata, une cible instrumentée le sert sans bloc (D11.3) ; la trempe statique trempe le texte (sabotages 1, 2) et ne consulte pas le registre pour lui ; le scellement ne lui sème pas de densho ; la page le lit sans l'éditer |
| B — l'import comme proposition | à faire |
| C — la page et les observatoires | à faire — les trois encres par kata, le geste « remplacer par un densho » |

---
*Note d'établi : le RFC-008 disait qu'un harness n'est pas dedans-ou-dehors, mais plus ou moins* su *par la forge. Ce RFC dit la même chose d'un kata : un texte collé est une étape que la forge ne sait pas encore lire — pas une étape qu'elle refuse.*
