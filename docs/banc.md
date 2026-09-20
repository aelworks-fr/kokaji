# Le banc

```bash
kokaji banc <harness> --kata <id> [--modele <virtuel>]... [--persona <id>]...
            [--tours N] [--temperature T] [--detail]
```

Joue les personas déclarés par le harness contre un kata, à travers le Dojo, et
lit ce qui s'est passé (SPECS §5).

## Ce qu'est une session de banc

Rien de particulier. Elle passe par la passerelle avec sa propre clé, elle est
journalisée comme toute autre, elle produit un ha. Le banc n'ouvre aucune porte
dérobée : il ne lit jamais une coupe directement, sinon il éprouverait autre
chose que ce que vit une vraie session.

Deux échanges se déroulent en parallèle, et **chacun ne voit que le sien** :

- le **persona** reçoit sa consigne — sujet, posture, pièges — et les répliques
  du kata. Il ignore la coupe.
- le **kata** reçoit la coupe injectée par la passerelle et les répliques du
  persona. Il ignore la consigne du persona.

Le persona est servi par un modèle déclaré dans `KOKAJI_MODELES_NUS`, que le
hook laisse passer sans injection : un persona n'est pas un kata, il ne
s'incarne pas.

## La température

Figée à `0` par défaut. Comparer deux coupes sans fixer la température, c'est
mesurer la somme de deux variations — celle qu'on cherche et celle du moteur.

## L'évaluation déterministe

Deux familles, qui ne se mélangent pas.

**Les checks du harness**, déclarés dans son manifest. Kokaji exécute des types
de règles, il n'en écrit aucune :

| Type | Ce qu'il fait |
|---|---|
| `regex-par-tour` | compte les **occurrences** d'un `motif` par tour, au-delà de `maximum`. `ignorer` exclut des lignes du décompte. |
| `regex-par-bloc` | compte les **paragraphes** où le `motif` apparaît. Les blocs de code sont exclus. |
| `interdit` | signale la présence d'un des `motifs` dans un tour. |

### Pourquoi deux types de comptage

`une-question-par-tour` a d'abord été déclaré en `regex-par-tour` sur `\?`. Il
signalait 34 % des tours, dont la plupart à tort : compter les symboles confond
une question qui propose ses options en ligne, une question de l'interlocuteur
citée, et deux questions réellement distinctes. Un tour qui en posait deux était
compté 8.

Le paragraphe sépare ces trois cas — une question et ses options tiennent
ensemble, deux questions distinctes se rédigent séparément. Rejoué sur le
journal : 15 % de tours signalés, maximum 3. Proxy assumé, mais qui mesure
quelque chose.

Un type inconnu arrête le banc : mieux vaut refuser que passer en silence sur
une règle que le harness croit appliquée.

**Les invariants de Kokaji**, qui portent sur la structure qu'il impose — le
bloc d'état, et lui seul :

- `etat-bien-forme` — le bloc annoncé se lit et porte ses sections
- `etat-champs-declares` — aucune clé de `champs` hors du gabarit forgé
- `etat-statuts-declares` — statuts et confiances dans les taxonomies déclarées
- `etat-passage-declare` — `pret_pour` désigne un nœud que la chaîne place après
- `etat-options-declarees` — options émises par un kata qui les déclare, chacune
  avec identifiant, libellé non vide et nœud de la chaîne (RFC-001)
- `etat-decision-coherente` — `ferme` et `ouvre` ne citent que des options
  déclarées, éventuellement plusieurs tours plus tôt

## Le rapport

Une ligne par session, comparables entre modèles et entre cibles (R5.6) :

```
persona         kata  modèle                     tours  blocs  constats  règles en faute
porteur-bavard  idee  atelier/idee               8      0      2         une-question-par-tour
porteur-bavard  idee  atelier/idee@instrumentee  8      0      6         une-question-par-tour
```

`--detail` liste chaque constat, situé à son tour.

## Le juge (deuxième étage)

```bash
kokaji banc <harness> --kata … --juge <modele> [--variable <nom>]...
```

Beaucoup de variables de design ne se comptent pas : *« le livrable n'affirme-t-il
que ce qui a été dit ? »* ne se mesure pas par une expression régulière. Le juge
répond à ces questions-là.

**Kokaji fournit le mécanisme, le harness fournit la grille.** Les variables
vivent dans `registre.design_exerce`, avec la question qu'elles posent ; aucune
question n'est écrite dans le code.

### Quatre règles, et pourquoi elles sont là

**Une question à la fois.** Posées ensemble, elles s'entraînent : la seconde
hérite du ton de la première.

**La consigne est à charge.** On demande au juge de *chercher le manquement*, pas
d'évaluer la conformité. `tenue` ne s'obtient qu'après avoir cherché sans
trouver.

**Un bloc d'état n'est pas citable.** Il dit ce que le kata *déclare*, pas ce
qu'il *fait* — les blocs sont retirés de la matière qu'on donne au juge.

**Une accusation demande une preuve ; un acquittement, non.** Seul `non-tenue`
exige un extrait, et cet extrait est **vérifié** : il doit se retrouver
littéralement dans l'échange, sinon le verdict est écarté. Une citation inventée
ne prouve rien.

`indecidable` reste une réponse pleine, et un verdict est un avis : le modèle qui
l'a rendu est inscrit à côté, rien ne l'agrège en score. Un juge qui répond mal
ne fait pas tomber l'évaluation — chaque écart est constaté.

### Ce que ces règles ont coûté à trouver

**Premier essai : 8 verdicts sur 8 en « tenue ».** Un juge qui ne contredit
jamais ne mesure rien. Pire, sur `separation-etabli-suppose`, il citait comme
preuve de conformité `hypotheses_de_valeur: en_cours` — la faute même que l'étage
déterministe signalait au même tour. Il prenait une violation pour une preuve de
respect.

**Deuxième essai, consigne à charge : 6 verdicts sur 8 « illisibles »**, faute de
citation. La règle était contradictoire : on ne cite pas la preuve d'une absence.
Demander un extrait à l'appui d'un `tenue` force le juge à en inventer un — ou,
comme mesuré, à se taire.

**Troisième essai** : un `non-tenue` argumenté, un `indecidable` motivé, six
`tenue` qui montrent leur recherche — *« j'ai cherché un moment où la forme cède
à une demande directe de solution… aucun tour ne la voit fournir une solution
clé en main »*.

### Ce qui ne va toujours pas

L'unique `non-tenue` du troisième essai porte sur `une-question-par-tour`, et le
juge **réinterprète la variable** : il reproche au kata de ne pas avoir posé de
question en retour, là où la variable demande de n'en poser qu'une. Le biais de
complaisance est traité ; la justesse de lecture ne l'est pas.

Piste non explorée : faire juger par plusieurs modèles et ne retenir que la
majorité. Une seule voix reste une opinion.

## La non-régression (R5.6)

```bash
kokaji regression <harness> [--corpus X] [--variable <nom>]... [--plafond N] [--essai]
```

Un ha porte la version de coupe qui l'a produit. Quand la source change, la forge
en produit une autre : les ha nés de l'ancienne deviennent **périmés** — ils
documentent une forme qui n'existe plus. La commande les repère en comparant leur
`version_coupe` à celle que la forge rend aujourd'hui, **sans rien écrire**.

`--variable` restreint aux ha qui exercent une variable de design donnée : c'est
le « rejouer les ha exerçant les variables touchées » du R5.6. Les variables
viennent de l'annotation du ha ; un ha `brut` n'en porte aucune.

### Le rejeu

Il reprend **les tours de l'interlocuteur tels qu'ils ont été dits** et les
rejoue contre la coupe actuelle. Même matière, forme nouvelle : ce qui diffère
vient de la forme, et de rien d'autre.

Deux règles le tiennent :

- **Les deux côtés sont évalués avec les checks d'aujourd'hui.** Comparer une
  ancienne note à une nouvelle mêlerait deux changements — celui de la coupe et
  celui du check. L'ancien transcript est donc réévalué, pas relu.
- **Un rejeu n'est pas la session d'origine.** L'interlocuteur y est une
  transcription, pas une personne : il ne réagit pas à ce que la nouvelle forme
  dit. Le rejeu montre ce que la forme fait d'une matière donnée, pas comment
  l'échange aurait tourné.

### Ce qu'il rend

```
= CAS-0002-relance-non-bornee — rien n'a bougé
⚠ CAS-0003-cadrage-instrumentee-82b2a1
    ↓ pas-de-solution-non-sollicitee : 1 → 0
    ↑ une-question-par-tour : 0 → 4
  CAS-0005-cadrage-instrumentee-d6ef3e
    ↓ etat-statuts-declares : 5 → 0
    ↓ une-question-par-tour : 4 → 3
```

Le `⚠` marque une **régression** : une règle qui mord là où elle se taisait. La
commande sort en erreur s'il y en a une. Les flèches vers le bas sont des gains —
le CAS-0005 montre les cinq fautes de taxonomie disparues avec la coupe corrigée.

## Le resserrage (RFC-002 §6.4)

```bash
kokaji resserrer <harness> [--corpus X] [--minimum N]
```

Le régime « prudence » permet de sous-promettre : un `produit` en dessous de ce
que la pratique livre reste conforme. C'est ce qui rend les contrats stables
pendant que les kata s'améliorent — et la RFC nomme elle-même le prix : **la
composition du slack**. Trois kata qui sous-promettent un peu font un contrat de
bout en bout très en dessous de la pratique.

Ce lint mesure l'écart sur le corpus et **propose** un resserrage :

```
idee — 4 ha observé(s)
  = idee.besoin : `fait_etabli` tient au plus juste
  ↑ idee.valeur_visee : déclaré `hypothese`, tenu à `fait_etabli` sur 4/4 ha

  - id: idee
    produit:
      - idee.valeur_visee: fait_etabli   # resserré
```

Trois règles :

- **Une garantie est un minimum**, donc le statut proposé est le **plus faible
  observé**, jamais le plus fréquent. Un seul ha en dessous suffit à retenir la
  promesse.
- **En deçà de `--minimum` ha, on ne conclut rien.** Trois par défaut. Un
  resserrage sur un tirage n'est pas un resserrage.
- **Rien n'est appliqué.** Modifier un f♯ est une version majeure du kata, et
  cette décision appartient au forgeron (RFC-002 §3). La commande rend un
  fragment à coller.

Le cas inverse — un `produit` que la pratique ne tient pas — n'est pas l'affaire
de ce lint : c'est la sur-promesse, et le carré continu la détecte déjà (§6.3).

## Ce qui n'existe pas encore

L'**échantillonnage humain**, troisième étage du R5.5 — le seul qui, par
définition, ne s'automatise pas.

## La justesse du diagnostic (RFC-003 §5.4) — construit

`kokaji banc --kata <k> --nature` mesure, après avoir joué : la nature émise par
le kata contre la `typologie:` déclarée du kin, le tour où le diagnostic s'est
posé, les révisions en chemin, les natures jamais jouées, et le verdict face au
seuil que le harness s'est donné dans `trempe.justesse`.

Avec `--passes N`, chaque kin est rejoué N fois et le rapport devient une
**distribution** (RFC-003 §7) : un compte de réussite par kin, et un verdict de
stabilité — tenu seulement si chaque kin passe son seuil et si tout kin piège
tombe juste à *chaque* passe. Une réussite unique prouve qu'un harness *peut*
diagnostiquer ; N passes disent s'il le *sait*.

Avec `--juge`, la **conformité de conduite** s'y ajoute : le juge est interrogé
sur le contrat du §3 correspondant à la nature *diagnostiquée* — les questions
viennent de `conduite_par_nature` au registre du harness, aucune n'est écrite
dans Kokaji.

Première campagne, août 2026 : `idee@instrumentee`, 4/4 justes dont le piège.
Le détail et ses limites sont dans le [RFC-003](rfc-003-diagnostic-de-nature.md).

### Ce qui reste

Le texte ci-dessous décrivait le travail avant qu'il soit fait. Ce qui n'est
toujours pas construit :

- **La matrice kata × typologie à travers plusieurs campagnes.** La couverture
  est calculée pour *une* campagne ; rien n'agrège l'histoire des campagnes.
- **Le rejeu de campagne.** Rien ne conserve un résultat de justesse : chaque
  mesure vit dans son rapport et disparaît. Comparer deux versions d'un kata sur
  la justesse demande de relancer les deux.

Rien de ce qui suit n'est construit. Le matériau l'est : les quatre kin du fil
rouge « Se former à l'asso » vivent dans `harness/atelier/personas/`, chacun
portant sa `typologie:`, et le piège portant en plus son `enonce_comme:`.

Ce que le pas 4 aura à faire :

- **Lire `typologie:` et `enonce_comme:`** au chargement d'un persona. Le
  chargeur les ignore aujourd'hui : les deux champs sont dans les fichiers, pas
  encore dans le modèle.
- **La matrice de couverture kata × typologie** — quel kata a été éprouvé contre
  quelles natures, et lesquelles n'ont jamais été jouées.
- **La justesse** : la nature émise par le kata correspond-elle à la typologie
  déclarée du kin, et au bout de combien de tours.
- **La conformité de conduite** : le kata a-t-il tenu le contrat du RFC-003 §3
  pour la nature qu'il a diagnostiquée. C'est une grille de juge, déclarée dans
  la trempe du harness — donc du vocabulaire de domaine, pas de Kokaji.
- **Le seuil d'acceptabilité par kata**, écrit avant la campagne qu'il juge, et
  le kin piège compté à part : [carnet #9](carnet.md).

Le critère « juste assez » du RFC-003 (§7) — trois diagnostics justes sur quatre,
dont impérativement le piège — **n'est pas vérifiable avant ce pas**. Il ne sera
pas simulé d'ici là : un critère qu'on déclare tenu sans l'avoir mesuré ne vaut
rien, et vaut même moins que rien puisqu'il ferme la question.
