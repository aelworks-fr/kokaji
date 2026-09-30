# AGENTS.md — ce qu'un agent doit savoir avant de toucher à Kokaji

Ce fichier complète `CLAUDE.md` (les règles non négociables : tout en français,
aucune référence professionnelle, ce dépôt est le produit et rien d'autre,
« juste assez », souveraineté). Il ne les répète pas. Il dit ce que les
documents ne disent pas assez fort : comment les pièces se parlent vraiment,
les pièges déjà rencontrés, et la façon de travailler ici.

## Lire dans cet ordre

1. `CLAUDE.md` — les règles.
2. `docs/SPECS.md` — tout part de là ; le vocabulaire est en §1.2.
3. `STRUCTURE.md` — où vit chaque pièce.
4. Les RFC, `docs/rfc-001…019`, **dans l'ordre** ; chacune finit par un tableau
   d'application qui dit ce qui est fait. La prochaine porte le numéro **020**.
5. `docs/carnet.md` — les vigilances : ce qu'on a appris en se trompant.
6. La doc de la pièce touchée : `docs/corpus.md`, `docs/middleware.md`,
   `docs/qg.md`, `docs/forge.md`, `docs/banc.md`, `docs/hds-v0.md`.

En cas de contradiction entre documents : s'arrêter et poser la question.
Ne jamais inventer de contenu de SPECS ou de RFC.

## Le circuit d'une conversation, tel qu'il tourne

```
chat (Open WebUI)
  │  jeton signé X-OpenWebUI-User-Jwt (secret partagé) + fil de conversation
  ▼
relais Kokaji  POST /v1/chat/completions   kokaji/middleware/chat.py (routeur_chat)
  │  vérifie le jeton, refuse un kata hors du harness courant, et ne transmet
  │  à la passerelle que l'email vérifié et le fil — jamais les secrets du client
  ▼
passerelle (litellm)   dojo/litellm/hooks/
  │  coupe_injector : injecte la coupe du kata (la cible : @sobre, @nue, @instrumentee),
  │                   pose l'identité de ha (harness, kata, cible, clé, fil, praticien_email)
  │  journal_ha     : écrit chaque appel au journal (fichiers, ou base si KOKAJI_BASE_URL)
  ▼
veille   kokaji middleware --boucle …        kokaji/middleware/__init__.py → kokaji/corpus/
  │  verser : une session → un ha brut (fiche, transcript, états, carré, matériaux),
  │           rafraîchi à chaque passage tant qu'il est brut ; sessions écartées sautées
  ▼
QG   kokaji/qg/ (+ vue.html)   lit les fiches et les états — n'invente rien
```

Trois vérités qui découlent de ce circuit et qui ont coûté des journées :

- **Le journal est la vérité, en ajout seul.** Un ha ne se supprime jamais en
  silence : il reviendrait au passage suivant. Écarter = **déclarer** la session
  (`ecart`) puis **retirer** le ha (`ecarter_ha`, `kokaji ecarter`).
- **Une fiche a trois sortes de champs** (NOTE-0021, `corpus/__init__.py`) :
  ceux de la capture, réécrits à chaque passage (`CHAMPS_DE_LA_CAPTURE`) ;
  ceux « si connus », posés mais jamais effacés (`praticien`, `fil`) ; tout le
  reste, qui appartient à d'autres gestes. Ajouter un champ, c'est choisir sa
  sorte.
- **Un ha sans praticien est orphelin de porte** : personne ne le lit,
  propriétaire du harness compris (RFC-004 §5, R12.4). C'est voulu. Le
  praticien vient de l'identité **signée** du chat, résolue en compte à la
  capture, jamais devinée, jamais d'un en-tête en clair (RFC-019).

## Pièges déjà tombés — ne pas y retomber

- **Une cible sans bloc d'état (`etat_structure: false`, ex. un harness
  importé en `nue`) n'émet pas d'état** : ses conversations n'ont pas de sujet
  au QG. Ce n'est pas un bug. La ré-abstraction (RFC-002 §7.2) reconstruit un
  état **marqué lecture**, jamais silencieusement ; l'instrumentation
  (`@instrumentee`) est une affaire de **banc** — le bloc `kokaji_state` n'est
  pas filtré du chat, il s'afficherait à l'utilisateur.
- **Les tâches d'interface d'Open WebUI** (titre, étiquettes, questions
  suivantes) commencent par `### Task:` ; la capture les marque `interface`.
  Ce ne sont pas des pratiques. Elles se coupent côté chat (voir la compose de
  référence, `dojo/compose.yaml`, et ses deux pièges : réglages persistés,
  modèle de tâche exigé dans la liste des modèles).
- **Les modèles nus** (`KOKAJI_MODELES_NUS`) sont servis mais **absents** de
  `/v1/models` : un rouage d'interface n'est pas un kata.
- **Un fil de conversation** traverse plusieurs kata et plusieurs jours ; Kokaji
  découpe une session par kata parce que la coupe change. La `racine` (empreinte
  du premier tour humain, rejoué à chaque appel) regroupe — avec une limite
  connue : deux chats au même premier message fusionnent.
- **En régime base** (RFC-014), un corpus est clé par son identité
  `<harness>/<nom>` : passer par `depot_pour(harness)`. Et **toujours filtrer
  par harness** dans une requête : `CAS-0148` existe dans deux harness.
- **Le style est un contrôle de la CI, pas des tests** : `ruff check kokaji tests`
  (workflow `trempe`) a déjà rougi un commit poussé pour un ordre d'import.
- **Un chantier de fond ne se pose pas sur une frustration d'usage.** Le
  23 septembre 2026, trois chantiers empilés en un matin ont été remontés le
  soir, données comprises. Nommer le besoin d'abord ; le geste juste ne coûte
  rien à refaire seul.

## La méthode, telle qu'elle est pratiquée

- Un changement de conception commence par une **RFC courte** : motivation,
  décisions scellées `Dn.m`, surface, ce qui change, non-objectifs, critère
  « juste assez » **avec sabotages**, plan en lots, tableau d'application.
  Puis l'implémentation, lot par lot, et l'on met à jour le tableau.
- Un vérificateur n'est prouvé que quand on l'a **vu refuser**.
- Les commits sont narratifs, en français : ce qui manquait, pourquoi, ce
  qu'on fait, ce que les tests couvrent.
- Quand un chantier part de travers : **sauvegarder, puis tout remonter**, git
  et données, et garder le travail sur une branche de garde.

## Tester ici

- Les tests sont en `unittest`, sans pytest : `cd tests && python -m unittest
  test_corpus test_middleware …`. Les dépendances viennent de
  `pip install -e '.[service,base]'` (ou de l'image du produit).
- La page du QG est un seul script inline : `node --check` sur son contenu
  attrape une faute de syntaxe avant le déploiement.
- **Avant tout push** : le même contrôle que la CI, dans un conteneur si
  l'hôte n'a pas ruff —
  `docker run --rm -v "$PWD":/src:ro -w /src python:3.12-slim sh -c "pip -q install ruff >/dev/null && python -m ruff check --no-cache kokaji tests"`.
- `trempe/check.sh` — la trempe que le dépôt s'applique à lui-même
  (vocabulaire interdit, rien d'une instance dans le produit).

## Ce qui est ouvert (30 septembre 2026)

- La collision des fils au même premier tour (`racine`).
- Un écart déclaré sans retrait devrait se voir ; la fiche illisible remplacée
  par `rafraichir_fiche` perd ses annotations sans trace.
- RFC-018 lot C (la bascule gardée de l'agent qui raisonne), RFC-007 (les
  cartographies), la page du transfert d'autorat (RFC-004), l'affichage mobile.

## L'instance

Le produit ne connaît aucune instance. Une instance est un dépôt séparé
(privé), qui porte son propre `AGENTS.md` avec ce qui est propre à son
déploiement : machine, images, sauvegardes, réglages du chat. Rien de cela ne
doit entrer ici (RFC-009).
