"""Le dépôt de ha — l'interface du corpus (RFC-014 D14.2).

Un ha est une exécution gardée : sa fiche, son transcript, sa sortie, son
matériau, ses blocs d'état, son carré, ses jugements. Jusqu'ici chaque module
— le QG, la veille, la surface HTTP, le banc, les commandes — lisait et
écrivait ces pièces en parcourant des dossiers `CAS-XXXX/`. Ils parlent
désormais à un **dépôt**, et le dépôt sait où les pièces vivent.

Deux dépôts, une interface : celui des fichiers — le régime d'aujourd'hui,
intact, celui que les tests éprouvent et qu'une instance sans base sert — et,
au lot B, celui de la base de l'instance. Rien ne bascule sans qu'on l'ait
demandé : `depot_pour` rend le dépôt des fichiers tant que rien d'autre n'est
déclaré.

Une référence de ha (`RefHa`) nomme un ha sans dire où il est : son corpus,
son nom de dossier. Le dépôt des fichiers la résout en chemin ; un autre la
résoudra autrement. Ce qui n'est pas une pièce d'un ha — le journal, les
personas, la définition — ne passe pas par ici.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

import yaml

__all__ = [
    "DepotDeHa", "DepotFichiers", "RefHa", "depot_pour", "identifiant_de", "ref_de", "transferer",
]


def identifiant_de(nom: str) -> str:
    """`CAS-0012` depuis `CAS-0012-idee-sobre-34c46a` — l'identifiant, sans le titre."""
    morceaux = nom.split("-")
    return "-".join(morceaux[:2]) if len(morceaux) >= 2 and morceaux[0] == "CAS" else nom


@dataclass(frozen=True)
class RefHa:
    """Un ha, nommé sans être situé : son corpus et son nom.

    `chemin` est là pour le dépôt des fichiers, et pour la transition : ce qui
    a besoin d'un dossier le lit ici, en attendant de ne plus en avoir besoin.
    """

    corpus: Path
    nom: str

    @property
    def identifiant(self) -> str:
        return identifiant_de(self.nom)

    @property
    def chemin(self) -> Path:
        return Path(self.corpus) / self.nom

    def __fspath__(self) -> str:  # laisse `Path(ref)` et `open(ref / …)` fonctionner
        return str(self.chemin)

    def __truediv__(self, autre) -> Path:
        return self.chemin / autre

    def __str__(self) -> str:
        return self.nom


def ref_de(dossier) -> RefHa:
    """Une référence depuis un chemin de dossier — ou depuis une référence, telle quelle.

    La frontière de la transition : ce qui reçoit encore un `Path` le convertit
    ici, et le dépôt ne voit que des références.
    """
    if isinstance(dossier, RefHa):
        return dossier
    chemin = Path(dossier)
    return RefHa(chemin.parent, chemin.name)


@runtime_checkable
class DepotDeHa(Protocol):
    """Ce qu'un dépôt de ha sait faire — et rien d'autre."""

    def tous(self, corpus: Path) -> list[RefHa]: ...
    def trouver(self, corpus: Path, identifiant: str) -> RefHa | None: ...
    def existe(self, ref: RefHa) -> bool: ...
    def numero_suivant(self, corpus: Path) -> int: ...
    def creer(self, corpus: Path, nom: str) -> RefHa: ...
    def supprimer(self, ref: RefHa) -> None: ...

    def fiche(self, ref: RefHa) -> str | None: ...
    def entete(self, ref: RefHa) -> dict: ...
    def ecrire_fiche(self, ref: RefHa, texte: str) -> None: ...
    def transcript(self, ref: RefHa) -> str | None: ...
    def ecrire_transcript(self, ref: RefHa, texte: str) -> None: ...
    def sortie(self, ref: RefHa) -> str | None: ...
    def ecrire_sortie(self, ref: RefHa, texte: str) -> None: ...
    def materiau(self, ref: RefHa, nom: str) -> str | None: ...
    def ecrire_materiau(self, ref: RefHa, nom: str, texte: str) -> None: ...
    def materiaux(self, ref: RefHa) -> list[str]: ...
    def etats(self, ref: RefHa) -> list[dict]: ...
    def a_des_etats(self, ref: RefHa) -> bool: ...
    def ecrire_etats(self, ref: RefHa, releves: list[dict]) -> None: ...
    def carre(self, ref: RefHa) -> str | None: ...
    def ecrire_carre(self, ref: RefHa, texte: str) -> None: ...
    def retirer_carre(self, ref: RefHa) -> None: ...
    def jugements(self, ref: RefHa) -> list[dict]: ...
    def ajouter_jugement(self, ref: RefHa, jugement: dict) -> None: ...
    def ecartes(self, corpus: Path) -> list[dict]: ...
    def ecarter(self, corpus: Path, session: str, raison: str, quand: str) -> None: ...


def _jsonl(texte: str) -> list[dict]:
    lignes: list[dict] = []
    for ligne in texte.splitlines():
        if not ligne.strip():
            continue
        try:
            lignes.append(json.loads(ligne))
        except json.JSONDecodeError:
            continue
    return lignes


class DepotFichiers:
    """Le corpus tel qu'il est sur le disque : un dossier `CAS-XXXX-titre/` par ha,
    ses pièces en fichiers, le journal des écartés à côté. Le format d'échange
    et de sauvegarde (D9.1) — et le régime de travail d'une instance sans base.
    """

    ECARTES = ".ecartes.jsonl"

    # --- les ha d'un corpus ---------------------------------------------------

    def tous(self, corpus: Path) -> list[RefHa]:
        corpus = Path(corpus)
        return [RefHa(corpus, d.name) for d in sorted(corpus.glob("CAS-*")) if d.is_dir()]

    def trouver(self, corpus: Path, identifiant: str) -> RefHa | None:
        corpus = Path(corpus)
        trouves = sorted(corpus.glob(f"{identifiant}-*")) or sorted(corpus.glob(identifiant))
        return RefHa(corpus, trouves[0].name) if trouves else None

    def existe(self, ref: RefHa) -> bool:
        return ref.chemin.is_dir()

    def numero_suivant(self, corpus: Path) -> int:
        import re

        existants = [
            int(m.group(1))
            for d in Path(corpus).glob("CAS-*")
            if (m := re.match(r"CAS-(\d+)", d.name))
        ]
        return max(existants, default=0) + 1

    def creer(self, corpus: Path, nom: str) -> RefHa:
        ref = RefHa(Path(corpus), nom)
        ref.chemin.mkdir(parents=True, exist_ok=True)
        return ref

    def supprimer(self, ref: RefHa) -> None:
        shutil.rmtree(ref.chemin, ignore_errors=True)

    # --- les pièces ---------------------------------------------------------------

    def _lire(self, ref: RefHa, nom: str) -> str | None:
        fichier = ref.chemin / nom
        return fichier.read_text(encoding="utf-8") if fichier.is_file() else None

    def _ecrire(self, ref: RefHa, nom: str, texte: str) -> None:
        fichier = ref.chemin / nom
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(texte, encoding="utf-8")

    def fiche(self, ref: RefHa) -> str | None:
        return self._lire(ref, "fiche.md")

    def entete(self, ref: RefHa) -> dict:
        """Le frontmatter d'un ha, sans son corps — vide si la fiche manque ou n'en a pas."""
        texte = self.fiche(ref)
        if not texte or not texte.startswith("---"):
            return {}
        morceaux = texte.split("---", 2)
        if len(morceaux) < 3:
            return {}
        donnees = yaml.safe_load(morceaux[1]) or {}
        return donnees if isinstance(donnees, dict) else {}

    def ecrire_fiche(self, ref: RefHa, texte: str) -> None:
        self._ecrire(ref, "fiche.md", texte)

    def transcript(self, ref: RefHa) -> str | None:
        return self._lire(ref, "transcript.md")

    def ecrire_transcript(self, ref: RefHa, texte: str) -> None:
        self._ecrire(ref, "transcript.md", texte)

    def sortie(self, ref: RefHa) -> str | None:
        return self._lire(ref, "sortie.md")

    def ecrire_sortie(self, ref: RefHa, texte: str) -> None:
        self._ecrire(ref, "sortie.md", texte)

    def materiau(self, ref: RefHa, nom: str) -> str | None:
        return self._lire(ref, f"materiau/{nom}")

    def ecrire_materiau(self, ref: RefHa, nom: str, texte: str) -> None:
        self._ecrire(ref, f"materiau/{nom}", texte)

    def materiaux(self, ref: RefHa) -> list[str]:
        dossier = ref.chemin / "materiau"
        return sorted(f.name for f in dossier.iterdir() if f.is_file()) if dossier.is_dir() else []

    def etats(self, ref: RefHa) -> list[dict]:
        return _jsonl(self._lire(ref, "etats.jsonl") or "")

    def a_des_etats(self, ref: RefHa) -> bool:
        return (ref.chemin / "etats.jsonl").is_file()

    def ecrire_etats(self, ref: RefHa, releves: list[dict]) -> None:
        self._ecrire(
            ref, "etats.jsonl",
            "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in releves),
        )

    def carre(self, ref: RefHa) -> str | None:
        return self._lire(ref, "carre.md")

    def ecrire_carre(self, ref: RefHa, texte: str) -> None:
        self._ecrire(ref, "carre.md", texte)

    def retirer_carre(self, ref: RefHa) -> None:
        (ref.chemin / "carre.md").unlink(missing_ok=True)

    def jugements(self, ref: RefHa) -> list[dict]:
        return _jsonl(self._lire(ref, "jugements.jsonl") or "")

    def ajouter_jugement(self, ref: RefHa, jugement: dict) -> None:
        with (ref.chemin / "jugements.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(jugement, ensure_ascii=False) + "\n")

    # --- les écartés --------------------------------------------------------------

    def ecartes(self, corpus: Path) -> list[dict]:
        fichier = Path(corpus) / self.ECARTES
        return _jsonl(fichier.read_text(encoding="utf-8")) if fichier.is_file() else []

    def ecarter(self, corpus: Path, session: str, raison: str, quand: str) -> None:
        fichier = Path(corpus) / self.ECARTES
        fichier.parent.mkdir(parents=True, exist_ok=True)
        with fichier.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps({"session": session, "raison": raison, "le": quand}, ensure_ascii=False)
                + "\n"
            )


_FICHIERS = DepotFichiers()
_BASES: dict[str, DepotDeHa] = {}


def depot_pour(harness=None) -> DepotDeHa:
    """Le dépôt de ha en service : la base que l'instance déclare par
    `KOKAJI_BASE_URL` (RFC-014 D14.1), sinon les fichiers. Rien ne bascule
    sans qu'on l'ait demandé."""
    url = os.environ.get("KOKAJI_BASE_URL", "").strip()
    if not url:
        return _FICHIERS
    if url not in _BASES:
        from .base import DepotBase

        _BASES[url] = DepotBase(url)
    return _BASES[url]


def transferer(ref: RefHa, de: DepotDeHa, vers: DepotDeHa, corpus: Path | None = None) -> RefHa:
    """Un ha, pièce par pièce, d'un dépôt à l'autre — l'export et l'import de
    D14.8, dans les deux sens, sans rien interpréter. `corpus` : où l'écrire
    dans le dépôt d'arrivée, si ce n'est pas au même endroit."""
    cible = vers.creer(corpus if corpus is not None else ref.corpus, ref.nom)
    for lire, ecrire in (
        (de.fiche, vers.ecrire_fiche),
        (de.transcript, vers.ecrire_transcript),
        (de.sortie, vers.ecrire_sortie),
        (de.carre, vers.ecrire_carre),
    ):
        texte = lire(ref)
        if texte is not None:
            ecrire(cible, texte)
    for nom in de.materiaux(ref):
        vers.ecrire_materiau(cible, nom, de.materiau(ref, nom) or "")
    if de.a_des_etats(ref):
        vers.ecrire_etats(cible, de.etats(ref))
    for jugement in de.jugements(ref):
        vers.ajouter_jugement(cible, jugement)
    return cible
