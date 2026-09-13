"""La surface HTTP du middleware — lecture, et l'autorat (SPECS §7, §12, RFC-004).

Le middleware lit le journal du Dojo et le corpus, et les rend consultables.
Aucune route n'écrit dans un corpus : la veille seule le fait, en tâche de fond,
sans dépendre d'une requête.

Le RFC-004 y ajoute une surface d'écriture **étroite et nommée** : ouvrir une
session, gérer les membres d'un harness, régler la visibilité d'un de ses
propres ha. Rien d'autre. Le §12 de la SPECS a été amendé en conséquence : la
lecture seule porte désormais sur les corpus et l'état, pas sur l'autorat.

**Deux modes, et c'est délibéré.** Sans magasin de comptes, le service tourne
comme avant : un seul praticien, aucune ACL, tout est lisible. Avec un magasin,
l'authentification est exigée et les droits du RFC-004 §3 s'appliquent. Le
premier mode n'est pas une porte dérobée — c'est l'installation mono-utilisateur
qui existait avant ce RFC, et qui n'a personne à isoler de personne.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from ..comptes import (
    AccesRefuse,
    AclInvalide,
    Comptes,
    Utilisateur,
    exiger,
)
from ..comptes.chat import Chat
from ..comptes.modele import PROPRIETAIRE, VISIBILITES
from ..conception import (
    JOURNAL,
    Proposition,
    ScellementRefuse,
    juger,
    sceller,
    versions_prevues,
)
from ..corpus.visibilite import acces, lisible_par, regler_visibilite
from ..forge import ForgeImpossible, TrempeEchouee, forger_harness
from ..hds import Harness, charger_valides
from ..qg import activites, composer, composition, sujets
from .chat import Passerelle, routeur_chat
from .exploitation import routeur_exploitation
from .identite import Identification, routeur_comptes, routeur_pages

try:
    from fastapi import Body, Depends, FastAPI, HTTPException, Request
except ModuleNotFoundError as err:  # pragma: no cover - dépend de l'installation
    raise ModuleNotFoundError(
        "la surface HTTP demande l'extra `service` : pip install -e '.[service]'"
    ) from err

__all__ = ["creer", "creer_harness", "servir"]

# Un corps de requête déclaré une fois : appeler `Body()` dans un défaut
# d'argument construit l'objet à chaque définition de route.
CORPS = Body(embed=True)


def _fiche(dossier: Path) -> dict:
    """Le frontmatter d'un ha, sans son corps."""
    texte = (dossier / "fiche.md").read_text(encoding="utf-8")
    if not texte.startswith("---"):
        return {}
    _, entete, _ = texte.split("---", 2)
    donnees = yaml.safe_load(entete) or {}
    return donnees if isinstance(donnees, dict) else {}


def _lire_jsonl(fichier: Path) -> list[dict]:
    if not fichier.is_file():
        return []
    return [
        json.loads(ligne)
        for ligne in fichier.read_text(encoding="utf-8").splitlines()
        if ligne.strip()
    ]


def creer(
    harness: Harness,
    journal: Path,
    comptes: Comptes | None = None,
    entete_identite: str = "",
    portail: Path | None = None,
    secret_chat: str = "",
    passerelle: Passerelle | None = None,
) -> FastAPI:
    """L'application complète d'**un** harness — la forme historique.

    `entete_identite` — le nom d'un en-tête portant l'email de la personne.

    Un portail placé devant le service (Authelia, oauth2-proxy…) authentifie déjà
    et pose l'identité dans un en-tête. La lui faire redemander par Kokaji
    imposerait deux connexions pour une seule porte.

    **La confiance est déclarée, jamais supposée.** Sans ce réglage, l'en-tête
    est ignoré. Avec, il n'est sûr qu'à deux conditions : le service n'est
    joignable que par le portail, et le portail **écrase** cet en-tête au lieu de
    laisser passer celui du client. Les deux tiennent ici — le conteneur n'expose
    rien, et `authResponseHeaders` réécrit `Remote-*`.

    Un en-tête ne crée jamais de compte : il désigne un compte existant, ou il
    ne vaut rien.

    `portail` — le fichier d'utilisateurs du portail. Quand il est donné,
    consommer une invitation y inscrit aussi la personne : sans quoi elle se
    créerait un compte Kokaji et resterait arrêtée à la porte du domaine.
    """
    identification = Identification(comptes, entete_identite, secret_chat)
    app = creer_harness(harness, journal, comptes, identification, passerelle)
    app.include_router(routeur_pages())
    chat = Chat.depuis_l_environnement()
    app.include_router(routeur_comptes(identification, comptes, portail, chat))
    app.include_router(
        routeur_exploitation(
            identification, {harness.id: harness}, journal, comptes, chat=chat
        )
    )
    return app


def creer_harness(
    harness: Harness,
    journal: Path,
    comptes: Comptes | None,
    identification: Identification,
    passerelle: Passerelle | None = None,
    rafraichir=None,
) -> FastAPI:
    """Les routes d'un harness, et rien d'autre — RFC-005 §5.

    Toute route déclarée ici nomme un harness. C'est ce qui permet à
    l'aiguilleur d'en monter une par harness : une route ne peut pas voir le
    harness d'une autre application, l'isolation est tenue par la portée et non
    par la vigilance.
    """
    app = FastAPI(
        title=f"Kokaji — middleware ({harness.id})",
        description=(
            "Lecture sur le corpus et l'état ; écriture limitée à l'autorat (RFC-004)."
        ),
        version=harness.version,
    )
    # La façade du chat vit dans l'application du harness : sa liste de modèles
    # *est* la liste des kata de ce harness (RFC-005 §3.2).
    app.include_router(
        routeur_chat(
            harness,
            passerelle,
            # Lu à chaque requête et non au montage : archiver doit prendre effet
            # sans redémarrage, comme naître.
            archive=(lambda: comptes.archive_le(harness.id) is not None)
            if comptes is not None
            else None,
        )
    )

    def role_de(qui: Utilisateur | None) -> str:
        """Le rôle sur *ce* harness. En mode mono-utilisateur, propriétaire."""
        if comptes is None or qui is None:
            return PROPRIETAIRE
        return comptes.role(harness.id, qui.id)

    def membre(requete: Request) -> tuple[Utilisateur | None, str]:
        """Exige au minimum le droit de lire la définition de ce harness.

        C'est le sabotage n°2 du §8 : un utilisateur non membre qui tente de
        lire la définition doit se voir refuser, pas servir.
        """
        qui = identification.qui(requete)
        role = role_de(qui)
        try:
            exiger("lire", role, harness.id)
        except AccesRefuse as err:
            raise HTTPException(status_code=403, detail=str(err)) from err
        return qui, role

    def dossier_du_ha(identifiant: str) -> Path:
        trouves = sorted(harness.corpus.glob(f"{identifiant}-*"))
        if not trouves:
            raise HTTPException(status_code=404, detail=f"ha inconnu : {identifiant}")
        return trouves[0]

    def ha_lisible(identifiant: str, qui: Utilisateur | None, role: str) -> Path:
        """Le dossier d'un ha, si cette personne a le droit de le lire.

        Sabotage n°3, le plus important du RFC : le propriétaire du harness
        n'obtient rien ici sur un ha non versé de son contributeur. On répond
        403 et non 404 — le ha existe, et le nier serait mentir ; ce qui est
        refusé, c'est de le lire.
        """
        dossier = dossier_du_ha(identifiant)
        if comptes is None:
            return dossier
        if not lisible_par(dossier, qui.id if qui else "", role):
            raise HTTPException(status_code=403, detail="ha non versé : lecture refusée")
        return dossier

    @app.get("/ha", summary="La liste des ha capturés")
    def liste_ha(qui_role: tuple = Depends(membre)) -> list[dict]:
        """Ce que *cette* personne peut voir : les siens, plus les ha versés.

        La liste ne dit pas non plus qu'un ha existe et se tait : un ha qu'on
        n'a pas le droit de lire n'y figure pas du tout. Compter les silences
        renseignerait déjà sur la pratique d'autrui.
        """
        qui, role = qui_role
        ha = []
        for dossier in sorted(harness.corpus.glob("CAS-*")):
            if comptes is not None and not lisible_par(dossier, qui.id if qui else "", role):
                continue
            fiche = _fiche(dossier)
            ha.append(
                {
                    "id": dossier.name.split("-", 2)[0] + "-" + dossier.name.split("-")[1],
                    "dossier": dossier.name,
                    "kata": fiche.get("kata"),
                    "cible": fiche.get("cible"),
                    "statut": fiche.get("statut"),
                    "verdict": fiche.get("verdict"),
                    "praticien": fiche.get("praticien") or "",
                    "visibilite": acces(dossier).visibilite,
                    "carre": _carre_lu(dossier),
                }
            )
        return ha

    @app.get("/ha/{identifiant}", summary="La fiche d'un ha")
    def un_ha(identifiant: str, qui_role: tuple = Depends(membre)) -> dict:
        dossier = ha_lisible(identifiant, *qui_role)
        return {
            "dossier": dossier.name,
            "fiche": _fiche(dossier),
            "carre": _carre_lu(dossier),
            "blocs_etat": len(_lire_jsonl(dossier / "etats.jsonl")),
        }

    @app.get("/ha/{identifiant}/transcript", summary="Le transcript d'un ha")
    def transcript(identifiant: str, qui_role: tuple = Depends(membre)) -> dict:
        dossier = ha_lisible(identifiant, *qui_role)
        fichier = dossier / "transcript.md"
        if not fichier.is_file():
            raise HTTPException(status_code=404, detail="transcript absent")
        return {"dossier": dossier.name, "transcript": fichier.read_text(encoding="utf-8")}

    @app.get("/ha/{identifiant}/etat", summary="Les blocs d'état, horodatés")
    def etat(identifiant: str, qui_role: tuple = Depends(membre)) -> list[dict]:
        return _lire_jsonl(ha_lisible(identifiant, *qui_role) / "etats.jsonl")

    @app.post("/ha/{identifiant}/visibilite", summary="Verser un ha aux co-auteurs, ou le reprendre")
    def visibilite(
        identifiant: str,
        valeur: str = Body(embed=True),
        qui_role: tuple = Depends(membre),
    ) -> dict:
        """RFC-004 §5 — « elle se verse, elle ne se prend pas ».

        Seul le praticien décide, et le geste est révocable. Reprendre ne défait
        pas les agrégats déjà calculés : les checks tournent sur tous les ha, ce
        qu'ils exposent aux co-auteurs est agrégé.
        """
        qui, _ = qui_role
        if valeur not in VISIBILITES:
            raise HTTPException(
                status_code=400, detail=f"visibilité hors liste (attendu : {', '.join(VISIBILITES)})"
            )
        dossier = dossier_du_ha(identifiant)
        try:
            regler_visibilite(dossier, valeur, par=qui.id if qui else "")
        except PermissionError as err:
            raise HTTPException(status_code=403, detail=str(err)) from err
        return {"dossier": dossier.name, "visibilite": valeur}

    @app.get("/sujet/{sujet}/etat", summary="Le dernier état connu d'un sujet")
    def etat_du_sujet(sujet: str) -> dict:
        """R7.4 — `get_state(sujet)`. Le sujet est déclaré par les blocs eux-mêmes."""
        dernier = None
        for dossier in sorted(harness.corpus.glob("CAS-*")):
            for releve in _lire_jsonl(dossier / "etats.jsonl"):
                if (releve.get("etat") or {}).get("sujet") != sujet:
                    continue
                if dernier is None or (releve.get("horodatage") or "") >= (
                    dernier.get("horodatage") or ""
                ):
                    dernier = {**releve, "ha": dossier.name}
        if dernier is None:
            raise HTTPException(status_code=404, detail=f"aucun état pour le sujet {sujet!r}")
        return dernier

    @app.get("/definition", summary="Ce que le harness déclare — réservé à ses co-auteurs")
    def definition(qui_role: tuple = Depends(membre)) -> dict:
        """La définition d'un harness appartient à ses co-auteurs (RFC-004 §2).

        Les assets héritent de l'ACL du harness : pas d'ACL par asset en v1. Un
        non-membre se voit donc refuser l'ensemble, template compris.
        """
        return {
            "harness": harness.id,
            "nom": harness.nom,
            "version": harness.version,
            "kata": [
                {
                    "id": k.id,
                    "nom": k.nom,
                    "amont": list(k.amont),
                    "herite": list(k.herite),
                    "produit": [{r: s} for r, s in k.produit],
                    "emet_options": k.emet_options,
                }
                for k in harness.kata
            ],
            "cibles": [c.id for c in harness.cibles],
        }

    @app.get("/chaine", summary="La topologie déclarée par le manifest")
    def chaine(qui_role: tuple = Depends(membre)) -> dict:
        """Ce que le QG rendra (§8). Le middleware la transporte, ne l'interprète pas."""
        return {
            "noeuds": [{"id": n.id, "type": n.type, "nom": n.nom} for n in harness.chaine.noeuds],
            "aretes": [{"de": a.de, "vers": a.vers, "label": a.label} for a in harness.chaine.aretes],
        }

    def _corpus(nom: str | None) -> str:
        connus = [c.nom for c in harness.corpus_nommes]
        choisi = nom or connus[0]
        if choisi not in connus:
            raise HTTPException(
                status_code=404,
                detail=f"corpus inconnu : {choisi!r} (connus : {', '.join(connus)})",
            )
        return choisi

    def filtre(qui, role):
        """Le prédicat de lisibilité que le QG applique ha par ha (RFC-004 §5)."""
        if comptes is None:
            return None
        return lambda dossier: lisible_par(dossier, qui.id if qui else "", role)

    @app.get("/qg/corpus", summary="Les corpus déclarés par le harness")
    def qg_corpus(qui_role: tuple = Depends(membre)) -> list[dict]:
        """Le harness peut en déclarer plusieurs : les cas vécus, les essais."""
        return [
            {
                "nom": c.nom,
                "cles": list(c.cles),
                "sujets": len(sujets(harness, journal, c.nom, filtre(*qui_role))),
            }
            for c in harness.corpus_nommes
        ]

    @app.get("/qg/profil", summary="Le module Profil — activités accessibles et harness possédés")
    def qg_profil(corpus: str | None = None, qui_role: tuple = Depends(membre)) -> dict:
        """Ce que la personne connectée peut observer, et ce qu'elle possède.

        Sans magasin de comptes il n'y a personne à nommer : l'identité est
        `null` plutôt qu'inventée, et la vue le dit. Le rôle, lui, reste
        connaissable — c'est celui qu'on a sur ce harness.
        """
        qui, role = qui_role
        vise = _corpus(corpus)
        lisible = filtre(qui, role)
        actives = activites(harness, journal, vise, lisible)

        return {
            "utilisateur": (
                {"nom": qui.nom, "email": qui.email, "initiale": qui.nom[:1].upper()}
                if qui
                else None
            ),
            "corpus": vise,
            "sessions": sum(a["sessions"] for a in actives),
            "activites": [
                {
                    "sujet": a["sujet"],
                    "harness": a["harness"],
                    "version": a["version"],
                    "sessions": a["sessions"],
                    "derniere": a["derniere"],
                    # Le rôle vient de l'ACL du harness, jamais du corpus : on
                    # peut observer sans pratiquer, et pratiquer sans posséder.
                    "role": "praticien" if role == PROPRIETAIRE else "observateur",
                }
                for a in actives
            ],
            "harness": [
                {
                    "nom": harness.nom,
                    "version": harness.version,
                    "noeuds": len(harness.chaine.noeuds),
                    "composition": composition(harness),
                    "sujets": len(actives),
                    "role": role,
                }
            ],
        }

    @app.get("/qg/usage", summary="Ce que la pratique a coûté, et ce qu'elle a rendu")
    def qg_usage(corpus: str | None = None, qui_role: tuple = Depends(membre)) -> dict:
        """Le relevé du harness et de ses kata — RFC-002 §6.3 et SPECS §5.6.

        Il se lit **dans le module design**, à côté de ce que chaque kata
        promet : voir ce qu'une étape coûte en modifiant son contrat change la
        conversation, alors que le même chiffre au terminal ne la change pas.

        La dépense est celle du corpus entier, pas de ce que l'appelant peut
        lire : un agrégat ne révèle aucune pratique (RFC-004 §5), et le
        restreindre le rendrait faux sans rien protéger.
        """
        from ..usage import mesurer

        vise = _corpus(corpus)
        declare = harness.corpus_par_nom(vise)
        releve = mesurer(harness, declare.chemin if declare else None)

        def dire(d) -> dict:
            return {
                "ha": d.ha, "tours": d.tours, "blocs": d.blocs,
                "entree": d.entree, "sortie": d.sortie, "jetons": d.jetons,
                "par_tour": round(d.par_tour), "par_bloc": round(d.par_bloc) if d.blocs else None,
                "conformes": d.conformes, "juges": d.juges, "carres": dict(d.carres),
            }

        return {
            "corpus": vise,
            "tout": dire(releve.tout),
            "par_kata": {cle: dire(d) for cle, d in releve.par_kata.items()},
            "par_cible": {cle: dire(d) for cle, d in releve.par_cible.items()},
            "sans_scores": releve.sans_scores,
            # Incluse dans `tout`, jamais retranchée en silence : un total
            # corrigé sans le dire ne se relit dans aucune fiche.
            "doubles": dire(releve.doubles),
        }

    @app.get("/qg/sujets", summary="Les sujets que les blocs d'état déclarent")
    def qg_sujets(corpus: str | None = None, qui_role: tuple = Depends(membre)) -> list[str]:
        return sujets(harness, journal, _corpus(corpus), filtre(*qui_role))

    @app.get("/qg/donnees", summary="La vue d'un sujet — chaîne, état, possibles")
    def qg_donnees(
        sujet: str | None = None,
        corpus: str | None = None,
        qui_role: tuple = Depends(membre),
    ) -> dict:
        vise = _corpus(corpus)
        lisible = filtre(*qui_role)
        connus = sujets(harness, journal, vise, lisible)
        if not connus:
            raise HTTPException(status_code=404, detail=f"aucun sujet observé dans {vise!r}")
        choisi = sujet or connus[0]
        if choisi not in connus:
            raise HTTPException(status_code=404, detail=f"sujet inconnu : {choisi!r}")
        donnees = composer(harness, choisi, journal, vise, lisible).as_dict(harness)
        donnees["corpus"] = vise
        return donnees

    # --- l'autorat (RFC-004 §2, §3) ---------------------------------------
    #
    # Ces routes n'existent qu'avec un magasin de comptes. Sans lui, il n'y a
    # personne à authentifier ni membre à gérer : les déclarer quand même
    # donnerait des portes qui répondent 500 au lieu de ne pas être là.

    if comptes is not None:

        def _acl_ou_404():
            acl = comptes.acl(harness.id)
            if acl is None:
                raise HTTPException(status_code=404, detail=f"harness non enregistré : {harness.id}")
            return acl

        @app.get("/membres", summary="Les co-auteurs de ce harness")
        def membres(qui_role: tuple = Depends(membre)) -> dict:
            acl = _acl_ou_404()
            return {"harness": acl.harness_id, **_membres(acl)}

        def _gerant(requete: Request, geste: str) -> Utilisateur:
            """Exige le geste réservé au propriétaire. Sabotage n°1 du §8."""
            qui = identification.qui(requete)
            try:
                exiger(geste, role_de(qui), harness.id)
            except AccesRefuse as err:
                raise HTTPException(status_code=403, detail=str(err)) from err
            return qui

        @app.get("/membres/candidats", summary="Qui l'on peut encore ajouter ici")
        def candidats(requete: Request) -> dict:
            """La liste que la page déroule, réservée à qui peut ajouter.

            **Elle nomme des comptes du service à quelqu'un qui n'est pas
            administrateur**, et c'est le prix d'un choix dans une liste plutôt
            qu'une adresse tapée de mémoire. Ce qui en sort est le strict
            nécessaire pour désigner quelqu'un — nom, adresse, identifiant — et
            rien de sa pratique ni de ses harness (RFC-004 §5, R12.4).

            Le geste est le même que celui d'ajouter : qui n'a pas le droit
            d'ajouter n'a pas à savoir qui existe.
            """
            _gerant(requete, "gerer_membres")
            acl = _acl_ou_404()
            deja = {acl.proprietaire, *acl.contributeurs}
            return {
                "candidats": [
                    {"id": c["id"], "nom": c["nom"], "email": c["email"]}
                    for c in comptes.utilisateurs()
                    if c["id"] not in deja
                ]
            }

        @app.post("/membres", summary="Ajouter un contributeur, par email")
        def ajouter(requete: Request, email: str = Body(embed=True)) -> dict:
            _gerant(requete, "gerer_membres")
            invite = comptes.par_email(email)
            if invite is None:
                raise HTTPException(status_code=404, detail="aucun compte pour cet email")
            try:
                acl = comptes.ajouter_contributeur(harness.id, invite.id)
            except AclInvalide as err:
                raise HTTPException(status_code=409, detail=str(err)) from err
            return {"harness": acl.harness_id, **_membres(acl)}

        @app.delete("/membres/{utilisateur_id}", summary="Retirer un contributeur")
        def retirer(requete: Request, utilisateur_id: str) -> dict:
            _gerant(requete, "gerer_membres")
            try:
                acl = comptes.retirer_contributeur(harness.id, utilisateur_id)
            except AclInvalide as err:
                # Retirer le propriétaire est refusé par le modèle lui-même :
                # c'est un conflit d'état, pas un défaut de droit.
                raise HTTPException(status_code=409, detail=str(err)) from err
            return {"harness": acl.harness_id, **_membres(acl)}

        @app.post("/transfert", summary="Transférer la propriété du harness")
        def transferer(
            requete: Request,
            vers: str = Body(embed=True),
            garder_ancien: bool = Body(default=True, embed=True),
        ) -> dict:
            _gerant(requete, "transferer")
            try:
                acl = comptes.transferer(harness.id, vers, garder_ancien)
            except AclInvalide as err:
                raise HTTPException(status_code=409, detail=str(err)) from err
            return {
                "harness": acl.harness_id,
                "proprietaire": acl.proprietaire,
                "contributeurs": list(acl.contributeurs),
            }

    # --- la conception (module 3 du design, RFC-004 §3) ----------------------
    #
    # La seule surface d'écriture sur une *définition*. Elle était volontairement
    # absente tant que la vue n'existait pas : figer un contrat d'échange qu'un
    # design contredirait ensuite n'aurait servi personne. Le design est versé,
    # la voici.

    def _racine() -> Path:
        return harness.template.parent

    def _dernier_scellement() -> dict | None:
        fichier = _racine() / JOURNAL
        if not fichier.is_file():
            return None
        lignes = [l for l in fichier.read_text(encoding="utf-8").splitlines() if l.strip()]
        return json.loads(lignes[-1]) if lignes else None

    @app.get("/conception", summary="La définition, en forme éditable")
    def conception(qui_role: tuple = Depends(membre)) -> dict:
        """Ce que le module 3 met à l'écran. Lecture seule : éditer se propose."""
        acl = comptes.acl(harness.id) if comptes else None
        return {
            "harness": {
                "id": harness.id,
                "nom": harness.nom,
                "version": harness.version,
                # La page en a besoin pour offrir le bon geste d'ajout : une
                # étape adoptée est un texte, une étape native une source.
                "exogene": harness.exogene,
                "dernier_scellement": _dernier_scellement(),
            },
            "statuts_champ": list(harness.etat.statuts_champ),
            "kata": [
                {
                    "id": k.id,
                    "nom": k.nom,
                    "livrable": k.livrable,
                    "amont": list(k.amont),
                    "herite": [
                        {"champ": r, "minimum": k.exigences.get(r, "")} for r in k.herite
                    ],
                    "produit": [{"champ": r, "statut": s} for r, s in k.produit],
                    "emet_options": k.emet_options,
                }
                for k in harness.kata
            ],
            "chaine": {
                "noeuds": [{"id": n.id, "type": n.type, "nom": n.nom} for n in harness.chaine.noeuds],
                "aretes": [{"de": a.de, "vers": a.vers, "label": a.label} for a in harness.chaine.aretes],
            },
            "trempe": {
                "vocabulaire_interdit": list(harness.trempe.vocabulaire_interdit),
                "checks_session": [dict(c) for c in harness.trempe.checks_session],
                "justesse": {
                    "defaut": harness.trempe.justesse_defaut,
                    "par_kata": dict(harness.trempe.justesse_par_kata),
                },
                "grille_judge": [
                    {"id": c.id, "question": c.question, "echelle": c.echelle}
                    for c in harness.trempe.grille_judge
                ],
            },
            "membres": _membres(acl),
        }

    def _qui(utilisateur_id: str) -> dict:
        """Un membre, tel qu'on peut le nommer.

        L'identifiant seul est illisible : la page affichait des UUID là où il
        fallait reconnaître quelqu'un. Le nom est ce qu'on lit, l'identifiant
        reste ce qu'on envoie — et l'email ce qui distingue deux homonymes.
        Un compte disparu se dit plutôt que de laisser un blanc.
        """
        connu = comptes.utilisateur(utilisateur_id) if comptes is not None else None
        if connu is None:
            return {"id": utilisateur_id, "nom": "compte inconnu", "email": ""}
        return {"id": connu.id, "nom": connu.nom, "email": connu.email}

    def _membres(acl) -> dict | None:
        if acl is None:
            return None
        return {
            "proprietaire": _qui(acl.proprietaire),
            "contributeurs": [_qui(c) for c in acl.contributeurs],
        }

    def _proposition(brut: dict):
        try:
            return Proposition.depuis(brut or {})
        except (TypeError, ValueError) as err:
            raise HTTPException(status_code=400, detail=str(err)) from err

    @app.post("/conception/epreuve", summary="Éprouver une proposition — rien n'est écrit")
    def epreuve(requete: Request, proposition: dict = CORPS) -> dict:
        """L'essai à blanc : la trempe elle-même, sur une copie.

        Ce n'est pas un contrôle de formulaire. La proposition est appliquée à
        une copie du harness, qui est chargée, forgée et trempée pour de vrai.
        """
        qui = identification.qui(requete)
        try:
            exiger("editer", role_de(qui), harness.id)
        except AccesRefuse as err:
            raise HTTPException(status_code=403, detail=str(err)) from err

        verdict = juger(_racine(), _proposition(proposition))
        return {
            "tient": verdict.tient,
            "fautes": list(verdict.fautes),
            "anomalies": list(verdict.anomalies),
            "touche_contrat": verdict.touche_contrat,
            "kata_touches": list(verdict.kata_touches),
            "changements": [
                {
                    "ou": c.ou,
                    "avant": c.avant,
                    "apres": c.apres,
                    "touche_contrat": c.touche_contrat,
                }
                for c in verdict.changements
            ],
            "versions": versions_prevues(_racine(), verdict),
        }

    @app.post("/conception/scellement", summary="Sceller — versionné, signé, journalisé")
    def scellement(
        requete: Request,
        proposition: dict = CORPS,
        auteur: str = Body(embed=True),
        motif: str = Body(default="", embed=True),
    ) -> dict:
        qui = identification.qui(requete)
        try:
            exiger("sceller", role_de(qui), harness.id)
        except AccesRefuse as err:
            raise HTTPException(status_code=403, detail=str(err)) from err

        try:
            trace = sceller(_racine(), _proposition(proposition), auteur=auteur, motif=motif)
        except ScellementRefuse as err:
            # 409 et non 400 : la proposition est bien formée, c'est l'état du
            # harness qui la refuse.
            raise HTTPException(status_code=409, detail=str(err)) from err
        reponse = {
            "auteur": trace.auteur,
            "motif": trace.motif,
            "le": trace.quand,
            "versions": trace.versions,
            "changements": list(trace.changements),
            "coupes": _forger_apres_scellement(),
            "passerelle": _publier_a_la_passerelle(),
        }
        # La définition servie doit suivre celle du disque : sans ce remontage,
        # le module design rechargeait… l'instantané du démarrage, et un
        # scellement parfaitement écrit se lisait comme jamais persisté. Le
        # premier scellement de contrats réels l'a montré — les précédents
        # étaient des arrêts sans changement, où l'ancien et le neuf se
        # confondent.
        if rafraichir is not None:
            rafraichir()
        return reponse

    def _publier_a_la_passerelle() -> dict:
        """Déclare à la passerelle ce que ce harness sert — NOTE-0016.

        Forger ne suffisait pas : la passerelle refusait un harness neuf parce
        que ses deux registres l'ignoraient — celui qui **route** et celui qui
        **autorise**. Ils étaient dérivables, mais rien ne les publiait, si bien
        qu'un harness créé par quelqu'un restait inutilisable jusqu'à ce qu'un
        administrateur lance une commande.

        Comme la forge : cela **suit** le scellement et ne le conditionne pas.
        Un échec se dit, il n'annule rien.
        """
        import yaml

        from ..passerelle import (
            PasserelleInjoignable,
            entrees_de_la_passerelle,
            modeles_virtuels,
            publier_autorisation,
            publier_modeles,
        )

        base = os.environ.get("KOKAJI_PASSERELLE_URL") or ""
        admin = os.environ.get("LITELLM_MASTER_KEY") or ""
        cle = os.environ.get("KOKAJI_PASSERELLE_CLE") or ""
        moteurs_chemin = os.environ.get("KOKAJI_MOTEURS") or ""
        if not (base and admin and cle and moteurs_chemin):
            return {"publie": False, "motif": "passerelle non administrable depuis ici"}

        try:
            frais = charger_valides(_racine())[0]
            if not frais:
                return {"publie": False, "motif": "le harness scellé ne se recharge pas"}
            ne = next(iter(frais.values()))
            moteurs = yaml.safe_load(Path(moteurs_chemin).read_text(encoding="utf-8")) or {}
            nus = tuple(
                m.strip()
                for m in (os.environ.get("KOKAJI_MODELES_NUS") or "").split(",")
                if m.strip()
            )
            ajoutes = publier_modeles(base, admin, entrees_de_la_passerelle({ne.id: ne}, moteurs))
            # L'autorisation porte sur **tout** ce que la clé doit pouvoir
            # appeler : la republier pour un seul harness effacerait les autres.
            tous = charger_valides(Path(os.environ.get("KOKAJI_HARNESS") or "/harness"))[0]
            attendus = tuple(
                nom for _, h in sorted(tous.items()) for nom in modeles_virtuels(h)
            ) + nus
            publier_autorisation(base, admin, cle, attendus)
        except (PasserelleInjoignable, OSError) as err:
            return {"publie": False, "motif": f"{type(err).__name__} : {err}"}
        return {"publie": True, "ajoutes": list(ajoutes), "autorises": len(attendus)}

    def _forger_apres_scellement() -> dict:
        """Forge les coupes du harness qu'on vient de sceller — RFC-006 §4 amendé.

        **La forge suit le scellement, elle ne le conditionne pas.** Sceller
        arrête une définition ; forger produit ce qui la rend appelable. Une
        forge qui échoue n'annule donc rien : le scellement a eu lieu, il est au
        journal, et l'échec se dit au lieu de se propager.

        Le harness est **rechargé depuis le disque** : le scellement vient d'y
        écrire de nouvelles versions, et forger l'objet gardé en mémoire
        produirait des coupes estampillées de l'ancienne.
        """
        sortie = os.environ.get("KOKAJI_COUPES") or ""
        if not sortie:
            return {"forgees": False, "motif": "aucune sortie de coupes configurée"}
        try:
            frais = charger_valides(_racine())[0]
            if not frais:
                return {"forgees": False, "motif": "le harness scellé ne se recharge pas"}
            resultat = forger_harness(next(iter(frais.values())), sortie=Path(sortie), trempe=True)
        except (ForgeImpossible, TrempeEchouee, OSError) as err:
            return {"forgees": False, "motif": f"{type(err).__name__} : {err}"}
        return {
            "forgees": True,
            "combien": len(resultat.coupes),
            # Ce qui a bougé, nommé : « rien n'a changé » après un scellement est
            # une information, et la taire laisserait croire à une forge muette.
            "modifiees": sorted(f"{c.cible}/{c.kata}" for c in resultat.modifiees),
        }

    # --- l'administration de l'exploitation ---------------------------------
    #
    return app


def _carre_lu(dossier: Path) -> str | None:
    fichier = dossier / "carre.md"
    if not fichier.is_file():
        return None
    premiere = fichier.read_text(encoding="utf-8").splitlines()[0]
    return premiere.replace("# Carré de naturalité — ", "").strip() or None


def servir(
    chemin_harness: Path,
    journal: Path,
    hote: str,
    port: int,
    comptes: Path | None = None,
    entete_identite: str = "",
    portail: Path | None = None,
) -> int:  # pragma: no cover
    """Sert tous les harness du dossier — un seul si le dossier en est un.

    L'aiguilleur est monté même pour un harness unique : deux chemins de code
    pour la même surface se mettraient à diverger, et c'est le chemin rare qui
    pourrirait. Avec un seul harness, il aiguille vers lui sans rien demander.
    """
    import sys

    import uvicorn

    from .aiguilleur import creer_tous

    # Un harness cassé ne met pas les autres à terre : il est signalé et
    # écarté. Refuser de démarrer pour un seul manifest fautif priverait tous
    # les autres de service — c'est le motif de NOTE-0009.
    harness, refuses = charger_valides(chemin_harness)
    for nom, motif in refuses:
        print(f"✗ {nom} — {motif}", file=sys.stderr)
    if not harness:
        print("✗ aucun harness exploitable", file=sys.stderr)
        return 1

    magasin = Comptes(comptes) if comptes else None
    uvicorn.run(
        creer_tous(
            harness, journal, magasin, entete_identite, portail,
            # La confiance se déclare : sans secret, aucun jeton du chat n'est
            # même regardé (RFC-005 §3.3).
            secret_chat=os.environ.get("KOKAJI_CHAT_SECRET") or "",
            passerelle=Passerelle.depuis_l_environnement(),
            # Les harness naissent là où on les sert (RFC-006). Un dossier qui
            # *est* un harness ne peut pas en accueillir : on ne fait naître que
            # dans un dossier qui en contient.
            dossier_harness=(
                Path(chemin_harness)
                if not (Path(chemin_harness) / "harness.yaml").is_file()
                else None
            ),
            exemple=os.environ.get("KOKAJI_HARNESS_EXEMPLE") or "",
        ),
        host=hote,
        port=port,
        log_level="info",
    )
    return 0
