# RFC-008 — Import de harness exogènes
> **Statut : proposé, décisions structurantes scellées** (établi, août 2026).
> Dépend de : HDS (manifest), RFC-001 (capture), RFC-004 (autorat, versement), RFC-007 (observation — comportement par niveau). Objet : adopter dans Kokaji un harness **né hors de la forge** — des prompts faits main — pour l'expérimenter et l'évaluer.

---

## 1. Motivation

Des harness existent hors de Kokaji : écrits à la main, joués en copier-coller, sans template, sans manifest, sans instrumentation. Ils ont vocation à être joués « avec un modèle quelconque derrière » — exactement ce que le Dojo sait faire — et méritent d'être évalués avec les instruments de la trempe. L'import est une **capacité générique** : tout harness exogène, quel qu'en soit l'auteur ou le domaine, devient expérimentable dans Kokaji.

## 2. Régime de séparation (décision scellée : « les deux, séparés »)

- Ce RFC spécifie une mécanique **générique** ; il ne mentionne, n'embarque ni ne présuppose aucun harness particulier.
- **La mécanique se valide sur l'instance personnelle avec un harness exogène neutre** (créé pour l'occasion ou tiers public) — jamais avec un harness professionnel.
- Un harness professionnel s'expérimente sur **une instance Kokaji dédiée, côté professionnel** (Kokaji consommé comme outil externe — conformément à R10.4). Aucun contenu professionnel ne transite par l'instance personnelle ni, a fortiori, par le repo.
- Le développement des capacités d'évaluation (judge, grilles, banc) est du **développement Kokaji, générique** — il appartient au projet personnel, hors relation d'emploi ; seules les *données* d'un harness pro restent côté pro.

## 3. Ontologie : la coupe orpheline et l'échelle d'adoption

Un prompt fait main est, dans le vocabulaire Kokaji, une **coupe sans tamahagane** : un artefact jouable dont la forme source n'existe pas. L'import est donc une **adoption par niveaux**, chaque niveau débloquant des capacités nommées :

| Niveau | Ce qu'on déclare/fait | Ce qui s'allume |
|---|---|---|
| **N0 — jouable** | les prompts, tels quels | modèles virtuels, sessions, capture des ha, A/B moteurs, judge sur transcripts |
| **N1 — situé** | la chaîne (topologie) | fil d'ariane du QG (sans états), carto structurelle en mode dégradé |
| **N2 — instrumenté** | vocabulaire de champs + coupe instrumentée générée | blocs d'état, QG coloré, carto des certitudes |
| **N3 — contractualisé** | les f♯ (herite/produit), à la main | le carré continu, le slack, le typage de chaîne |
| **N4 — forgé** | rétro-ingénierie du tamahagane | citoyen complet : la forge régénère, la trempe statique s'applique |

**Périmètre v1 (scellé) : N0 + N2** (N1 vivement conseillé au passage — il est déclaratif et petit). N3-N4 : différés, la structure les attend.

## 4. Le manifest d'import (extension HDS)

> **Amendement du 28 août 2026 — deux décisions prises en confrontant ce
> paragraphe au code, avant toute implémentation.**
>
> **1. Un mode *est* un kata ; nue et instrumentée sont des cibles.** La
> première version de ce paragraphe introduisait `modes:` comme concept
> parallèle. Or toute la pile — forge, passerelle, chat, capture, QG — parle
> `<harness>/<kata>@<cible>`, et le §6 dit déjà que les deux coupes
> « coexistent comme deux cibles » : le concept parallèle redisait l'existant
> en le doublant. Un second genre de « chose jouable » se serait payé partout,
> à chaque route et à chaque registre. Le manifest d'import déclare donc des
> **kata** — dont la source est un texte importé au lieu d'une source de
> forge — et les deux incarnations sont les cibles `nue` et `instrumentee`.
> Tout ce qui sait servir un kata sait servir un import, sans une ligne.
>
> **2. Les champs d'un kata exogène viennent du manifest, par exception
> nommée, et l'exception se referme à N3.** La règle existante dit : une seule
> source de vérité, les champs se dérivent du contrat f♯ (`herite` +
> `produit`), et une clé `champs:` posée ailleurs est *refusée* pour que deux
> déclarations ne divergent jamais (RFC-002 §3). Or N2 veut des blocs d'état
> **avant** les contrats, qui n'arrivent qu'à N3 — il demande exactement ce
> que la règle interdit. L'issue retenue : tant que `exogene: true` **et**
> qu'aucun kata ne déclare de contrat, les champs viennent de `etat.champs`
> du manifest. Dès qu'un contrat apparaît (N3), la règle générale reprend et
> `etat.champs` devient une faute de manifest — les deux sources ne
> coexistent jamais. L'alternative — dériver des contrats implicites au
> statut le plus faible — était écartée : elle aurait rallumé le carré, donc
> fait paraître vérifié ce qui ne l'est pas (§8).
>
> **Conséquence chiffrée au passage** : sans contrats, le carré actuel
> conclurait `conforme` **par vacuité** — la boucle des manquants est vide.
> Le sabotage d'honnêteté du §9 échouerait aujourd'hui. L'état « sans
> contrats » (carré éteint) est donc un **préalable** à tout N2, et il se
> code dans la même famille que `carre_attendu` : on ne juge pas une promesse
> qui n'a jamais été faite.

```yaml
harness:
  id: ""
  nom: ""
  version: ""                      # versionnage Kokaji, démarre à l'import
  exogene: true
  provenance:                      # estampillé UNE FOIS à l'import — trace, pas verrou
    source: ""                     # libre : « manuel », URL, référence
    version_source: ""
    checksum_import: ""            # empreinte des textes tels qu'importés
    date_import: ""

kata:                              # un par coupe orpheline — voir amendement (1)
  - id: ""
    nom: ""
    source: prompts/<id>.md        # le texte importé, tel quel ; pas une source de forge
    amont: []                      # N1 — optionnel
    herite: []                     # N3 — vides jusque-là
    produit: []

chaine: { noeuds: [], aretes: [] } # optionnel — N1

cibles:                            # les deux incarnations — voir amendement (1)
  - { id: nue, etat_structure: false }
  - { id: instrumentee, etat_structure: true }   # n'existe qu'à partir de N2

etat:                              # requis pour N2 — lu seulement tant qu'aucun
  champs: []                       # kata ne déclare de contrat (amendement (2))
  statuts_champ: [fait_etabli, hypothese, en_pause]

trempe:
  grille_judge:                    # priorité v1 (décision scellée)
    - { id: "", question: "", echelle: "1-5" }
  checks_session: []               # déclarables, non prioritaires
```

## 5. N0 — l'import jouable (et la décision d'éditabilité)

- Chaque prompt importé devient une coupe enregistrée ; chaque kata un modèle virtuel `<harness>/<kata>` du Dojo — la mécanique existante, sans extension. Les sessions sont capturées en ha avec l'identité complète (la version étant celle du versionnage Kokaji post-import).
- **Décision scellée : le harness importé est éditable** — l'import est une *migration*, pas une consignation ; le harness devient un harness Kokaji normal (autorat RFC-004 : l'importeur en est propriétaire). Contrepartie tracée sans contredire la décision : la **provenance est estampillée une fois** (checksum et version source à l'import) — on saura toujours d'où c'est parti et si ça a divergé, sans figer quoi que ce soit.

## 6. N2 — l'instrumentation par enrichissement

- Kokaji **génère** la coupe instrumentée : le texte du prompt + le bloc d'instruction d'émission `kokaji_state` (adossé au vocabulaire de champs déclaré au manifest). Le texte d'origine n'est pas réécrit : l'instruction s'ajoute.
- Les deux coupes (nue / instrumentée) coexistent comme deux cibles — ce qui permet de **mesurer l'effet de l'instrumentation elle-même** (A/B nue vs instrumentée : l'ajout du bloc change-t-il le comportement ? — vigilance nommée, mesurable par le judge).
- Sans vocabulaire de champs déclaré, pas de N2 — erreur explicite, jamais de champs inventés.

## 7. L'évaluation v1 (priorité scellée : le judge sur grille)

- **LLM-as-judge sur grille déclarée** : les critères du manifest (question + échelle) appliqués aux transcripts des ha — dans le respect du versement (RFC-004 : un judge lancé par un co-auteur n'évalue que les ha versés et les siens). Résultats rattachés aux ha, comparables par `(version, moteur, kata, cible)`.
- Gratuit dès N0 : l'**A/B de moteurs** (changer le moteur sous un kata importé = une ligne) et la capture. Checks déterministes et personas rejouables : déclarables au manifest, implémentation différée (backlog du banc).
- Discipline du judge reconduite : **juge ≠ pratiquant** (moteur de jugement distinct), scores descriptifs, formules visibles.

## 8. Comportement des observatoires par niveau — l'honnêteté d'affichage

Le QG et l'Épure appliquent la règle des trois encres à l'adoption : **ce qui n'existe pas s'affiche comme absent, jamais comme simulé**. Harness N0 : pas de fil d'ariane (pas de chaîne déclarée), carrés de l'Épure **éteints** avec la mention « sans contrats » — ni verts ni rouges. N1 : topologie dessinée, nœuds neutres. N2 : le QG se colore, la carto des certitudes s'allume ; les carrés restent éteints jusqu'à N3. Un harness importé ne paraît jamais plus vérifié qu'il ne l'est.

## 9. Critère « juste assez » — avec sabotages

- **Nominal** (sur l'instance personnelle, harness neutre de 2-3 prompts créé pour l'occasion) : import N0 → les kata sont jouables via le Dojo et un A/B de moteurs tourne ; déclaration du vocabulaire + génération N2 → une session sur la coupe instrumentée produit des blocs d'état capturés ; une grille de 3 critères déclarée → le judge score des transcripts et les scores sont rattachés aux ha.
- **Sabotages** : manifest citant un fichier absent → erreur explicite à l'import, rien d'enregistré ; N2 demandé sans vocabulaire de champs → refus nommé ; judge lancé sur les ha non versés d'autrui → ne les voit pas ; l'Épure d'un harness N0 → carrés **éteints** (le sabotage d'honnêteté : vérifier qu'aucun vert n'apparaît).

## 10. Changements et vigilances

| Document | Changement |
|---|---|
| SPECS | v1.6 → v1.7 : l'import exogène rejoint la brique HDS/forge ; l'échelle d'adoption au glossaire |
| HDS | Extension `exogene`/`provenance` + manifest d'import (§4) |
| Carnet de vigilances | + « effet de l'instrumentation sur le comportement (A/B nue/instrumentée) » ; + « qualité du vocabulaire de champs déclaré à l'import — le judge peut auditer sa pertinence » |

---
*Note d'établi : l'échelle d'adoption est le vrai contenu de ce RFC. Elle dit qu'un harness n'est pas dedans-ou-dehors : il est plus ou moins* su *par la forge — jouable avant d'être situé, situé avant d'être instrumenté, instrumenté avant d'être contractualisé. C'est la doctrine du projet appliquée à ses propres frontières : on n'exige pas d'un arrivant qu'il soit citoyen complet ; on lui donne un chemin, et chaque pas s'achète par une déclaration honnête — jamais par une simulation.*
