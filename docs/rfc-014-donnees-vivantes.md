# RFC-014 — Les données vivantes : la base de l'instance

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : RFC-009 (D9.1, la deuxième ligne du régime de persistance), RFC-004 (praticien et visibilité d'un ha), RFC-006 §5 (archiver), RFC-012 (un harness est un dépôt git), SPECS §6 (le corpus), §7 (le middleware). Objet : donner aux données vivantes — le journal des appels, les ha capturés, les blocs d'état, les jugements du banc, les comptes — leur régime de travail dans le Postgres de l'instance, sans qu'aucune ne devienne captive.

---

## 1. Motivation

La RFC-009 D9.1 a tranché trois régimes : les sources d'un harness dans un dépôt git, les données vivantes dans le Postgres de l'instance, les coupes nulle part. Le premier est fait (RFC-012), le troisième tenu depuis toujours. Le deuxième n'a jamais été commencé : les ha vivent en dossiers `CAS-XXXX/` sous `corpus/` de chaque harness, le journal du Dojo en fichiers JSONL par jour — dix-sept mégaoctets sur la première instance —, les jugements du banc en `jugements.jsonl`, les comptes en SQLite. Le QG compose sa vue en relisant des fichiers ; la visibilité d'un ha est une ligne de frontmatter.

Ça tenait. La RFC-012 vient de le rendre intenable : **le corpus est désormais dans le clone git du harness.** Chaque session que la veille verse crée un dossier non suivi ; le clone n'est plus propre ; tirer refuse ; et le scellement suivant commite cent vingt-trois ha `brut` dans le dépôt de la définition, puis les pousse au dépôt nu. La première instance a aujourd'hui cent soixante-trois fiches suivies par git, dont cinq annotées. D9.1 le disait déjà : la donnée vivante n'a rien à faire dans le dépôt de la forme — sauf ce qu'un humain y a **versé**.

Il y a une seconde raison, plus ancienne. Le cycle de vie d'un ha — `brut` → `anonymise` → `annote` —, sa visibilité — privée, versée —, son praticien, ses jugements, tout cela sont des **requêtes** : « les ha versés de ce corpus, jugés, sur ce kata, depuis cette version ». Un système de fichiers les sert en parcourant tout ; une base les sert en les demandant. Le QG, l'usage, la régression et le banc font aujourd'hui ce parcours à chaque lecture.

## 2. Ce qui vit où — la ligne exacte

| Donnée | Régime | Pourquoi |
|---|---|---|
| Le **journal** des appels (ce que la passerelle a servi) | base | volume, une ligne par appel ; la veille le lit par session, pas par fichier |
| Un **ha `brut`** ou `anonymise` : identité, transcript, sortie, matériau, blocs d'état, carré | base | c'est la matière vivante ; elle change de statut, de visibilité ; elle se compte et se requête |
| Un **ha `annote`** — celui qu'un humain a promu | **base, et exporté au dépôt du harness** en `CAS-XXXX/` | « corpus versé au harness » (D9.1, première ligne) : il fait partie de la forme, il se diffe, il voyage avec elle |
| Les **jugements** du banc, les résultats de régression | base | rattachés aux ha, comparables par version, moteur, kata, cible |
| Les **comptes**, invitations, ACL, sessions, enregistrements de dépôt | base | déjà une base (SQLite) ; le même schéma, un moteur de plus |
| Le **verdict de la vigie** | fichier, inchangé | c'est la fraîcheur du fichier qui trahit une vigie morte — une base ne dit pas « personne n'écrit plus » |
| Les **coupes** | nulle part | dérivées, régénérées (R4.1) |

Le fichier `CAS-XXXX/` reste **le format d'échange et de sauvegarde** de tout ha : ce qui est en base s'exporte tel quel, ce qui est en fichier s'importe tel quel. Aucune donnée vivante n'est captive de la base — c'est la promesse de D9.1, et le sabotage 4 la garde.

## 3. Décisions scellées

### D14.1 — Une base par instance, la même que celle de la passerelle

L'instance a déjà un Postgres : celui de LiteLLM, dans le dojo. Kokaji y prend **sa propre base** (`kokaji`), pas les tables de la passerelle. Un seul moteur à sauvegarder, deux bases qui s'ignorent. `KOKAJI_BASE_URL` la désigne ; sans elle, le produit reste en régime fichiers — ce qui garde le clone étranger, les tests et l'usage solitaire exactement tels qu'ils sont.

### D14.2 — Le corpus est une interface, avec deux dépôts

`kokaji/corpus/` cesse d'écrire et de lire des chemins pour parler à un **dépôt de ha** : `verser`, `lire`, `regler_visibilite`, `ecarter`, `promouvoir`, `exporter`, `importer`, et les requêtes que le QG, l'usage et le banc font aujourd'hui en parcourant. Deux implémentations, une seule interface :

- **fichiers** — le régime d'aujourd'hui, intact : c'est lui que les tests éprouvent, lui que sert une instance sans base ;
- **base** — Postgres, éprouvé en CI par un service Postgres à côté des tests, sur la même suite.

Une instance choisit l'un ou l'autre par sa configuration ; le produit ne le devine pas, et rien ne bascule sans qu'on l'ait demandé.

### D14.3 — Un ha est une ligne, ses pièces sont ses lignes

Le schéma dit ce qu'un dossier `CAS-XXXX/` dit :

```
ha         id · harness · corpus · kata · version_kata · version_coupe · cible · moteur ·
           date · session · praticien · visibilite · source · statut · completude ·
           verdict · scores (json) · design_exerce (json) · titre
tour       ha · rang · role · texte · horodatage
sortie     ha · texte
materiau   ha · nom · texte                (la coupe injectée, les tours envoyés…)
etat       ha · rang · horodatage · bloc (json)        (etats.jsonl)
carre      ha · rendu · conforme · detail (json)      (carre.md)
jugement   ha · id · juge · grille · scores (json) · quand
appel      id · session · harness · kata · cible · moteur · statut · etat_avant ·
           etat_apres · horodatage · messages (json) · reponse · usage (json) · erreur
ecart      harness · corpus · session · pourquoi · quand   (les .ecartes.jsonl)
```

Rien de plus que ce que les fichiers portent. Ce que le QG compose — chaleur, possibles, décisions — reste **composé à la lecture**, jamais stocké : une agrégation stockée est une agrégation qui ment quand sa source change.

### D14.4 — Le journal entre en base à la source

Le hook de la passerelle, qui écrit aujourd'hui une ligne JSONL par appel, écrit la ligne `appel` en base quand `KOKAJI_BASE_URL` est là — et continue le JSONL sinon. La veille lit les sessions closes en base au lieu de relire des fichiers de dix-sept mégaoctets ; le QG suit les sessions en cours par la même requête. Le journal en fichiers reste lisible par `kokaji corpus` : un journal exporté d'ailleurs se verse encore.

### D14.5 — La promotion écrit au dépôt du harness

Promouvoir un ha en `annote` est un geste humain (SPECS §6). Il devient aussi le geste qui **exporte** : l'ha annoté est écrit en `CAS-XXXX/` dans le `corpus/` du clone du harness, où le scellement suivant le commite et le pousse. Un ha `brut` n'y entre jamais : le clone reste propre entre deux scellements, tirer ne refuse plus pour une séance de plus, et le dépôt de la forme ne porte que ce qu'un humain y a versé.

**Lot 0, immédiat, sans base** : tant que la base n'est pas là, les ha `brut` restent en fichiers mais **hors du dépôt git du harness** — un `.gitignore` sur `corpus/**/CAS-*/` dans chaque clone, et la promotion les ajoute de force (`git add -f`). Les cent vingt-trois ha `brut` déjà suivis par git le restent : on ne réécrit pas l'historique.

### D14.6 — La visibilité et le praticien sont des colonnes

R12.4 tient pareil en base : un ha privé n'est lisible que par son praticien, un ha versé par les co-auteurs du harness, et **la requête le filtre** — ce n'est pas une couche qui masque après coup. Le sabotage 3 le vérifie : la lecture d'un contributeur ne voit jamais un ha privé d'autrui, par quelque route que ce soit.

### D14.7 — Les comptes migrent, le schéma ne change pas

Le magasin des comptes passe de SQLite à la même base, tables identiques (`utilisateurs`, `invitations`, `identites_externes`, `harness_acl`, `contributeurs`, `sessions`, `harness_depot`). Une instance sans base garde SQLite. La migration est une commande, jouée une fois.

### D14.8 — Rien de captif : l'instance s'exporte entière

`kokaji instance exporter <dossier>` écrit tout ce que la base contient au format fichiers — un `CAS-XXXX/` par ha, le journal en JSONL, les jugements, les comptes en SQLite — et `kokaji instance importer` fait l'inverse. Une instance se déplace, se sauvegarde et se quitte avec ses fichiers. C'est aussi le chemin de la migration de la première instance (§6).

## 4. La surface

- CLI : `kokaji corpus` (verser) et `kokaji purger` parlent au dépôt de ha, quel qu'il soit ; `kokaji promouvoir <harness> <CAS>` — la promotion, qui exporte ; `kokaji instance exporter|importer`.
- Routes : inchangées. `/ha`, `/ha/{id}`, `/qg/donnees`, `/qg/usage`, la visibilité — même contrat, autre dépôt derrière.
- Configuration : `KOKAJI_BASE_URL` (dojo : la base `kokaji` du Postgres existant), et rien d'autre.
- Le hook de la passerelle : une seconde sortie, la base, quand elle est déclarée.

## 5. Ce qui change

| Document | Changement |
|---|---|
| SPECS §6 | R6.x (proposée) : le corpus a deux régimes, fichiers et base, une interface ; le fichier `CAS-XXXX/` est le format d'échange |
| SPECS §7 | le middleware lit et écrit par le dépôt de ha |
| RFC-009 D9.1 | appliquée pour la deuxième ligne ; précisée : « corpus versé » = ha annoté |
| RFC-012 | D12.3 : tirer n'est plus refusé pour un ha brut ; le clone ne porte que le versé |
| docs/corpus.md, docs/middleware.md, dojo/README.md | les deux régimes, la promotion, l'export |
| Carnet de vigilances | + « une agrégation stockée ment quand sa source change — composer à la lecture » |

## 6. La première instance

1. Lot 0 dès maintenant : les ha `brut` hors git dans les cinq clones.
2. Créer la base `kokaji` dans le Postgres du dojo ; `KOKAJI_BASE_URL` au compose.
3. `kokaji instance importer` : les cent soixante-trois ha, le journal, les jugements, les comptes — et vérifier les comptes : autant de ha, les mêmes identités, les mêmes visibilités.
4. Le QG en régime base rend, sujet par sujet, **exactement** ce qu'il rendait en régime fichiers — c'est le nominal, et il se mesure avant de basculer.
5. Basculer ; garder les fichiers un mois, puis les retirer du clone.

## 7. Non-objectifs

- Une fédération d'instances, une migration base à base entre instances (D9.4 : le seul canal est le fichier).
- Des vues matérialisées, des indicateurs stockés — composer à la lecture, toujours.
- Changer le format `CAS-XXXX/`.
- Un autre moteur que Postgres : c'est celui que le dojo a déjà.

## 8. Critère « juste assez » — avec sabotages

**Nominal** : sur la première instance, une séance au chat donne un ha en base, visible au QG dans les deux minutes, sans qu'un fichier n'apparaisse dans le clone du harness ; `git status` du clone reste vide ; promouvoir cet ha l'écrit en `CAS-XXXX/` dans le clone, et le scellement suivant le commite ; `kokaji instance exporter` puis `importer` sur une base vide redonne le même QG.

**Sabotages** :

1. Une séance de plus, puis `git status` du clone → **vide** ; puis `tirer` → accepté.
2. La base injoignable → le QG le dit, ne montre rien de périmé ; la veille attend et le dit ; la vigie **rougit**.
3. Un contributeur lit `/ha` → aucun ha privé d'autrui, en base comme en fichiers (R12.4).
4. Export puis import sur une base vide → même nombre de ha, mêmes identités, même QG ; et l'export d'un ha est identique, octet pour octet, au `CAS-XXXX/` que le régime fichiers écrivait.
5. Une agrégation stockée à la main dans la base → aucun code ne la lit ; le QG compose à la lecture, et un test le prouve en changeant un bloc d'état sous lui.
6. Le régime fichiers, sans base : toute la suite de tests passe inchangée — le clone étranger aussi.

## 9. Plan d'implémentation

| Lot | Contenu |
|---|---|
| **0 — le clone reste propre** | `.gitignore` des ha brut dans chaque clone ; la promotion ajoute de force ; l'instance migrée le jour même |
| **A — l'interface** | `kokaji/corpus/depot.py` : l'interface et le dépôt fichiers, extraits de l'existant ; QG, usage, banc, régression, purger, visibilité passent par elle ; la suite de tests inchangée |
| **B — le dépôt base** | le schéma (§D14.3), le dépôt Postgres, un service Postgres en CI, la même suite jouée sur les deux dépôts |
| **C — le journal à la source** | le hook écrit en base ; la veille et le QG lisent les sessions par requête |
| **D — promouvoir et exporter** | `kokaji promouvoir`, `kokaji instance exporter|importer`, sabotage 4 |
| **E — les comptes** | le magasin sur Postgres, la migration une fois |
| **F — la première instance** | §6, dans l'ordre, avec la mesure de parité avant de basculer |

Les lots A et B se livrent sans toucher à la production ; C à F la touchent, un par un.

## 10. Tableau d'application

| Lot | État (15 septembre 2026) |
|---|---|
| 0 — le clone reste propre | appliqué — `.gitignore` posé par `initier()`, `kokaji promouvoir` ajoute de force ; les cinq clones de la première instance migrés le jour même |
| A — l'interface | appliqué — `kokaji/corpus/depot.py` : `DepotDeHa` (protocole), `RefHa` (un ha nommé sans être situé), `DepotFichiers` (le régime d'aujourd'hui, intact), `depot_pour(harness)` qui rend les fichiers tant qu'aucune base n'est déclarée ; le corpus (verser, écarter, existants), la visibilité, la surface HTTP `/ha`, le QG, la veille et la ré-abstraction, l'usage, le banc (rejeu, resserrage, jugement) et les commandes (réabstraire, purger, rattacher, juger, promouvoir) ne lisent ni n'écrivent plus une pièce de ha sans passer par lui ; plus un `CAS-*` parcouru hors du dépôt, sauf la copie d'épreuve qui les exclut ; le jeu de tests du dépôt (`tests/test_corpus_depot.py`) servira tel quel au dépôt base ; la suite existante inchangée |
| B — le dépôt base | appliqué — `kokaji/corpus/base.py` : `DepotBase` sur Postgres (`psycopg`, extra `base`, dans l'image), le schéma §D14.3 posé à la première connexion — à une nuance près : les tours ne sont pas éclatés en lignes, le transcript est la pièce et les tours se lisent dedans ; la fiche, le transcript et la sortie sont gardés entiers et les colonnes de `ha` en sont tirées à l'écriture ; les blocs et jugements en `json` (pas `jsonb`), pour que l'export redonne la ligne d'origine ; `depot_pour` rend la base dès que `KOKAJI_BASE_URL` est là ; `transferer(ref, de, vers)` fait passer un ha d'un dépôt à l'autre, et le va-et-vient fichiers → base → fichiers est identique octet pour octet (sabotage 4, en avance) ; une base injoignable lève `BaseInjoignable` (sabotage 2, la moitié qui revient au dépôt) ; la CI pose un Postgres et joue le même contrat sur les deux dépôts. Mesure de parité : la suite entière jouée en régime base passe 378 tests avant le premier qui lit le disque lui-même — la parité complète est l'affaire du lot F, sur le QG de la première instance |
| C — le journal à la source | à faire |
| D — promouvoir et exporter | à faire |
| E — les comptes | à faire |
| F — la première instance | à faire |

---
*Note d'établi : la RFC-009 avait écrit la phrase — « la base est le régime de travail, le fichier le régime d'échange » — et laissé le régime de travail en fichiers. La RFC-012 a rendu la dette visible en mettant le corpus dans un dépôt git : ce qui vit ne se versionne pas, sauf quand quelqu'un décide que ça vaut d'être gardé. Cette RFC met chaque chose à sa place, et garde le fichier comme porte de sortie.*
