"""Semer un cas de test depuis une pratique rapportée (RFC-020 D20.4).

La valeur d'un ha rapporté ne tient pas d'abord à la qualité de son exécution :
elle tient à son **scénario**. Un déroulé réel, venu d'ailleurs, est une
source d'inspiration pour le corpus de cas — les kin que le banc joue — et
c'est ce qui tire l'exploration du harness hors de son propre voisinage (§4).

Un cas, ici, c'est un **persona** du harness (`personas/<id>.yaml`) : le kin
que le banc fait jouer. On le pré-remplit depuis le ha — le sujet depuis la
déclaration et le premier tour du porteur, le déroulé-type depuis ses tours —
et il porte `seme_par:` vers son ha d'origine. Même encre, même honnêteté :
le cas semé dit d'où il vient, et ce que le forgeron doit encore écrire (la
posture, les pièges) reste marqué à écrire, jamais inventé.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ...corpus.depot import depot_pour, ref_de
from ...corpus.provenance import RAPPORTE, provenance_de
from ...hds import Harness
from .rejeu import tours_du_ha

__all__ = ["CasSeme", "SemenceRefusee", "semer_cas"]

A_ECRIRE = "À écrire — semé depuis un ha rapporté, non joué par le banc."


class SemenceRefusee(Exception):
    """Rien n'a été semé, et la raison est nommée."""


@dataclass(frozen=True)
class CasSeme:
    id: str
    chemin: Path
    seme_par: str
    tours: int


def _identifiant(identifiant: str, kin: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", (kin or identifiant).lower()).strip("-")
    return base or identifiant.lower()


def semer_cas(
    harness: Harness,
    dossier: Path,
    identifiant: str | None = None,
    par: str = "",
) -> CasSeme:
    """Écrit `personas/<id>.yaml` pré-rempli depuis le ha, avec `seme_par:`.

    Refuse — et n'écrit rien — un ha qui n'est pas rapporté, un transcript
    vide, ou un persona qui existe déjà sous ce nom : semer n'écrase pas.
    """
    depot = depot_pour(harness)
    ref = ref_de(dossier)
    entete = depot.entete(ref)
    if not entete:
        raise SemenceRefusee(f"{ref.nom} : fiche absente ou illisible")
    if provenance_de(entete) != RAPPORTE:
        raise SemenceRefusee(
            f"{ref.nom} est `{provenance_de(entete)}` : on sème depuis une pratique rapportée"
            " — un ha observé est déjà né d'un kin ou d'une personne"
        )
    porteurs, tours = tours_du_ha(ref)
    porteurs = [p for p in porteurs if p]
    if not porteurs:
        raise SemenceRefusee(f"{ref.nom} : aucun tour du porteur — rien à semer")

    declaration = entete.get("declaration") or {}
    kin = str(declaration.get("kin") or "").strip()
    id_cas = identifiant or _identifiant(ref.identifiant, kin)
    chemin = Path(harness.personas) / f"{id_cas}.yaml"
    if chemin.exists():
        raise SemenceRefusee(f"{chemin.name} existe déjà : semer n'écrase pas un kin")

    cas = {
        "id": id_cas,
        "nom": kin or f"Cas semé depuis {ref.identifiant}",
        "sujet": porteurs[0] if not kin else f"{kin}\n\n{porteurs[0]}",
        "posture": A_ECRIRE,
        "pieges": [],
        "design_exerce": [],
        "tours_max": max(len(tours) + 2, 6),
        # Le déroulé-type : ce que le porteur a dit, tour par tour, tel quel.
        "deroule": porteurs,
        # La traçabilité de l'inspiration (RFC-020 D20.4).
        "seme_par": ref.identifiant,
        "seme_de": {
            "harness": harness.id,
            "corpus": str(ref.corpus.name),
            "kata": str(entete.get("kata") or ""),
            "source_texte": str(declaration.get("source_texte") or ""),
            "par": par,
        },
    }
    en_tete = (
        f"# Cas semé depuis {ref.identifiant} — une pratique rapportée (RFC-020 D20.4).\n"
        "# Le sujet et le déroulé viennent du ha ; la posture et les pièges sont à écrire.\n\n"
    )
    Path(harness.personas).mkdir(parents=True, exist_ok=True)
    chemin.write_text(
        en_tete + yaml.safe_dump(cas, allow_unicode=True, sort_keys=False, width=1000),
        encoding="utf-8",
    )
    return CasSeme(id=id_cas, chemin=chemin, seme_par=ref.identifiant, tours=len(porteurs))
