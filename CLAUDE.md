# Discipline de travail — à lire avant tout geste

**Lire `docs/SPECS.md` d'abord.** Tout part de là ; les RFC (`docs/rfc-*.md`)
précisent, dans l'ordre. En cas de doute ou de contradiction entre documents,
poser la question et s'arrêter — ne jamais inventer de contenu de SPECS ou de RFC.

## Règles non négociables

- **Tout en français** : code, commentaires, commits, tests, docs. Vocabulaire
  à deux registres (technique / imagerie japonaise), défini en SPECS §1.2.
  Le terme « mode guidé » est **interdit** partout.
- **Aucune référence** à un quelconque employeur, client ou projet
  professionnel — y compris fixtures et messages de commit. La liste des
  termes interdits vit dans `trempe/vocabulaire-interdit.local.txt`
  (non versionné ; gabarit `.example` versionné). `trempe/check.sh` la lit.
- **Ce repo est le produit, et rien d'autre** (RFC-007 D7.2, R10.6) : aucune
  coupe, aucun ha, aucun corpus, aucun harness hors `atelier/`. La trempe du
  produit le vérifie ; elle se lance par `trempe/check.sh` et tourne en CI.
- **Doctrine** : « juste assez », un pas à la fois, pas d'optimisation
  prématurée. Un vérificateur n'est prouvé que lorsqu'on l'a **vu refuser**
  (sabotage) — un test qui n'a jamais échoué ne prouve rien.
- **Souveraineté** (D7.4) : aucune télémétrie, aucun phone-home, aucun compte
  central. Toute destination réseau en dur hors appels moteurs configurés est
  un bug.

## Convention de commit

Français, impératif, une intention par commit.
