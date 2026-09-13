"""La surface que le chat consomme — RFC-005 §3.

Kokaji sert lui-même la liste des modèles au lieu de la subir. Deux raisons, et
la seconde n'est apparue qu'en pratique :

1. **Une liste tenue à la main décroche.** La passerelle énumérait ses modèles
   virtuels dans un fichier ; la forge produisait une coupe que cette liste ne
   servait pas, et rien ne l'a signalé — c'est `NOTE-0002`. Une liste calculée
   depuis la définition ne peut pas décrocher d'elle.
2. **Une clé partagée ne peut produire qu'une liste partagée.** Le chat parle à
   la passerelle avec une seule clé pour tout le monde : aucun filtrage par
   personne n'était possible en amont de Kokaji.

L'identité de l'appelant doit être **signée**. Le chat sait envoyer un JWT HS256
dès qu'un secret est partagé ; sans lui il envoie des en-têtes en clair, que
n'importe qui atteignant le point d'entrée peut écrire. Une façade qui prétend
filtrer par personne ne peut pas croire son appelant sur parole.

La vérification est écrite ici plutôt qu'empruntée : elle tient en vingt lignes,
et les trois pièges qui la rendent inutile — accepter `none`, accepter un autre
algorithme, comparer les signatures sans temps constant — se lisent alors au
lieu de se supposer.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

from ..hds import Harness

try:
    from fastapi import APIRouter, HTTPException, Request
except ModuleNotFoundError as err:  # pragma: no cover - dépend de l'installation
    raise ModuleNotFoundError(
        "la surface HTTP demande l'extra `service` : pip install -e '.[service]'"
    ) from err

__all__ = ["JetonInvalide", "Passerelle", "routeur_chat", "verifier_jeton"]

# Le seul algorithme admis. Le lire dans l'en-tête du jeton pour choisir comment
# le vérifier, c'est laisser l'attaquant choisir sa serrure.
ALGORITHME = "HS256"


class JetonInvalide(Exception):
    """Le jeton n'est pas celui qu'il prétend être, ou ne vaut plus."""


def _decoder(segment: str) -> bytes:
    """Base64url sans remplissage — le JWT le retire, Python l'exige."""
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def verifier_jeton(jeton: str, secret: str, maintenant: float | None = None) -> dict:
    """La charge d'un JWT HS256, ou une exception. Jamais de charge non vérifiée.

    Trois refus valent d'être nommés, parce que les oublier rend la
    vérification décorative :

    - **`alg` est imposé, pas lu.** Un jeton qui s'annonce `none` ou `RS256`
      est refusé sans examen : accepter l'algorithme que l'attaquant déclare,
      c'est le laisser choisir comment on le vérifie.
    - **La comparaison est à temps constant.** Un `==` fuit, octet par octet,
      de quoi reconstruire une signature.
    - **`exp` est exigé.** Un jeton sans expiration est une clé permanente
      posée dans un en-tête.
    """
    morceaux = jeton.split(".")
    if len(morceaux) != 3:
        raise JetonInvalide("jeton mal formé")
    entete_b64, charge_b64, signature_b64 = morceaux

    try:
        entete = json.loads(_decoder(entete_b64))
        charge = json.loads(_decoder(charge_b64))
        signature = _decoder(signature_b64)
    except (ValueError, json.JSONDecodeError) as err:
        raise JetonInvalide("jeton illisible") from err

    if entete.get("alg") != ALGORITHME:
        raise JetonInvalide(f"algorithme refusé : {entete.get('alg')!r}")

    attendue = hmac.new(
        secret.encode("utf-8"), f"{entete_b64}.{charge_b64}".encode(), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(signature, attendue):
        raise JetonInvalide("signature invalide")

    expire = charge.get("exp")
    if not isinstance(expire, (int, float)):
        raise JetonInvalide("jeton sans expiration")
    if (maintenant if maintenant is not None else time.time()) >= expire:
        raise JetonInvalide("jeton périmé")

    return charge


@dataclass(frozen=True)
class Passerelle:
    """Où relayer les complétions, avec quelle clé, et ce qui passe sans kata.

    `nus` — les modèles servis **sans coupe**, donc sans harness : le chat en
    appelle un pour ses propres fonctions d'interface (titres, étiquettes).
    Sans eux, basculer le chat sur Kokaji ferait échouer chaque titre de
    conversation, puisqu'un modèle d'interface n'est le kata de personne.

    Ils sont **déclarés, jamais devinés** — la même liste que le hook
    d'injection de la passerelle, qui les laisse déjà passer sans coupe. Une
    liste vide ferme la porte : c'est la déclaration qui ouvre, pas l'oubli.
    """

    base: str
    cle: str = ""
    nus: frozenset[str] = frozenset()

    @classmethod
    def depuis_l_environnement(cls) -> Passerelle | None:
        base = (os.environ.get("KOKAJI_PASSERELLE_URL") or "").rstrip("/")
        if not base:
            return None
        return cls(
            base,
            os.environ.get("KOKAJI_PASSERELLE_CLE") or "",
            frozenset(
                m.strip() for m in os.environ.get("KOKAJI_MODELES_NUS", "").split(",") if m.strip()
            ),
        )


def routeur_chat(
    harness: Harness, passerelle: Passerelle | None = None, archive=None
) -> APIRouter:
    """La surface compatible OpenAI d'**un** harness.

    Elle vit dans l'application du harness : la liste des modèles *est* la liste
    de ses kata, et l'aiguilleur a déjà résolu de quel harness il s'agit. Un
    kata d'un autre harness n'est donc pas seulement absent de la liste — il est
    inatteignable, ce qui est une frontière et non un confort d'affichage.
    """
    routeur = APIRouter()

    @routeur.get("/v1/models", summary="Les kata du harness courant, en modèles")
    def modeles() -> dict:
        """Calculée, jamais énumérée — c'est ce qui l'empêche de décrocher.

        Un modèle par kata, sans les variantes `@cible` : deux incarnations
        d'un même kata servent à les comparer au banc, pas à faire choisir
        quelqu'un entre deux versions de la même étape.

        **Un harness archivé n'en offre aucun** (RFC-006 §5) : il a cessé de
        servir. Ses ha restent lisibles au QG — archiver retire du service, il
        ne détruit pas ce qui a été observé.
        """
        if archive is not None and archive():
            return {"object": "list", "data": []}
        return {
            "object": "list",
            "data": [
                {
                    "id": harness.espace(kata.id),
                    "object": "model",
                    "created": 0,
                    "owned_by": harness.id,
                    # Le libellé est le nom du kata, l'identifiant reste la clé
                    # d'archive : on lit « Clarifier l'idée », le journal écrit
                    # `atelier/idee`.
                    "name": kata.nom,
                }
                for kata in harness.kata
            ],
        }

    @routeur.post("/v1/chat/completions", summary="Relayer une complétion à la passerelle")
    async def completions(requete: Request) -> object:
        import httpx
        from fastapi.responses import JSONResponse, StreamingResponse

        corps = await requete.json()
        # La frontière d'abord, la configuration ensuite : un kata étranger se
        # refuse même sans passerelle. Dans l'autre ordre, un service mal
        # configuré répondrait « pas de passerelle » à une tentative qui aurait
        # dû être refusée — et le jour où la passerelle arrive, la frontière
        # n'aurait jamais été éprouvée.
        if archive is not None and archive():
            raise HTTPException(
                status_code=403, detail=f"harness archivé : {harness.id}"
            )
        _exiger_du_harness(harness, str(corps.get("model") or ""), passerelle)
        if passerelle is None:
            raise HTTPException(status_code=503, detail="aucune passerelle configurée")

        entetes = {"content-type": "application/json"}
        if passerelle.cle:
            entetes["authorization"] = f"Bearer {passerelle.cle}"

        client = httpx.AsyncClient(timeout=None)
        amont = client.build_request(
            "POST", f"{passerelle.base}/v1/chat/completions", json=corps, headers=entetes
        )
        reponse = await client.send(amont, stream=True)

        if not corps.get("stream"):
            try:
                return JSONResponse(
                    json.loads(await reponse.aread()), status_code=reponse.status_code
                )
            finally:
                await reponse.aclose()
                await client.aclose()

        async def couler():
            try:
                async for morceau in reponse.aiter_raw():
                    yield morceau
            finally:
                await reponse.aclose()
                await client.aclose()

        return StreamingResponse(
            couler(),
            status_code=reponse.status_code,
            media_type=reponse.headers.get("content-type", "text/event-stream"),
        )

    return routeur


def _exiger_du_harness(
    harness: Harness, modele: str, passerelle: Passerelle | None = None
) -> None:
    """Le kata appelé appartient-il à ce harness ?

    Le filtrage de la liste ne suffit pas : un nom de modèle se forge à la main,
    et un fil rouvert après un changement de harness porte encore l'ancien. Sans
    ce refus, la liste ne serait qu'un confort d'affichage (RFC-005 §3.4).

    Les modèles nus passent — ils ne sont le kata de personne, et le Dojo
    déclare lesquels existent. Ils ne figurent pas pour autant dans
    `/v1/models` : ce sont des rouages d'interface, pas des étapes à pratiquer.
    """
    if passerelle is not None and modele in passerelle.nus:
        return
    prefixe, _, kata = modele.partition("/")
    # La cible forcée (`@instrumentee`) reste une affaire de banc : elle ne
    # change pas le kata, donc pas l'appartenance.
    kata = kata.partition("@")[0]
    if prefixe != harness.id or harness.kata_par_id(kata) is None:
        raise HTTPException(
            status_code=403,
            detail=f"modèle hors du harness courant : {modele!r}",
        )
