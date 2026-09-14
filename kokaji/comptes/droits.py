"""La matrice des droits — RFC-004 §3.

La décision scellée du RFC est que **les co-auteurs sont pleins** : un
contributeur édite, forge, pratique, et scelle des versions — y compris
majeures, y compris un f♯. Ce qui lui reste fermé tient en trois gestes, et
tous trois portent sur le harness comme *possession*, non comme *œuvre* :
gérer les membres, transférer, supprimer.

« Chaque scellement porte le nom de son auteur (traçabilité, pas goulot) » :
c'est la discipline qui remplace le verrou. Le droit de sceller n'est donc pas
un oubli de garde-fou, c'est le garde-fou déplacé.

Une part de cette matrice décrit des gestes que Kokaji **ne sait pas encore
faire** : éditer une définition et sceller une version appartiennent au mode
admin, qui n'est pas construit. Ils sont déclarés ici quand même. Le contrat
précède le geste ; le jour où le geste existera, il n'aura qu'à demander.
"""

from __future__ import annotations

from .modele import CONTRIBUTEUR, ETRANGER, PROPRIETAIRE

__all__ = [
    "ADMINISTRATION",
    "ANONYME",
    "COMPTE",
    "GESTES",
    "GESTES_DE_SERVICE",
    "QUALITES",
    "AccesRefuse",
    "exiger",
    "exiger_au_service",
    "peut",
    "peut_au_service",
]

# Le tableau du §3, tel quel. Un geste absent de cette table n'est pas un geste
# permissif par défaut : `peut` refuse ce qu'il ne connaît pas.
GESTES: dict[str, tuple[str, ...]] = {
    "lire": (PROPRIETAIRE, CONTRIBUTEUR),
    "editer": (PROPRIETAIRE, CONTRIBUTEUR),
    "forger": (PROPRIETAIRE, CONTRIBUTEUR),
    "tremper": (PROPRIETAIRE, CONTRIBUTEUR),
    "pratiquer": (PROPRIETAIRE, CONTRIBUTEUR),
    "sceller": (PROPRIETAIRE, CONTRIBUTEUR),
    "gerer_membres": (PROPRIETAIRE,),
    # Archiver remplace supprimer partout où l'on aurait voulu supprimer
    # (RFC-006 §5) : même réserve au propriétaire, puisqu'il porte sur la
    # possession et non sur l'œuvre.
    "archiver": (PROPRIETAIRE,),
    "transferer": (PROPRIETAIRE,),
    "supprimer": (PROPRIETAIRE,),
    # RFC-012 : enregistrer ou désenregistrer un dépôt nu porte sur la
    # possession ; pousser et tirer sont des gestes d'œuvre, de co-auteur.
    "enregistrer": (PROPRIETAIRE,),
    "pousser": (PROPRIETAIRE, CONTRIBUTEUR),
}


# --- les gestes de service (RFC-006 §2) ---------------------------------
#
# `creer` est le premier geste **sans objet**. Toute la table ci-dessus demande
# « quel est ton rôle sur ce harness » ; créer demande « as-tu le droit d'en
# faire un », ce qui ne se répond pas par un rôle puisqu'il n'y a pas encore de
# harness. Un geste sans objet ne peut donc pas emprunter le rôle d'un autre :
# les deux tables ne se connaissent pas, et c'est délibéré.
#
# La qualité d'un appelant, du plus faible au plus fort. Ce n'est pas un rôle :
# on ne l'a pas *sur* quelque chose, on l'est.
ANONYME = "anonyme"
COMPTE = "compte"
ADMINISTRATION = "administration"
QUALITES = (ANONYME, COMPTE, ADMINISTRATION)

# Geste → qualité minimale qui l'autorise.
GESTES_DE_SERVICE: dict[str, str] = {
    "creer": COMPTE,
    "administrer": ADMINISTRATION,
}


class AccesRefuse(Exception):
    """Un geste tenté sans le rôle qui l'autorise. Le service en fait un 403."""


def peut(geste: str, role: str) -> bool:
    """Ce rôle peut-il ce geste ?

    Refuse par défaut : un geste inconnu n'est pas un geste libre. C'est ce qui
    fait qu'ajouter un verbe à Kokaji sans l'inscrire ici le ferme au lieu de
    l'ouvrir à tout le monde.
    """
    if role == ETRANGER:
        return False
    return role in GESTES.get(geste, ())


def exiger(geste: str, role: str, quoi: str = "") -> None:
    """Laisse passer, ou lève. Le refus dit ce qui manquait, jamais pourquoi.

    Un refus qui explique « tu n'es pas propriétaire de ce harness » confirme
    au passage que le harness existe. On énonce donc le geste refusé, pas l'état
    du système.
    """
    if not peut(geste, role):
        sujet = f" sur {quoi}" if quoi else ""
        raise AccesRefuse(f"geste refusé{sujet} : {geste}")


def peut_au_service(geste: str, qualite: str) -> bool:
    """Cette qualité d'appelant autorise-t-elle ce geste de service ?

    Refuse par défaut, comme `peut` : un geste absent de la table n'est pas un
    geste libre. Et un geste de harness demandé ici est absent — c'est ce qui
    empêche `lire` d'ouvrir une création, et `creer` d'ouvrir une lecture.
    """
    exigee = GESTES_DE_SERVICE.get(geste)
    if exigee is None or qualite not in QUALITES:
        return False
    return QUALITES.index(qualite) >= QUALITES.index(exigee)


def exiger_au_service(geste: str, qualite: str) -> None:
    """Laisse passer, ou lève. Même discipline que `exiger` : on énonce le geste
    refusé, jamais l'état du système."""
    if not peut_au_service(geste, qualite):
        raise AccesRefuse(f"geste refusé : {geste}")
