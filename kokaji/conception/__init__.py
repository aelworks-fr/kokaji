"""Concevoir un harness — le module « Design du harness » (RFC-004 §3, §4).

On ne modifie pas une définition : on **propose**, on lit un verdict, on scelle.
La vérification est la trempe elle-même, jouée sur une copie ; rien n'est écrit
tant que la définition proposée ne tient pas.

La surface visuelle n'existe pas encore et ne s'invente pas : le handoff de
design la déclare emplacement réservé. Ce module en est le fond.
"""

from __future__ import annotations

from .brouillon import CoupeIntrouvable, appliquer, juger, rendre_coupe
from .modele import Changement, Proposition, Scellement, Verdict
from .sceller import JOURNAL, ScellementRefuse, sceller, version_suivante, versions_prevues

__all__ = [
    "JOURNAL",
    "Changement",
    "CoupeIntrouvable",
    "Proposition",
    "Scellement",
    "ScellementRefuse",
    "Verdict",
    "appliquer",
    "juger",
    "rendre_coupe",
    "sceller",
    "version_suivante",
    "versions_prevues",
]
