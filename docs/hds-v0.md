# HDS v0.1 — Harness Definition Standard

Le contrat entre Kokaji et un harness. Kokaji n'interprète que ce standard : il
ne sait rien du domaine qu'un harness couvre (SPECS §0).

Le HDS est versionné indépendamment de Kokaji. Ce document décrit la **v0.2**.

Changements depuis la v0 : `heritage` est renommé `herite` et ses champs sont
qualifiés ; `produit` est ajouté ; la clé `champs` de la source d'un kata
disparaît au profit de `produit` ([RFC-002](rfc-002-check-galoisien.md) §3).

## Le dossier

Un harness est un dossier autonome — un dépôt séparé est recommandé pour les
harness non publics. Kokaji le charge comme une donnée, jamais comme du code.

```
harness.yaml     le manifest — seul fichier dont le nom est imposé
template.md      le template commun, avec ses {{ variables }}
registre.yaml    les noms canoniques et les variables de design
kata/<id>.yaml   les valeurs des variables, un fichier par kata
personas/        les profils d'utilisateur simulé pour le banc
corpus/          les ha capturés et promus
```

Les chemins déclarés dans le manifest sont relatifs à ce dossier et ne peuvent
pas en sortir. Seul `harness.yaml` a un nom imposé : tous les autres se
déclarent.

## Le manifest

Sept sections, toutes obligatoires sauf `etat`.

### `harness` — l'identité

| Clé | Attendu |
|---|---|
| `id` | slug unique : minuscules, chiffres, tirets. Il préfixe **tout** ce que Kokaji manipule — modèles virtuels, journaux, ha, corpus — pour que plusieurs harness cohabitent sans se mélanger. |
| `nom`, `version` | texte libre ; la version appartient au harness, pas à Kokaji |
| `langue` | code de langue ; `fr` par défaut |
| `domaine` | le processus couvert, en une phrase. **Documentaire** : transporté tel quel, jamais interprété. |

### `kata` — les formes

Une liste ordonnée, dans l'ordre logique du domaine. Chaque entrée :

| Clé | Attendu |
|---|---|
| `id` | slug, unique dans le harness |
| `nom` | le nom lisible |
| `source` | chemin du fichier de variables — doit exister |
| `livrable` | le nom du document produit |
| `amont` | ids des kata dont il hérite ; ils doivent exister, sans cycle |
| `herite` | **f♯ domaine** — les champs attendus de l'amont, qualifiés `<kata>.<champ>`. Le préfixe doit désigner un amont déclaré. Hériter sans amont est une faute. Anciennement `heritage` ; l'ancien nom est refusé avec un message de renommage. |
| `produit` | **f♯ codomaine** — une liste de `<kata>.<champ>: <statut>`. Le préfixe doit être le kata lui-même ; le statut doit appartenir à `etat.statuts_champ` et vaut le **minimum garanti** par la pratique. |
| `emet_options` | booléen, `false` par défaut. `true` : ce kata élicite et suit des options, et son bloc d'état porte `options` et `decision` (SPECS §7, R8.4). Kokaji ne sait pas ce qu'est une option dans ce domaine — il sait seulement que ce kata en déclare. |
| `raccourci` | RFC-016 — nom d'usage : `echange` (défaut, modèle seul), `sonde` (+ lecture du monde), `production`/`commande` (+ écriture). Absent, il se déduit des `effets` ; inconnu, c'est une faute. |
| `intention` | RFC-016 — l'objet décisionnel de l'étape, libre. Optionnel. |
| `perception` | RFC-016 — `entrees:` et `retours:`. Les **retours** sont les canaux par lesquels le kata constate ses effets sur le monde. |
| `effets` | RFC-016 — par canal : `monde_lecture:` (échantillonné sans être modifié), `monde_ecriture:` (modifié). Le canal `modele` est universel et implicite (le bloc d'état, cf. `produit`). |

### Le triplet — une étape qui agit (HDS refondu, RFC-016)

Un kata est une étape décisionnelle qui **agit** : elle perçoit, porte une
intention méta, produit des effets. La conversation en est le cas le plus simple
— l'échange, où le seul effet est le bloc d'état (canal `modele`, universel).

```yaml
kata:
  - id: tests
    raccourci: sonde              # optionnel — se déduit des effets sinon
    intention: "établir si la suite passe sur le périmètre figé"
    perception:
      entrees: [suite_de_tests, perimetre_fige]
      retours: [rapport_de_tests]  # par où l'on constate l'effet
    effets:
      monde_lecture: [execution_suite]
```

Deux règles tiennent le triplet à ce niveau (les vérificateurs exécutables et le
routage viennent aux lots suivants de la RFC-016) :

- **Migration mécanique.** Tout absent, le kata vaut l'échange. Un manifeste
  d'avant la RFC-016 reste valide sans une retouche, et se joue à l'identique.
- **Interdit n°1 — pas d'action aveugle.** Tout effet du monde
  (`monde_lecture`/`monde_ecriture`) doit avoir son **retour** de perception :
  agir sans pouvoir constater ce qu'on a fait rend le manifeste invalide.

### `chaine` — la topologie

Ce que le QG rendra (§8). Kokaji la valide, ne l'interprète pas.

- `noeuds` : `id` unique, `type` parmi `kata | jalon | externe`, `nom`. Un nœud
  de type `kata` doit correspondre à un kata déclaré.
- `aretes` : `de` et `vers` doivent désigner des nœuds existants ; `label` libre.
- **Tout kata déclaré doit figurer dans la chaîne.** L'inverse est permis : la
  chaîne peut porter des jalons et des étapes externes au harness.

### `template` — le fichier commun

Chemin du template. Les blocs fixes portent la doctrine du harness ; les
`{{ variables }}` sont résolues à la forge.

| Variable | Résolue depuis | Rendu |
|---|---|---|
| `en_tete` | `cibles[].en_tete` | tel quel |
| `kata_nom` | `kata[].nom` | tel quel |
| `role` | `source.role` | tel quel — **obligatoire** |
| `interdits` | `source.interdits` | liste à puces |
| `questions` | `source.questions` | liste numérotée — **obligatoire** |
| `livrable_nom` | `source.livrable_nom`, sinon `kata[].livrable` | tel quel |
| `livrable_structure` | `source.livrable_structure` | liste à puces — **obligatoire** |
| `passage` | `source.passage` | tel quel — **obligatoire** |
| `heritage` | `kata[].amont` + `kata[].heritage` + `registre.champs` | section entière, **vide** si le kata n'a pas d'amont |
| `etat` | `etat` + `cibles[].etat_structure` + `source.champs` + `chaine` | section entière, **vide** si la cible ne la demande pas |

Le fichier `source` d'un kata porte aussi deux clés hors template :

- `version` — la version de la forme elle-même, reprise dans l'estampille.
  Sans elle, la version du harness sert de repli.
La clé `champs` de la v0 **n'existe plus** : le bloc d'état se construit depuis
`herite` puis `produit`, une seule source de vérité. La forge refuse une source
qui la porte encore.

Une variable du template sans valeur, ou une variable obligatoire vide, arrête
la forge. Aucune coupe n'est écrite avec un trou.

### Un kata en texte — l'orphelin (HDS v0.2, RFC-011)

Une `source` qui se termine par `.md` est **un texte servi tel quel** : le kata
est orphelin — il n'est pas assemblé depuis le gabarit, il ne tient pas de
contrat (`herite` et `produit` vides, sinon faute), son `livrable` est
facultatif (le nom en tient lieu), et il déclare d'où il vient :

```yaml
  - id: devis
    nom: Répondre à un devis
    source: kata/devis.md
    provenance: { source: "…", checksum_import: "…", date_import: "…" }
```

Un kata natif ne déclare pas de `provenance` ; un harness `exogene: true`
(RFC-008) est le cas où tous les kata sont orphelins, et la provenance est
alors celle du harness. Un gabarit importé tel quel porte la sienne au
manifest, sous `provenance_du_gabarit:` — mêmes clés.

### `cibles` — les profils de forge

Une liste non vide. Chaque cible produit son propre jeu de coupes.

| Clé | Attendu |
|---|---|
| `id` | slug, unique |
| `etat_structure` | booléen. `true` : les coupes émettent le bloc d'état aux points d'étape. `false` : elles n'en portent **aucune trace**. |
| `en_tete` | l'en-tête injecté |
| `packaging` | `dossier` ou `zip` |

Les cibles sont nommées par le harness. Kokaji n'en connaît aucune d'avance.

### `trempe` — ce qui bloque et ce qui mesure

| Clé | Attendu |
|---|---|
| `vocabulaire_interdit` | mots bannis des coupes **de ce harness** |
| `registre` | chemin du registre canonique — doit exister |
| `checks_session` | règles dynamiques déclaratives ; chacune porte au moins `id` et `type` |

Le harness définit ses propres interdits. Kokaji n'en impose aucun au niveau du
domaine — il n'a que ses invariants de structure (§5 R5.5).

### `etat` — la spécialisation du bloc d'état

Facultative. Sans elle, Kokaji applique ses défauts :

```yaml
statuts_champ: [fait_etabli, hypothese, en_pause]
statuts_hypothese: [en_cours, validee, infirmee, en_pause]
```

**L'ordre de `statuts_champ` porte une sémantique** : il range les statuts du plus
fort au plus faible. C'est cet ordre qui dit si un statut en couvre un autre —
l'ordre de D au sens de la [RFC-002](rfc-002-check-galoisien.md) §2. Un harness
qui surcharge la liste choisit donc aussi son ordre.

### `personas`

Chemin de dossier ; il doit exister, même vide.

### `corpus`

Un chemin — ou plusieurs **corpus nommés**, chacun avec les clés appelantes qui
l'alimentent :

```yaml
corpus:
  reel:
    chemin: corpus/reel/
    cles: [chat-public]
  essai: corpus/essai/
```

Le premier déclaré est celui qu'on lit par défaut. Un corpus sans `cles` reçoit
ce qu'aucun autre ne revendique. La forme simple, `corpus: corpus/`, reste
valide et vaut un unique corpus nommé `reel`.

## La validation

```bash
kokaji valider <dossier> [<dossier>...]
```

Deux règles de conduite :

1. **Rien n'est complété en silence.** Un manifest incomplet est refusé. Les
   seuls défauts appliqués sont ceux de `etat`, et ils sont documentés ci-dessus.
2. **Toutes les fautes sont rendues d'un coup**, chacune située par son chemin
   dans le manifest — `kata[1].amont`, `cibles[0].packaging`. La validation ne
   s'arrête pas à la première.

Sortie `0` si tous les harness passent, `1` sinon. Deux dossiers portant le même
`id` sont refusés ensemble : l'isolation repose sur l'unicité de l'id.
