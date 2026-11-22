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
from ..conception.modele import Proposition
from ..standard import hds
from .identite import AGENT, Identification

try:
    import httpx
    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse, Response
except ModuleNotFoundError as err:  # pragma: no cover - dépend de l'installation
    raise ModuleNotFoundError(
        "la surface HTTP demande l'extra `service` : pip install -e '.[service]'"
    ) from err

__all__ = ["OUTILS", "RESSOURCES", "routeur_mcp"]

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


# --- les ressources du §4.3 (D22.9) ------------------------------------------
#
# « Le standard voyage avec la surface » : un agent qui conçoit un harness doit
# savoir ce qu'est un harness. Ce sont des fichiers et des constantes **du
# produit**, servis tels quels — rien d'une instance, rien d'une pratique. La
# seule qui touche à une œuvre, les statuts d'un harness, passe par la route de
# sa définition : une seule autorité, comme pour les outils.

STANDARD_HDS = "kokaji://standard/hds"
STANDARD_PROPOSITION = "kokaji://standard/proposition"


def _uri_statuts(harness: str) -> str:
    return f"kokaji://harness/{harness}/statuts"


# Un exemple **minimal**, pas un extrait de l'Atelier lu sur le disque : le
# harness d'exemple n'est pas dans l'image, et le serait-il, ce serait servir
# une œuvre là où on doit servir un vocabulaire. Les id sont ceux de l'Atelier
# pour que l'exemple soit concret.
PROPOSITION_EXEMPLE = {"kata": [{"id": "idee", "nom": "Clarifier l'idée"}]}

PROPOSITION_FORME = {
    "kata": "la liste des kata, chacun avec son id, son nom, son livrable, ses amont, "
            "ce qu'il hérite et ce qu'il produit — la liste remplace celle en place",
    "retirer": "les id de kata à retirer de la chaîne",
    "chaine": "l'enchaînement des nœuds, quand il ne se déduit pas des amont",
    "trempe": "les seuils, les checks de session et le vocabulaire interdit",
    "source": "la source d'un kata : son densho, par id de kata",
    "template": "le texte du gabarit — une chaîne, pas une structure",
    "importe": "la provenance d'un texte importé, par quoi ; une provenance sans "
               "`source` n'enregistre rien",
}


def _proposition() -> dict:
    """Le vocabulaire d'une proposition, tenu par le modèle lui-même.

    Les clés viennent de `Proposition.CLES` : une liste recopiée ici
    divergerait au premier amendement, et la surface mentirait à l'agent.
    """
    return {
        "cles": list(Proposition.CLES),
        "forme": {cle: PROPOSITION_FORME.get(cle, "") for cle in Proposition.CLES},
        "exemple_minimal": PROPOSITION_EXEMPLE,
        "comment": "Éprouver (`proposition_eprouver`) jusqu'à ce que la définition tienne, "
                   "puis sceller (`proposition_sceller`). Une clé hors de ce vocabulaire "
                   "est refusée, elle n'est pas ignorée. `motif` n'en fait pas partie : "
                   "c'est un argument de `proposition_sceller`, à côté de la proposition.",
    }


def _schema(outil: Outil) -> dict:
    return {
        "type": "object",
        "properties": outil.proprietes,
        "required": list(outil.requis),
        "additionalProperties": False,
    }


RESSOURCES: tuple[dict, ...] = (
    {"uri": STANDARD_HDS, "name": "Le standard HDS",
     "description": "Le contrat entre Kokaji et un harness, tel que le produit le versionne. "
                    "Kokaji n'interprète que ce standard : il ne sait rien du domaine couvert.",
     "mimeType": "text/markdown"},
    {"uri": STANDARD_PROPOSITION, "name": "Le vocabulaire d'une proposition",
     "description": "Les clés d'une proposition, leur forme, et un exemple minimal. "
                    "Une clé hors de ce vocabulaire est refusée, pas ignorée.",
     "mimeType": "application/json"},
)


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

    def _contenu(uri: str, texte: str, type_mime: str) -> dict:
        return {"contents": [{"uri": uri, "mimeType": type_mime, "text": texte}]}

    async def _lire_ressource(ident, uri: str, qui, jeton) -> JSONResponse:
        # Toutes les ressources sont en lecture : toute portée les couvre.
        inconnue = (-32002, f"aucune ressource à cette adresse : {uri}")
        if uri == STANDARD_HDS:
            texte = hds()
            if texte is None:
                # Le document n'a pas voyagé avec cette image. On le dit : une
                # ressource annoncée puis vide serait pire qu'une absence.
                return _repondre(ident, erreur=(
                    -32002, "le standard HDS n'est pas dans cette image : rien à servir"))
            return _repondre(ident, _contenu(uri, texte, "text/markdown"))
        if uri == STANDARD_PROPOSITION:
            return _repondre(ident, _contenu(
                uri, json.dumps(_proposition(), ensure_ascii=False, indent=1), "application/json"))

        prefixe, _, reste = uri.partition("kokaji://harness/")
        harness, barre, quoi = reste.partition("/")
        if prefixe or not barre or quoi != "statuts" or not harness:
            return _repondre(ident, erreur=inconnue)
        # D22.5 — un harness étranger se refuse comme un harness qui n'existe
        # pas, et des deux côtés le même mot.
        if harness not in applications() or comptes.role(harness, qui.id) == ETRANGER:
            return _repondre(ident, erreur=inconnue)
        # Une seule autorité : les statuts viennent de la route de la
        # définition, pas d'une lecture parallèle du manifest.
        code, rendu = await _appeler(
            applications()[harness], (qui, jeton), "GET", "/conception", None)
        if code >= 400 or not isinstance(rendu, dict):
            detail = rendu.get("detail", rendu) if isinstance(rendu, dict) else rendu
            return _repondre(ident, erreur=(-32002, f"refusé ({code}) : {detail}"))
        statuts = {"harness": harness, "statuts_champ": rendu.get("statuts_champ") or []}
        return _repondre(ident, _contenu(
            uri, json.dumps(statuts, ensure_ascii=False, indent=1), "application/json"))

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
                "capabilities": {
                    "tools": {"listChanged": False},
                    # `listChanged` est faux et `subscribe` absent : la surface
                    # ne pousse rien, elle répond (§4.1, l'amendement « juste
                    # assez »). Les statuts d'un harness changent au
                    # scellement ; c'est à l'agent de relire.
                    "resources": {"listChanged": False},
                },
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
        if methode == "resources/list":
            # Les deux du standard, et les statuts de chaque harness lisible.
            # Énumérer plutôt que servir un gabarit d'adresse : l'agent voit ce
            # qu'il peut lire, et un harness étranger n'apparaît pas — comme
            # `harness_lister` (D22.5).
            return _repondre(ident, {"resources": [
                *RESSOURCES,
                *[{"uri": _uri_statuts(h), "name": f"Les statuts de champ de « {h} »",
                   "description": "Les statuts qu'un champ peut porter dans ce harness, "
                                  "du plus faible au plus fort.",
                   "mimeType": "application/json"}
                  for h in sorted(applications())
                  if comptes.role(h, qui.id) != ETRANGER],
            ]})
        if methode == "resources/read":
            return await _lire_ressource(ident, str(params.get("uri") or ""), qui, jeton)
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
