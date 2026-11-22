"""Le standard, tel que le produit le versionne — D22.9.

Un agent qui conçoit un harness doit savoir ce qu'est un harness. La surface de
l'agent sert donc le HDS et le vocabulaire d'une proposition en **ressources**
lisibles. Ce sont des fichiers et des constantes **du produit** : rien d'une
instance, rien d'une pratique.

Le HDS vit dans `docs/hds-v0.md`, qui est sa seule source. La roue en embarque
une copie sous `kokaji/standard/`, et l'image l'emporte — sans quoi « le
standard voyage avec la surface » serait faux dès qu'on déploie. Les deux
emplacements sont essayés, parce que les tests tournent depuis le dépôt, où le
document n'est qu'à sa place d'origine.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["HDS", "hds", "ou_est_le_hds"]

HDS = "hds-v0.md"


def ou_est_le_hds() -> Path | None:
    """La copie embarquée d'abord, la source du dépôt ensuite."""
    for chemin in (Path(__file__).parent / HDS, Path(__file__).parents[2] / "docs" / HDS):
        if chemin.is_file():
            return chemin
    return None


def hds() -> str | None:
    """Le HDS tel quel, ou `None` s'il n'a pas voyagé.

    Rendre `None` plutôt que lever : une ressource absente se dit à l'agent,
    elle ne casse pas la surface qui la propose.
    """
    chemin = ou_est_le_hds()
    return None if chemin is None else chemin.read_text(encoding="utf-8")
