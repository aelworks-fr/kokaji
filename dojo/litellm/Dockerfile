# La passerelle, plus le pilote Postgres : le hook du journal écrit en base
# à la source (RFC-014 D14.4). L'image de LiteLLM n'a ni pip ni pilote ;
# ensurepip suffit. Sans `KOKAJI_BASE_URL`, le hook écrit en fichiers et cette
# image se comporte exactement comme celle qu'elle étend.
ARG LITELLM_IMAGE=ghcr.io/berriai/litellm:main-stable
FROM ${LITELLM_IMAGE}
RUN python -m ensurepip --upgrade >/dev/null 2>&1 \
 && python -m pip install --quiet --no-cache-dir "psycopg[binary]>=3.1"
