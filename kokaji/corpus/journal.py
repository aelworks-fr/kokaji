"""Le journal des appels — ce que la passerelle a servi (RFC-014 D14.4).

Deux sources, une lecture. Le journal en fichiers — une ligne JSON par appel,
un fichier par jour, ce que le hook écrit quand aucune base n'est déclarée, et
ce qu'un journal exporté d'ailleurs reste — et le journal en base, la table
`appel`, où le hook écrit **à la source** dès que `KOKAJI_BASE_URL` est là.

`lire_journal` lit les deux et ne compte jamais un appel deux fois : la
première instance gardera ses fichiers un temps après avoir importé, et un
appel a un identifiant. Avec `harness`, la base ne rend que ce harness — la
veille et le QG demandent, ils ne parcourent plus dix-sept mégaoctets.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

__all__ = ["journal_pour", "lire_fichiers", "lire_journal"]


def lire_fichiers(dossier: Path | None) -> list[dict]:
    """Le journal en fichiers, tel quel — vide si le dossier n'existe pas."""
    lignes: list[dict] = []
    if dossier is None or not str(dossier) or not Path(dossier).is_dir():
        return lignes
    for fichier in sorted(Path(dossier).glob("*.jsonl")):
        for ligne in fichier.read_text(encoding="utf-8").splitlines():
            if ligne.strip():
                try:
                    lignes.append(json.loads(ligne))
                except json.JSONDecodeError:
                    continue  # une ligne illisible ne fait pas tomber la lecture
    return lignes


_JOURNAUX: dict[str, object] = {}


def journal_pour():
    """Le journal en base que l'instance déclare (`KOKAJI_BASE_URL`), ou rien."""
    url = os.environ.get("KOKAJI_BASE_URL", "").strip()
    if not url:
        return None
    if url not in _JOURNAUX:
        from .base import JournalBase

        _JOURNAUX[url] = JournalBase(url)
    return _JOURNAUX[url]


def _cle(ligne: dict) -> str:
    return str(ligne.get("id_appel") or "") or f"{ligne.get('session')}/{ligne.get('etat_apres')}"


def lire_journal(dossier: Path | None, harness: str | None = None) -> list[dict]:
    """Tous les appels connus, fichiers puis base, chacun une fois, dans l'ordre
    du temps. `harness` restreint la base à un harness ; les fichiers, eux, se
    lisent entiers — ils sont petits ou ils sont anciens."""
    lignes = lire_fichiers(dossier)
    journal = journal_pour()
    if journal is not None:
        vus = {_cle(ligne) for ligne in lignes}
        for ligne in journal.appels(harness):
            if _cle(ligne) not in vus:
                lignes.append(ligne)
        lignes.sort(key=lambda ligne: str(ligne.get("debut") or ""))
    if harness:
        lignes = [l for l in lignes if (l.get("identite") or {}).get("harness") == harness]
    return lignes
