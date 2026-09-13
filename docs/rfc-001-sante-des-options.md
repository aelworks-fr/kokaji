# RFC-001 — La santé des options, mesure de première classe du QG

> Statut : **accepté sur le principe** (séance de conception, août 2026) — intégré
> aux SPECS (passage v1.1 → v1.2).

## Motivation

Le gradient terminal du projet (et de son auteur) est la **survie des possibles** :
préserver la fécondité de l'espace des options, pas seulement livrer de la valeur.
Le QG ne doit donc pas répondre à la seule question « qu'est-ce qui est validé ? »
mais aussi à « **combien de possibles restent vivants, et qu'est-ce que chaque
décision en a coûté ?** ». Une chaîne qui livre en brûlant ses options à toute
vitesse est en train de perdre selon ce critère, même si chaque livraison est un
succès.

## Principe de tractabilité

On ne mesure **pas** l'espace réel des possibles (non mesurable). On mesure
l'espace **déclaré** : les options articulées en session — même geste épistémique
que les statuts `fait_etabli/hypothese/en_pause`, qui mesurent un statut déclaré,
pas une vérité. Le proxy est assumé, biaisé, et honnête.

## Modèle

**Option** — une possibilité identifiée et nommée, non engagée :
`{ id, libelle, noeud, nee_etape, statut }`.
Statuts v1 : `ouverte` | `engagee` (devenue travail) | `ecartee` (fermée, avec
raison). *(La « dormance » n'est pas un statut : c'est un âge — dérivé, pas
déclaré.)*

**Décision** — toute coupe opérée en session (choix d'un prochain pas, d'un
périmètre, d'une piste) déclare son delta :
`{ libelle, ferme: [ids], ouvre: [ids] }`. Le coût en possibles d'une décision
devient un **fait observé**, pas une impression.

## Changements de spec (v1.2)

### 1. §7 — extension du bloc `kokaji_state` (champs optionnels)

```json
"options": [
  { "id": "OPT-1", "libelle": "", "noeud": "", "statut": "ouverte|engagee|ecartee" }
],
"decision": { "libelle": "", "ferme": ["OPT-2"], "ouvre": ["OPT-4"] }
```

Émis uniquement par les kata qui manipulent des options (déclaré au manifest).
Règle inchangée : bloc malformé loggé, jamais bloquant (R7.2).

### 2. §2 — manifest HDS : déclaration par kata

```yaml
kata:
  - id: ""
    emet_options: false     # true = ce kata élicite et suit des options
```

### 3. §8 — QG : nouvelle exigence

- **R8.4 — Seconde lecture du fil d'ariane : la santé des options.** Par nœud et
  par sujet : le compte d'options vivantes, leur liste, leur âge ; par décision :
  son delta (fermées / ouvertes). Visuel v1 : un badge numérique par nœud + un
  panneau « possibles vivants » du sujet. Pas de halo ni d'animation en v1.

### 4. Métriques v1 — juste assez, et rien de plus

Nombre d'options ouvertes (par nœud, par sujet) · âge médian des options
ouvertes · delta par décision. **Aucun indice composite, aucun score de fécondité
en v1** — un chiffre agrégé magique inviterait au pilotage aveugle ; on regarde
d'abord les données brutes vivre.

### 5. Vigilance #8 (ajoutée au carnet) — Goodhart

La mesure est **descriptive, jamais un objectif** : pas de cible chiffrée
d'options, sous peine d'inflation d'options fictives (un libellé sans substance
pour gonfler le compteur). Parades : une option n'existe que nommée et tracée en
session ; le QG lit et n'évalue pas ; toute lecture normative (« ce sujet brûle
ses options ») reste un jugement humain devant les données.

### 6. §9 — Atelier (fixture)

Le kata `cadrage` passe `emet_options: true` : les hypothèses de valeur non
retenues et les variantes de premier incrément deviennent les options de
démonstration. Le kata `decoupage` déclare ses décisions (delta fermé/ouvert) sur
le choix des étapes.

## Critère « juste assez » de la fonctionnalité

Dérouler une session `atelier/cadrage` : le QG affiche le nœud avec ses n options
vivantes ; prendre une décision en session ; le delta (fermées/ouvertes) apparaît
au QG **sans aucune saisie manuelle**. Trois coches : options visibles, décision
tracée, zéro geste humain.

## Note d'intention (pour mémoire)

Chaque décision est une coupe — *de-caedere*, trancher. Ce RFC ne demande qu'une
chose : que la coupe déclare ce qu'elle tranche. Le reste (compter, dater,
afficher) est de la tuyauterie. C'est ce qui rend possible ce qui semblait
impossible : on n'instrumente pas l'espace des possibles, on instrumente **le
geste qui le referme**.

## État d'application

| Changement | État |
|---|---|
| §2 — `emet_options` au manifest, validé par le HDS | appliqué |
| §7 — extension du bloc d'état | appliqué — la forge l'émet, le middleware la stocke |
| §8 — R8.4 | appliqué — badge par nœud, panneau « possibles vivants », trois métriques |
| §7 — la forge émet le gabarit pour les kata déclarés | appliqué |
| §7 — le banc vérifie options et décisions | appliqué |
| §9 — fixture Atelier | appliqué |
| Vigilance #8 | au carnet |
