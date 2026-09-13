"""Une application par harness, et un aiguilleur devant — RFC-005 §5.

Le harness cesse d'être une propriété du déploiement pour devenir une propriété
de la personne : chaque requête est remise à l'application du harness que son
appelant pratique. La résolution se fait **avant** le routage, parce qu'elle ne
dépend pas du chemin demandé mais de qui le demande.

**L'isolation est tenue par la portée, pas par la vigilance.** Une route vit
dans l'application d'un seul harness et n'a aucun moyen d'en nommer un autre :
il n'y a pas d'oubli possible, parce qu'il n'y a rien à ne pas oublier. C'est la
même discipline que l'invariant « exactement un propriétaire » du RFC-004 —
inexprimable plutôt qu'interdit.

Quatre choses vivent hors des harness et leur sont communes : les pages,
l'identification, les comptes et l'exploitation. Elles sont reconnues par
filtrage du chemin sur la table de routes commune, et servies **avant** toute
résolution — sinon on demanderait à quelqu'un de choisir un harness pour avoir
le droit d'ouvrir une session, ou de se connecter pour savoir si le service
répond.
"""

from __future__ import annotations

from pathlib import Path

from ..comptes import Comptes
from ..comptes.chat import Chat
from ..hds import Harness, charger
from .chat import Passerelle
from .exploitation import routeur_exploitation
from .identite import Identification, routeur_comptes, routeur_pages
from .service import creer_harness

try:
    from fastapi import FastAPI, HTTPException, Request
    from starlette.responses import JSONResponse
    from starlette.routing import Match
    from starlette.types import Receive, Scope, Send
except ModuleNotFoundError as err:  # pragma: no cover - dépend de l'installation
    raise ModuleNotFoundError(
        "la surface HTTP demande l'extra `service` : pip install -e '.[service]'"
    ) from err

__all__ = ["Aiguilleur", "creer_tous"]


class Aiguilleur:
    """Remet chaque requête à l'application du harness courant de l'appelant."""

    def __init__(
        self,
        applications: dict[str, FastAPI],
        commun: FastAPI,
        identification: Identification,
        comptes: Comptes | None = None,
    ):
        self.applications = applications
        self.commun = commun
        self.identification = identification
        self.comptes = comptes
        # Le défaut d'un déploiement mono-harness : s'il n'y en a qu'un, il n'y
        # a rien à choisir, et exiger un choix casserait une installation qui
        # marchait sans en avoir jamais fait.
        self.seul = next(iter(applications)) if len(applications) == 1 else None

    def _commun(self, scope: Scope) -> bool:
        """Ce chemin appartient-il à la surface hors harness ?

        `PARTIAL` compte autant que `FULL` : un chemin commun appelé avec la
        mauvaise méthode doit s'entendre répondre « pas cette méthode-là », pas
        se faire renvoyer vers un harness qui ne le connaît pas.
        """
        return any(route.matches(scope)[0] is not Match.NONE for route in self.commun.routes)

    def _courant(self, requete: Request) -> str | None:
        """Le harness courant de l'appelant, ou le seul harness servi."""
        if self.comptes is None:
            return self.seul
        qui = self.identification.qui(requete)
        courant = self.comptes.harness_courant(qui.id) if qui is not None else None
        # Un harness chargé mais jamais enregistré au magasin n'a pas d'ACL, donc
        # personne ne l'a « courant ». Le repli sur le seul harness servi garde
        # une installation neuve utilisable avant tout enregistrement.
        return courant or self.seul

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self._commun(scope):
            return await self.commun(scope, receive, send)

        try:
            identifiant = self._courant(Request(scope))
        except HTTPException as err:
            return await self._refus(err.status_code, err.detail, scope, receive, send)

        if identifiant is None:
            # On ne dit pas lesquels : lister les harness servis les rendrait
            # découvrables par qui n'est membre d'aucun, ce que le RFC-004 §7
            # écarte. La liste de *ses* harness se demande à `/profil`.
            return await self._refus(
                409, "aucun harness courant : choisis-en un", scope, receive, send
            )

        application = self.applications.get(identifiant)
        if application is None:
            # Le magasin connaît un harness que le service ne sert pas — un
            # dossier retiré, un déploiement partiel. Le dire est utile : c'est
            # une panne d'exploitation, pas un refus de droit.
            return await self._refus(
                404, f"harness non servi : {identifiant}", scope, receive, send
            )

        return await application(scope, receive, send)

    async def _refus(self, code: int, detail: str, scope, receive, send) -> None:
        await JSONResponse({"detail": detail}, status_code=code)(scope, receive, send)


def creer_tous(
    harness: dict[str, Harness],
    journal: Path,
    comptes: Comptes | None = None,
    entete_identite: str = "",
    portail: Path | None = None,
    secret_chat: str = "",
    passerelle: Passerelle | None = None,
    dossier_harness: Path | None = None,
    exemple: str = "",
) -> Aiguilleur:
    """Monte une application par harness, et l'aiguilleur qui les dessert.

    `dossier_harness` et `exemple` ouvrent la naissance (RFC-006) : un harness
    créé reçoit son application sans redémarrage, sinon il existerait sur disque
    sans que personne puisse l'ouvrir.
    """
    identification = Identification(comptes, entete_identite, secret_chat)

    # Sans schéma ni documentation : ces chemins-là doivent traverser jusqu'à
    # l'application du harness, qui décrit les routes réellement servies.
    commun = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    commun.include_router(routeur_pages())
    chat = Chat.depuis_l_environnement()
    commun.include_router(routeur_comptes(identification, comptes, portail, chat))

    def _remonter(identifiant: str, racine: Path):
        """Recharge un harness du disque et remonte son application.

        Appelé après un scellement : la définition servie suit celle qui vient
        d'être écrite. `aiguilleur` est lu à l'appel, pas à la définition — il
        n'existe pas encore ici, et c'est voulu.
        """
        ne = charger(racine)
        harness[identifiant] = ne
        aiguilleur.applications[identifiant] = _monter(ne)
        return ne

    def _monter(h: Harness):
        return creer_harness(
            h, journal, comptes, identification, passerelle,
            rafraichir=lambda i=h.id, r=h.racine: _remonter(i, r),
        )

    applications = {identifiant: _monter(h) for identifiant, h in sorted(harness.items())}
    aiguilleur = Aiguilleur(applications, commun, identification, comptes)

    def accueillir(ne) -> None:
        """Monter l'application d'un harness qui vient de naître.

        L'aiguilleur cesse d'avoir un `seul` : servir deux harness sans que
        personne ait choisi n'aurait pas de réponse, et le repli mono-harness
        deviendrait un aiguillage au hasard.
        """
        aiguilleur.applications[ne.id] = _monter(ne)
        aiguilleur.seul = (
            next(iter(aiguilleur.applications)) if len(aiguilleur.applications) == 1 else None
        )

    commun.include_router(
        routeur_exploitation(
            identification, harness, journal, comptes, dossier_harness, exemple,
            accueillir, chat,
        )
    )
    return aiguilleur
