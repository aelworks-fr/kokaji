# RFC-003 — Le diagnostic de nature du sujet
> **Statut : proposé** (établi, août 2026) — à marteler puis intégrer (SPECS v1.3 → v1.4, template de harness, RFC-002 compatible).
> Inspiration interne : les domaines de Cynefin (simple / compliqué / complexe / chaotique / désordre). **Ce nom ne sort jamais** : ni face à l'utilisateur (silence méthodologique), ni dans les données (vocabulaire opérationnel propre, §2).

---

## 1. Principe

**Avant d'accompagner, situer.** Un kata qui déroule sa forme sans égard pour la *nature* du problème commet l'erreur que toute la doctrine combat : traiter l'émergent par l'analyse, l'évident par la cérémonie, l'urgence par le formulaire. La phase d'ouverture de tout kata (perception + compréhension, les phases 1-2 de la triade) inclut désormais un **diagnostic de nature**, léger, révisable, et *observable* — puis le kata **adapte sa conduite** ou **renvoie**.

Le désordre n'est pas un échec du diagnostic : c'est son cinquième résultat légitime — « je ne sais pas encore dans quelle nature on est » — et il déclenche précisément ce que le kata sait faire de mieux : des questions qui départagent.

## 2. Le vocabulaire opérationnel (dans les données et les prompts — jamais « Cynefin »)

| Nature | Définition opérationnelle | Signal de diagnostic |
|---|---|---|
| **évident** | La solution est connue et consensuelle ; il n'y a qu'à faire | « Quelqu'un a-t-il déjà résolu exactement ça, de façon reconnue ? » — oui, sans débat |
| **analysable** | Une expertise ou une étude peut donner la réponse avant d'agir | « Un expert pourrait-il trancher après analyse ? » — oui, et on sait lequel |
| **émergent** | Seul l'essai apprend ; les effets dépendent d'usages et de gens | « Faut-il essayer pour savoir ? Les réactions des gens font-elles le résultat ? » — oui |
| **urgence** | Des dégâts sont en cours ; stabiliser passe avant comprendre | « Est-ce que quelque chose brûle pendant qu'on parle ? » — oui |
| **indéterminé** | On ne sait pas encore — état de départ honnête | Aucun signal net — le diagnostic continue par les questions |

## 3. La conduite par nature (le contrat d'adaptation)

- **évident** → **mode raccourci** : le kata converge en un minimum de questions, propose la voie connue, documente, sort. Dérouler la cérémonie complète sur un problème évident est une faute (le « juste assez » s'applique à l'accompagnement lui-même).
- **analysable** → **mode instruction** : la forme complète, avec accent sur l'orientation vers les tiers (« en pause → qui peut trancher ? ») ; les hypothèses ont vocation à devenir des faits *par étude*, pas par essai.
- **émergent** → **mode sonde** (le terrain natal de la doctrine) : options maintenues vivantes, premier pas dimensionné pour le feedback, signal de re-décision explicite, **interdiction du plan complet**.
- **urgence** → **renvoi assumé** : le kata ne cadre pas un incendie. Il le dit (« stabilise d'abord — voici le strict nécessaire — reviens cadrer quand ça ne brûle plus »), aide au strict nécessaire si c'est dans ses cordes, et propose la reprise. Faire semblant de cadrer pendant l'incendie est la pire conduite possible.
- **indéterminé** → **le diagnostic EST la conversation** : les premières questions du kata départagent les natures avant d'engager la forme.

**Révisabilité** : la nature peut basculer en cours de session (un sujet émergent révèle un feu ; une urgence éteinte redevient analysable). Le kata re-diagnostique aux points d'étape ; chaque bascule est déclarée.

## 4. Observabilité (l'articulation avec RFC-001/002)

Extension du bloc d'état (champ optionnel, émis dès l'ouverture puis à chaque révision) :

```json
"nature": { "valeur": "evident|analysable|emergent|urgence|indetermine",
            "confiance": "faible|moyen|eleve",
            "revisee_le": "etape" }
```

Conséquence pour le banc — **la justesse du diagnostic devient une métrique** : chaque kin de banc déclare sa nature réelle dans son frontmatter (`typologie:`) ; le banc compare la nature émise par le kata à la nature déclarée du kin. Deux mesures : *justesse* (diagnostic correct, et en combien de tours) et *conformité de conduite* (le kata a-t-il tenu le contrat du §3 pour la nature diagnostiquée — grilles de judge déclarées dans la trempe du harness).

**Le test suprême** : les kin ambigus — déclarés d'une nature mais énoncés comme une autre (cf. variante « émergent » du fil rouge, §6). C'est là que la qualité d'un harness se voit.

## 5. Changements

1. **Template de harness** (l'Atelier d'abord) : la section d'ouverture des kata gagne le diagnostic (questions de nature intégrées à la perception du contexte — jamais nommées comme telles) + les cinq conduites du §3 comme comportements conditionnels.
2. **HDS** : rien — le mécanisme est un pattern de template, pas une structure de manifest. Kokaji reste agnostique : il transporte le champ `nature` du bloc d'état sans l'interpréter.
3. **Standard corpus** : champ `typologie:` au frontmatter des kin de banc et personas (evident/analysable/emergent/urgence + `enonce_comme:` pour les pièges).
4. **Banc** : matrice de couverture kata × typologie ; métriques justesse + conformité.
5. **QG** (plus tard, non bloquant) : la nature diagnostiquée est affichable au détail du nœud — une donnée de plus, pas une vue nouvelle.

## 6. Le fil rouge de test — « Se former à l'asso » (un sujet, quatre natures)

Un même univers (une association de bénévoles et sa formation), décliné en quatre kin de banc. Même vocabulaire, natures opposées — la variable isolée est le diagnostic.

### 6.1 · Variante ÉVIDENT — « Les supports en ligne »
**Énoncé du persona** : « On a 10 PDF de formation, les bénévoles les réclament par mail. Je veux les mettre en ligne pour qu'ils se servent. »
**Nature déclarée** : évident. **Conduite attendue** : convergence rapide (un espace partagé, fait), ≤ 5 questions, pas d'exploration d'options. **Échec typique à détecter** : le kata déroule sa forme complète et « cadre » un dépôt de fichiers pendant vingt tours.

### 6.2 · Variante ANALYSABLE — « Le choix du LMS »
**Énoncé** : « 200 bénévoles, des données personnelles, un budget serré, un annuaire existant à intégrer : il nous faut choisir et déployer une plateforme de formation. »
**Nature déclarée** : analysable. **Conduite attendue** : forme complète, orientation active vers les tiers (protection des données → référent, intégration → responsable technique), hypothèses converties en faits par étude comparative. **Échec typique** : le kata fait « sonder » ce qui se tranche par analyse — du faux-émergent.

### 6.3 · Variante ÉMERGENT (le piège) — « Qu'ils se forment vraiment »
**Énoncé (volontairement trompeur)** : « Il nous faut un système e-learning pour que les bénévoles se forment en continu. » *(Énoncé comme une demande de plateforme — nature réelle : l'engagement des bénévoles est émergent ; personne ne sait ce qui les fera se former.)*
**Nature déclarée** : émergent, `enonce_comme: analysable`. **Conduite attendue** : le kata **remonte de la solution au besoin**, diagnostique l'émergent, propose des sondes (un parcours pilote avec cinq volontaires, un binôme mentor) et maintient les options — pas de cahier des charges de plateforme. **Échec typique — LE test suprême** : le kata prend l'énoncé au mot et instruit un choix de LMS. Diagnostic raté = tout le reste est du travail bien fait sur le mauvais problème.

### 6.4 · Variante URGENCE — « L'audit dans dix jours »
**Énoncé** : « L'audit exige la preuve des formations réglementaires dans dix jours et l'ancien outil vient de perdre les inscriptions. Aidez-moi à monter le système qu'il faut. »
**Nature déclarée** : urgence. **Conduite attendue** : renvoi assumé — stabiliser (reconstituer les preuves : émargements, attestations, mails), parade manuelle pour l'audit, et *rendez-vous de cadrage après* ; session courte. **Échec typique** : le kata cadre sereinement un « système de suivi des formations » pendant que l'audit approche.

## 7. Critère « juste assez » du RFC

Les quatre kin du fil rouge passés au banc sur un même kata : le diagnostic émis correspond à la nature déclarée dans **3 cas sur 4 minimum, dont impérativement le piège (6.3)** ; et pour chaque diagnostic correct, la conduite tient son contrat (§3) au jugement du judge. Le jour où 6.3 est réussi — l'énoncé-plateforme requalifié en problème d'engagement — le diagnostic de nature cesse d'être une idée.

---
*Note d'établi : ce RFC déplace la frontière du harness — jusqu'ici les kata adaptaient leur exigence au contenu ; ils adaptent désormais leur forme à la nature. C'est la triade prise au sérieux : percevoir et comprendre incluent « comprendre quel genre de problème on tient », et la coupe (le choix de conduite) en découle. Un accompagnement qui ne sait pas dans quel monde il est n'accompagne rien.*

---

## État d'application

| Changement | Pas | État |
|---|---|---|
| §5.1 — SPECS §7, champ `nature` optionnel au bloc d'état | 1 | appliqué |
| §5.3 — SPECS §6, `typologie:` et `enonce_comme:` au standard corpus | 1 | appliqué |
| Carnet de vigilances — le seuil d'acceptabilité par kata | 1 | appliqué — vigilance #9 |
| §5.1 — template de l'Atelier : diagnostic à l'ouverture, cinq conduites | 2 | appliqué |
| §4 — le kata émet `nature` dès l'ouverture puis à chaque révision | 2 | appliqué |
| §6 — les quatre kin du fil rouge, au standard corpus | 2 | appliqué — matériau seul |
| §5.2 — HDS | — | **sans objet, et c'est le point** : Kokaji transporte `nature` sans l'interpréter |
| §5.4 — banc : matrice kata × typologie, justesse et conformité | 4 | appliqué — `kokaji banc --nature`, `--juge` pour la conduite |
| §5.5 — QG : la nature au détail du nœud | — | **pas construit — au backlog, non bloquant** |
| §7 — le critère « juste assez » | 4 | **atteint une fois, démenti la fois suivante** — le piège n'est pas stable (voir ci-dessous) |

### La première campagne (2026-08, `idee@instrumentee`)

Les quatre kin du fil rouge, joués contre le kata `idee` en cible instrumentée :

```
✓ asso-audit-dix-jours      attendu urgence     émis urgence     au tour 1
✓ asso-choix-plateforme     attendu analysable  émis analysable  au tour 2
✓ asso-formation-continue   attendu emergent    émis emergent    au tour 4   [piège]
✓ asso-supports-en-ligne    attendu evident     émis evident     au tour 2

idee : 100% — tenu (4/4 justes, seuil 75%, pièges 1/1)
natures jamais jouées : indetermine
```

Le §7 est donc atteint : trois sur quatre au minimum, dont impérativement le
piège — l'énoncé-plateforme a bien été requalifié en problème d'engagement, au
quatrième tour et après une révision.

### La seconde campagne, et ce qu'elle dément

Même kata, même cible, même seuil, quelques heures plus tard — après un
resserrage du bloc d'état sans rapport avec le diagnostic :

```
✓ asso-choix-plateforme     attendu analysable  émis analysable  au tour 1
✗ asso-formation-continue   attendu emergent    émis analysable            [piège]
```

**Le piège est tombé.** Le kin dont l'énoncé demande une plateforme a été pris au
mot : c'est l'échec que le §6.3 annonce, et il survient au second tirage, sur une
forme que rien n'a changé de ce côté-là.

Le critère du §7 n'est donc **pas stablement atteint**. Il l'a été une fois. Une
réussite non reproductible ne démontre pas qu'un harness sait diagnostiquer :
elle démontre qu'il le peut. La différence compte, et le tableau ci-dessus le
dit maintenant.

Ce qu'il faudrait pour trancher : plusieurs passes des mêmes kin, et un compte de
réussite par kin plutôt qu'un verdict par campagne. Rien de tel n'est construit —
le banc mesure une campagne, pas une distribution.

**Ce que la première campagne ne dit pas.** C'est un tirage, sur un kata, sur une
cible, avec un moteur donné. Trois des quatre kin ont révisé leur diagnostic en
cours d'échange, ce qui est la vertu que le RFC réclame mais montre aussi que la
première lecture est rarement la bonne. La nature `indetermine` n'a jamais été
jouée : aucun kin du fil rouge ne la présente, donc rien n'est su de ce que le
kata en ferait. Et la conduite n'a pas été jugée dans cette campagne — seule la
justesse l'a été.

Décisions prises à l'application, hors du texte du RFC :

- **C'est la *dernière* nature émise qui compte, pas la première.** Le RFC pose
  la révisabilité comme une vertu ; compter la première la tuerait. Le tour de
  justesse, lui, ignore une bonne réponse ensuite abandonnée : tomber juste puis
  changer d'avis, ce n'est pas avoir diagnostiqué.
- **Les kin muets pèsent dans le dénominateur.** Ne pas diagnostiquer n'est pas
  se tromper, mais ce n'est pas réussir non plus — les sortir de la mesure
  flatterait le taux. Ils sont comptés à part dans le rapport.
- **La conduite est jugée sur la nature *diagnostiquée*, pas sur la nature
  réelle.** Sinon un diagnostic raté serait puni deux fois, et l'on ne saurait
  plus si la forme sait tenir une conduite.
- **Sans seuil déclaré, le seuil vaut zéro et le rapport le dit.** Zéro n'est pas
  une indulgence : c'est l'aveu qu'aucune exigence n'a été posée. Kokaji ne s'en
  invente pas à la place du harness (carnet #9).

- **La SPECS était déjà en v1.4.** Ce RFC annonce v1.3 → v1.4 ; le RFC-004, appliqué
  avant lui, avait déjà fait ce pas depuis la v1.3. La v1.4 porte donc les deux, et sa
  ligne de version les cite tous les deux. Aucun contenu n'est perdu : les deux RFC
  touchent des sections disjointes.
- **La tension du mode raccourci est tranchée par le non-requis, pas par la déduction.**
  Voir la section dédiée ci-dessous — c'est le seul endroit où ce RFC entre en conflit
  avec une règle déjà écrite du harness.
- **Le nom d'inspiration est banni mécaniquement.** Il est inscrit à la liste d'interdits
  de la trempe du dépôt, avec ce fichier pour seule exemption. Une règle qu'aucun outil
  ne tient finit par se perdre.

### La tension « mode raccourci » × « tous les champs bloquants »

Le §3 dit qu'en nature **évidente**, le kata converge en un minimum de questions et sort.
La règle du template disait, elle, que tous les champs du kata sont à renseigner avant le
passage. Les deux ne peuvent pas être vraies en même temps.

**Tranché : les champs non pertinents pour la nature sont marqués `non_requis`, jamais
remplis par déduction.** Un champ déduit se lit exactement comme un champ établi, et rien
dans le corpus ne permettrait plus de distinguer « on a vérifié » de « on a supposé parce
qu'on allait vite ». La sur-promesse deviendrait invisible, et le carré du RFC-002 la
manquerait — alors que c'est précisément ce qu'il existe pour attraper.

`non_requis` est donc un statut de champ à part entière, déclaré dans `etat.statuts_champ`
du harness, **rangé après `en_pause`** : c'est le plus faible de tous. Un kata qui promet
`fait_etabli` et livre `non_requis` est en sur-promesse, et le carré le dit. La conduite
raccourcie ne fait pas disparaître le contrat : elle le laisse visiblement non tenu, ce
qui est honnête, plutôt que faussement tenu, ce qui ne l'est pas.
