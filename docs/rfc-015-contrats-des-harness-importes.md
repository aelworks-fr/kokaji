# RFC-015 — Le contrat f♯ s'édite sur un harness importé

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : RFC-002 (le contrat f♯ — `herite`, `produit`, seuils), RFC-008 (le harness exogène), RFC-011 (l'import d'un prompt, la coupe orpheline, D11.3), RFC-010/013 (l'axe « Contrats f♯ » devenu facette). Objet : rendre le contrat f♯ d'un kata **importé** aussi éditable que celui d'un kata natif, depuis la page, sans passer par une réécriture en densho.

---

## 1. Motivation

Un harness importé — `carto-be` sur la première instance en est l'exemple — a des kata dont la source est un texte (RFC-011), et pourtant un contrat f♯ complet : `carto-be` déclare au manifest, pour chacun de ses six kata, ce qu'il hérite et ce qu'il produit, avec statuts et seuils. Le manifest l'accepte, la forge le sert, le QG l'affiche : le contrat d'un kata décrit la **structure de son état** (RFC-002), et cela ne dépend pas de la forme de son prompt.

Une seule pièce ne suit pas : la facette « Contrats f♯ » de la page **refuse d'éditer** ce contrat dès que le kata est orphelin ou son harness exogène. Elle affiche « un texte servi tel quel ne tient pas de contrat » et ne propose que « remplacer par un densho ». Pour ajouter une contrainte à `carto-be`, il faut donc éditer le manifest à la main et sceller — le geste que toute la page existe pour éviter.

Cette phrase vient de la RFC-011 D11.3, qui tenait l'orphelin pour « un citoyen incomplet, sans contrat propre tant qu'il n'a pas été réécrit ». Elle confondait deux choses : la **source du prompt** (un texte, pas encore un densho) et le **contrat d'état** (le f♯). La première reste à réécrire ; le second n'a jamais eu à attendre.

## 2. Décisions scellées

### D15.1 — Le contrat f♯ est éditable indépendamment de la source du prompt

Un kata importé — orphelin dans un harness natif, ou tout kata d'un harness exogène — porte et **édite** son contrat f♯ exactement comme un kata natif : ajouter et retirer un champ hérité ou produit, poser son statut minimal, poser un seuil sur l'hérité. La facette « Contrats f♯ » lui ouvre la même surface qu'à un natif, et la proposition qui en sort suit le même chemin — épreuve, puis scellement — que le backend accepte déjà pour un kata exogène.

Ce qui distingue encore un kata importé reste **sa source** : un texte, servi tel quel. « Remplacer par un densho » (RFC-011 D11.3) demeure le geste, séparé, qui change cette source. Éditer le contrat ne réécrit pas le prompt, et réécrire le prompt n'efface pas le contrat.

### D15.2 — « Sans contrat » veut dire « sans `produit` », rien de plus

Un nœud s'affiche « sans contrat » et éteint au QG quand il ne déclare aucun `produit` — et non parce que sa source est un texte. C'est déjà le calcul du QG ; ce RFC le confirme et l'étend à la facette : un kata importé qui déclare un `produit` est un nœud plein, éditable, allumé. Un kata importé sans `produit` reste éteint, et la facette invite alors à lui en donner un, au lieu de le déclarer inéligible.

### D15.3 — La RFC-011 D11.3 est amendée, pas défaite

D11.3 disait « ni densho ni contrat propre tant qu'il n'a pas été réécrit ». Elle devient : « **ni densho** tant qu'il n'a pas été réécrit ; son contrat f♯, lui, s'édite dès maintenant ». Les trois encres du RFC-008 §8 tiennent inchangées : ce qui n'est pas déclaré s'affiche absent, jamais simulé — mais un contrat déclaré à la main est déclaré, donc affiché et éditable.

## 3. La surface

- Facette « Contrats f♯ » (`kokaji/qg/vue.html`) : le court-circuit `if (k.orphelin)` disparaît ; la facette rend, pour un kata importé, la même édition d'hérité et de produit que pour un natif. Les marques par nœud (`marquesDe`) gardent `densho: false` pour un orphelin — il n'y a pas de densho à compléter — mais retrouvent le contrat et le seuil.
- Facette « Coupes » : inchangée. La source d'un kata importé s'y lit toujours en texte, et « remplacer par un densho » y reste.
- Aucune route nouvelle : la proposition de contrat existe déjà (`POST /conception/coupe` et le scellement), et n'a jamais refusé un kata exogène.

## 4. Ce qui change

| Document | Changement |
|---|---|
| RFC-011 §3 D11.3 | amendée par D15.3 : le contrat s'édite avant la réécriture ; seul le densho attend |
| SPECS §2 | R2.5 précisée : orphelin dit la **source** (un texte), pas l'absence de contrat ; un kata importé peut porter un f♯ |
| docs/qg.md | la facette « Contrats f♯ » vaut pour les harness importés ; « sans contrat » = sans `produit` |
| Carnet de vigilances | + « le contrat d'un kata décrit son état, pas la forme de son prompt — ne pas confondre orphelin (source) et sans contrat (produit) » |

## 5. Non-objectifs

- La rétro-ingénierie d'un texte en gabarit + densho (N4 du RFC-008) — toujours hors sujet.
- Déduire un contrat depuis le texte du prompt : le contrat se déclare, il ne se devine pas.
- Toucher au registre autrement que par ce qu'un `produit`/`herite` neuf y nomme déjà (RFC-008 §6).

## 6. Critère « juste assez » — avec sabotages

**Nominal**, sur une copie de `carto-be` : ouvrir la facette « Contrats f♯ » d'un kata, ajouter un champ produit avec son statut, poser un champ hérité d'un amont avec un seuil, éprouver, sceller ; le manifest porte le nouveau contrat, la version majeure du kata monte (le contrat a bougé), le QG allume le nœud et montre le lien. La source du prompt n'a pas changé, et le kata reste un texte servi tel quel.

**Sabotages** :

1. Hériter d'un champ que **rien** ne produit en amont → la facette le dit « rien ne le produit », comme pour un natif, et l'épreuve le compte comme lien rompu.
2. Poser un seuil qu'aucun amont ne couvre → la clause d'ordre du RFC-002 §6.2 refuse à l'épreuve, exactement comme pour un natif.
3. « Remplacer par un densho » après avoir édité le contrat → la source devient un densho, le contrat déjà posé **reste**.
4. Un kata importé sans `produit` → nœud éteint, « sans contrat », et la facette propose d'en ajouter un — elle ne le déclare pas inéligible.

## 7. Plan d'implémentation

**Lot unique** (`kokaji/qg/vue.html`, `tests/test_vue.py`, docs) — le backend est prêt.
- Retirer le court-circuit orphelin de `rendreContrats` ; ouvrir l'édition d'hérité/produit/seuil à un kata importé ; `marquesDe` garde `densho: false` mais rend contrat et seuil.
- Tests de page : la facette d'un kata importé porte l'édition (sabotages 1, 4) ; « remplacer par un densho » reste offert à part (sabotage 3).
- Amender RFC-011 (tableau), SPECS §2, docs/qg.md, le carnet.

## 8. Tableau d'application

| Lot | État |
|---|---|
| unique — la facette s'ouvre aux importés | appliqué — `rendreContrats` n'a plus de court-circuit orphelin : un kata importé édite hérité, produit et seuils comme un natif (le serveur les sérialisait déjà de la même façon, le backend les acceptait déjà) ; `marquesDe` garde `densho: false` pour un texte importé mais rend contrat et seuil ; la facette Coupes ne dit plus « ni contrat » et renvoie vers « Contrats f♯ » ; tests de page ; RFC-011, SPECS §2, docs/qg.md et le carnet suivis |
