#!/usr/bin/env bash
# Les tests de rendu, dans un conteneur qui porte un navigateur — NOTE-0008.
#
# `tests/test_rendu.py` ouvre un vrai navigateur sur un vrai écran de 360 px et
# mesure des rectangles. Il tourne nativement dès que le poste a Chromium et ses
# bibliothèques système :
#
#     pip install playwright && playwright install chromium
#     sudo playwright install-deps
#
# Ce script est la variante pour un poste où l'on ne veut rien installer — ou
# qui n'a pas les droits pour le faire. Il ne change rien à ce qui est mesuré :
# c'est le même fichier de test, le même navigateur.
#
# Sans lui, ces tests se sautent en silence sur une machine sans navigateur, et
# un test qui se saute finit par ne plus exister. C'est la panne que le carnet
# décrit trois fois : ce qui se tait se lit comme ce qui va bien.
set -euo pipefail

DEPOT="$(cd "$(dirname "$0")/../.." && pwd)"
IMAGE="${IMAGE_PLAYWRIGHT:-mcr.microsoft.com/playwright/python:v1.62.0-noble}"

exec docker run --rm \
  -v "$DEPOT:/depot" -w /depot \
  --user "$(id -u):$(id -g)" \
  -e HOME=/tmp \
  -e PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
  "$IMAGE" \
  sh -c '
    pip install --quiet --no-input --target=/tmp/paquets \
      fastapi uvicorn pyyaml argon2-cffi "ruamel.yaml" pytest playwright >/dev/null 2>&1
    PYTHONPATH=/tmp/paquets:/depot exec python -m pytest tests/test_rendu.py "$@"
  ' -- "$@"
