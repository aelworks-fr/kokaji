# RFC-012 — Un harness, un dépôt : l'enregistrement, et ce qu'il change à l'ergonomie

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : RFC-009 (D9.1 « un repo git par harness », §3 « l'enregistrement », D9.4 souveraineté), RFC-006 (naître), RFC-004 §3 (droits), RFC-010 (le scellement commite). Objet : faire exister le geste que la RFC-009 nommait sans le poser — **chaque harness est un dépôt git** — et adapter la naissance, le module Design et le Profil à ce fait. **Périmètre : des dépôts locaux, sur la machine de l'instance.** L'interconnexion avec une forge distante (GitHub ou autre) est différée, et sa forme est déjà décidée (§6).

---

## 1. Motivation

Depuis la RFC-010, un scellement depuis le QG commite le harness dans le dépôt qui le contient. C'est un demi-geste : sur la première instance, « le dépôt qui le contient » est le dépôt de l'instance entière, où cinq harness se partagent un historique avec le déploiement. Un harness n'est pas une chose qu'on peut cloner, donner, reprendre ailleurs — il est un sous-dossier.

La RFC-009 D9.1 avait tranché le régime — *un repo git par harness, enregistré auprès de l'instance* — et son §3 décrit l'enregistrement : « l'instance note l'URL (ou le chemin local), le commit de référence, et forge depuis là ». Rien de cela n'existe. La carte de conviction porte ce trou au critère B, ouvert depuis le 13 septembre.

Ce RFC pose le geste, en local, et tout ce que le geste entraîne à l'écran : on ne peut pas faire d'un harness un dépôt sans que la naissance le sache, sans que le Design le montre, sans que le Profil dise lequel a des modifications non scellées.

## 2. Ce qu'un dépôt fait à un harness

```
DÉPÔT NU (un chemin de la machine)           — la vérité durable, d'où l'on clone depuis son poste
   │  pousser au scellement · tirer à la demande       (facultatif : un harness peut vivre sans)
   ▼
harness/<id>/  (un clone git à part entière) — ce que l'instance sert et édite
   │  scellement = commit (RFC-010)
   ▼
COUPES · HA · ÉTAT                           — dérivés et données vivantes, hors du dépôt (D9.1)
```

Le dépôt ne sait pas où il est enregistré : l'enregistrement est **une métadonnée d'instance**, jamais du manifest (RFC-009 §4). Tout ici tient sur une machine : aucune émission réseau, D9.4 reste entière.

## 3. Décisions scellées

### D12.1 — Un harness est un dépôt git, l'instance n'en suit pas le contenu

`harness/<id>` est un dépôt git à part entière — `git init` à la naissance, commit à chaque scellement (RFC-010). Le dépôt de l'instance **ignore** le dossier des harness : il porte le déploiement, plus le contenu.

**Migration de la première instance** : chaque harness quitte le dépôt de l'instance par `git subtree split`, qui garde son historique, vers un dépôt à lui. Le dépôt de l'instance garde le sien, sans réécriture (RFC-009 §6).

### D12.2 — Le distant, s'il existe, est un chemin de la machine

Un harness peut être **enregistré** auprès d'un **dépôt nu** local — un chemin, `/srv/depots/<id>.git` par exemple. C'est de là qu'on clone depuis son poste, en SSH, pour éditer dans un vrai éditeur ; c'est là que le scellement pousse. Un harness sans dépôt nu est un harness normal, marqué *non enregistré* : il a son historique local, et rien ne l'empêche de vivre.

L'enregistrement est une ligne du magasin de l'instance, à côté de l'ACL du harness :

```
harness_depot : harness_id · chemin · branche · commit_reference · pousser_au_scellement · enregistre_le
```

`commit_reference` est le dernier commit connu du dépôt nu pour cette branche, posé à l'enregistrement et à chaque tirer ou pousser : il permet de dire *à jour*, *en avance*, *en retard* ou *divergé* sans relire le dépôt nu à chaque page. **Désenregistrer ne détruit rien** : la ligne s'efface, le clone reste, le dépôt nu vit sa vie.

### D12.3 — Trois gestes, et jamais de fusion

- **Enregistrer** : soit lier un dépôt nu à un harness existant — créé s'il n'existe pas, et l'historique local y est poussé —, soit **cloner** un dépôt nu pour faire naître un harness. Dans les deux cas, le dépôt est chargé et **validé** (R2.1) avant que la ligne ne s'écrive : un dépôt qui n'est pas un harness n'est pas enregistré.
- **Pousser** : la branche enregistrée, en avance rapide. Le scellement pousse s'il est réglé pour (`pousser_au_scellement`, vrai par défaut quand un dépôt nu existe), sinon on pousse depuis le panneau.
- **Tirer** : en avance rapide seulement, et seulement si le clone est propre. Un clone qui a des modifications non scellées, ou une branche qui a divergé, **refuse** et le dit. Kokaji ne fusionne jamais : une fusion est un jugement sur deux définitions, ça se fait dans un éditeur, pas dans un service.

Un harness qui a divergé reste servi tel qu'il est sur le disque : le panneau montre l'état, il ne bloque rien.

### D12.4 — Naître, avec ou sans dépôt nu

La naissance (RFC-006) gagne une troisième voie et un choix :

- *copier* un harness, *semer* — les voies existantes — ou **cloner** un dépôt nu qui est déjà un harness ;
- pour les deux premières, **enregistrer un dépôt nu** tout de suite, ou plus tard.

Le dialogue dit ce que chaque voie fait à la pratique — le corpus reste vide, comme aujourd'hui — et ce qu'elle fait au dépôt.

### D12.5 — L'ergonomie suit le fait

- **Design du harness** — un panneau « Dépôt », à côté de « qui forge avec moi » : l'état (*non enregistré · à jour · en avance de N · en retard de N · divergé*, et *modifications non scellées* quand le clone n'est pas propre), le dernier commit, le chemin du dépôt nu s'il y en a un, les boutons *pousser* et *tirer*, la case *pousser à chaque scellement*, *enregistrer* ou *désenregistrer*. Enregistrer et désenregistrer sont des gestes de propriétaire ; pousser et tirer, de co-auteur (RFC-004 §3, étendue).
- **Profil — mes harness** — le même état, en badge, par harness.
- **La trace du scellement** — déjà « commité : abc123 » ; devient « commité et poussé », ou « commité, non poussé — pourquoi ».

## 4. La surface

| Route | Geste | Droit |
|---|---|---|
| `GET /depot` | l'état du dépôt du harness courant | lire |
| `PUT /depot` | enregistrer : chemin, branche, pousser_au_scellement | propriétaire |
| `DELETE /depot` | désenregistrer — la ligne, pas le clone | propriétaire |
| `POST /depot/pousser` | pousser la branche, en avance rapide | éditer |
| `POST /depot/tirer` | tirer, en avance rapide, clone propre exigé | éditer |
| `POST /naissance` | existante ; gagne `depot: { chemin, branche }` et la voie `cloner` | créer |

Le CLI suit : `kokaji enregistrer <harness> --nu <chemin>`, `kokaji pousser <harness>`, `kokaji tirer <harness>` — sur git seul, l'enregistrement au magasin restant le geste du service (`kokaji depot` est déjà la trempe du dépôt, R10.2).

Les chemins admis sont ceux d'un dossier déclaré au déploiement (`KOKAJI_DEPOTS`, monté dans le conteneur) : le service n'écrit ni ne clone n'importe où sur la machine.

## 5. Ce qui change

| Document | Changement |
|---|---|
| RFC-009 | §3 : l'enregistrement est posé ici, en local ; D9.1 : le clone local existe même sans dépôt nu |
| RFC-006 | §3 : une troisième voie, cloner ; §4 : naître avec ou sans dépôt nu |
| RFC-004 §3 | deux gestes de plus à la matrice : enregistrer/désenregistrer (propriétaire), pousser/tirer (co-auteur) |
| dojo | `harness/` ignoré par le dépôt de l'instance ; un volume `KOKAJI_DEPOTS` pour les dépôts nus ; `KOKAJI_DEPOT_PUSH` disparaît au profit du réglage par harness |
| Carte de conviction | critère B fermé par l'enregistrement de la première instance |

## 6. Non-objectifs — et ce qui est déjà décidé pour la suite

- **L'interconnexion avec une forge distante** (GitHub, Forgejo…) : hors de ce RFC. Quand elle viendra, l'authentification sera **un jeton par personne** — chaque co-auteur confie à Kokaji un jeton de son compte, et pousse en son nom — plutôt qu'une clé de déploiement partagée par l'instance : l'auteur d'un push doit être la personne, pas le serveur. Elle demandera d'amender D9.4 (les dépôts enregistrés deviennent des destinations admises, à côté des moteurs) ; rien de tout cela n'est nécessaire en local.
- Fusionner, rebaser, résoudre un conflit : un éditeur et un humain.
- Plusieurs distants par harness, ou plusieurs branches servies.
- Un catalogue de dépôts de harness : rien n'est découvrable (RFC-004 §7).

## 7. Critère « juste assez » — avec sabotages

**Nominal**, sur la première instance : chaque harness sort du dépôt de l'instance vers le sien, historique compris ; chacun a son dépôt nu sous `KOKAJI_DEPOTS` ; un scellement depuis le QG commite et pousse ; un commit fait depuis un poste, poussé au dépôt nu, se tire depuis le panneau ; un dépôt nu se clone en une naissance — c'est le critère B de la RFC-009.

**Sabotages** :

1. Enregistrer un chemin qui n'est pas un harness → refus nommé, aucune ligne, aucun dossier.
2. Enregistrer un chemin hors de `KOKAJI_DEPOTS` → refus nommé.
3. Tirer avec des modifications non scellées → refus, le clone intact.
4. Tirer une branche qui a divergé → refus, jamais de fusion, l'état dit *divergé*.
5. Un contributeur enregistre ou désenregistre → 403 ; un non-membre pousse → 403.
6. Une destination réseau écrite en dur dans le produit → la trempe refuse (souveraineté, déjà là).

## 8. Plan d'implémentation

**Lot A — le dépôt local et l'état** (`kokaji/depot/`, `naissance.py`, `comptes/depot.py`, tests)
- Naître fait `git init` et un premier commit ; le scellement commite déjà. `etat(harness)` : propre ou non, dernier commit, et — si un dépôt nu est enregistré — avance, retard, divergence depuis `commit_reference`.
- La table `harness_depot`, ses lectures et écritures ; `KOKAJI_DEPOTS`.

**Lot B — le dépôt nu et les trois gestes** (`kokaji/depot/`, `service.py`, `cli.py`, tests)
- Enregistrer (lier ou cloner), désenregistrer, pousser, tirer — la validation avant l'écriture ; les routes et le CLI ; les sabotages 1 à 5.

**Lot C — la page** (`vue.html`, tests)
- Le panneau « Dépôt », la naissance à trois voies avec ou sans dépôt nu, le badge au Profil, la trace du scellement.

**Lot D — la première instance** (dépôt privé, docs/deploiement.md)
- `git subtree split` par harness, cinq dépôts, `harness/` ignoré, `KOKAJI_DEPOTS` monté, cinq dépôts nus ; l'enregistrement des cinq ; le critère B consigné.

## 9. Tableau d'application

| Lot | État (14 septembre 2026) |
|---|---|
| A — le dépôt local et l'état | appliqué — `kokaji/depot`, naître et adopter initient, `harness_depot`, `GET /depot` |
| B — le dépôt nu et les trois gestes | appliqué — `chemin_admis`, `lier`, `pousser`, `tirer`, `cloner` ; `PUT`/`DELETE /depot`, `POST /depot/pousser`, `/depot/tirer` ; le scellement pousse si le harness le demande ; `POST /harness` accepte `depot` et `cloner_depuis` ; CLI `kokaji enregistrer`, `pousser`, `tirer` ; `KOKAJI_DEPOTS` remplace `KOKAJI_DEPOT_PUSH` ; sabotages 1 à 5 en tests |
| C — la page | appliqué — le panneau Dépôt enregistre, désenregistre, pousse, tire, règle le push au scellement ; la naissance clone un dépôt nu ou en lie un ; la trace du scellement dit poussé ou pourquoi non ; le Profil et l'offre portent l'état du dépôt |
| D — la première instance | appliqué le 14 septembre 2026 — cinq harness sortis par `git subtree split`, historique compris ; cinq dépôts nus sous `dojo/depots/` ; `harness/` ignoré par le dépôt de l'instance ; les cinq enregistrés, pousser au scellement |

---
*Note d'établi : la RFC-009 disait « un repo git par harness » et l'a laissé à l'état de phrase. Ce RFC la prend au mot, sans sortir de la machine — parce qu'un dépôt qu'on ne voit pas est un dépôt qu'on oublie de pousser, et qu'un dépôt qu'on ne peut pas cloner n'est pas un dépôt.*
