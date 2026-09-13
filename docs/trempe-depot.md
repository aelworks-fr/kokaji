# La trempe du dépôt

```bash
kokaji depot [racine]
```

Kokaji se trempe lui-même (SPECS §10, R10.2). Le principe de découplage se
vérifie ou n'existe pas : aucun nom de processus, de rôle, d'organisation ou de
domaine ne doit entrer dans ce dépôt — ni dans le code, ni dans les
commentaires, les fixtures, la documentation, **ni dans les messages de commit**
(R10.1).

## Ce qui est lu

Les fichiers **suivis par git**, et les derniers messages de commit. Ce qui n'est
pas versionné n'est pas lu : un brouillon local ne quitte pas la machine, la
trempe n'a pas à s'en mêler. Les binaires sont ignorés.

## Les deux listes

```yaml
# .trempe-kokaji.yaml — publique, donc partielle par construction
interdits: [ … ]
exemptions: [ … ]   # chaque exemption se justifie en une ligne
commits: 50
```

```yaml
# .trempe-kokaji.local.yaml — hors du dépôt, même format, fusionnée
interdits: [ … ]
```

La seconde liste est la seule qui compte vraiment, et elle ne peut pas être
publiée : nommer publiquement les termes qu'on cherche à taire les publierait.
Elle est ignorée par git et n'existe que sur la machine de développement.

## Les exemptions

Un fichier qui **nomme l'interdit pour l'établir** doit être exempté — les SPECS
bannissent un terme, donc elles le citent. Une exemption sans justification en
commentaire n'a rien à faire dans la liste.

## Ce que la trempe a attrapé en naissant

Deux fois de suite, sur nous :

1. Le harness d'exemple redéclarait dans son `vocabulaire_interdit` un terme que
   Kokaji bannit déjà du dépôt entier. Redondant : les interdits de Kokaji sont
   déclarés une seule fois, ceux d'un harness ne portent que son domaine.
2. Le commentaire écrit pour expliquer le retrait **citait le terme**. Réécrit
   sans le nommer.

Le second cas est le plus utile : il montre que la règle mord sur la prose qui
parle de la règle. C'est inconfortable et c'est le comportement voulu.

## En intégration continue

`.github/workflows/trempe.yml` enchaîne quatre étapes, dans l'ordre où elles
échouent le plus utilement : les tests, le manifest du harness d'exemple, la
trempe statique, la trempe du dépôt. L'historique complet est nécessaire —
`fetch-depth: 0` — pour relire les messages de commit.
