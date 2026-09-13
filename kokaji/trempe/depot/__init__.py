"""La trempe du dépôt — Kokaji se trempe lui-même (SPECS §10, R10.1, R10.2).

Le principe de découplage n'est pas une intention : c'est une propriété
vérifiable. Aucun nom de processus, de rôle, d'organisation ou de domaine ne doit
exister dans le code, les commentaires, les commits, les fixtures ou la
documentation.

La liste des interdits vit dans `.trempe-kokaji.yaml`. Une seconde liste,
`.trempe-kokaji.local.yaml`, reste hors du dépôt : c'est là que se déclarent les
termes qu'on ne peut pas publier sans dire précisément ce qu'on cherche à ne pas
publier.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

__all__ = ["Trouvaille", "charger_interdits", "trempe_du_depot"]

CONFIG = ".trempe-kokaji.yaml"
CONFIG_LOCALE = ".trempe-kokaji.local.yaml"


@dataclass(frozen=True)
class Trouvaille:
    terme: str
    ou: str
    ligne: int | None
    extrait: str

    def __str__(self) -> str:
        situe = f"{self.ou}:{self.ligne}" if self.ligne else self.ou
        return f"{situe} — « {self.terme} » : {self.extrait}"


@dataclass(frozen=True)
class Interdits:
    termes: tuple[str, ...]
    exemptions: tuple[str, ...]
    commits: int

    def exempte(self, chemin: str) -> bool:
        return any(fnmatch.fnmatch(chemin, motif) for motif in self.exemptions)


def charger_interdits(racine: Path) -> Interdits:
    """La liste publique, complétée par la locale si elle existe."""
    termes: list[str] = []
    exemptions: list[str] = []
    commits = 0

    for nom in (CONFIG, CONFIG_LOCALE):
        fichier = racine / nom
        if not fichier.is_file():
            continue
        donnees = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        termes += [str(t) for t in donnees.get("interdits") or []]
        exemptions += [str(e) for e in donnees.get("exemptions") or []]
        commits = max(commits, int(donnees.get("commits") or 0))

    return Interdits(tuple(dict.fromkeys(termes)), tuple(exemptions), commits)


def _fichiers_suivis(racine: Path) -> list[str]:
    sortie = subprocess.run(
        ["git", "-C", str(racine), "ls-files"],
        capture_output=True, text=True, check=True,
    )
    return [ligne for ligne in sortie.stdout.splitlines() if ligne.strip()]


def _messages_de_commit(racine: Path, combien: int) -> list[tuple[str, str]]:
    if combien <= 0:
        return []
    sortie = subprocess.run(
        ["git", "-C", str(racine), "log", f"-{combien}", "--format=%h%x00%B%x1e"],
        capture_output=True, text=True, check=True,
    )
    messages = []
    for bloc in sortie.stdout.split("\x1e"):
        if "\x00" not in bloc:
            continue
        empreinte, message = bloc.split("\x00", 1)
        messages.append((empreinte.strip(), message))
    return messages


def _chercher(terme: str, texte: str, ou: str, avec_lignes: bool) -> list[Trouvaille]:
    motif = re.compile(re.escape(terme), re.IGNORECASE)
    trouvailles = []
    for rang, ligne in enumerate(texte.splitlines(), 1):
        trouve = motif.search(ligne)
        if not trouve:
            continue
        debut = max(0, trouve.start() - 30)
        trouvailles.append(
            Trouvaille(
                terme=terme,
                ou=ou,
                ligne=rang if avec_lignes else None,
                extrait=ligne[debut : trouve.end() + 30].strip(),
            )
        )
    return trouvailles


def trempe_du_depot(racine: Path, interdits: Interdits | None = None) -> tuple[Trouvaille, ...]:
    """Cherche les interdits dans les fichiers suivis et les messages de commit."""
    racine = Path(racine)
    interdits = interdits or charger_interdits(racine)
    if not interdits.termes:
        return ()

    trouvailles: list[Trouvaille] = []

    for chemin in _fichiers_suivis(racine):
        if interdits.exempte(chemin):
            continue
        fichier = racine / chemin
        try:
            texte = fichier.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue  # un binaire ne porte pas de vocabulaire
        for terme in interdits.termes:
            trouvailles += _chercher(terme, texte, chemin, avec_lignes=True)

    for empreinte, message in _messages_de_commit(racine, interdits.commits):
        for terme in interdits.termes:
            trouvailles += _chercher(terme, message, f"commit {empreinte}", avec_lignes=False)

    return tuple(trouvailles)
