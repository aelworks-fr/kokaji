"""Le deuxième étage de l'évaluation — le juge (SPECS §5 R5.5).

L'étage déterministe compte ce qui se compte. Beaucoup de variables de design ne
se comptent pas : « le livrable n'affirme-t-il que ce qui a été dit ? » ne se
mesure pas par une expression régulière.

Kokaji fournit le mécanisme, **le harness fournit la grille** : les variables de
design vivent dans son registre, avec la question qu'elles posent. Aucune
question n'est écrite ici.

Trois règles tiennent ce module :

- **Une accusation demande une preuve ; un acquittement, non.** Seul un verdict
  `non-tenue` doit citer le tour qui le fonde, et cette citation doit se
  retrouver **littéralement dans la prose de l'échange** — une citation inventée
  est rejetée. Exiger une citation pour `tenue` reviendrait à demander la preuve
  d'une absence.
- **Un bloc d'état ne prouve rien.** Il dit ce que le kata *déclare*, pas ce
  qu'il *fait* : les blocs sont retirés de la matière citable.
- **`indecidable` est une réponse.** Forcer un binaire fabriquerait de la
  certitude là où la session ne tranche pas.
- **Un verdict est un avis, pas une mesure.** Le modèle qui l'a rendu est
  inscrit à côté, et rien ne l'agrège en score.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

import yaml

from ...hds import Harness
from .client import Passerelle, PasserelleInjoignable

__all__ = ["Verdict", "grille", "grille_conduite", "juger", "juger_conduite"]

BLOC = re.compile(r"```json\s*(\[.*?\]|\{.*?\})\s*```", re.DOTALL)
VERDICTS = ("tenue", "non-tenue", "indecidable")


@dataclass(frozen=True)
class Verdict:
    variable: str
    verdict: str  # tenue | non-tenue | indecidable | illisible
    tour: int | None
    citation: str
    motif: str
    juge: str

    @property
    def fonde(self) -> bool:
        """Seule une accusation demande une preuve.

        On ne cite pas la preuve d'une absence : exiger un extrait pour `tenue`
        forcerait le juge à en inventer un, ou à se taire — mesuré, il se tait.
        """
        return self.verdict != "non-tenue" or bool(self.citation.strip())

    def __str__(self) -> str:
        ou = f" (tour {self.tour})" if self.tour else ""
        return f"[{self.variable}] {self.verdict}{ou} — {self.motif}"


def grille(harness: Harness) -> dict[str, str]:
    """Les variables de design déclarées par le harness, avec leur question."""
    donnees = yaml.safe_load(harness.trempe.registre.read_text(encoding="utf-8")) or {}
    variables = donnees.get("design_exerce") or {}
    return {str(nom): str(question).strip() for nom, question in variables.items()}


def grille_conduite(harness: Harness) -> dict[str, str]:
    """Le contrat de conduite, nature par nature — déclaré par le harness.

    RFC-003 §3 donne cinq conduites ; ce qu'elles veulent dire dans un domaine
    donné n'appartient pas à Kokaji. Le harness écrit donc, pour chaque nature,
    la question qui juge si le kata a tenu sa conduite. Aucune n'est écrite ici.
    """
    donnees = yaml.safe_load(harness.trempe.registre.read_text(encoding="utf-8")) or {}
    contrats = donnees.get("conduite_par_nature") or {}
    return {str(nature): str(question).strip() for nature, question in contrats.items()}


def juger_conduite(
    harness: Harness,
    tours: list,
    nature: str,
    passerelle: Passerelle,
    modele: str,
    temperature: float | None = 0.0,
) -> Verdict | None:
    """La conformité de conduite pour la nature **diagnostiquée** (RFC-003 §4).

    On juge le kata sur la conduite qu'appelait *son* diagnostic, pas sur celle
    qu'appelait la nature réelle : sinon un diagnostic raté serait puni deux
    fois, et l'on ne saurait plus si la forme sait tenir une conduite.

    Rend `None` quand le harness n'a pas écrit de contrat pour cette nature —
    l'absence de grille est un silence, pas un échec.
    """
    contrats = grille_conduite(harness)
    question = contrats.get(nature)
    if not question or not tours:
        return None

    nom = f"conduite:{nature}"
    try:
        reponse = passerelle.completer(
            modele,
            [
                {"role": "system", "content": _consigne(nom, question)},
                {"role": "user", "content": _transcript(tours)},
            ],
            temperature,
        )
    except PasserelleInjoignable as err:
        return Verdict(nom, "illisible", None, "", f"juge injoignable : {err}", modele)
    verdicts = _lire(reponse, {nom: question}, modele, _transcript(tours))
    return verdicts[0] if verdicts else None


def _consigne(nom: str, question: str) -> str:
    """Une consigne **à charge** : chercher le manquement, pas la conformité.

    Une consigne neutre obtient une approbation uniforme — mesuré : huit verdicts
    sur huit en « tenue » au premier essai. On demande donc l'inverse de ce qu'on
    veut établir, et la conformité ne s'obtient que faute d'avoir trouvé mieux.
    """
    return (
        "Tu relis un échange terminé pour y chercher **un manquement précis**, et\n"
        "un seul :\n\n"
        f"> {question}\n\n"
        "Ton travail est de trouver le tour où la forme **échoue** à tenir cela.\n"
        "Cherche d'abord à charge : relis en te demandant « où est-ce que ça casse ? ».\n"
        "Tu ne conclus `tenue` que si tu as cherché un manquement et n'en as trouvé\n"
        "aucun — jamais parce que l'échange se lit bien.\n\n"
        "Tu ne juges ni le sujet, ni la personne, ni la qualité du résultat.\n\n"
        "Réponds par ce bloc, et rien d'autre :\n\n"
        "```json\n"
        '{ "variable": "' + nom + '", "verdict": "non-tenue | tenue | indecidable",\n'
        '  "tour": 0, "citation": "", "motif": "" }\n'
        "```\n\n"
        "Si tu conclus `non-tenue`, `citation` est un extrait **littéral** du texte\n"
        "que tu as sous les yeux — recopié mot pour mot, pas reformulé. Une citation\n"
        "que je ne retrouve pas dans l'échange invalide ton verdict. Si tu conclus\n"
        "`tenue`, laisse `citation` vide : on ne cite pas la preuve d'une absence.\n"
        "Dis plutôt dans `motif` ce que tu as cherché et n'as pas trouvé.\n\n"
        "**`indecidable` est une réponse pleine.** Si l'échange ne met pas cette\n"
        "question à l'épreuve, dis-le : inventer un verdict serait pire que se taire."
    )


BLOC_CODE = re.compile(r"```.*?```", re.DOTALL)


def _transcript(tours: list) -> str:
    """L'échange, **blocs d'état retirés**.

    Un bloc dit ce que le kata déclare, pas ce qu'il fait. Le laisser lisible
    l'offre en preuve : au premier essai, le juge a cité `hypotheses_de_valeur:
    en_cours` — la faute même que l'étage déterministe signalait — comme preuve
    que la forme distinguait bien l'établi du supposé.
    """
    lignes = []
    for rang, tour in enumerate(tours, 1):
        dit = BLOC_CODE.sub("", tour.reponse or "").strip()
        lignes += [f"## Tour {rang}", "", f"[porteur] {tour.porteur}", "", f"[kata] {dit}", ""]
    return "\n".join(lignes)


def _empreinte(texte: str) -> str:
    return " ".join((texte or "").split()).lower()


def _citee(citation: str, transcript: str) -> bool:
    """La citation se retrouve-t-elle littéralement dans l'échange ?

    Sur un extrait court, on tolère la troncature : les trente premiers
    caractères doivent y être. Au-delà, c'est une invention.
    """
    aiguille = _empreinte(citation)[:40]
    return bool(aiguille) and aiguille in _empreinte(transcript)


def juger(
    harness: Harness,
    tours: list,
    passerelle: Passerelle,
    modele: str,
    variables: tuple[str, ...] = (),
    temperature: float | None = 0.0,
) -> tuple[Verdict, ...]:
    """Rend un verdict par variable de design, fondé sur un tour cité."""
    toutes = grille(harness)
    if variables:
        inconnues = sorted(set(variables) - set(toutes))
        if inconnues:
            raise ValueError(
                f"variable(s) hors du registre : {', '.join(inconnues)} "
                f"(connues : {', '.join(sorted(toutes))})"
            )
        toutes = {nom: toutes[nom] for nom in variables}
    if not toutes or not tours:
        return ()

    # Une question à la fois : posées ensemble, elles s'entraînent vers une
    # réponse uniforme — la seconde hérite du ton de la première.
    transcript = _transcript(tours)
    verdicts = []
    for nom, question in toutes.items():
        try:
            reponse = passerelle.completer(
                modele,
                [
                    {"role": "system", "content": _consigne(nom, question)},
                    {"role": "user", "content": transcript},
                ],
                temperature,
            )
        except PasserelleInjoignable as err:
            verdicts.append(
                Verdict(nom, "illisible", None, "", f"juge injoignable : {err}", modele)
            )
            continue
        verdicts += _lire(reponse, {nom: question}, modele, transcript)
    return tuple(verdicts)


def _lire(
    reponse: str, variables: dict[str, str], modele: str, transcript: str = ""
) -> tuple[Verdict, ...]:
    """Un juge qui répond mal ne fait pas tomber l'évaluation : il est constaté."""
    trouve = BLOC.search(reponse or "")
    try:
        brut = json.loads(trouve.group(1)) if trouve else json.loads(reponse)
    except (json.JSONDecodeError, AttributeError, TypeError):
        return tuple(
            Verdict(nom, "illisible", None, "", "le juge n'a pas rendu de tableau lisible", modele)
            for nom in variables
        )

    entrees = brut if isinstance(brut, list) else [brut]
    par_nom = {
        str(e.get("variable")): e for e in entrees if isinstance(e, dict) and e.get("variable")
    }

    verdicts = []
    for nom in variables:
        entree = par_nom.get(nom)
        if entree is None:
            verdicts.append(Verdict(nom, "illisible", None, "", "variable non traitée", modele))
            continue

        rendu = str(entree.get("verdict") or "").strip()
        if rendu not in VERDICTS:
            verdicts.append(
                Verdict(nom, "illisible", None, "", f"verdict hors grille — {rendu!r}", modele)
            )
            continue

        tour = entree.get("tour")
        verdict = Verdict(
            variable=nom,
            verdict=rendu,
            tour=int(tour) if isinstance(tour, int | float) and tour else None,
            citation=str(entree.get("citation") or ""),
            motif=str(entree.get("motif") or ""),
            juge=modele,
        )
        # Une accusation sans preuve n'est pas une accusation.
        if not verdict.fonde:
            verdict = Verdict(
                nom, "illisible", None, "", "manquement affirmé sans citation à l'appui", modele
            )
        # Et une preuve qu'on ne retrouve pas dans l'échange n'est pas une preuve.
        elif transcript and verdict.citation and not _citee(verdict.citation, transcript):
            verdict = Verdict(
                nom, "illisible", None, verdict.citation,
                "citation introuvable dans l'échange — verdict écarté", modele,
            )
        verdicts.append(verdict)
    return tuple(verdicts)
