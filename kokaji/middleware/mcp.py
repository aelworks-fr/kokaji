"""La surface de l'agent — RFC-022 : un client MCP forge au nom d'un compte.

**Une seule autorité.** Un outil n'est pas une seconde implémentation d'un
geste : c'est la traduction d'un appel à la route qui le porte déjà, jouée
dans le même processus. L'appel interne porte le compte dans la portée ASGI
(`AGENT`), jamais dans un en-tête, si bien qu'un client ne peut ni l'écrire ni
y glisser celui du portail. La matrice du RFC-004, les refus et les codes
restent ceux de la route ; cette surface n'ajoute que deux choses :

- **la portée du jeton** (D22.4), qui s'ajoute au rôle et ne le remplace pas ;
- **le harness nommé** (D22.5) : l'appel va à l'application de *ce* harness,
  sans lire ni écrire le harness courant, qui appartient à la pratique.

Le protocole est tenu « juste assez » : JSON-RPC sur `POST /mcp`, réponses en
JSON (le transport HTTP du protocole les admet à la place d'un flux), sans
session ni notification serveur. Aucune dépendance de plus, aucune émission
réseau : la surface reçoit, elle n'appelle personne (R12.5).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

from ..comptes import CONCEPTION, ETRANGER, LECTURE, Comptes
from .identite import AGENT, Identification

try:
    import httpx
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse, Response
except ModuleNotFoundError as err:  # pragma: no cover - dépend de l'installation
    raise ModuleNotFoundError(
        "la surface HTTP demande l'extra `service` : pip install -e '.[service]'"
    ) from err

__all__ = ["OUTILS", "routeur_mcp"]

# Les versions du protocole qu'on sait parler. On rend celle du client si on la
# connaît, sinon la plus récente : c'est au client de dire s'il la parle.
VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26")

# Une portée couvre ce qu'elle nomme, et `conception` couvre aussi la lecture.
COUVRE = {LECTURE: {LECTURE}, CONCEPTION: {LECTURE, CONCEPTION}}

CONSIGNES = (
    "Kokaji forge des harness : des ensembles de kata (étapes décisionnelles) "
    "définis par un manifest HDS, un gabarit et une source par kata. Tu agis au "
    "nom d'un compte, sur les harness où il est propriétaire ou contributeur. "
    "Pour changer une définition : lis-la (`harness_lire`), propose, fais "
    "éprouver (`proposition_eprouver`) jusqu'à ce qu'elle tienne, puis scelle "
    "(`proposition_sceller`). Une proposition a pour clés possibles : kata, "
    "retirer, chaine, trempe, source, template, importe. La pratique (les "
    "conversations, les sujets) n'est pas sur cette surface."
)


@dataclass(frozen=True)
class Outil:
    nom: str
    description: str
    portee: str
    proprietes: dict
    requis: tuple[str, ...]
    # `(arguments, compte) -> (où, méthode, chemin, corps)` : « commun » pour
    # ce qui ne vit dans aucun harness, sinon l'id du harness nommé.
    appel: Callable


HARNESS = {"type": "string", "description": "l'id du harness"}
PROPOSITION = {
    "type": "object",
    "description": "les changements proposés — clés : kata, retirer, chaine, trempe, "
    "source, template, importe ; voir `harness_lire` pour la forme en place",
}


CHEMIN_NU = {
    "type": "string",
    "description": "le dépôt nu, sous le dossier que le déploiement déclare — un chemin hors "
    "de ce dossier se refuse",
}
BRANCHE = {"type": "string", "description": "la branche ; « main » si rien n'est dit"}


def _sur(chemin: str, methode: str = "GET", corps: Callable | None = None):
    """Un appel à l'application du harness nommé."""
    return lambda a, qui: (a["harness"], methode, chemin, corps(a, qui) if corps else None)


def _commun(chemin: Callable | str, methode: str = "GET", corps: Callable | None = None):
    return lambda a, qui: (
        "commun", methode, chemin(a) if callable(chemin) else chemin,
        corps(a, qui) if corps else None,
    )


def _garder(*cles: str):
    return lambda a, qui: {k: a[k] for k in cles if k in a}


OUTILS: tuple[Outil, ...] = (
    # --- lire ---------------------------------------------------------------
    Outil("harness_lister", "Mes harness, mon rôle sur chacun, et le harness d'exemple copiable.",
          LECTURE, {}, (), _commun("/harness")),
    Outil("harness_lire",
          "La définition d'un harness en forme éditable : gabarit, cibles, kata (triplet, "
          "source, contrat), chaîne, trempe, dernier scellement, membres.",
          LECTURE, {"harness": HARNESS}, ("harness",), _sur("/conception")),
    Outil("coupe_voir",
          "La coupe d'un kata pour une cible, forgée en mémoire depuis la définition en place "
          "ou depuis une proposition. Rien n'est écrit.",
          LECTURE,
          {"harness": HARNESS, "kata": {"type": "string"}, "cible": {"type": "string"},
           "proposition": PROPOSITION},
          ("harness", "kata", "cible"),
          _sur("/conception/coupe", "POST", _garder("kata", "cible", "proposition"))),
    Outil("depot_etat", "L'état du dépôt git du harness : propre, en avance, en retard, divergé.",
          LECTURE, {"harness": HARNESS}, ("harness",), _sur("/depot")),
    Outil("membres_lister", "Le propriétaire et les contributeurs du harness.",
          LECTURE, {"harness": HARNESS}, ("harness",), _sur("/membres")),
    Outil("proposition_eprouver",
          "Éprouver une proposition : elle est appliquée à une copie, chargée, forgée et "
          "trempée pour de vrai. Rend le verdict, les fautes et les versions prévues. Rien "
          "n'est écrit.",
          LECTURE, {"harness": HARNESS, "proposition": PROPOSITION}, ("harness", "proposition"),
          _sur("/conception/epreuve", "POST", _garder("proposition"))),
    # --- créer --------------------------------------------------------------
    Outil("harness_creer",
          "Faire naître un harness : copier `source` (un des miens, ou l'exemple), ou semer "
          "le gabarit neuf si `source` est vide. L'id est immuable, le nom libre.",
          CONCEPTION,
          {"id": {"type": "string"}, "nom": {"type": "string"}, "source": {"type": "string"}},
          ("id", "nom"),
          _commun("/harness", "POST", lambda a, qui: {
              "id_harness": a["id"], "nom": a["nom"], "source": a.get("source", "")})),
    Outil("harness_cloner",
          "Faire naître un harness d'un dépôt nu qui en est déjà un (RFC-012 D12.4) : le clone "
          "est lu et validé avant que quoi que ce soit ne s'enregistre. Un dépôt qui n'est pas "
          "un harness ne laisse rien. Le nom vient du manifest cloné, pas d'un argument.",
          CONCEPTION,
          {"id": {"type": "string", "description": "l'id du harness à faire naître, immuable"},
           "chemin": CHEMIN_NU, "branche": BRANCHE},
          ("id", "chemin"),
          _commun("/harness", "POST", lambda a, qui: {
              "id_harness": a["id"],
              "cloner_depuis": {"chemin": a["chemin"], "branche": a.get("branche", "main")}})),
    Outil("harness_adopter",
          "Adopter des textes faits main : chaque texte devient un kata servi tel quel.",
          CONCEPTION,
          {"id": {"type": "string"}, "nom": {"type": "string"},
           "textes": {"type": "array", "items": {
               "type": "object", "properties": {"nom": {"type": "string"},
                                                "texte": {"type": "string"}}}},
           "provenance": {"type": "string", "description": "d'où viennent les textes"}},
          ("id", "nom", "textes", "provenance"),
          _commun("/harness/adoption", "POST", lambda a, qui: {
              "id_harness": a["id"], "nom": a["nom"], "prompts": a["textes"],
              "provenance": a["provenance"]})),
    Outil("etape_adoptee_ajouter", "Ajouter un texte fait main comme étape d'un harness adopté.",
          CONCEPTION,
          {"harness": HARNESS, "nom": {"type": "string"}, "texte": {"type": "string"}},
          ("harness", "nom", "texte"),
          _commun(lambda a: f"/harness/{a['harness']}/etape-adoptee", "POST",
                  _garder("nom", "texte"))),
    # --- concevoir ----------------------------------------------------------
    Outil("proposition_sceller",
          "Sceller une proposition : versionnée, commitée, poussée si le harness le demande, "
          "forgée. Le scellement est signé du nom du compte, et la trace nomme ce jeton.",
          CONCEPTION,
          {"harness": HARNESS, "proposition": PROPOSITION,
           "motif": {"type": "string", "description": "pourquoi ce changement"}},
          ("harness", "proposition"),
          _sur("/conception/scellement", "POST", lambda a, qui: {
              "proposition": a["proposition"], "motif": a.get("motif", ""),
              # Écrasé par la route (D22.8) : l'auteur est le compte, pas un argument.
              "auteur": qui.nom})),
    Outil("depot_pousser", "Pousser la branche du harness vers son dépôt nu, en avance rapide.",
          CONCEPTION, {"harness": HARNESS}, ("harness",), _sur("/depot/pousser", "POST")),
    Outil("depot_tirer", "Tirer la branche du dépôt nu, en avance rapide, clone propre exigé.",
          CONCEPTION, {"harness": HARNESS}, ("harness",), _sur("/depot/tirer", "POST")),
    # --- posséder (propriétaire seul ; le transfert reste à la main, D22.7) --
    Outil("harness_archiver", "Archiver un harness (`archive` vrai), ou l'en sortir.",
          CONCEPTION, {"harness": HARNESS, "archive": {"type": "boolean"}}, ("harness",),
          _commun(lambda a: f"/harness/{a['harness']}/archive", "POST",
                  lambda a, qui: {"archive": a.get("archive", True)})),
    Outil("membres_candidats", "Les comptes qu'on peut ajouter comme contributeurs.",
          CONCEPTION, {"harness": HARNESS}, ("harness",), _sur("/membres/candidats")),
    Outil("membre_ajouter", "Ajouter un contributeur, par son email.",
          CONCEPTION, {"harness": HARNESS, "email": {"type": "string"}}, ("harness", "email"),
          _sur("/membres", "POST", _garder("email"))),
    Outil("membre_retirer", "Retirer un contributeur, par son id.",
          CONCEPTION, {"harness": HARNESS, "utilisateur_id": {"type": "string"}},
          ("harness", "utilisateur_id"),
          lambda a, qui: (a["harness"], "DELETE", f"/membres/{a['utilisateur_id']}", None)),
    Outil("depot_enregistrer",
          "Lier le harness à un dépôt nu : le dépôt est créé s'il n'existe pas, l'historique y "
          "est poussé, et la ligne ne s'écrit qu'après — un push refusé n'enregistre rien.",
          CONCEPTION,
          {"harness": HARNESS, "chemin": CHEMIN_NU, "branche": BRANCHE,
           "pousser_au_scellement": {
               "type": "boolean",
               "description": "pousser à chaque scellement ; vrai si rien n'est dit"}},
          ("harness", "chemin"),
          _sur("/depot", "PUT",
               _garder("chemin", "branche", "pousser_au_scellement"))),
    Outil("depot_desenregistrer",
          "Délier : la ligne seulement. Le clone et le dépôt nu restent intacts, et le harness "
          "se réenregistre (RFC-012 D12.2 — rien n'est détruit).",
          CONCEPTION, {"harness": HARNESS}, ("harness",), _sur("/depot", "DELETE")),
)

PAR_NOM = {o.nom: o for o in OUTILS}


def _schema(outil: Outil) -> dict:
    return {
        "type": "object",
        "properties": outil.proprietes,
        "required": list(outil.requis),
        "additionalProperties": False,
    }


def routeur_mcp(
    identification: Identification,
    comptes: Comptes,
    commun: Callable,
    applications: Callable,
    version: str = "",
) -> APIRouter:
    """`commun` et `applications` sont lus à l'appel : un harness né après le
    montage doit être joignable sans redémarrage, comme pour l'aiguilleur."""
    routeur = APIRouter()

    async def _appeler(cible, qui_jeton, methode: str, chemin: str, corps) -> tuple[int, object]:
        async def avec_agent(scope, receive, send):
            await cible({**scope, AGENT: qui_jeton}, receive, send)

        transport = httpx.ASGITransport(app=avec_agent)
        async with httpx.AsyncClient(transport=transport, base_url="http://interne") as client:
            reponse = await client.request(methode, chemin, json=corps)
        try:
            return reponse.status_code, reponse.json()
        except ValueError:
            return reponse.status_code, reponse.text

    async def _outil(nom: str, arguments: dict, qui, jeton) -> dict:
        outil = PAR_NOM.get(nom)
        if outil is None or outil.portee not in COUVRE.get(jeton.portee, set()):
            # Un outil hors de la portée se refuse comme un outil inconnu : la
            # liste qu'on a reçue ne le montrait pas.
            return _resultat(f"aucun outil à ce nom : {nom}", erreur=True)
        if not isinstance(arguments, dict):
            return _resultat("les arguments sont un objet", erreur=True)
        inconnus = sorted(set(arguments) - set(outil.proprietes))
        if inconnus:
            return _resultat(f"argument(s) inconnu(s) : {', '.join(inconnus)}", erreur=True)
        manquants = [r for r in outil.requis if r not in arguments]
        if manquants:
            return _resultat(f"argument(s) manquant(s) : {', '.join(manquants)}", erreur=True)

        if "harness" in arguments:
            # D22.5 — le harness d'autrui se refuse comme celui qui n'existe pas.
            harness = str(arguments["harness"])
            if harness not in applications() or comptes.role(harness, qui.id) == ETRANGER:
                return _resultat(f"aucun harness à ce nom : {harness}", erreur=True)

        ou, methode, chemin, corps = outil.appel(arguments, qui)
        cible = commun() if ou == "commun" else applications()[ou]
        code, rendu = await _appeler(cible, (qui, jeton), methode, chemin, corps)
        if code >= 400:
            detail = rendu.get("detail", rendu) if isinstance(rendu, dict) else rendu
            return _resultat(f"refusé ({code}) : {detail}", erreur=True)
        return _resultat(rendu)

    def _repondre(ident, resultat=None, erreur: tuple[int, str] | None = None) -> JSONResponse:
        corps = {"jsonrpc": "2.0", "id": ident}
        if erreur is not None:
            corps["error"] = {"code": erreur[0], "message": erreur[1]}
        else:
            corps["result"] = resultat
        return JSONResponse(corps)

    @routeur.post("/mcp", summary="La surface de l'agent — RFC-022")
    async def mcp(requete: Request) -> Response:
        qui, jeton = identification.par_jeton_agent(requete)
        try:
            message = await requete.json()
        except ValueError:
            return _repondre(None, erreur=(-32700, "JSON illisible"))
        if not isinstance(message, dict):
            return _repondre(None, erreur=(-32600, "un message à la fois"))

        methode = str(message.get("method") or "")
        ident = message.get("id")
        params = message.get("params") or {}
        if ident is None:
            # Une notification, ou une réponse du client : rien à rendre.
            return Response(status_code=202)

        if methode == "initialize":
            demandee = str(params.get("protocolVersion") or "")
            return _repondre(ident, {
                "protocolVersion": demandee if demandee in VERSIONS else VERSIONS[0],
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "kokaji", "version": version or "0"},
                "instructions": CONSIGNES,
            })
        if methode == "ping":
            return _repondre(ident, {})
        if methode == "tools/list":
            couverts = COUVRE.get(jeton.portee, set())
            return _repondre(ident, {"tools": [
                {"name": o.nom, "description": o.description, "inputSchema": _schema(o)}
                for o in OUTILS if o.portee in couverts
            ]})
        if methode == "tools/call":
            return _repondre(ident, await _outil(
                str(params.get("name") or ""), params.get("arguments") or {}, qui, jeton
            ))
        return _repondre(ident, erreur=(-32601, f"méthode inconnue : {methode}"))

    @routeur.get("/mcp", summary="Pas de flux serveur : la surface répond en JSON")
    def mcp_flux() -> Response:
        return Response(status_code=405, headers={"Allow": "POST"})

    return routeur


def _resultat(rendu, erreur: bool = False) -> dict:
    texte = rendu if isinstance(rendu, str) else json.dumps(rendu, ensure_ascii=False, indent=1)
    sortie = {"content": [{"type": "text", "text": texte}], "isError": erreur}
    if isinstance(rendu, dict) and not erreur:
        sortie["structuredContent"] = rendu
    return sortie
