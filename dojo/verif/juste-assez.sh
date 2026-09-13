#!/usr/bin/env bash
# Critère « juste assez » du Dojo (SPECS §3) :
#   1. converser avec <harness>/<kata> via curl
#   2. retrouver la session dans le journal avec son identité de ha complète
#
# Le troisième point — changer le moteur en une ligne — se vérifie à la main en
# éditant la ligne `model:` de l'entrée dans litellm/config.yaml.
set -euo pipefail

ICI="$(cd "$(dirname "$0")" && pwd)"
PASSERELLE="${PASSERELLE:-http://127.0.0.1:4000}"
CLE="${DOJO_CLE_BANC:?DOJO_CLE_BANC manquant — voir dojo/README.md}"
MODELE="${MODELE:-atelier/idee}"
JOURNAL="${JOURNAL:-$ICI/../journal}"

echo "→ 1/2  conversation avec ${MODELE}"
curl -sS "${PASSERELLE}/v1/chat/completions" \
	-H "Authorization: Bearer ${CLE}" \
	-H "Content-Type: application/json" \
	-d "{\"model\":\"${MODELE}\",\"messages\":[{\"role\":\"user\",\"content\":\"Bonjour.\"}]}" \
	| python3 -c 'import json,sys; print(json.load(sys.stdin)["choices"][0]["message"]["content"])'

sleep 2

echo
echo "→ 2/2  dernière ligne du journal"
python3 - "$JOURNAL" <<'PY'
import json, pathlib, sys

fichiers = sorted(pathlib.Path(sys.argv[1]).glob("*.jsonl"))
if not fichiers:
    sys.exit("aucun journal — la session n'a pas été tracée")

*_, derniere = fichiers[-1].read_text(encoding="utf-8").splitlines()
ligne = json.loads(derniere)
identite = ligne["identite"]

attendus = ["harness", "kata", "version_kata", "version_coupe", "cible", "date"]
manquants = [c for c in attendus if not identite.get(c)]

print(f"  statut     {ligne['statut']}")
print(f"  session    {ligne['session']}")
print(f"  moteur     {ligne['fournisseur']}/{ligne['moteur']}")
for champ in attendus:
    print(f"  {champ:<10} {identite.get(champ)}")
print(f"  tours      {len(ligne['messages'])}")

if manquants:
    sys.exit(f"\nidentité de ha incomplète : {', '.join(manquants)}")
print("\nidentité de ha complète.")
PY
