"""Le scellement commite — la définition d'un harness vit dans un dépôt git (RFC-009 D9.1).

Sceller écrivait les fichiers et s'arrêtait là : sur un serveur, un harness
modifié depuis le QG restait sur le disque, hors de tout historique, et rien
ne le disait. Un scellement est pourtant exactement ce qu'un commit est — un
état daté, signé, motivé. On le commite donc, dans le dépôt qui contient le
harness, et seulement le harness : s'il vit dans un dépôt plus large, le reste
de ce dépôt n'est pas touché.

Ce geste **suit** le scellement et ne le conditionne pas. Sans git, hors de
tout dépôt, ou si le commit échoue, le scellement tient et la trace dit
pourquoi rien n'a été commité. Pousser est un réglage du harness
(RFC-012, `pousser_au_scellement`), et le service s'en charge après le
scellement.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import yaml

from ..depot import git

__all__ = ["commiter"]


_git = git  # le même appel que le module des dépôts (RFC-012)


def _id_du_harness(racine: Path) -> str:
    try:
        manifest = yaml.safe_load((racine / "harness.yaml").read_text(encoding="utf-8")) or {}
        return str((manifest.get("harness") or {}).get("id") or racine.name)
    except (OSError, yaml.YAMLError):
        return racine.name


def commiter(racine: Path, auteur: str, motif: str, versions: dict[str, str]) -> tuple[str, str]:
    """Commite l'état du harness. Rend `(sha, "")`, ou `("", pourquoi pas)`."""
    racine = Path(racine).resolve()
    if shutil.which("git") is None:
        return "", "git est absent"
    haut = _git(racine, "rev-parse", "--show-toplevel")
    if haut.returncode != 0:
        return "", "le harness n'est dans aucun dépôt git"
    depot = Path(haut.stdout.strip())

    # Seulement le harness : `-A` limité à son chemin. Un dépôt qui porte
    # d'autres choses en cours n'a pas à les voir partir sous ce nom.
    chemin = racine.relative_to(depot).as_posix() or "."
    ajout = _git(depot, "add", "-A", "--", chemin)
    if ajout.returncode != 0:
        return "", f"git add a refusé : {ajout.stderr.strip()}"
    if _git(depot, "diff", "--cached", "--quiet", "--", chemin).returncode == 0:
        return "", "rien à commiter"

    message = f"scellement : {_id_du_harness(racine)} — " + " · ".join(
        f"{q} v{v}" for q, v in versions.items()
    )
    if motif.strip():
        message += f"\n\n{motif.strip()}"
    message += f"\n\nScellé par {auteur.strip()} depuis le QG."
    # L'identité git est celle du dépôt s'il en a une ; sinon l'auteur du
    # scellement, pour que le commit existe plutôt que d'échouer sur un réglage.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": os.environ.get("GIT_AUTHOR_NAME") or auteur.strip(),
        "GIT_AUTHOR_EMAIL": os.environ.get("GIT_AUTHOR_EMAIL") or "scellement@kokaji.local",
        "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME") or "Kokaji",
        "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL") or "scellement@kokaji.local",
    }
    commit = subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(depot), "commit", "--quiet", "-m", message,
         "--", chemin],
        capture_output=True, text=True, timeout=60, check=False, env=env,
    )
    if commit.returncode != 0:
        return "", f"git commit a refusé : {commit.stderr.strip()}"
    sha = _git(depot, "rev-parse", "--short", "HEAD").stdout.strip()
    return sha, ""
