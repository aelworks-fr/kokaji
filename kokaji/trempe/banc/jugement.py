"""Le judge sur grille — RFC-008 §7, la priorité v1 de l'évaluation.

(Le module s'appelle `jugement` et non `grille` : le paquet expose déjà une
fonction `grille` — celle du registre du juge de conduite — et un module du
même nom la masquerait à l'import, en silence.)

Un harness adopté n'a ni contrats ni blocs d'état : la seule matière est le
transcript, et la seule évaluation possible est un avis porté dessus. Le
harness déclare sa grille (`trempe.grille_judge` : question + échelle) ;
Kokaji applique chaque critère au transcript et rattache les scores au ha.
Le mécanisme est générique — un harness natif peut déclarer une grille aussi.

La discipline du juge est reconduite de l'étage de conduite :

- **juge ≠ pratiquant** — le moteur qui juge n'est pas celui qui a conversé.
  Un modèle qui note sa propre copie a un avis sur lui-même, pas sur elle.
- **un score est un avis, pas une mesure** — le juge est inscrit à côté de
  chaque note, l'échelle avec, et rien n'agrège les critères en score global.
- **`null` est une réponse** — un critère que le transcript ne permet pas de
  noter se dit ; forcer un chiffre fabriquerait de la certitude.
- **les blocs d'état sont retirés de la matière** — ils disent ce que le kata
  déclare, pas ce qu'il fait.

Les scores s'écrivent dans `jugements.jsonl`, à côté de la fiche — en append,
jamais en écrasant : deux juges, ou deux passages du même juge, se comparent
au lieu de s'effacer. Chaque ligne porte de quoi comparer par
`(version, moteur, kata, cible)`.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ...hds import Critere, Harness
from .client import Passerelle, PasserelleInjoignable

__all__ = ["JugeRefuse", "Jugement", "Score", "juger_grille"]

BLOC = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
BLOC_ETAT = re.compile(r"```json\s+kokaji_state\s*.*?```", re.DOTALL)


class JugeRefuse(Exception):
    """Le jugement n'a pas eu lieu, et la raison est nommée."""


@dataclass(frozen=True)
class Score:
    critere: str
    question: str
    echelle: str
    note: int | None  # None : le juge n'a pas pu noter, et l'a dit
    motif: str
    juge: str


@dataclass(frozen=True)
class Jugement:
    """Les scores d'un ha, avec de quoi les comparer (RFC-008 §7)."""

    ha: str
    kata: str
    cible: str
    moteur_pratiquant: str
    version_coupe: str
    juge: str
    le: str
    scores: tuple[Score, ...]


def _consigne(critere: Critere) -> str:
    bas, haut = critere.bornes
    return (
        "Tu notes un échange déjà terminé, sur un seul critère. Tu ne juges\n"
        "que ce que le transcript montre — pas ce qu'il aurait pu montrer.\n\n"
        f"Le critère : {critere.question}\n\n"
        f"L'échelle : de {bas} (pas du tout) à {haut} (pleinement), entiers seuls.\n"
        "Si le transcript ne permet pas de noter ce critère, `note` vaut null\n"
        "et `motif` dit pourquoi — ne force jamais un chiffre.\n\n"
        "Réponds par ce bloc, seul, sans une ligne autour :\n\n"
        "```json\n"
        f'{{ "critere": "{critere.id}", "note": <entier ou null>, "motif": "<une phrase>" }}\n'
        "```"
    )


def _matiere(transcript: str) -> str:
    """Le transcript, blocs d'état retirés — ils déclarent, ils ne prouvent pas."""
    return BLOC_ETAT.sub("", transcript or "").strip()


def _lire(reponse: str, critere: Critere, juge: str) -> Score:
    """Un juge qui répond mal ne fait pas tomber la campagne : il est constaté."""
    trouve = BLOC.search(reponse or "")
    try:
        brut = json.loads(trouve.group(1) if trouve else reponse)
    except (json.JSONDecodeError, TypeError):
        brut = None
    if not isinstance(brut, dict):
        return Score(critere.id, critere.question, critere.echelle, None,
                     "le juge n'a pas rendu de bloc lisible", juge)

    vise = str(brut.get("critere") or "").strip()
    if vise and vise != critere.id:
        # Le juge a répondu à côté : prendre sa note pour celle du critère posé
        # rattacherait un avis au mauvais objet, sans que rien ne le montre.
        return Score(critere.id, critere.question, critere.echelle, None,
                     f"le juge a répondu sur {vise!r}", juge)

    note, motif = brut.get("note"), str(brut.get("motif") or "").strip()
    if note is None:
        return Score(critere.id, critere.question, critere.echelle, None,
                     motif or "le juge n'a pas pu noter, sans dire pourquoi", juge)
    bas, haut = critere.bornes
    if not isinstance(note, int) or isinstance(note, bool) or not bas <= note <= haut:
        # Hors échelle n'est pas une note basse : c'est un juge qui n'a pas
        # suivi la consigne, et le dire évite qu'un 7 sur 5 entre au corpus.
        return Score(critere.id, critere.question, critere.echelle, None,
                     f"note hors échelle {critere.echelle} — {note!r}", juge)
    return Score(critere.id, critere.question, critere.echelle, int(note), motif, juge)


def juger_grille(
    harness: Harness,
    dossier: Path,
    passerelle: Passerelle,
    modele: str,
    temperature: float | None = 0.0,
) -> Jugement:
    """Applique la grille du harness au transcript d'un ha, et rattache les scores.

    Une question à la fois : posées ensemble, elles s'entraînent vers une
    réponse uniforme — la seconde hérite du ton de la première.
    """
    if not harness.trempe.grille_judge:
        raise JugeRefuse(
            f"{harness.id} : aucune grille déclarée — `trempe.grille_judge` au manifest"
        )

    fiche = (Path(dossier) / "fiche.md").read_text(encoding="utf-8")
    entete = yaml.safe_load(fiche.split("---")[1]) or {}
    pratiquant = str(entete.get("moteur") or "")
    if modele and pratiquant and modele == pratiquant:
        raise JugeRefuse(
            f"juge et pratiquant confondus : {modele} — un modèle qui note sa "
            "propre copie a un avis sur lui-même, pas sur elle"
        )

    matiere = _matiere(
        (Path(dossier) / "transcript.md").read_text(encoding="utf-8")
    )
    if not matiere:
        raise JugeRefuse(f"{Path(dossier).name} : transcript vide — rien à juger")

    scores = []
    for critere in harness.trempe.grille_judge:
        try:
            reponse = passerelle.completer(
                modele,
                [
                    {"role": "system", "content": _consigne(critere)},
                    {"role": "user", "content": matiere},
                ],
                temperature,
            )
        except PasserelleInjoignable as err:
            scores.append(Score(critere.id, critere.question, critere.echelle, None,
                                f"juge injoignable : {err}", modele))
            continue
        scores.append(_lire(reponse, critere, modele))

    jugement = Jugement(
        ha=Path(dossier).name.split("-")[0] + "-" + Path(dossier).name.split("-")[1],
        kata=str(entete.get("kata") or ""),
        cible=str(entete.get("cible") or ""),
        moteur_pratiquant=pratiquant,
        version_coupe=str(entete.get("version_coupe") or ""),
        juge=modele,
        le=datetime.now(UTC).isoformat(),
        scores=tuple(scores),
    )
    with (Path(dossier) / "jugements.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(jugement), ensure_ascii=False) + "\n")
    return jugement


def deja_juge(dossier: Path, juge: str, version_coupe: str) -> bool:
    """Ce juge a-t-il déjà noté cette version de la coupe ?

    Rejuger la même version par le même juge n'apprend rien et coûte : la
    campagne saute ce qui est fait, et `--rejuger` force. Une autre version,
    ou un autre juge, est une nouvelle information — jamais sautée.
    """
    fichier = Path(dossier) / "jugements.jsonl"
    if not fichier.is_file():
        return False
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            fait = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        if fait.get("juge") == juge and fait.get("version_coupe") == version_coupe:
            return True
    return False
