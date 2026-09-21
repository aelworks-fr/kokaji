"""L'exécution d'une coupe-outil — la façade, et son défaut inerte (RFC-016 D16.3).

Un kata d'action est incarné par un **agent CLI** que l'instance câble : le
produit ne connaît ni produit ni isolement (RFC-016 §6, souveraineté RFC-009).
Il expose une façade — donner une coupe-outil et des entrées, recevoir un
résultat (actions, artefacts, verdict) — et un **exécuteur inerte** par défaut,
qui n'exécute rien : il journalise l'intention et rend un résultat vide, marqué
inerte. Le vrai agent se branche le jour où une RFC d'isolement dit où et
comment il touche le monde. D'ici là, tout le runtime se bâtit et s'éprouve
sans rien lancer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

logger = logging.getLogger("kokaji.execution")

__all__ = ["Executeur", "ExecuteurInerte", "Resultat", "executeur_pour"]


@dataclass(frozen=True)
class Resultat:
    """Ce qu'une exécution laisse : ses actions, ses artefacts, son verdict.

    `inerte` dit qu'aucun agent n'a tourné — le résultat est un placeholder, pas
    une pratique. Les vérificateurs ne se prononcent pas sur de l'inerte.
    """

    actions: tuple[dict, ...] = ()
    artefacts: dict[str, str] = field(default_factory=dict)
    verdict: dict | None = None
    inerte: bool = False
    note: str = ""


@runtime_checkable
class Executeur(Protocol):
    """Ce qu'un exécuteur sait faire — incarner une coupe-outil, rendre un résultat."""

    def executer(self, outil: dict, entrees: dict) -> Resultat: ...


class ExecuteurInerte:
    """Le défaut : n'exécute rien, journalise l'intention (RFC-016 D16.3).

    C'est la couture où un agent CLI se câblera. Tant qu'aucun ne l'est, le
    runtime tourne à vide — utile pour tout éprouver sans toucher le monde.
    """

    def executer(self, outil: dict, entrees: dict) -> Resultat:
        capacites = (outil or {}).get("capacites") or []
        logger.info(
            "exécution inerte — aucun agent câblé ; capacités demandées : %s",
            ", ".join(capacites) or "aucune",
        )
        return Resultat(
            inerte=True,
            note="exécution inerte — aucun agent n'est câblé (RFC-016 D16.3) ; "
            "l'isolement d'exécution attend sa RFC.",
        )


def executeur_pour(moteur: str = "") -> Executeur:
    """L'exécuteur en service. Inerte tant qu'aucun agent n'est déclaré — le seul
    régime pour l'instant (le câblage d'un agent réel viendra avec l'isolement)."""
    # `moteur` est le point d'entrée du câblage futur : un nom d'agent que
    # l'instance mappe. Aucun n'est reconnu aujourd'hui : on reste inerte.
    return ExecuteurInerte()
