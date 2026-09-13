"""Le persona simulé — l'utilisateur que le banc joue (SPECS §5 R5.4).

Un persona appartient au harness : Kokaji ne connaît que la forme du fichier, ni
son sujet ni sa posture. Il est joué par un appel de modèle scénarisé, tour par
tour, et non par un script figé — sinon on éprouve la forme contre ce qu'on
attendait d'elle.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


class PersonaInvalide(Exception):
    """Le fichier ne décrit pas un persona jouable."""


@dataclass(frozen=True)
class Persona:
    id: str
    nom: str
    sujet: str
    posture: str
    pieges: tuple[str, ...]
    design_exerce: tuple[str, ...]
    tours_max: int
    # RFC-003 §4 — la nature *réelle* du sujet, déclarée par l'auteur du kin, et
    # la nature que son énoncé suggère quand les deux diffèrent. Kokaji ne sait
    # pas ce que ces mots veulent dire : il les transporte et les compare à ce
    # que le kata a émis. Vides, ils sortent simplement le kin de la mesure.
    typologie: str = ""
    enonce_comme: str = ""

    @property
    def piege(self) -> bool:
        """L'énoncé dit une nature, le sujet en est une autre.

        C'est là que la qualité d'un harness se voit — et c'est pourquoi ces
        kin ne se moyennent pas avec les autres.
        """
        return bool(self.enonce_comme) and self.enonce_comme != self.typologie

    @property
    def consigne(self) -> str:
        """Ce qui est injecté au modèle qui joue ce persona."""
        pieges = "\n".join(f"- {p}" for p in self.pieges)
        return (
            "Tu joues une personne qui vient travailler sur son projet. Tu es "
            "l'utilisateur, pas l'accompagnant : tu ne poses pas de questions "
            "sur la méthode, tu réponds à celles qu'on te pose.\n\n"
            f"## Ton sujet\n\n{self.sujet}\n\n"
            f"## Ta manière d'être\n\n{self.posture}\n\n"
            f"## Ce que tu fais en cours d'échange\n\n{pieges}\n\n"
            "Réponds en une ou deux phrases, comme on parle. N'annonce jamais "
            "que tu joues un rôle, ne commente pas l'échange, ne produis aucun "
            "document. Si l'échange te paraît terminé, dis-le simplement."
        )


def charger(chemin: Path) -> Persona:
    donnees = yaml.safe_load(Path(chemin).read_text(encoding="utf-8")) or {}
    if not isinstance(donnees, dict):
        raise PersonaInvalide(f"{chemin.name} ne décrit pas une section")

    manquants = [c for c in ("id", "nom", "sujet", "posture") if not donnees.get(c)]
    if manquants:
        raise PersonaInvalide(f"{chemin.name} : champ(s) absent(s) — {', '.join(manquants)}")

    return Persona(
        id=str(donnees["id"]),
        nom=str(donnees["nom"]),
        sujet=str(donnees["sujet"]).strip(),
        posture=str(donnees["posture"]).strip(),
        pieges=tuple(str(p) for p in donnees.get("pieges") or ()),
        design_exerce=tuple(str(d) for d in donnees.get("design_exerce") or ()),
        tours_max=int(donnees.get("tours_max") or 12),
        typologie=str(donnees.get("typologie") or "").strip(),
        enonce_comme=str(donnees.get("enonce_comme") or "").strip(),
    )


def charger_tous(dossier: Path) -> tuple[Persona, ...]:
    return tuple(charger(f) for f in sorted(Path(dossier).glob("*.yaml")))
