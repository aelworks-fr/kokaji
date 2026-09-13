"""La justesse du diagnostic de nature — RFC-003 §4 et §5.4, pas 4.

Chaque kin de banc déclare la nature *réelle* de son sujet (`typologie:`) ; le
kata, lui, émet la nature qu'il croit lire, dans son bloc d'état. Comparer les
deux donne deux mesures :

- **la justesse** — le diagnostic est-il correct, et au bout de combien de tours ;
- **la couverture** — quel kata a été éprouvé contre quelles natures, et
  lesquelles n'ont jamais été jouées.

Trois règles tiennent ce module, et elles viennent du carnet [#9](../../../docs/carnet.md) :

- **Le seuil est déclaré par le harness, jamais par Kokaji.** Ce qui est
  acceptable est un jugement de domaine. Kokaji compare et rapporte.
- **Le seuil est écrit avant la campagne qu'il juge.** Ce module ne sait pas
  faire autrement : il lit le manifest, il ne le propose ni ne l'écrit.
- **Le kin piège compte à part.** Une moyenne noie le cas qui portait toute la
  question. Un harness qui réussit trois kin faciles et rate l'énoncé trompeur
  n'a rien démontré — le verdict le dit séparément.

Ce module ne joue rien : il mesure ce qu'une campagne a produit. Le banc joue.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from itertools import pairwise

from ...hds import Harness

__all__ = [
    "Couverture",
    "Diagnostic",
    "Verdict",
    "couverture",
    "mesurer",
    "natures_emises",
    "verdict",
]

BLOC = re.compile(r"```json\s+kokaji_state\s*(\{.*?\})\s*```", re.DOTALL)


def _natures_du_tour(texte: str) -> list[str]:
    """Les natures déclarées dans les blocs d'état d'un tour."""
    trouvees = []
    for brut in BLOC.findall(texte or ""):
        try:
            etat = (json.loads(brut) or {}).get("kokaji_state") or {}
        except json.JSONDecodeError:
            continue  # R7.2 — un bloc malformé n'interrompt rien
        nature = etat.get("nature")
        if isinstance(nature, dict) and str(nature.get("valeur") or "").strip():
            trouvees.append(str(nature["valeur"]).strip())
    return trouvees


def natures_emises(tours) -> list[tuple[int, str]]:
    """Les natures émises, avec le rang du tour — dans l'ordre de l'échange."""
    suite = []
    for tour in tours:
        for nature in _natures_du_tour(getattr(tour, "reponse", "")):
            suite.append((tour.rang, nature))
    return suite


@dataclass(frozen=True)
class Diagnostic:
    """Ce qu'un kin a obtenu d'un kata, sur la seule question de la nature."""

    persona: str
    kata: str
    attendue: str
    piege: bool
    emises: tuple[tuple[int, str], ...]

    @property
    def muet(self) -> bool:
        """Aucune nature émise — le kata n'a pas diagnostiqué du tout."""
        return not self.emises

    @property
    def finale(self) -> str:
        return self.emises[-1][1] if self.emises else ""

    @property
    def juste(self) -> bool:
        """C'est la **dernière** nature qui compte, pas la première.

        Le RFC pose la révisabilité comme une vertu : un kata qui se trompe puis
        se corrige a bien travaillé. Compter la première tuerait la révision.
        """
        return bool(self.attendue) and self.finale == self.attendue

    @property
    def tour_de_justesse(self) -> int | None:
        """Le premier tour où la nature attendue est émise — et tenue ensuite.

        Un kata qui tombe juste par hasard au tour 2 puis change d'avis n'a pas
        diagnostiqué au tour 2 : il a hésité.
        """
        if not self.juste:
            return None
        rang = None
        for tour, nature in self.emises:
            if nature == self.attendue:
                rang = rang if rang is not None else tour
            else:
                rang = None
        return rang

    @property
    def revisions(self) -> int:
        """Combien de fois la nature a changé au cours de l'échange."""
        valeurs = [n for _, n in self.emises]
        return sum(1 for a, b in pairwise(valeurs) if a != b)

    def __str__(self) -> str:
        if self.muet:
            return f"{self.persona} — aucune nature émise (attendu : {self.attendue})"
        marque = "✓" if self.juste else "✗"
        ou = f" au tour {self.tour_de_justesse}" if self.tour_de_justesse else ""
        piege = " [piège]" if self.piege else ""
        return (
            f"{marque} {self.persona}{piege} — attendu {self.attendue}, "
            f"émis {self.finale}{ou}"
        )


def mesurer(persona, kata: str, tours) -> Diagnostic:
    """La justesse d'un kin sur une session jouée."""
    return Diagnostic(
        persona=persona.id,
        kata=kata,
        attendue=getattr(persona, "typologie", ""),
        piege=getattr(persona, "piege", False),
        emises=tuple(natures_emises(tours)),
    )


@dataclass(frozen=True)
class Couverture:
    """Quelles natures un kata a réellement rencontrées (RFC-003 §5.4)."""

    kata: str
    jouees: dict[str, int]
    connues: tuple[str, ...]

    @property
    def manquantes(self) -> tuple[str, ...]:
        """Les natures qu'aucun kin n'a jamais présentées à ce kata.

        Une nature jamais jouée n'est pas une nature réussie : elle est
        inconnue. Le dire évite de lire une bonne moyenne comme une preuve de
        robustesse.
        """
        return tuple(n for n in self.connues if not self.jouees.get(n))


def couverture(kata: str, personas, natures_connues: tuple[str, ...]) -> Couverture:
    jouees: dict[str, int] = {}
    for persona in personas:
        typologie = getattr(persona, "typologie", "")
        if typologie:
            jouees[typologie] = jouees.get(typologie, 0) + 1
    return Couverture(kata=kata, jouees=jouees, connues=tuple(natures_connues))


@dataclass(frozen=True)
class Verdict:
    """Le résultat d'une campagne, face au seuil que le harness s'est donné."""

    kata: str
    seuil: float
    justes: int
    mesures: int
    pieges_justes: int
    pieges: int
    muets: int

    @property
    def taux(self) -> float | None:
        return self.justes / self.mesures if self.mesures else None

    @property
    def pieges_tenus(self) -> bool:
        """Tous les pièges, ou aucun verdict favorable.

        Le RFC le dit sans détour : « dont impérativement le piège ». Ce n'est
        pas une pondération, c'est une condition.
        """
        return self.pieges == 0 or self.pieges_justes == self.pieges

    @property
    def tenu(self) -> bool | None:
        """`None` quand rien n'a été mesuré — ce n'est pas un échec, c'est un vide."""
        if not self.mesures:
            return None
        return self.taux >= self.seuil and self.pieges_tenus

    def __str__(self) -> str:
        if not self.mesures:
            return f"{self.kata} : aucune mesure — rien n'a été joué"
        taux = f"{self.taux:.0%}"
        etat = "tenu" if self.tenu else "non tenu"
        detail = f"{self.justes}/{self.mesures} justes, seuil {self.seuil:.0%}"
        if self.pieges:
            detail += f", pièges {self.pieges_justes}/{self.pieges}"
        if self.muets:
            detail += f", {self.muets} sans diagnostic"
        return f"{self.kata} : {taux} — {etat} ({detail})"


def verdict(harness: Harness, kata: str, diagnostics) -> Verdict:
    """Confronte une campagne au seuil déclaré par le harness.

    Les kin muets — aucune nature émise — comptent comme des échecs, et sont
    aussi rapportés à part : ne pas diagnostiquer n'est pas se tromper, mais ce
    n'est pas non plus réussir, et les sortir du dénominateur flatterait le taux.
    """
    mesurables = [d for d in diagnostics if d.attendue]
    pieges = [d for d in mesurables if d.piege]
    return Verdict(
        kata=kata,
        seuil=harness.trempe.seuil_justesse(kata),
        justes=sum(1 for d in mesurables if d.juste),
        mesures=len(mesurables),
        pieges_justes=sum(1 for d in pieges if d.juste),
        pieges=len(pieges),
        muets=sum(1 for d in mesurables if d.muet),
    )
