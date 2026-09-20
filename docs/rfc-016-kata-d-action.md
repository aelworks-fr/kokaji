# RFC-016 — Le kata d'action (refonte unificatrice)

**Statut :** scellée (décisions structurantes + validation philosophique en keiko, 2026)
**Dépend de :** SPECS ; RFC-002 (check galoisien de l'héritage — appliquée) ; RFC-003 (diagnostic de nature — proposée, non construite) ; RFC-009 (séparation produit/instance — appliquée) ; RFC-014 (données vivantes — appliquée)
**Refond :** SPECS §2 (HDS) et §3 (dojo) ; amende RFC-002 et RFC-003
**Prérequis remontés :** cette RFC fait passer la RFC-003 de « proposée » à « requise » — la sortie de budget (D16.4) et la règle nature × canaux (D16.5) s'appuient sur ses conduites.

---

## 1. Motivation

Kokaji sait forger, jouer, observer et éprouver des kata **conversationnels**.
Mais le dev génératif — faire naître un truc qui marche, puis le faire grandir
pas à pas — demande plus que des échanges : il demande des **étapes d'action**.
Lancer une suite de tests. Produire un patch. Déployer. Évaluer une
fonctionnalité. Et enchaîner ces étapes selon leurs résultats.

Le geste fondateur de cette RFC est une inversion : on ne rajoute pas un
« type action » à côté de la conversation. On reconnaît que **la conversation
était une action depuis le début** — une action d'échange d'information, dont
la trempe vérifie la qualité et la pertinence. Le modèle ne grossit pas :
il se généralise. C'est pourquoi cette RFC est une **refonte unificatrice**.

---

## 2. Le primitif : perception + intention méta → effets sur le système

Un **kata** est la forme codifiée d'une étape décisionnelle qui agit.
Son primitif n'est pas un type de geste : c'est un **triplet**, déclaré
au manifeste.

- **Perception** : ce que le kata perçoit — ses entrées, et les **retours
  d'effets** par lesquels il constate ce que son action a fait.
- **Intention méta** : l'objet décisionnel de l'étape (le champ `objet` du
  bloc d'état — il était là depuis toujours).
- **Effets** : ce que l'action change, déclaré **par système touché** et
  par canal.

Il n'y a que deux systèmes, et trois canaux :

| Canal | Système | Statut | Exemple |
|---|---|---|---|
| `modele` | Le modèle partagé (état épistémique pratiquant ↔ humain) | **Universel** — tout kata émet un bloc d'état ; c'est cet effet | verdict, hypothèse révisée, décision |
| `monde_lecture` | Le monde, échantillonné sans être modifié | Optionnel | faire tourner une suite de tests, inspecter un système |
| `monde_ecriture` | Le monde, modifié | Optionnel | produire un patch, déployer |

Le kata conversationnel est le cas `modele` seul. La **sonde** de la RFC-003
est le cas `modele + monde_lecture` — la conduite prescrite en nature
émergente était déjà, sans le nom, l'action qui lit avant d'écrire.
La refonte recolle les deux RFC sans couture.

**Types dérivés.** Les anciens types survivent comme **raccourcis** de
manifeste, qui se développent mécaniquement en triplet : `echange`
(modele seul), `sonde` (+ lecture), `production` et `commande` (+ écriture).
Un raccourci n'ajoute aucune sémantique : c'est un développement, pas une
ontologie seconde. La liste des raccourcis s'étend par RFC, jamais par usage.

**Trois interdits fondent la justesse du triplet :**

1. **Pas d'action aveugle.** Tout effet déclaré doit avoir son canal de
   perception : un `effet` sans `retour` correspondant dans la perception
   et sans vérificateur dans la trempe rend le manifeste **invalide**.
   Agir sans pouvoir percevoir ce qu'on a fait n'est pas un kata.
2. **Pas de monde auto-rapporté.** Le vérificateur d'un effet sur le monde
   échantillonne le monde **indépendamment** de la déclaration du
   pratiquant : le rapport n'est jamais sa propre preuve.
3. **Pas de surprise avalée.** Un écart que l'étape ne résout pas **remonte**
   — au checkpoint humain — jamais absorbé en silence (voir §4, cycles).

---

## 3. Décisions scellées

### D16.1 — Toute étape est une action ; la conversation en est un cas

SPECS §2 et le HDS sont **réécrits** autour du triplet (§2). Migration
mécanique : un kata sans déclaration d'effets vaut `echange` — les
manifestes existants restent valides sans retouche. La surface d'écriture
à la main (RFC-010 : gabarit, densho, coupe visible) accueille le triplet
comme un bloc de plus du gabarit, optionnel tant qu'on reste en `echange`.
Preuve de non-régression : l'existant se joue à l'identique (§7).

### D16.2 — La coupe d'un kata d'action est un outil prêt à l'usage

La forge produit toujours la même chose : un exécutable de kata. Pour un
kata qui touche le monde, la coupe empaquette **prompt + configuration
d'outils + vérificateurs d'effet** — un outil prêt à l'usage pour le moteur.

Le moteur est un **agent CLI existant** (moteur agentique), piloté par la
coupe comme le moteur conversationnel l'est par le prompt. Il reste
interchangeable : le manifeste déclare des **capacités requises**
(ex. `execution_shell`), jamais un produit. L'observabilité s'appuie sur ce
que l'agent journalise ; un runner dédié ne naîtra que si cette
journalisation ne suffit pas (décision de bascule à documenter le jour venu).

Les adjonctions **héritées et produites** (`herite:`/`produit:`, RFC-002)
se déclarent comme sur tout kata : agir ne dispense pas de dire ce qu'on
reçoit et ce qu'on promet. Le contrat f♯ et sa vérification par la trempe
et le middleware s'appliquent tels quels.

### D16.3 — Sorties multiples : l'arête porte une condition sur le bloc d'état

La chaîne cesse d'être linéaire. Une arête porte une **condition déclarative
sur le bloc d'état émis** par le kata amont. Le dojo route **mécaniquement** :
il évalue les conditions, il ne juge pas. Si aucune condition ne tranche,
la chaîne s'arrête sur un **checkpoint humain** — jamais de branche devinée.
Cohérence : là où la condition calcule, l'adjoint existe et la machine
route ; « la coupe commence où l'adjonction s'arrête », et le checkpoint
humain est exactement cet endroit.

**Loi de prudence, désormais armée.** Le verdict qui route est un effet
`modele`, écrit par le kata lui-même. Un kata qui sur-promet
(« tous_passes » alors qu'un test a échoué) ne commet plus une erreur
d'affichage : il **route la chaîne de travers**. L'interdit n°2 (§2) est le
garde-fou : le monde est échantillonné indépendamment du rapport, et la
trempe devient le contrôle d'honnêteté du routage. Le carré lax de la
RFC-002 est le garde-fou d'un aiguillage.

### D16.4 — Cycles avec budget

Les boucles sont permises (tests échoués → correction → re-tests), mais tout
cycle déclare un **budget** au manifeste : passages maximaux et/ou enveloppe
de coût. Budget épuisé = sortie d'urgence vers un checkpoint humain, avec la
conduite de la nature **urgence** (RFC-003 : départage, état gelé, main
rendue). C'est l'interdit n°3 incarné : l'écart que l'étage ne résout pas
remonte à l'étage au-dessus — l'humain n'est pas un superviseur extérieur,
il est l'étage supérieur. Aucun cycle sans budget ne passe la trempe du
manifeste. *(Dépendance : la conduite d'urgence vit dans la RFC-003, non
construite — voir « prérequis remontés » en tête.)*

### D16.5 — Le bloc d'état s'étend : `actions[]`

`kokaji_state` gagne un champ, obligatoire pour tout kata dont les effets
dépassent `modele` :

```json
"actions": [
  {
    "intention": "faire tourner la suite de tests fournie",
    "canal": "monde_lecture",
    "artefact": "rapport-tests.xml",
    "verdict": { "valeur": "echecs", "detail": "2/148 en échec", "confiance": 0.98 }
  }
]
```

L'action s'insère entre deux émissions du bloc ; le reste du schéma est
inchangé. Amendements : RFC-002 (α couvre les actions — l'abstraction d'une
pratique qui agit inclut ce qu'elle a fait), RFC-003 (la nature conditionne
les **canaux permis** : en nature émergente, `monde_lecture` avant tout
`monde_ecriture` — la sonde d'abord).

### D16.6 — Trempe : le résultat est jugé, la trace est gardée

L'évaluation porte sur le **résultat** : l'artefact produit passe les
vérificateurs exécutables déclarés au manifeste (tests, compilation, lint —
l'étage 1 déterministe cesse d'être un pis-aller de regex), puis les étages
judge et humain s'appliquent au résultat. La **trace complète** des actions
est capturée dans le ha, sous le régime base des données vivantes
(RFC-014), mais n'est pas évaluée en v1 : l'évaluation de trace deviendra
possible plus tard **sans rien perdre**. Capture par défaut, jugement
juste assez.

---

## 4. Modèle (HDS refondu, extrait)

```yaml
kata:
  - nom: tests
    raccourci: sonde                   # optionnel — se développe ci-dessous
    perception:
      entrees: [suite_de_tests, perimetre_fige]
      retours: [rapport_de_tests]      # canal de perception des effets
    intention: "établir si la suite passe sur le périmètre figé"
    effets:
      modele: [verdict_tests]
      monde_lecture: [execution_suite]
    herite: [perimetre_fige]
    produit: [verdict_tests]
    trempe:
      verificateurs:
        - type: executable
          check: "le rapport couvre 100% de la suite fournie"   # interdit n°1
          source: rapport-tests.xml                             # interdit n°2

  - nom: correction
    raccourci: production
    perception: { entrees: [rapport_de_tests], retours: [patch] }
    intention: "corriger les échecs constatés"
    effets: { modele: [hypothese_correction], monde_ecriture: [patch] }

  - nom: deploiement
    raccourci: commande

chaine:
  aretes:
    - { de: tests, vers: deploiement, condition: "resultat.verdict == 'tous_passes'" }
    - { de: tests, vers: correction,  condition: "resultat.verdict == 'echecs'" }
    - { de: correction, vers: tests }          # referme le cycle
  cycles:
    - noeuds: [tests, correction]
      budget: { passages: 3 }
```

---

## 5. Changements de documents

- **SPECS §2 / HDS** : réécriture autour du triplet (D16.1, §4) ; `echange`
  par défaut, migration sans retouche. Le gabarit et le densho (RFC-010)
  gagnent le bloc triplet, optionnel en `echange`.
- **SPECS §3 (dojo)** : routage conditionnel + moteur agentique (agent CLI
  derrière la même façade quand c'est possible, à côté sinon) ; l'exécution
  se fait **dans le périmètre de l'instance** (souveraineté, RFC-009 —
  aucune émission réseau nouvelle côté produit).
- **RFC-002** : α étendu aux actions ; loi de prudence énoncée comme
  propriété de routage. Le carré qui rougit désigne désormais un aiguillage
  suspect — matière pour les cartos de la RFC-007 quand elle se construira.
- **RFC-003** : nature × canaux d'effet (émergent ⇒ lecture avant écriture ;
  urgence ⇒ conduite de sortie de budget). La sonde y gagne sa définition
  générale : effet `modele + monde_lecture`. Statut : ces amendements
  s'écrivent dans la RFC-003 **avant** sa construction — elle se construira
  amendée.
- **RFC-008 / RFC-015** : un harness importé peut déclarer des kata à effets
  monde ; le niveau instrumenté (N2) exige alors `actions[]` dans le bloc
  d'état, et le contrat f♯ sur harness importé (RFC-015) couvre les
  adjonctions de ces kata sans régime spécial.

---

## 6. Non-objectifs

- Sandbox durcie du produit : l'exécution a lieu là où l'instance le décide ;
  le produit norme le manifeste et la capture, pas l'isolement d'exécution
  (RFC dédiée si besoin).
- Branches parallèles — la chaîne reste séquentielle.
- Orchestration distribuée, files de jobs, reprise sur panne.
- Catalogue d'outils ou standard d'outillage : le manifeste déclare des
  capacités, l'instance les mappe sur son moteur.
- Contrôle d'accès par ressource nommée (les trois canaux suffisent en v1).
- Évaluation de trace (explicitement différée, D16.6).

---

## 7. Critère « juste assez » et sabotages

La refonte est normative dès maintenant, mais n'est **prouvée** que
lorsqu'on l'a vue fonctionner — et refuser :

1. **Nominal — le cycle qui converge** : un harness d'essai `tests →
   correction → tests → deploiement` joué de bout en bout avec un agent
   CLI ; blocs d'état avec `actions[]`, routage par conditions, ha complet
   (artefacts + trace).
2. **Nominal — la non-régression** : un harness existant (pur `echange`)
   se joue à l'identique sous le HDS refondu, sans modification de son
   manifeste ni de son densho.
3. **Sabotage — la sur-promesse** : un kata `tests` forcé à déclarer
   `tous_passes` alors qu'un test a échoué ; le vérificateur, qui lit le
   rapport et non la déclaration, **refuse**. (La visualisation du carré
   qui rougit attendra les cartos de la RFC-007 ; le refus, lui, n'attend
   pas.)
4. **Sabotage — l'action aveugle** : un manifeste déclarant un effet
   `monde_ecriture` sans retour de perception ni vérificateur ; la trempe
   du manifeste le **rejette** avant toute forge.
5. **Sabotage — le budget** : un kata `correction` qui ne corrige jamais ;
   au 3ᵉ passage la chaîne **sort en urgence** vers le checkpoint humain au
   lieu de boucler.
6. **Sabotage — le routage muet** : un verdict hors vocabulaire des
   conditions ; le dojo **s'arrête** sur checkpoint humain, aucune branche
   n'est devinée.

---

## 8. Généalogie (seule section où ces noms ont droit de cité)

Le triplet du §2 est une formulation propre à Kokaji d'un modèle de
cognition dû à son auteur — *perception + intention méta → effets sur le
système* — dont la parenté avec l'**inférence active** (Friston) est
assumée : perception et action y sont le même mouvement pris dans les deux
sens ; l'action s'y dédouble en pragmatique (écrire le monde) et
épistémique (le lire — notre sonde) ; l'écart non résolu y remonte la
hiérarchie (notre checkpoint humain) ; et il y est interdit de réduire
l'écart en truquant le rapport plutôt qu'en agissant — notre loi de
prudence, mot pour mot.

Mais on retient la mise en garde de Cobb (*The Idea of the Brain*) : chaque
époque a décrit la cognition avec sa technologie du moment, et chaque
métaphore a passé. L'inférence active est ici une **grammaire de
conception**, retenue pour ce qu'elle interdit (§2, les trois interdits) —
pas une thèse sur ce que « sont » les pratiquants. En conséquence, régime
strict : *inférence active*, *énergie libre*, *prédiction*, *surprise*,
*Friston*, *Cobb* n'apparaissent **que dans cette section**. Le vocabulaire
opérationnel — manifestes, code, QG, bancs — dit : percevoir, intention,
effet, canal, sonde, écart. Des mots à nous.

---

## 9. Note d'établi

Le sol est posé : le dépôt public est sorti et l'image le remplace
(RFC-009), l'import et son contrat sont en production (RFC-008, RFC-015),
les données vivantes ont leur régime (RFC-014). Cette RFC refond le modèle
que tout cela sert, et elle réordonne la file des chantiers non construits :
la **RFC-003 passe devant** — ses conduites (sonde, urgence) sont désormais
des prérequis du kata d'action, et elle se construira déjà amendée par le
présent texte. La RFC-007 (cartos) et le N4 de la RFC-008 suivent leur
cours propre. Le choix de la refonte plutôt que de l'ajout est assumé :
puisque la conversation est une action, maintenir deux modèles serait
entretenir une distinction que la théorie vient de dissoudre. La taxonomie
initiale par types de gestes a été démontée en keiko au profit du triplet :
le geste n'était pas le primitif, la boucle l'est. Mais la doctrine tient :
rien n'est cru avant le sabotage. La forge sait maintenant que couper,
c'est agir — il reste à la voir refuser une coupe qui ment.
