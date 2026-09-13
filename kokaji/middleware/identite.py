"""Ce qui ne dépend d'aucun harness — l'identité, les comptes, les pages.

Servir plusieurs harness suppose de savoir **qui parle avant de savoir quel
harness lui répondre** (RFC-005 §5) : le harness courant se lit sur le compte,
donc l'identification précède la résolution. Tant que les deux vivaient dans la
même fermeture, cet ordre était implicite et inexprimable ; il est ici rendu
explicite, et c'est tout ce que cette séparation cherche.

Trois familles se retrouvent de ce côté-ci, et aucune ne pourrait nommer un
harness sans mentir :

- **l'identification** — le jeton, la personne, l'administrateur d'exploitation ;
- **les comptes** — ouvrir et fermer une session, son profil, son mot de passe,
  et consommer une invitation reçue ;
- **les pages** — du HTML et une feuille de style, servis tels quels.

Ce qui porte sur *une œuvre* reste dans `service` : les membres d'un harness,
le transfert de sa propriété, sa définition, ses ha. Ce qui porte sur *le
service entier* vit dans `exploitation` : la santé, et l'administration.
"""

from __future__ import annotations

from pathlib import Path

from ..comptes import (
    ADMINISTRATION,
    ANONYME,
    COMPTE,
    AccesRefuse,
    AclInvalide,
    Comptes,
    IdentiteInconnue,
    PortailIndisponible,
    Utilisateur,
    exiger_au_service,
    inscrire,
)
from ..comptes.chat import Chat, ChatInjoignable
from ..qg import racine_html
from .chat import JetonInvalide, verifier_jeton

try:
    from fastapi import APIRouter, Body, HTTPException, Request
    from fastapi.responses import HTMLResponse, Response
except ModuleNotFoundError as err:  # pragma: no cover - dépend de l'installation
    raise ModuleNotFoundError(
        "la surface HTTP demande l'extra `service` : pip install -e '.[service]'"
    ) from err

__all__ = ["BISCUIT", "ENTETE_CHAT", "Identification", "routeur_comptes", "routeur_pages"]

BISCUIT = "kokaji_session"
# Le nom par défaut de l'en-tête où le chat pose son jeton signé.
ENTETE_CHAT = "X-OpenWebUI-User-Jwt"


class Identification:
    """Qui parle — indépendamment de ce à quoi il parle.

    **La confiance est déclarée, jamais supposée.** Sans `entete_identite`,
    l'en-tête d'un portail est ignoré. Avec, il n'est sûr qu'à deux conditions :
    le service n'est joignable que par le portail, et le portail **écrase** cet
    en-tête au lieu de laisser passer celui du client.

    Un en-tête ne crée jamais de compte : il désigne un compte existant, ou il
    ne vaut rien.
    """

    def __init__(
        self,
        comptes: Comptes | None = None,
        entete_identite: str = "",
        secret_chat: str = "",
        entete_chat: str = ENTETE_CHAT,
    ):
        self.comptes = comptes
        self.entete_identite = entete_identite
        # Le secret partagé avec le chat. Sans lui, aucun jeton n'est même
        # regardé : une identité signée qu'on accepterait sans secret serait
        # une identité déclarative avec une étape de plus.
        self.secret_chat = secret_chat
        self.entete_chat = entete_chat

    def _du_chat(self, requete: Request) -> Utilisateur | None:
        """La personne que le chat annonce, si sa signature tient (RFC-005 §3.3).

        Le chat sait envoyer un JWT HS256 dès qu'un secret est posé. Sans
        secret, on ne lit rien : les en-têtes en clair qu'il envoie alors sont
        déclaratifs, et quiconque atteint le point d'entrée peut les écrire.

        Un jeton valide **désigne** un compte, il n'en crée aucun — même règle
        que pour le portail.
        """
        if not self.secret_chat or self.comptes is None:
            return None
        jeton = (requete.headers.get(self.entete_chat) or "").strip()
        if not jeton:
            return None
        try:
            charge = verifier_jeton(jeton, self.secret_chat)
        except JetonInvalide as err:
            raise HTTPException(status_code=401, detail=f"jeton du chat refusé : {err}") from err
        courriel = str(charge.get("email") or "").strip()
        connu = self.comptes.par_email(courriel) if courriel else None
        if connu is None:
            raise HTTPException(
                status_code=403,
                detail=f"aucun compte Kokaji pour {courriel} — demande une invitation",
            )
        return connu

    def jeton(self, requete: Request) -> str:
        """Le jeton de session, du cookie ou de l'en-tête `Authorization`."""
        entete = requete.headers.get("authorization") or ""
        if entete.lower().startswith("bearer "):
            return entete[7:].strip()
        return requete.cookies.get(BISCUIT, "")

    def qui(self, requete: Request) -> Utilisateur | None:
        """`None` en mode mono-utilisateur, jamais en mode partagé."""
        if self.comptes is None:
            return None
        du_chat = self._du_chat(requete)
        if du_chat is not None:
            return du_chat
        if self.entete_identite:
            annonce = (requete.headers.get(self.entete_identite) or "").strip()
            if annonce:
                connu = self.comptes.par_email(annonce)
                if connu is not None:
                    return connu
                # Le portail connaît quelqu'un que Kokaji ignore. On ne le crée
                # pas : un compte se crée par invitation, jamais par une entête.
                raise HTTPException(
                    status_code=403,
                    detail=f"aucun compte Kokaji pour {annonce} — demande une invitation",
                )
        try:
            return self.comptes.session(self.jeton(requete))
        except IdentiteInconnue as err:
            raise HTTPException(status_code=401, detail=str(err)) from err

    def qualite(self, requete: Request) -> str:
        """Ce que l'appelant **est** au regard du service — RFC-006 §2.

        Ce n'est pas un rôle : on ne l'a pas *sur* quelque chose. C'est ce qui
        permet de peser un geste sans objet, comme créer un harness.

        Sans magasin, la qualité est `anonyme` et non `administration` : il n'y
        a alors ni compte à administrer, ni propriétaire à qui attribuer une
        création. L'absence de magasin ferme ces gestes au lieu de les ouvrir.
        """
        qui = self.qui(requete)
        if self.comptes is None or qui is None:
            return ANONYME
        return ADMINISTRATION if self.comptes.est_admin(qui.id) else COMPTE

    def exiger_de_service(self, requete: Request, geste: str) -> Utilisateur | None:
        """Exige un geste de service, ou lève un 403 qui n'explique rien."""
        try:
            exiger_au_service(geste, self.qualite(requete))
        except AccesRefuse as err:
            raise HTTPException(status_code=403, detail=str(err)) from err
        return self.qui(requete)

    def gerant(self, requete: Request) -> Utilisateur:
        """L'administration **de l'exploitation**, et rien d'autre.

        Elle ne donne aucun accès à la pratique d'autrui : R12.4 vaut pour
        l'admin comme pour tout le monde — un compte qui verrait tout rendrait
        fausse la phrase qui fonde le RFC-004.

        Elle passe par la table des gestes de service : une seule autorité
        décide, et le refus s'écrit au même endroit que les autres.
        """
        return self.exiger_de_service(requete, "administrer")


def routeur_pages() -> APIRouter:
    """Du HTML et une feuille de style. Aucune donnée, donc aucun droit à peser."""
    routeur = APIRouter()

    def page(nom: str) -> str:
        return (racine_html().parent / nom).read_text(encoding="utf-8")

    @routeur.get("/qg/organic-styles.css", summary="La feuille du système de design")
    def qg_styles() -> Response:
        return Response(page("organic-styles.css"), media_type="text/css")

    @routeur.get("/", response_class=HTMLResponse, summary="Le QG, à la racine")
    def racine() -> str:
        """L'interface, dès l'adresse de base. `/qg` reste l'espace des données."""
        return racine_html().read_text(encoding="utf-8")

    @routeur.get("/qg", response_class=HTMLResponse, summary="Le fil d'ariane (§8)")
    def qg() -> str:
        """Le QG lit l'état ; il n'interprète ni ne modifie rien (R8.3)."""
        return racine_html().read_text(encoding="utf-8")

    @routeur.get("/admin", response_class=HTMLResponse, summary="La page d'administration")
    def admin_page() -> str:
        return page("admin.html")

    @routeur.get(
        "/invitation/{jeton}", response_class=HTMLResponse, summary="Créer son compte"
    )
    def invitation_page(jeton: str) -> str:
        return page("invitation.html")

    return routeur


def routeur_comptes(
    identification: Identification,
    comptes: Comptes | None = None,
    portail: Path | None = None,
    chat: Chat | None = None,
) -> APIRouter:
    """Les gestes qui portent sur une personne, jamais sur un harness.

    `portail` — le fichier d'utilisateurs du portail. Quand il est donné,
    consommer une invitation y inscrit aussi la personne : sans quoi elle se
    créerait un compte Kokaji et resterait arrêtée à la porte du domaine.
    """
    routeur = APIRouter()

    # Ces trois-là n'existent qu'avec un magasin. Sans lui, il n'y a personne à
    # authentifier : les déclarer quand même donnerait des portes qui répondent
    # 500 au lieu de ne pas être là.
    if comptes is not None:

        @routeur.post("/session", summary="Ouvrir une session")
        def ouvrir(
            email: str = Body(embed=True), mot_de_passe: str = Body(embed=True)
        ) -> dict:
            try:
                jeton = comptes.ouvrir_session(email, mot_de_passe)
            except IdentiteInconnue as err:
                raise HTTPException(status_code=401, detail=str(err)) from err
            qui = comptes.par_email(email)
            return {"jeton": jeton, "utilisateur": {"id": qui.id, "nom": qui.nom}}

        @routeur.delete("/session", summary="Fermer sa session")
        def fermer(requete: Request) -> dict:
            comptes.fermer_session(identification.jeton(requete))
            return {"ferme": True}

        @routeur.get(
            "/profil", summary="Mon compte et mes harness — le fond de l'onglet Profil"
        )
        def profil(requete: Request) -> dict:
            """Les données du §4. La forme attend le design, elle ne s'invente pas ici."""
            qui = identification.qui(requete)
            return {
                "utilisateur": {"id": qui.id, "nom": qui.nom, "email": qui.email},
                "harness": [
                    {"harness": h, "role": r} for h, r in comptes.harness_de(qui.id)
                ],
            }

    @routeur.get("/invitation/{jeton}/etat", summary="Cette invitation vaut-elle encore ?")
    def invitation_etat(jeton: str) -> dict:
        if comptes is None:
            raise HTTPException(status_code=404, detail="aucun magasin de comptes")
        try:
            return comptes.invitation(jeton)
        except IdentiteInconnue as err:
            raise HTTPException(status_code=404, detail=str(err)) from err

    @routeur.post("/invitation/{jeton}", summary="Consommer l'invitation et créer le compte")
    def invitation_consommer(
        jeton: str, nom: str = Body(embed=True), mot_de_passe: str = Body(embed=True)
    ) -> dict:
        if comptes is None:
            raise HTTPException(status_code=404, detail="aucun magasin de comptes")
        try:
            invite = comptes.consommer(jeton, nom, mot_de_passe)
        except IdentiteInconnue as err:
            raise HTTPException(status_code=404, detail=str(err)) from err
        except AclInvalide as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

        # Le chat est le troisième côté de la même identité. L'y créer **actif**
        # évite qu'il redemande une validation de la décision déjà prise en
        # invitant — c'est ce qui bloquait chaque invité sur une porte de plus.
        au_chat = "non administré"
        if chat is not None:
            try:
                chat.creer(invite.email, invite.nom, mot_de_passe)
                au_chat = "actif"
            except ChatInjoignable as err:
                au_chat = f"non créé : {err}"

        # Une seule identité : le compte doit exister au portail, sinon la
        # personne vient de se créer un compte et va se faire arrêter à la porte.
        if portail is not None:
            try:
                inscrire(portail, email=invite.email, nom=invite.nom, mot_de_passe=mot_de_passe)
            except PortailIndisponible as err:
                # Le compte Kokaji existe déjà : le nier serait pire. On dit ce
                # qui manque, et l'administrateur inscrit à la main.
                return {
                    "id": invite.id,
                    "nom": invite.nom,
                    "email": invite.email,
                    "portail": f"non inscrit au portail : {err}",
                    "chat": au_chat,
                }
        return {
            "id": invite.id, "nom": invite.nom, "email": invite.email,
            "portail": "inscrit", "chat": au_chat,
        }

    @routeur.post("/moi/mot-de-passe", summary="Changer son propre mot de passe")
    def changer_mot_de_passe(requete: Request, nouveau: str = Body(embed=True)) -> dict:
        """Le sien, jamais celui d'un autre : un admin ne réécrit pas un secret
        qui ne lui appartient pas. Pour rouvrir un compte perdu, on invite à
        nouveau."""
        qui = identification.qui(requete)
        if comptes is None or qui is None:
            raise HTTPException(status_code=404, detail="aucun magasin de comptes")
        try:
            comptes.changer_mot_de_passe(qui.id, nouveau)
        except AclInvalide as err:
            raise HTTPException(status_code=400, detail=str(err)) from err
        return {"change": True}

    return routeur
