"""La forge — build multi-cibles (SPECS §4).

`dist/` est un produit : rien ne s'y édite à la main, tout s'y régénère (R4.1).
La forge y écrit les coupes de chaque cible, leur estampille, et le relevé de ce
qui a changé depuis la forge précédente.
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass
from pathlib import Path

from ..hds import Harness
from ..trempe.statique import TrempeEchouee, verifier
from .coupe import Coupe, Estampille, ForgeImpossible, charger_registre, forger

__all__ = [
    "Coupe",
    "Estampille",
    "ForgeImpossible",
    "Resultat",
    "TrempeEchouee",
    "forger_harness",
]

SORTIE_DEFAUT = Path("dist/coupes")


@dataclass(frozen=True)
class Changement:
    cible: str
    kata: str
    etat: str  # nouveau | modifie | inchange
    diff: str = ""


@dataclass(frozen=True)
class Resultat:
    racine: Path
    coupes: tuple[Coupe, ...]
    changements: tuple[Changement, ...]

    @property
    def modifiees(self) -> tuple[Changement, ...]:
        return tuple(c for c in self.changements if c.etat != "inchange")


def forger_harness(
    harness: Harness,
    sortie: Path | str = SORTIE_DEFAUT,
    cibles: tuple[str, ...] = (),
    trempe: bool = True,
) -> Resultat:
    """Forge toutes les coupes d'un harness, ou seulement celles des cibles données.

    Les coupes sont assemblées en mémoire, trempées, puis écrites. Une anomalie
    bloque la forge (SPECS §5) : `dist/` ne reçoit jamais une coupe fautive.
    """
    retenues = harness.cibles
    if cibles:
        inconnues = sorted(set(cibles) - {c.id for c in harness.cibles})
        if inconnues:
            raise ForgeImpossible(f"cible(s) inconnue(s) : {', '.join(inconnues)}")
        retenues = tuple(c for c in harness.cibles if c.id in cibles)

    template = harness.template.read_text(encoding="utf-8")
    registre = charger_registre(harness.trempe.registre)

    # L'id du harness préfixe la sortie : deux harness forgés côte à côte ne se
    # recouvrent jamais (R2.2).
    racine = Path(sortie) / harness.id
    produites: list[Coupe] = []

    for cible in retenues:
        for kata in harness.kata:
            produites.append(forger(harness, kata, cible, template, registre))

    # La trempe statique ne s'applique qu'à ce que la forge a assemblé : un
    # texte importé tel quel n'a rien promis qu'elle sache vérifier, et la
    # refuser ferait de l'import un citoyen de seconde zone au lieu d'un
    # arrivant honnête. Elle s'allumera à N4, quand la forge régénérera
    # (RFC-008 §3).
    if trempe and not harness.exogene:
        anomalies = verifier(harness, produites, registre)
        if anomalies:
            raise TrempeEchouee(anomalies)

    changements: list[Changement] = []
    for coupe in produites:
        dossier = racine / coupe.cible
        dossier.mkdir(parents=True, exist_ok=True)
        changements.append(_ecrire(dossier, coupe))

    _ecrire_changements(racine, changements)
    return Resultat(racine=racine, coupes=tuple(produites), changements=tuple(changements))


def _ecrire(dossier: Path, coupe: Coupe) -> Changement:
    fichier = dossier / f"{coupe.kata}.md"
    ancien = fichier.read_text(encoding="utf-8") if fichier.is_file() else None

    if ancien is None:
        etat, diff = "nouveau", ""
    elif ancien == coupe.texte:
        etat, diff = "inchange", ""
    else:
        etat = "modifie"
        diff = "".join(
            difflib.unified_diff(
                ancien.splitlines(keepends=True),
                coupe.texte.splitlines(keepends=True),
                fromfile=f"{fichier.name} (forge précédente)",
                tofile=f"{fichier.name} (cette forge)",
                n=2,
            )
        )

    fichier.write_text(coupe.texte, encoding="utf-8")
    # L'estampille en JSON : c'est elle que la passerelle lit pour identifier
    # les ha (§3 R3.3).
    (dossier / f"{coupe.kata}.json").write_text(
        json.dumps(coupe.estampille.as_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return Changement(cible=coupe.cible, kata=coupe.kata, etat=etat, diff=diff)


def _ecrire_changements(racine: Path, changements: list[Changement]) -> None:
    """Le relevé de forge — R4.3, changelog par diff de source."""
    modifiees = [c for c in changements if c.etat != "inchange"]
    lignes = ["# Relevé de forge", ""]

    if not modifiees:
        lignes.append("Aucune coupe n'a changé depuis la forge précédente.")
    else:
        for c in modifiees:
            lignes.append(f"## {c.cible}/{c.kata} — {c.etat}")
            lignes.append("")
            if c.diff:
                lignes += ["```diff", c.diff.rstrip("\n"), "```", ""]

    racine.mkdir(parents=True, exist_ok=True)
    (racine / "CHANGEMENTS.md").write_text("\n".join(lignes).rstrip() + "\n", encoding="utf-8")
