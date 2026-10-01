# RFC-020 — Import de conversation (la pratique rapportée)

**Statut :** scellée (décisions validées en keiko, 2026) — **en cours d'application** (lots 0 et A appliqués le 30 septembre 2026, §9-10)
**Dépend de :** RFC-014 (données vivantes — appliquée) ; RFC-016 (kata d'action — scellée) ; standard de corpus (champ `source`, complétude) ; doctrine des trois encres (déclaré / observé / idéalisé)
**En miroir de :** RFC-008 (import de harness exogènes) — la 008 importe la **forme** (le kata né ailleurs), la 020 importe la **pratique** (le déroulé joué ailleurs).

---

## 1. Motivation

Des conversations utiles au harness se jouent hors du dojo — dans un autre
outil, un autre contexte, avant même que le kata existe. Aujourd'hui elles
sont perdues, ou converties à la main (le tout premier cas du corpus était
exactement cela : un déroulé externe transcrit artisanalement). Cette RFC
fait de ce geste artisanal un régime du produit : **importer une
conversation, la référencer, et la soumettre à une trempe a posteriori**
pour qu'elle entre dans la boucle standard — on observe, on améliore,
on itère.

Le principe directeur : **on ne peut pas refuser que le monde existe.**
On préfère une pratique déroulée au sein d'un kata, dans un dojo Kokaji —
mais toute expérience est bonne à prendre, de façon ouverte, à une seule
condition : **rester au courant de sa source.** Un ha externe est par
nature moins crédible qu'un ha déroulé en interne dans la version courante
du kata ; il n'en est pas moins une source d'expérience potentiellement
instructive. La crédibilité est un **axe de lecture**, jamais une porte
d'entrée.

Ce besoin est aigu : le corpus est aujourd'hui **trop mince** pour
refléter la réalité. Chaque scénario réellement déroulé — même hors dojo,
même imparfaitement — est de la matière rare.

## 2. La frontière : est importable ce qui est re-percevable

Le périmètre de cette RFC est la **conversation** au sens des premières
versions de Kokaji. Dans le modèle étendu (RFC-016), ce mot a une adresse
précise : le kata dont les effets se limitent au canal `modele` — le cas
`echange`. Et cette restriction n'est pas une prudence de v1, c'est un
**théorème de la 016** :

- Une conversation ne touche que le modèle partagé. Son transcript est la
  trace complète de ce qui s'est passé : tout peut être **re-perçu après
  coup** par un juge ou un humain qui relit. La trempe a posteriori est
  donc légitime.
- Un déroulé externe qui prétend avoir agi sur le monde (« j'ai lancé les
  tests, tout passait ») est inimportable en l'état : le monde d'alors ne
  peut plus être échantillonné, et l'interdit n°2 de la 016 — **pas de
  monde auto-rapporté** — bloque précisément ce cas.

Frontière de la RFC : **l'import accepte les déroulés à effets `modele`
seuls ; tout effet monde allégué est refusé à l'import** (voir sabotage
§7.4). La vieille notion de conversation est le nom de ce périmètre.

---

## 3. Décisions scellées

### D20.1 — Entrée : collage brut, découpage assisté

L'utilisateur **colle le texte** de la conversation. L'instance découpe les
tours par heuristique simple et lui **montre le découpage pour correction**
avant enregistrement. Aucun format imposé, aucune conversion à sa charge —
le geste doit rester assez léger pour être fréquent. Le découpage corrigé
fait partie de la déclaration : c'est l'utilisateur qui affirme « voilà les
tours », à l'encre déclarée.

À l'enregistrement, l'utilisateur déclare : le **kata de rattachement**
(obligatoire), le sujet (kin), le moteur et la date d'origine s'il les
connaît, et la source (outil d'origine, en texte libre).

### D20.2 — Entrée directe au corpus : la provenance est un axe, pas une porte

Le ha importé entre **directement** au corpus, au statut `brut` du cycle
de vie standard (brut → anonymisé → annoté, visibilité privé/versé) —
ni quarantaine, ni promotion, ni geste d'admission. **Aucun jugement ne
conditionne l'entrée** : juger une expérience digne ou indigne d'exister
n'est pas un concept de Kokaji.

Ce qui est non négociable, c'est la marque : l'axe de **provenance** —
`observé` (joué au dojo) ou `rapporté` (importé) — est **obligatoire et
indélébile**. Anonymisation, annotation, export, réimport : rien n'efface
`rapporté`. Toute vue qui montre le ha montre son encre.

### D20.3 — La trempe a posteriori : des critères neutres, pas un verdict d'admission

La trempe a posteriori **tourne et valide des critères neutres** — les
mêmes exigences pour tous, dont les résultats s'attachent au ha sans
jamais commander son existence :

1. **Déterministe** : les checks de session du kata (vocabulaire interdit,
   registre) tournent sur le transcript tel quel. Les checks qui supposent
   des blocs d'état émis sont **éteints, et affichés éteints** — l'honnêteté
   d'affichage de la 008 vaut ici.
2. **Judge** : contrôle de **conformité au kata déclaré** + grille de
   qualité de l'échange, juge ≠ moteur d'origine (quand ce dernier est
   connu). *Précision d'établi* : la conformité au kata est un **invariant
   de Kokaji** — une seule question, générique, posée devant la coupe du
   kata déclaré — au même titre que les invariants du bloc d'état ; la
   grille de qualité, elle, reste celle du harness (`trempe.grille_judge`),
   aucune question de domaine n'entre dans le code. Le rattachement au kata reste une **déclaration de
   l'utilisateur** ; le juge peut la contester, et son verdict s'affiche
   **à côté** de la déclaration — jamais à sa place. Deux encres, jamais
   fusionnées. Un déroulé contesté reste au corpus : les presque-conformes
   sont instructifs.
3. **Humain** : la grille standard, avec l'encre de provenance visible
   pendant la notation.

La trempe a posteriori est **rejouable** : chaque passage s'ajoute aux
résultats, daté et versionné — la boucle standard, observer, améliorer,
itérer.

### D20.4 — Le scénario comme semence : nourrir le corpus de cas

La valeur d'un ha rapporté ne tient pas d'abord à la qualité de son
exécution — elle tient à son **scénario** : un déroulé réel est une
source d'inspiration pour le corpus de cas de test qu'on cherche à
constituer pour refléter la réalité.

Le produit outille ce geste : depuis un ha rapporté, on peut **semer un
cas de test** (le gabarit du standard de corpus se pré-remplit depuis le
déroulé : kin, contexte, déroulé-type). Le cas semé porte un lien
`seme_par:` vers son ha d'origine — la traçabilité de l'inspiration,
même encre, même honnêteté. Un scénario vaut d'être gardé même quand
l'exécution qui l'a révélé était médiocre : c'est souvent là qu'on voit
ce que le kata devra mieux traiter.

### D20.5 — Au banc : exclu par défaut, tranche dédiée

Les ha `rapporté` sont visibles partout en observation, à leur encre. Mais
ils sont **exclus par défaut** des agrégats du banc et de la
non-régression ; une **tranche dédiée** (`provenance: rapporté`) permet de
les inclure explicitement. Le doute ne se dilue jamais dans une moyenne :
aucun chiffre agrégé ne mélange silencieusement observé et rapporté.

Moins crédible ne veut pas dire moins utile : la tranche rapportée est
précisément celle qui montre le harness confronté à des déroulés qu'il
n'a pas produits lui-même.

---

## 4. Finalité : l'optimum global, pas le local

Le but de fond de Kokaji reste de trouver le **harness idéal** — avec,
peut-être, chacun des kata idéaux — en optimisant **le tout, et non le
local**. Cette RFC y contribue directement : un corpus constitué
uniquement de déroulés internes ne fait explorer au harness que son
propre voisinage — chaque kata s'ajuste à ce qu'il produit déjà, et
l'ensemble converge vers un optimum local. L'expérience rapportée est
l'antidote : des scénarios que le harness n'a pas engendrés, venus du
monde tel qu'il est, qui tirent l'exploration hors du voisinage.
C'est pour cela qu'on accueille ouvertement, et qu'on marque plutôt
qu'on ne filtre : **filtrer appauvrit l'exploration, marquer préserve
le jugement.**

Les règles quantitatives — quota nécessaire et suffisant de cas réels,
règles d'enrichissement du corpus — viendront plus tard, quand la matière
existera (non-objectif §6).

---

## 5. Modèle (extrait de fiche)

```yaml
# fiche du ha importé
provenance: rapporte            # indélébile — observé | rapporté
statut: brut                    # cycle de vie standard, directement
declaration:                    # tout ceci est à l'encre déclarée
  kata: cadrage
  version_kata_supposee: "2.x"  # optionnel, si l'utilisateur sait
  kin: "refonte du portail adhérents"
  moteur_origine: inconnu
  date_origine: 2026-08-12
  source_texte: "conversation menée dans un chat généraliste"
  decoupage_corrige: true
conformite:                     # rempli par la trempe a posteriori
  verdict: conteste             # conforme | conteste
  detail: "l'étape de cadrage est entamée mais le déroulé dévie en découpage"
  juge: <moteur-juge>, <version-grille>

# cas de test semé depuis ce ha (fichier séparé, standard de corpus)
seme_par: HA-XXXX               # traçabilité de l'inspiration
```

---

## 6. Changements et non-objectifs

**Changements de documents :**

- **Standard de corpus** (SPECS §6, `docs/corpus.md`) : la fiche gagne l'axe
  `provenance` (`observe` / `rapporte`), obligatoire et immuable ; les blocs
  `declaration` et `conformite` ; le gabarit de cas gagne `seme_par:`.
  Les cas convertis à la main avant cette RFC sont re-marqués `rapporte`.
  *Amendement d'établi (30 septembre 2026)* : le champ `source`
  (`reel | scenario | simule`) **reste** — il dit d'où vient la matière (un
  sujet réel, un scénario, un persona du banc) et route les sessions vers
  leur corpus ; la provenance dit d'où vient le déroulé (joué ici ou
  ailleurs). Les deux axes sont orthogonaux : une conversation rapportée
  porte souvent un sujet réel. `provenance` est donc un champ **neuf**, à
  côté de `source`, et non son renommage.
- **RFC-008** : la dualité est nommée dans les deux textes — forme
  importée (008) / pratique rapportée (020). Un harness importé N0 peut
  recevoir des pratiques rapportées : c'est même son premier corpus
  plausible.
- **RFC-016** : la frontière du §2 (re-percevable) est référencée comme
  conséquence de l'interdit n°2.
- **RFC-007 (cartos, non construite)** : les vues d'observation devront
  porter l'encre de provenance — elle se construira amendée.

**Non-objectifs :**

- **Import de déroulés à effets monde** — exclu par théorème (§2) ; si un
  jour des traces externes signées et vérifiables existent, autre RFC.
- **Quota et règles d'enrichissement du corpus de cas réels** —
  explicitement différés : d'abord la matière, ensuite la norme.
- **Rétro-instrumentation** (reconstruire des blocs d'état a posteriori
  sur le transcript) — différée, en symétrie avec le N4 de la 008 :
  les deux rétro-gestes se feront ensemble ou pas.
- Import automatique par connecteurs ; import en masse — le geste
  unitaire d'abord.
- Toute forme de score de « fiabilité » du déposant — la provenance
  marque le matériau, jamais la personne.

---

## 7. Critère « juste assez » et sabotages

1. **Nominal — le geste complet** : coller une conversation, corriger le
   découpage, déclarer le kata ; la retrouver **immédiatement** au corpus
   à l'encre `rapporté`, statut brut ; lancer la trempe a posteriori et
   voir ses verdicts s'attacher.
2. **Nominal — la semence** : depuis ce ha, semer un cas de test
   pré-rempli ; vérifier le lien `seme_par:` et l'encre sur le cas semé.
3. **Sabotage — le hors-sujet** : importer une conversation manifestement
   étrangère au kata déclaré ; le juge **conteste**, le verdict s'affiche
   à côté de la déclaration sans l'écraser — et le ha **reste** au corpus.
4. **Sabotage — l'action rapportée** : importer un déroulé alléguant des
   effets monde (« j'ai déployé, ça marche ») rattaché à un kata à effets
   monde ; l'import **refuse** en citant la frontière du §2.
5. **Sabotage — la dilution** : vérifier qu'aucun agrégat par défaut du
   banc n'inclut un ha rapporté ; l'inclure exige la tranche explicite.
6. **Sabotage — l'encre indélébile** : tenter de passer un ha `rapporté`
   en `observé` (par édition, par annotation, par export/réimport) ;
   **refusé** partout — un vérificateur doit être vu en train de refuser.

---

## 8. Note d'établi

Le premier cas du corpus était une conversation convertie à la main :
cette RFC existait en germe avant d'avoir un numéro. Une version
intermédiaire du texte comportait une quarantaine et un geste de
promotion ; elle a été démontée en keiko — juger une expérience digne
d'entrer n'est pas un concept de Kokaji. On ne peut pas refuser que le
monde existe : on l'accueille, on le marque, et on garde le jugement pour
la lecture. La forge accueille désormais ce qui est né ailleurs,
définitions comme déroulés, à condition de ne jamais maquiller l'encre —
parce que le but de fond est l'optimum du tout, et qu'un harness qui ne
lit que sa propre pratique ne trouverait jamais que lui-même.

---

## 9. Plan d'implémentation

Six lots côté produit, un côté instance. Chaque lot porte ses sabotages.

- **Lot 0 — les documents.** La RFC dans `docs/` du produit avec ce plan ;
  SPECS §6, `docs/corpus.md`, RFC-008, RFC-016, `STRUCTURE.md` amendés.
- **Lot A — le modèle et l'entrée** (`kokaji/corpus/provenance.py`,
  `kokaji/corpus/rapporte.py`, les deux dépôts, `cli.py`). L'axe
  `provenance`, posé une fois, hors de la capture, **refusé à toute
  réécriture par les deux dépôts** — le seul endroit par où toute fiche
  passe (sabotage 6 : édition, visibilité, annotation, export puis réimport).
  Le découpage heuristique du texte collé ; le ha `brut` au format que le
  middleware écrit ; le refus d'un kata à effets monde en citant §2
  (sabotage 4) ; `kokaji rapporter`.
- **Lot B — la trempe a posteriori.** Les checks du harness sur le
  transcript ; les invariants du bloc d'état éteints et dits éteints ; le
  juge de conformité (invariant Kokaji) et la grille du harness, juge
  distinct du moteur d'origine ; résultats datés, cumulés, `conformite`
  posée à côté de `declaration` (sabotage 3).
- **Lot C — la semence.** Semer un persona pré-rempli depuis le ha ;
  `seme_par` lu par le chargeur de personas.
- **Lot D — le banc.** Exclusion par défaut des `rapporte` dans l'usage, la
  non-régression, le resserrage et le juge ; la tranche explicite
  `--provenance rapporte` (sabotage 5).
- **Lot E — la page.** La zone de collage et le découpage corrigeable ;
  l'encre visible sur la liste, la fiche et `/ha` ; semer et tremper depuis
  le ha.
- **Lot F — l'instance.** Déploiement ; re-marquage des cas convertis à la
  main ; preuve en direct.

## 10. Tableau d'application

| Lot | État |
|---|---|
| 0 — les documents | appliqué (30 septembre 2026) — RFC dans le produit ; SPECS §6, `docs/corpus.md`, RFC-008 §1, RFC-016 §2, `STRUCTURE.md` amendés |
| A — le modèle et l'entrée | appliqué (30 septembre 2026) — `provenance: observe` posé par la capture, `rapporte` par l'import, gardé par `verifier_inalterable` dans les deux dépôts (sabotage 6 vu refuser : passage en `observe`, encre tue, valeur hors liste, export maquillé réimporté) ; colonne `provenance` en base, ajoutée sans migration ; `decouper` (étiquettes des outils de chat, sinon paragraphes en alternance) et `rapporter` (fiche avec `declaration`, transcript lisible par le QG et le banc, sortie, texte collé en matériau) ; un kata à effets monde refusé en citant §2 (sabotage 4) ; `kokaji rapporter --essai` puis `--tours` |
| B — la trempe a posteriori | appliqué (30 septembre 2026) — `tremper` (`kokaji/trempe/banc/posteriori.py`) : les checks du harness sur le transcript ; les invariants du bloc d'état éteints et dits éteints ; la conformité au kata déclaré demandée devant la coupe (invariant Kokaji, `conformite-1`), puis la grille du harness ; juge ≠ moteur d'origine connu ; `conformite:` posé à côté de `declaration:`, chaque passage ajouté aux jugements, daté ; `kokaji tremper [--juge]` ; sabotage 3 vu : le hors-sujet contesté, la déclaration intacte, le ha reste brut |
| C — la semence | appliqué (30 septembre 2026) — `semer_cas` écrit `personas/<id>.yaml` pré-rempli (sujet depuis le kin déclaré et le premier tour du porteur, `deroule` depuis ses tours), `seme_par:` vers le ha, posture et pièges marqués à écrire ; `Persona` lit `seme_par` et `deroule` ; semer n'écrase pas, ne sème que du rapporté ; `kokaji semer --ha` |
| D — le banc | appliqué (30 septembre 2026) — `dans_la_tranche` : l'usage, la non-régression (`perimes`), le resserrage (`observer`) et le juge de grille lisent `observe` par défaut ; `--provenance rapporte` (et `?provenance=` sur `/qg/usage`) pour la tranche rapportée seule, pas de « toutes » ; l'usage dit les ha de l'autre encre restés dehors ; sabotage 5 vu |
| E — la page | appliqué (30 septembre 2026) — « rapporter une conversation » dans les Conversations : collage, découpage proposé par `POST /qg/rapporte/decoupage`, corrigeable tour par tour (rôle, texte, fusionner, supprimer — la correction se déclare), déclaration, `POST /qg/rapporte` (praticien = la personne, 422 en citant §2 pour un kata à effets monde) ; l'encre `rapporté` sur la session, le fil, `/ha` et le pied du transcript, la déclaration et la conformité côte à côte ; « tremper a posteriori » et « semer un cas » depuis le ha (`POST /qg/conversation/tremper`, `/semer`) ; un ha illisible reste inconnu (404) ; tour visuel du 1er octobre 2026 dans le navigateur de la vigie, à 1280 et 360 px : rien ne déborde, le découpage se corrige au doigt, les passages de trempe se lisent au pied du transcript |
| F — l'instance | appliqué (30 septembre 2026) — image `sha-b5df83a` en service, sans redémarrage ni traceback ; la colonne `provenance` posée en base sans migration, la veille a posé `observe` sur tous les ha bruts au premier passage (les annotés, jamais réécrits, se lisent `observe` par défaut) ; les deux cas convertis à la main avant la RFC (`atelier/essai` CAS-0001 et CAS-0002) re-marqués `rapporte` avec leur `declaration`, en base et dans le clone du harness ; preuve en direct : une conversation fictive rapportée dans `atelier/essai` (CAS-0152), trempée a posteriori (aucun check ne mord, invariants éteints), hors du relevé d'usage par défaut et dite |
