# La vigie regarde aussi le rendu — il lui faut donc un navigateur, ce que
# l'image de Kokaji n'a pas et n'a pas à avoir : le service sert des pages, il
# n'en regarde aucune. Deux besoins, deux images.
#
# Sans cette image, les mesures de rendu ne tourneraient qu'à la main, et une
# vérification qu'on lance à la main retombe dans le silence qu'elle combat
# (NOTE-0011).
FROM mcr.microsoft.com/playwright/python:v1.62.0-noble

WORKDIR /kokaji
COPY pyproject.toml README.md ./
COPY kokaji ./kokaji
RUN pip install --quiet --no-input ".[service]" playwright

ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
# Pas d'ENTRYPOINT : les autres services du dojo nomment `kokaji` dans leur
# `command`, et deux conventions pour une même image donnent `kokaji kokaji`.
