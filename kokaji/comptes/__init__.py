"""Utilisateurs, autorat et droits — RFC-004.

Deux relations, jamais confondues : l'autorat se partage (`Acl`), la pratique se
verse (`visibilite` sur le ha). Voir `modele.py` pour le pourquoi.
"""

from __future__ import annotations

from .depot import DUREE_INVITATION, Comptes, IdentiteInconnue, ou_ouvrir, transvaser
from .droits import (
    ADMINISTRATION,
    ANONYME,
    COMPTE,
    GESTES,
    GESTES_DE_SERVICE,
    QUALITES,
    AccesRefuse,
    exiger,
    exiger_au_service,
    peut,
    peut_au_service,
)
from .modele import (
    CONCEPTION,
    CONTRIBUTEUR,
    ETRANGER,
    LECTURE,
    PORTEES,
    PRIVEE,
    PROPRIETAIRE,
    ROLES,
    VERSE,
    VISIBILITES,
    Acl,
    AclInvalide,
    JetonAgent,
    Utilisateur,
)
from .portail import PortailIndisponible, inscrire

__all__ = [
    "ADMINISTRATION",
    "ANONYME",
    "COMPTE",
    "CONCEPTION",
    "CONTRIBUTEUR",
    "DUREE_INVITATION",
    "ETRANGER",
    "GESTES",
    "GESTES_DE_SERVICE",
    "LECTURE",
    "PORTEES",
    "PRIVEE",
    "PROPRIETAIRE",
    "QUALITES",
    "ROLES",
    "VERSE",
    "VISIBILITES",
    "AccesRefuse",
    "Acl",
    "AclInvalide",
    "Comptes",
    "IdentiteInconnue",
    "JetonAgent",
    "PortailIndisponible",
    "Utilisateur",
    "exiger",
    "exiger_au_service",
    "inscrire",
    "ou_ouvrir",
    "peut",
    "peut_au_service",
    "transvaser",
]
