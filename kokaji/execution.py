"""L'exécution d'une coupe-outil — la façade, l'inerte, la boîte aux lettres.

Un kata d'action est incarné par un **agent CLI** que l'instance câble (RFC-016
§6, RFC-017) : le produit ne connaît ni produit ni isolement. Il expose une
façade — donner une coupe-outil et des entrées, recevoir un résultat — et deux
exécuteurs :

- **inerte** (défaut) : n'exécute rien, journalise l'intention. Le régime tant
  qu'aucun agent n'est câblé (RFC-016 D16.3).
- **boîte aux lettres** (RFC-017 D17.8) : dépose un job dans un volume partagé
  avec le bac à sable, attend le résultat, sans socket ni réseau. Le bac
  surveille, exécute l'agent et les vérificateurs sur un dossier jetable, écrit
  le résultat. Un résultat en retard remonte en urgence (interdit n°3) ; une
  capacité non accordée fait refuser le run avant même de le déposer (D17.3).

Rien ne bascule sans configuration : sans boîte déclarée, l'exécuteur est inerte.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger("kokaji.execution")

__all__ = [
    "CapaciteRefusee",
    "Executeur",
    "ExecuteurBoite",
    "ExecuteurInerte",
    "ExecutionEnRetard",
    "Resultat",
    "executeur_pour",
]


class CapaciteRefusee(RuntimeError):
    """Une capacité requise que l'instance n'a pas accordée — le run refuse de
    partir (RFC-017 D17.3). On ne dégrade pas la conduite en silence."""


class ExecutionEnRetard(RuntimeError):
    """Le bac à sable n'a pas répondu dans le délai — l'écart remonte en urgence
    (RFC-017 D17.6), il ne s'oublie pas."""


@dataclass(frozen=True)
class Resultat:
    """Ce qu'une exécution laisse : ses actions, ses artefacts, son verdict.

    `inerte` dit qu'aucun agent n'a tourné — un placeholder, pas une pratique.
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
    """Le défaut : n'exécute rien, journalise l'intention (RFC-016 D16.3)."""

    def executer(self, outil: dict, entrees: dict) -> Resultat:
        capacites = (outil or {}).get("capacites") or []
        logger.info(
            "exécution inerte — aucun agent câblé ; capacités demandées : %s",
            ", ".join(capacites) or "aucune",
        )
        return Resultat(
            inerte=True,
            note="exécution inerte — aucun agent n'est câblé (RFC-016 D16.3) ; "
            "l'isolement d'exécution attend sa bascule (RFC-017).",
        )


class ExecuteurBoite:
    """La boîte aux lettres du RFC-017 D17.8 : un job déposé, un résultat attendu.

    Le produit n'exécute rien lui-même — il ne sait ni ne veut toucher le monde.
    Il dépose le job dans le volume partagé, le bac à sable fait le reste, et le
    produit lit ce qui revient. Une capacité non accordée est refusée avant le
    dépôt ; un résultat en retard remonte en urgence.
    """

    def __init__(
        self, boite: Path | str, accordees: tuple[str, ...] = (),
        delai: float = 300.0, intervalle: float = 0.5,
    ):
        self.boite = Path(boite)
        self.accordees = set(accordees)
        self.delai = delai
        self.intervalle = intervalle

    def executer(self, outil: dict, entrees: dict) -> Resultat:
        requises = set((outil or {}).get("capacites") or [])
        manquantes = requises - self.accordees
        if manquantes:
            raise CapaciteRefusee(
                "capacité(s) requise(s) non accordée(s) par l'instance : "
                + ", ".join(sorted(manquantes))
            )

        identifiant = uuid.uuid4().hex[:16]
        job = self.boite / identifiant
        job.mkdir(parents=True, exist_ok=True)
        (job / "job.json").write_text(
            json.dumps({"outil": outil, "entrees": entrees}, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        # Le job est prêt quand `job.json` est écrit : un marqueur dit au bac
        # qu'il peut le prendre, pour qu'il ne lise pas un job à moitié posé.
        (job / "pret").write_text("", encoding="utf-8")

        resultat = job / "resultat.json"
        echeance = time.monotonic() + self.delai
        while time.monotonic() < echeance:
            if resultat.is_file():
                lu = json.loads(resultat.read_text(encoding="utf-8"))
                return Resultat(
                    actions=tuple(lu.get("actions") or ()),
                    artefacts=dict(lu.get("artefacts") or {}),
                    verdict=lu.get("verdict"),
                    note=str(lu.get("note") or ""),
                )
            time.sleep(self.intervalle)
        raise ExecutionEnRetard(
            f"le bac à sable n'a pas répondu en {self.delai:.0f}s — job {identifiant}"
        )


def katas_executables() -> set[str]:
    """La liste blanche des kata que l'instance autorise à s'exécuter — le verrou
    par kata (RFC-017 D17.7). Des clés `<harness>/<kata>`, séparées par des
    virgules dans `KOKAJI_KATA_EXECUTABLES`. Vide, personne ne s'exécute."""
    return {
        c.strip() for c in os.environ.get("KOKAJI_KATA_EXECUTABLES", "").split(",") if c.strip()
    }


def executeur_pour(cle: str = "") -> Executeur:
    """L'exécuteur en service, pour le kata `cle` (`<harness>/<kata>`).

    Trois gardes, dans l'ordre : sans boîte déclarée (`KOKAJI_BOITE_EXECUTION`),
    l'inerte — le régime par défaut ; **avec** une boîte mais un kata **hors de
    la liste blanche** (`KOKAJI_KATA_EXECUTABLES`), l'inerte aussi — le verrou par
    kata (D17.7 : « un kata d'essai, et seulement lui ») ; sinon la boîte aux
    lettres, avec les capacités que l'instance accorde (`KOKAJI_CAPACITES_ACCORDEES`,
    D17.3).
    """
    boite = os.environ.get("KOKAJI_BOITE_EXECUTION", "").strip()
    if not boite:
        return ExecuteurInerte()
    if cle and cle not in katas_executables():
        logger.info("verrou par kata — %r n'est pas autorisé à s'exécuter (RFC-017 D17.7)", cle)
        return ExecuteurInerte()
    accordees = tuple(
        c.strip() for c in os.environ.get("KOKAJI_CAPACITES_ACCORDEES", "").split(",") if c.strip()
    )
    delai = float(os.environ.get("KOKAJI_EXECUTION_DELAI", "300"))
    return ExecuteurBoite(boite, accordees=accordees, delai=delai)
