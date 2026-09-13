# Kokaji — le service de lecture et la veille (SPECS §7, §8).
#
# Une seule image pour les deux : ce sont deux commandes du même paquet. Le
# harness, les coupes et le corpus sont montés, pas copiés — ils vivent, l'image
# non.

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /kokaji

COPY pyproject.toml README.md ./
COPY kokaji ./kokaji

RUN pip install --quiet ".[service]"

# Ni la veille ni le service n'ont besoin d'être root : la veille écrit dans le
# corpus monté, le service ne fait que lire.
RUN useradd --create-home --uid 10001 forgeron
USER forgeron

EXPOSE 8100

# Par défaut, la lecture seule. La veille se lance avec `command:`.
CMD ["kokaji", "service", "/harness", "--journal", "/journal", "--hote", "0.0.0.0", "--port", "8100"]
