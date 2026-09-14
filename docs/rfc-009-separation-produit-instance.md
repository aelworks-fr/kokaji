# RFC-009 — Séparation produit / instance (la forge open source)

**Statut :** scellée (décisions structurantes validées en keiko, 2026)
**Dépend de :** SPECS §10 (règles de séparation), RFC-004 (utilisateurs), RFC-006 (import/export)
**Amende :** SPECS §3 (dojo), §10 (R10.5 résolue), §12 (sécurité) ; HDS ; RFC-004 §6 ; RFC-006 §2

---

## 1. Motivation

Jusqu'ici, un seul repo portait tout : le produit Kokaji (forge, trempe, dojo, QG)
**et** le contenu d'une instance (coupes, corpus de ha, harness, fixtures).
Cette confusion était implicite — la RFC-006 reposait déjà sur une notion
d'instance jamais formulée. Cette RFC la formule.

Le but : faire de Kokaji une **forge open source disponible à tous**.
Quiconque clone le produit doit pouvoir démarrer une instance vide, souveraine,
et y forger ses propres harness — sans jamais voir le contenu de qui que ce soit,
à commencer par celui de l'auteur.

Corollaire immédiat pour nous : épurer. Le repo actuel mélange produit et
contenu ; il faut trancher.

---

## 2. Décisions scellées

### D9.1 — Persistance : hybride git + base

Trois familles de données, trois régimes :

| Donnée | Régime | Justification |
|---|---|---|
| **Sources de harness** (harness.yaml, kata, trempe locale, corpus versé au harness) | **Un repo git par harness**, enregistré auprès de l'instance | Versionnable, diffable, portable, co-autorat par PR (RFC-004) |
| **Données vivantes** (ha, utilisateurs, résultats de banc, blocs d'état) | **Postgres de l'instance** | Volume, requêtes, cycle de vie brut→anonymisé→annoté, visibilité privé/versé |
| **Coupes** (`dist/coupes/<cible>/`) | **Dérivées — jamais persistées** | La forge est déterministe : source + version ⇒ même coupe. On régénère, on ne stocke pas |

Le corpus vivant reste **exportable** au format fichier `CAS-XXXX/` (standard v0) :
la base est le régime de travail, le fichier est le régime d'échange et de sauvegarde.
Aucune donnée vivante n'est captive de la base.

> **Application, 14 septembre 2026** — le scellement commite le harness dans le
> dépôt qui le contient (`kokaji/conception/depot.py`), auteur et motif au
> message ; un harness modifié depuis le QG n'est plus hors historique. Le push
> reste un choix de déploiement.

**Ce que ça interdit :** commiter une coupe. Une coupe dans un repo git est un
artefact fossile qui divergera de sa source — la trempe du produit doit le refuser
(`dist/` reste dans `.gitignore`, et un check CI échoue si un fichier de `dist/`
est suivi).

### D9.2 — Deux repos : le produit naît propre

- **Nouveau repo public `kokaji`** : le produit seul, historique vierge.
  Forge, trempe, dojo (compose), QG, HDS, SPECS, RFC, gabarits, harness de
  démonstration Atelier (§9 SPECS — neutre par construction).
- **Le repo actuel devient la première instance** : il garde ses harness, ses
  coupes historiques, son corpus, son historique git — et s'enregistre auprès
  d'une instance comme n'importe quel repo de harness.

Aucune réécriture d'historique, donc aucun risque de fuite : on ne nettoie pas
un passé, on n'en hérite pas.

**Ce que ça interdit :** faire du repo actuel le repo public par « épuration ».
Un historique git n'oublie rien ; un repo né propre n'a rien à oublier.

### D9.3 — Licence : Apache-2.0

Le repo produit est sous **Apache License 2.0** (LICENSE + NOTICE).
Résout R10.5, en attente depuis le premier commit. Motifs : clause de brevet
explicite, compatibilité entreprise large, obligation de NOTICE qui sert notre
règle d'attribution.

Les repos de harness des utilisateurs choisissent **leur propre licence** —
le produit n'impose rien au contenu (cohérent avec D9.4).

### D9.4 — Souveraineté totale, instances isolées

Chaque instance est **souveraine** : son contenu, ses utilisateurs, ses clés
moteurs, ses données lui appartiennent en propre.

- Le produit ne voit rien : **aucune télémétrie**, aucun phone-home, aucun
  compte central. `git clone` + `docker compose up` = instance complète.
- Les instances **ne se connaissent pas** : pas d'annuaire, pas de fédération,
  pas de découverte.
- Le **seul canal inter-instances** est l'export/import de la RFC-006 :
  un harness sort en manifeste + fichiers, entre ailleurs par le régime
  d'adoption (N0→N4). Un futur RFC pourra outiller cet échange ; il passera
  par ce canal, pas par un couplage réseau.

**Ce que ça interdit :** tout code du produit qui émet vers l'extérieur autre
chose que les appels moteurs configurés par l'instance. Un `curl` vers un
domaine kokaji-quelconque dans le produit est un bug de souveraineté.

---

## 3. Modèle

```
PRODUIT (repo public kokaji, Apache-2.0)
  forge/  trempe/  dojo/  qg/  hds/  docs(SPECS, RFC)/  atelier/(démo)
        │
        │  git clone + docker compose up
        ▼
INSTANCE (souveraine, isolée)
  ├─ Postgres : utilisateurs (RFC-004), ha (RFC-001/004), résultats de banc,
  │             registre des harness enregistrés
  ├─ Repos de harness enregistrés (1 repo git = 1 harness, licence au choix)
  │             └─ ex. : l'actuel repo Kokaji, devenu contenu de la 1ʳᵉ instance
  ├─ dist/coupes/ : cache local régénérable, jamais versionné
  └─ .env : clés moteurs, domaine, secrets — jamais dans aucun repo
        │
        │  export / import RFC-006 (manifeste + fichiers, N0→N4)
        ▼
AUTRE INSTANCE (qui ne nous connaît pas)
```

L'**enregistrement d'un harness** est le geste qui lie un repo git à une
instance : l'instance note l'URL (ou le chemin local), le commit de référence,
et forge depuis là. Désenregistrer ne détruit rien — le repo vit sa vie.

---

## 4. Changements induits

- **SPECS §10** : R10.5 close (Apache-2.0). Ajouter R10.6 : « le repo produit
  ne contient aucun contenu d'instance ; toute coupe, tout ha, tout harness
  non-démonstration vit hors du repo produit ».
- **SPECS §12** : ajouter la clause souveraineté (aucune émission réseau hors
  appels moteurs configurés).
- **HDS** : le manifeste reste inchangé ; s'ajoute la notion d'enregistrement
  (métadonnée d'instance, pas du harness — le harness ne sait pas où il est
  enregistré, cohérent avec « non couplé »).
- **RFC-004** : les comptes sont **par instance** (déjà le cas : comptes locaux
  OAuth-ready) ; le co-autorat s'exerce sur le repo git du harness.
- **RFC-006** : §2 « les deux, séparés » devient un cas particulier du modèle
  général : un harness importé est un repo de harness comme un autre, enregistré
  avec son tampon de provenance.
- **Atelier (§9 SPECS)** : seul harness qui vit **dans** le repo produit, en tant
  que démonstration — il est au produit ce que le lorem ipsum est au QG.

---

## 5. Plan d'épuration

1. Créer le repo public `kokaji` (vierge) : LICENSE Apache-2.0, NOTICE, README,
   CLAUDE.md, SPECS, RFC-001→009, HDS, gabarits, atelier/, dojo/, trempe du
   produit (lint vocabulaire + lint contenu).
2. Y déplacer **par copie choisie** (jamais par filtrage d'historique) les
   fichiers produit du repo actuel, relus un à un avant commit.
3. Dans le repo actuel : retirer ce qui est parti au produit, garder harness,
   corpus, coupes historiques si utiles comme archives — il devient
   « instance-content » de la première instance.
4. Premier boot de référence : clone du produit sur machine neutre,
   `docker compose up`, instance vide fonctionnelle, enregistrement du repo
   actuel comme premier harness.

---

## 6. Non-objectifs

- Fédération, annuaire ou marketplace d'instances (canal RFC-006 seulement,
  futur RFC si besoin réel).
- Migration automatisée base→base entre instances.
- Multi-tenancy (une instance = un déploiement ; plusieurs instances = plusieurs
  déploiements).
- Réécriture de l'historique du repo actuel.

---

## 7. Critère « juste assez » et sabotages

La RFC est prouvée quand :

1. **Nominal — le clone étranger** : sur une machine qui n'a jamais vu Kokaji,
   `git clone` du repo produit + `docker compose up` donne une instance vide
   où l'on peut enregistrer un harness, forger une coupe, jouer un keiko,
   capturer un ha.
2. **Nominal — la première instance** : le repo actuel s'enregistre comme
   harness de cette instance et ses kata se forgent sans modification du produit.
3. **Sabotage — la coupe commitée** : on tente de commiter un fichier de
   `dist/coupes/` dans un repo de harness → le check du produit **refuse**.
4. **Sabotage — la fuite de contenu** : on tente d'ajouter un ha ou un harness
   non-démonstration au repo produit → le lint de contenu CI **refuse**
   (un vérificateur doit être vu en train de refuser).
5. **Sabotage — le phone-home** : une revue du produit ne trouve aucune
   émission réseau hors appels moteurs ; on ajoute artificiellement un appel
   sortant → le test de souveraineté le **détecte**.

---

## 8. Note d'établi

La RFC-006 demandait « où jouer un harness venu d'ailleurs » ; la réponse
supposait une instance. Cette RFC paie cette dette : l'instance existe, elle est
souveraine, et le produit est ce qui reste quand on lui retire tout contenu.
La forge ne possède aucune lame — elle sait seulement forger.
