"""L'étage déterministe de l'évaluation (SPECS §5 R5.5).

Deux familles, qui ne se mélangent pas :

- les **checks du harness**, déclarés dans son manifest. Kokaji exécute des
  types de règles, il n'en écrit aucune : les interdits appartiennent au harness.
- les **invariants de Kokaji**, qui portent sur la structure qu'il impose —
  aujourd'hui le bloc d'état et lui seul.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ...etat import extraire, fautes_de_bloc
from ...hds import Harness, Kata

# Le contenu est pris tel quel, sans exiger qu'il ressemble à du JSON : un bloc
# annoncé mais illisible est une faute à constater, pas un bloc à ignorer.
BLOC_CODE = re.compile(r"```.*?```", re.DOTALL)
SEPARATEUR = re.compile(r"\n\s*\n")


@dataclass(frozen=True)
class Constat:
    regle: str
    tour: int | None
    message: str

    def __str__(self) -> str:
        ou = f"tour {self.tour}" if self.tour else "session"
        return f"[{self.regle}] {ou} : {self.message}"


class RegleInconnue(Exception):
    """Le harness déclare un type de règle que Kokaji ne sait pas exécuter."""


TYPES_CONNUS = frozenset({"regex-par-tour", "regex-par-bloc", "interdit"})


def blocs_etat(texte: str) -> list[dict]:
    """Les blocs d'état d'une réponse — délégué au module partagé."""
    return extraire(texte)


def _regex_par_tour(regle: dict, tours: list) -> list[Constat]:
    motif = re.compile(regle.get("motif") or "")
    ignorer = re.compile(regle["ignorer"]) if regle.get("ignorer") else None
    # `or 1` transformait un maximum de **zéro** en un : une règle qui dit
    # « aucune occurrence » devenait « au plus une », en silence. Zéro est une
    # valeur, pas une absence.
    declare = regle.get("maximum")
    maximum = int(declare) if declare is not None else 1
    message = regle.get("message") or f"plus de {maximum} occurrence(s)"

    constats = []
    for rang, tour in enumerate(tours, 1):
        lignes = [
            ligne
            for ligne in (tour.reponse or "").split("\n")
            if not (ignorer and ignorer.search(ligne))
        ]
        compte = sum(len(motif.findall(ligne)) for ligne in lignes)
        if compte > maximum:
            constats.append(Constat(regle["id"], rang, f"{message} (compté : {compte})"))
    return constats


def _regex_par_bloc(regle: dict, tours: list) -> list[Constat]:
    """Compte les **paragraphes** qui matchent, pas les occurrences.

    Compter les symboles confond trois choses : une question qui propose ses
    options en ligne, une question de l'interlocuteur citée, et deux questions
    réellement distinctes. Le paragraphe est le grain qui les sépare — une
    question et ses options tiennent ensemble, deux questions distinctes se
    rédigent séparément. Proxy assumé, et bien meilleur que le précédent : sur le
    journal, 16 % de tours signalés contre 34 %, avec un maximum de 3 au lieu
    de 8 pour un tour qui pose deux questions.
    """
    motif = re.compile(regle.get("motif") or "")
    ignorer = re.compile(regle["ignorer"]) if regle.get("ignorer") else None
    # `or 1` transformait un maximum de **zéro** en un : une règle qui dit
    # « aucune occurrence » devenait « au plus une », en silence. Zéro est une
    # valeur, pas une absence.
    declare = regle.get("maximum")
    maximum = int(declare) if declare is not None else 1
    message = regle.get("message") or f"plus de {maximum} bloc(s) concerné(s)"

    constats = []
    for rang, tour in enumerate(tours, 1):
        # Les blocs de code ne sont pas de la prose : ils ne questionnent pas.
        texte = BLOC_CODE.sub("", tour.reponse or "")
        compte = 0
        for bloc in SEPARATEUR.split(texte):
            lignes = [
                ligne for ligne in bloc.split("\n") if not (ignorer and ignorer.search(ligne))
            ]
            if motif.search("\n".join(lignes)):
                compte += 1
        if compte > maximum:
            constats.append(Constat(regle["id"], rang, f"{message} (compté : {compte})"))
    return constats


def _interdit(regle: dict, tours: list) -> list[Constat]:
    motifs = [m.lower() for m in regle.get("motifs") or []]
    message = regle.get("message") or "formulation interdite"
    constats = []
    for rang, tour in enumerate(tours, 1):
        texte = (tour.reponse or "").lower()
        for motif in motifs:
            if motif in texte:
                constats.append(Constat(regle["id"], rang, f"{message} — « {motif} »"))
    return constats


def checks_du_harness(harness: Harness, tours: list) -> list[Constat]:
    constats: list[Constat] = []
    for regle in harness.trempe.checks_session:
        type_regle = regle.get("type")
        if type_regle not in TYPES_CONNUS:
            raise RegleInconnue(
                f"{regle.get('id')} : type inconnu — {type_regle!r} "
                f"(connus : {', '.join(sorted(TYPES_CONNUS))})"
            )
        if type_regle == "regex-par-tour":
            constats += _regex_par_tour(regle, tours)
        elif type_regle == "regex-par-bloc":
            constats += _regex_par_bloc(regle, tours)
        else:
            constats += _interdit(regle, tours)
    return constats


def invariants_kokaji(
    harness: Harness, kata: Kata, champs_admis: tuple[str, ...], tours: list
) -> list[Constat]:
    """Ce que Kokaji impose lui-même : la bonne forme du bloc d'état.

    La règle vit dans `kokaji.etat`, partagée avec le middleware : une seule
    définition de « bloc bien formé », sinon les deux dérivent.
    """
    # Les options se déclarent au fil de la session : une décision peut citer
    # une option nommée plusieurs tours plus tôt.
    connues: set[str] = set()
    constats: list[Constat] = []

    for rang, tour in enumerate(tours, 1):
        for etat in extraire(tour.reponse):
            for regle, message in fautes_de_bloc(harness, kata, champs_admis, etat, connues):
                constats.append(Constat(regle, rang, message))
    return constats
