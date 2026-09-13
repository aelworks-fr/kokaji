# Le middleware

```bash
kokaji middleware <harness> [--journal <dossier>] [--repos <secondes>]
kokaji service    <harness> [--journal <dossier>] [--hote …] [--port …]
```

Deux surfaces pour un même service (SPECS §7) : une **veille** qui écrit, une
**lecture** qui n'écrit jamais.

## La veille

Trois gestes, dans cet ordre.

**1 · Capturer (R7.3).** Toute session devient un ha `brut`, **y compris pendant
qu'elle se déroule**. Le ha se rafraîchit à chaque passage de la veille et porte
`en_cours: true` tant que la conversation vit ; il passe à `false` et à
`completude: B` une fois close — silencieuse depuis `--repos` secondes.

Pourquoi rafraîchir plutôt qu'attendre la clôture : baisser le délai de clôture
figerait un ha au milieu d'une conversation et perdrait tous les tours suivants.
Le ha suit la session, il ne la devance pas.

**Un ha annoté n'est jamais réécrit.** La promotion humaine prime sur la
capture — c'est la seule chose que la veille refuse de toucher.

**2 · Extraire l'état (R7.1, R7.2).** Les blocs `kokaji_state` sont sortis des
réponses, validés contre le schéma spécialisé par le manifest, horodatés, et
écrits dans `etats.jsonl` à côté du ha :

```json
{"horodatage": "…", "id_appel": "…", "etat": { … },
 "fautes": [{"regle": "etat-statuts-declares", "message": "…"}]}
```

Un bloc malformé est **consigné, jamais bloquant**. Il entre au corpus avec sa
faute : l'observation prime sur la propreté.

**3 · Vérifier le carré (RFC-002 §6.3).** Pour chaque ha, `carre.md` :

| Verdict | Ce qu'il dit |
|---|---|
| `conforme` | l'état final livre au moins ce que `produit` promet |
| `sur-promesse` | un champ promis manque ou est trop faible — **non-conformité** |
| `hors-premisse` | l'état d'entrée ne satisfait pas `herite` : le carré n'est pas évaluable |
| `sans-etat` | aucun bloc lisible dans ce ha |

`hors-premisse` n'est pas une conformité. Un ha qui ne remplit pas la prémisse ne
prouve rien — le distinguer d'un `conforme` évite de compter des succès qui n'en
sont pas.

Un statut hors taxonomie est traité comme **le plus faible de tous** : un statut
inventé ne garantit rien. C'est ce qui relie les deux étages — un bloc mal formé
n'invalide pas le carré par principe, mais il ne peut pas non plus le satisfaire.

`kokaji middleware` sort en erreur s'il trouve une sur-promesse : le kata
garantit ce que la pratique ne livre pas.

## La lecture

`kokaji service` expose une API **en lecture seule** (§12). Aucune route n'écrit
— une requête d'écriture reçoit `405`.

| Route | Ce qu'elle rend |
|---|---|
| `GET /ha` | la liste des ha, avec statut et verdict de carré |
| `GET /ha/{id}` | la fiche, le carré, le nombre de blocs |
| `GET /ha/{id}/transcript` | le transcript |
| `GET /ha/{id}/etat` | les blocs d'état horodatés |
| `GET /sujet/{sujet}/etat` | le dernier état connu d'un sujet — R7.4, `get_state` |
| `GET /chaine` | la topologie déclarée, pour le QG (§8) |
| `GET /sante` | le service répond-il |

Lié à la loopback par défaut. La surface **MCP** de R7.4 n'existe pas encore ;
ces routes en sont la matière.

## Installation

FastAPI et uvicorn sont un extra : `pip install -e ".[service]"`. Sans eux,
`kokaji middleware` fonctionne — seule la surface HTTP demande l'extra.
