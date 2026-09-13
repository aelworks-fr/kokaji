#!/usr/bin/env bash
# La trempe du produit — RFC-009. Trois vérificateurs et la souveraineté,
# sur les seuls fichiers versionnés : ce que git ne suit pas ne sera pas
# publié, le vérifier crierait sur ce qui ne sort jamais.
set -uo pipefail
cd "$(dirname "$0")/.."

ROUGE=0
dire() { printf '%s\n' "$*"; }
refuser() { ROUGE=1; printf '✗ %s\n' "$*"; }

fichiers_suivis() {
  # Les suivis, plus l'index : un sabotage ajouté par `git add` doit être vu
  # avant son commit, pas après.
  { git ls-files; git diff --cached --name-only; } | sort -u
}

exempte() { # $1 = chemin
  grep -v '^\s*#' trempe/exemptions.txt 2>/dev/null \
    | awk '{print $1}' | grep -qxF "$1"
}

# --- 1 · lint vocabulaire -----------------------------------------------------
TERMES=("mode guidé" "mode guide")
LOCAL="trempe/vocabulaire-interdit.local.txt"
if [ -f "$LOCAL" ]; then
  while IFS= read -r ligne; do
    ligne="${ligne%%#*}"; ligne="$(echo "$ligne" | xargs 2>/dev/null || true)"
    [ -n "$ligne" ] && TERMES+=("$ligne")
  done < "$LOCAL"
else
  dire "⚠ vocabulaire : $LOCAL absent — seuls les interdits publics sont vérifiés."
fi
while IFS= read -r f; do
  [ -f "$f" ] && ! exempte "$f" || continue
  for t in "${TERMES[@]}"; do
    if grep -liF -- "$t" "$f" >/dev/null 2>&1; then
      refuser "vocabulaire : terme interdit dans $f"
    fi
  done
done < <(fichiers_suivis)

# --- 2 · lint contenu (D9.2 / R10.6) -----------------------------------------
# Le repo produit ne contient aucun contenu d'instance : pas de ha, pas de
# corpus peuplé, aucun harness hors atelier/.
while IFS= read -r f; do
  case "$f" in
    *CAS-[0-9][0-9][0-9][0-9]*) refuser "contenu : un ha dans le produit — $f" ;;
  esac
  case "$f" in
    kokaji/corpus/*) ;; # le module qui lit les corpus, pas un corpus
    */corpus/*) [ "$(basename "$f")" = ".gardien" ] || refuser "contenu : corpus peuplé — $f" ;;
  esac
  case "$f" in
    harness.yaml|*/harness.yaml)
      # La semence (kokaji/semence/) est le gabarit d'un harness neuf : du produit.
      case "$f" in atelier/harness.yaml|kokaji/semence/harness.yaml) ;;
        *) refuser "contenu : harness hors atelier/ — $f" ;; esac ;;
  esac
  case "$f" in
    *fiche.md|*transcript.md|*etats.jsonl|*scellements.jsonl|*.ecartes.jsonl)
      refuser "contenu : fichier de pratique — $f" ;;
  esac
done < <(fichiers_suivis)

# --- 3 · check coupe (D9.1) ---------------------------------------------------
# Une coupe est un dérivé : régénérée, jamais commitée.
COUPES="$( { git ls-files 'dist/*'; git diff --cached --name-only -- 'dist/*'; } | sort -u)"
if [ -n "$COUPES" ]; then
  refuser "coupe : dist/ est suivi par git — $(echo "$COUPES" | head -3 | tr '\n' ' ')"
fi

# --- 4 · souveraineté (D9.4), v0 honnête --------------------------------------
# Un check statique : aucune destination réseau en dur dans le produit, hors
# (a) la configuration des moteurs (.env.example, litellm-config), (b) les
# registres de paquets des manifestes de build, (c) la prose (docs, README,
# licence) — une v0 greppe, elle ne prouve pas l'absence d'appel construit
# dynamiquement, et le dit.
while IFS= read -r f; do
  [ -f "$f" ] || continue
  case "$f" in
    docs/*|README.md|*/README.md|CLAUDE.md|LICENSE|NOTICE) continue ;;
    dojo/.env.example|dojo/litellm-config.yaml|dojo/Caddyfile) continue ;;
    pyproject.toml|package.json|*/pyproject.toml|*/package.json) continue ;;
  esac
  # Un hôte sans point est un service du réseau interne du compose
  # (litellm:4000) : rien n'en sort de la machine.
  if grep -nE 'https?://' "$f" 2>/dev/null \
      | grep -vE 'https?://(localhost|127\.0\.0\.1|[a-z0-9-]+)([^a-z0-9.-]|$)' | grep -q .; then
    refuser "souveraineté : destination réseau en dur dans $f"
  fi
done < <(fichiers_suivis)

if [ "$ROUGE" -eq 0 ]; then
  dire "✓ trempe du produit — vocabulaire, contenu, coupes, souveraineté"
fi
exit "$ROUGE"
