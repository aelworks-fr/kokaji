"""Un harness, un dépôt — RFC-012.

Chaque harness est un dépôt git à part entière sur la machine de l'instance :
`git init` à la naissance, un commit à chaque scellement (RFC-010), et un
état qu'on peut lire — propre ou non, dernier commit, avance sur le dernier
point connu du dépôt nu s'il y en a un. Tout ici tient sur la machine : aucune
émission réseau, la souveraineté (RFC-009 D9.4) reste entière.

Ce module ne fusionne jamais : une fusion est un jugement sur deux
définitions, ça se fait dans un éditeur, pas dans un service.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = ["DepotIndisponible", "Etat", "est_depot", "etat", "git", "initier"]


class DepotIndisponible(Exception):
    """git est absent, ou le dossier n'est pas un dépôt."""


def git(depot: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Un appel git, sans jamais lever : le code de retour se lit.

    `safe.directory` : le dépôt est monté dans un conteneur qui n'en est pas
    le propriétaire, et git refuserait de le lire sans le dire clairement.
    """
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(depot), *args],
        capture_output=True, text=True, timeout=60, check=False,
        env={**os.environ, **(env or {})},
    )


def _identite(auteur: str = "Kokaji") -> dict:
    """L'identité git du dépôt si elle est réglée, sinon celle qu'on donne —
    pour que le commit existe plutôt que d'échouer sur un réglage absent."""
    return {
        "GIT_AUTHOR_NAME": os.environ.get("GIT_AUTHOR_NAME") or auteur,
        "GIT_AUTHOR_EMAIL": os.environ.get("GIT_AUTHOR_EMAIL") or "scellement@kokaji.local",
        "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME") or "Kokaji",
        "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL") or "scellement@kokaji.local",
    }


def est_depot(racine: Path) -> bool:
    """Ce dossier est-il **lui-même** la racine d'un dépôt — et non un sous-dossier d'un autre ?"""
    if shutil.which("git") is None:
        return False
    haut = git(racine, "rev-parse", "--show-toplevel")
    return haut.returncode == 0 and Path(haut.stdout.strip()).resolve() == Path(racine).resolve()


def initier(racine: Path, message: str, auteur: str = "Kokaji") -> str:
    """Fait du dossier un dépôt, avec un premier commit de tout ce qu'il contient.

    Un harness qui naît est aussitôt un dépôt (RFC-012 D12.1) : le scellement
    a ainsi un historique où commiter dès le premier jour, et l'enregistrement
    d'un dépôt nu, plus tard, n'aura qu'à pousser cet historique. Rend le sha.
    Sans git sur la machine, on le dit — on ne fait pas semblant.
    """
    racine = Path(racine)
    if shutil.which("git") is None:
        raise DepotIndisponible("git est absent : le harness naît sans dépôt")
    if est_depot(racine):
        raise DepotIndisponible(f"{racine.name} est déjà un dépôt")
    for etape in (("init", "-q"), ("add", "-A"), ("commit", "-q", "-m", message)):
        fait = git(racine, *etape, env=_identite(auteur))
        if fait.returncode != 0:
            raise DepotIndisponible(f"git {etape[0]} a refusé : {fait.stderr.strip()}")
    return git(racine, "rev-parse", "--short", "HEAD").stdout.strip()


@dataclass(frozen=True)
class Etat:
    """Ce qu'on sait du dépôt d'un harness, sans rien toucher.

    `avance` compte les commits depuis la référence connue du dépôt nu ; `None`
    quand il n'y a pas de référence, ou qu'elle est inconnue du clone — on ne
    devine pas un retard qu'on n'a pas lu (le lot B tire, et saura).
    """

    est_depot: bool
    propre: bool = True
    branche: str = ""
    dernier_commit: str = ""
    dernier_message: str = ""
    dernier_le: str = ""
    avance: int | None = None
    reference_connue: bool = False

    @property
    def mot(self) -> str:
        """L'état en un mot, celui que le panneau et le badge affichent (D12.5)."""
        if not self.est_depot:
            return "sans dépôt"
        if not self.propre:
            return "modifications non scellées"
        if self.avance is None:
            return "non enregistré" if not self.reference_connue else "à jour"
        return "à jour" if self.avance == 0 else f"en avance de {self.avance}"


def etat(racine: Path, reference: str | None = None) -> Etat:
    racine = Path(racine)
    if not est_depot(racine):
        return Etat(est_depot=False)
    propre = git(racine, "status", "--porcelain").stdout.strip() == ""
    branche = git(racine, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    dernier = git(racine, "log", "-1", "--format=%h%x1f%s%x1f%cI").stdout.strip().split("\x1f")
    sha, message, quand = (dernier + ["", "", ""])[:3] if dernier != [""] else ("", "", "")
    avance: int | None = None
    connue = False
    if reference:
        connue = git(racine, "cat-file", "-e", f"{reference}^{{commit}}").returncode == 0
        if connue:
            compte = git(racine, "rev-list", "--count", f"{reference}..HEAD").stdout.strip()
            avance = int(compte) if compte.isdigit() else None
    return Etat(
        est_depot=True, propre=propre, branche=branche,
        dernier_commit=sha, dernier_message=message, dernier_le=quand,
        avance=avance, reference_connue=connue,
    )
