# La trempe statique

```bash
kokaji trempe <harness>          # vérifie sans rien écrire
kokaji forge <harness>           # trempe puis écrit
kokaji forge <harness> --sans-trempe
```

Ce qui bloque la forge (SPECS §5). Les coupes sont assemblées **en mémoire**,
vérifiées, puis écrites : `dist/` ne reçoit jamais une coupe fautive.

Aucune règle de domaine n'est écrite ici. Les interdits viennent du manifest, les
noms canoniques du registre — Kokaji ne fournit que les mécanismes.

## Ce qui porte sur les coupes

| Règle | Ce qu'elle attrape |
|---|---|
| `marqueur-residuel` | une variable `{{ … }}` non résolue, un crochet de gabarit `[nom du kata]`, une marque de chantier `TODO`/`FIXME`/`TBD` (R5.1) |
| `vocabulaire-interdit` | un terme de `trempe.vocabulaire_interdit` présent dans une coupe (R5.2) |
| `decompte` | un décompte annoncé qui ne correspond pas à ce qui suit (R5.3) |

Deux précisions apprises en construisant :

- **Les blocs de code sont exclus du repérage des crochets.** Un tableau JSON
  `["OPT-2"]` n'est pas un crochet de gabarit — la première exécution de la
  trempe a produit ce faux positif sur nos propres coupes. Une variable
  `{{ … }}` reste fautive partout, y compris dans un bloc de code.
- **Le décompte est volontairement étroit** : seul le motif
  `<nombre> <mot> :` immédiatement suivi d'une liste est lu. Un check large
  produirait des faux positifs, et un check faux est pire que pas de check.

## Ce qui porte sur le contrat et le registre

| Règle | Ce qu'elle attrape |
|---|---|
| `registre-canonique` | un kata, un livrable, un jalon ou un champ déclaré au manifest mais absent du registre (R5.3) |
| `contrat-complet` | un `produit` vide, ou un amont déclaré sans `herite` (RFC-002 §6.2) |
| `chemin-vide` | un kata sans amont qui hérite quand même — couplage caché |
| `typage-chaine` | un `herite` qui cite un champ absent du `produit` de son amont |
| `contrebande` | la source d'un kata nomme un champ qu'il n'hérite ni ne produit |

`contrebande` est le lint le plus intéressant du RFC-002 : il lit le **texte** de
la source, pas la pratique. Un kata qui parle d'un savoir hors de son contrat
s'appuie sur quelque chose que la chaîne ne lui garantit pas — et ça se voit
avant la première session.

## Ce qui n'est pas là

Le carré lui-même (RFC-002 §6.3) — la comparaison entre ce que `produit`
promet et ce que les ha livrent — est un check de données sur le corpus, au pas 5.
La trempe statique ne regarde que ce qui est déclaré et écrit, jamais ce qui est
vécu. Le lint de resserrage (§6.4) n'existe pas non plus.
