# Le corpus — les ha

Un **ha** est une exécution « cette fois-ci » : un kata appliqué, avec le
contexte et les connaissances du moment, à un sujet singulier. C'est l'unité qui
permet de comprendre ce qui marche (SPECS §0, §6).

Le corpus appartient au harness, pas à Kokaji. Un harness peut en déclarer
**plusieurs, nommés** (HDS v0.2) — les cas réels ne se mélangent pas aux essais :

```yaml
corpus:
  reel:
    chemin: corpus/reel/
    cles: [chat-public]      # les sessions issues de cette clé y vont
  essai:
    chemin: corpus/essai/    # tout le reste
```

La forme d'origine, `corpus: corpus/`, reste valide et vaut un unique corpus
nommé `reel`.

**Le tri se fait à la source, pas après coup.** Chaque ha porte la clé qui l'a
appelé — le chat, le banc, le QG — et c'est elle qui décide du corpus. Un corpus
sans `cles` prend ce qu'aucun autre ne revendique. Le QG applique le même
filtre : la vue d'un corpus ne montre jamais les sessions vivantes d'un autre.

## Un ha sur le disque

```
CAS-XXXX-titre/
  fiche.md        frontmatter YAML + constats et enseignements
  transcript.md   l'échange, tour par tour
  sortie.md       le livrable produit
  materiau/       ce qui a nourri la session — coupe injectée, tours envoyés
```

## Deux dépôts, une interface (RFC-014)

Le dossier ci-dessus est le **format d'échange** d'un ha. Ce qui le lit ou
l'écrit — le versement, la veille, le QG, l'usage, le banc, les commandes —
passe par un dépôt de ha (`kokaji/corpus/depot.py`), et il y en a deux :

- **les fichiers** — le régime d'aujourd'hui, celui d'un poste seul, du clone
  étranger et de la suite de tests ;
- **la base** — le Postgres de l'instance (`kokaji/corpus/base.py`), désigné
  par `KOKAJI_BASE_URL` (extra `pip install 'kokaji[base]'`). Un ha y est une
  ligne, ses pièces ses lignes ; la fiche, le transcript et la sortie y sont
  gardés entiers, ce qui rend l'export identique, octet pour octet, au dossier.

Sans `KOKAJI_BASE_URL`, rien ne bascule. Les deux dépôts tiennent le même
contrat, éprouvé par le même jeu de tests (`tests/test_corpus_depot.py`, la
CI pose un Postgres pour le second). `transferer(ref, de, vers)` fait passer
un ha de l'un à l'autre, dans les deux sens.

## Le frontmatter

| Champ | Rôle |
|---|---|
| `harness`, `kata`, `version_kata`, `version_coupe`, `cible`, `moteur`, `date` | l'identité de ha, reprise du journal du Dojo |
| `source` | `reel` \| `scenario` \| `simule` — d'où vient la matière |
| `statut` | `brut` \| `anonymise` \| `annote` — où en est le cycle de vie |
| `completude` | `A` \| `B` \| `C` — voir ci-dessous |
| `design_exerce` | les variables de design mises à l'épreuve — **noms du registre du harness** |
| `verdict` | le jugement porté, en quelques mots |
| `scores` | ce qui a été mesuré, pas ce qui a été ressenti |

`design_exerce` appartient au harness : Kokaji ne connaît pas cette taxonomie, il
vérifie seulement que les noms cités existent au registre.

### Les trois degrés de complétude

- **A** — transcript, livrable, matériau et annotation humaine. Exploitable pour
  le banc et pour la non-régression.
- **B** — transcript et livrable, sans annotation. Rejouable, pas encore
  interprétable.
- **C** — partiel : session interrompue, livrable absent, ou matériau manquant.
  Conservé, mais ne sert pas de référence.

## Verser le journal

```bash
kokaji corpus <harness> [--journal <dossier>] [--session <id>]... [--source reel|scenario|simule]
```

Écrit un ha `brut` par session trouvée dans le journal du Dojo : fiche,
transcript, dernière réponse, et la coupe injectée en matériau. Une session déjà
versée est ignorée, donc la commande se relance sans risque.

C'est une avance sur le middleware (§7), qui fera ce travail en continu. La règle
est la même : rien n'est jugé, rien n'est agrégé, rien n'est supprimé.

La promotion en `annote` reste un geste humain — on ouvre la fiche et on écrit,
ou `kokaji promouvoir <harness> CAS-XXXX…`, qui fait la même chose et **ajoute
l'ha au dépôt git du harness**. Car un ha brut n'y entre pas (RFC-014, lot 0) :
un harness naît avec un `.gitignore` sur `corpus/**/CAS-*/` — la donnée vivante
ne se versionne pas, sauf ce qu'un humain a décidé de garder avec la forme.

## Écarter un ha

```bash
kokaji purger <harness> [--corpus X] [--parasites | --session S] [--essai]
```

Un ha peut n'avoir rien à faire au corpus — un appel d'interface pris pour une
session, une sonde d'un seul tour. Le supprimer ne suffit pas : **le journal ne
perd rien**, et la veille le recrée au passage suivant, avec un numéro neuf.

Écarter, c'est donc **déclarer une décision**, consignée dans
`<corpus>/.ecartes.jsonl` :

```json
{"session": "…", "raison": "appel d'interface, pas une session de kata", "le": "…"}
```

La veille lit ce fichier et passe son chemin. Le transcript, lui, reste au
journal : on écarte du corpus, on n'efface pas la trace.

`--essai` montre ce qui serait écarté sans rien supprimer. **Un ha annoté n'est
jamais écarté à la volée** — comme pour le rafraîchissement, la promotion
humaine prime.

## Ré-abstraire un ha

```bash
kokaji reabstraire <harness> --ha CAS-XXXX [--corpus reel] [--modele …]
```

Un ha capturé sur une cible **non instrumentée** ne porte aucun bloc d'état : sa
conversation existe, son état non. On peut le reconstruire depuis le transcript
par un appel de modèle (RFC-002 §7.2).

**Ce n'est pas une observation.** Un bloc d'état est normalement
l'auto-abstraction de la pratique — le kata déclare ce qu'il a établi, pendant
qu'il l'établit. Reconstruire après coup produit une **lecture**, et le corpus
doit le dire :

- chaque relevé porte `reabstrait: true` et le modèle qui l'a produit ;
- la fiche porte `etat_reabstrait: true` et une réserve explicite ;
- `carre.md` précise que son verdict porte sur une lecture ;
- le QG l'affiche en tête de vue.

Sans ce marquage, le corpus mentirait sur sa propre nature — et c'est exactement
ce que le principe d'observabilité interdit.

## Le cycle de vie

1. **brut** — écrit par le middleware à la clôture de toute session, sans geste
   humain. La capture n'est jamais conditionnelle (R7.3).
2. **anonymisé** — le sujet est vérifié ou neutralisé. Automatique s'il est
   déclaré fictif.
3. **annoté** — promotion humaine : `design_exerce`, verdict, constats,
   enseignements.

Un ha annoté dit toujours **ce qu'il ne prouve pas**. Un tirage n'est pas une
mesure : sans température fixée ni persona joué par le banc, un ha renseigne sur
ce qui *peut* arriver, jamais sur ce qui arrive *habituellement*. La section
« Réserves » de la fiche existe pour ça.
