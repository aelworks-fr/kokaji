"""Le bloc d'état — extraction et bonne forme (SPECS §7).

Ce module est partagé : le banc s'en sert pour évaluer une session jouée, le
middleware pour valider ce qu'il capture. Une seule définition de « bloc bien
formé », sinon les deux dérivent.
"""

from __future__ import annotations

import json
import re

from .forge.coupe import STATUTS_OPTION
from .hds import Harness, Kata

BLOC_ETAT = re.compile(r"```json\s+kokaji_state\s*(.*?)```", re.DOTALL)
CONFIANCES = frozenset({"faible", "moyen", "eleve"})

__all__ = ["CONFIANCES", "extraire", "fautes_de_bloc"]


def extraire(texte: str) -> list[dict]:
    """Les blocs annoncés dans une réponse — même ceux qui ne se lisent pas.

    Un bloc illisible est rendu avec la clé `__illisible__` : c'est une faute à
    constater, pas un bloc à ignorer.
    """
    trouves = []
    for m in BLOC_ETAT.finditer(texte or ""):
        try:
            trouves.append(json.loads(m.group(1))["kokaji_state"])
        except (json.JSONDecodeError, KeyError, TypeError):
            trouves.append({"__illisible__": m.group(1)[:200]})
    return trouves


def _voisine(valeur, taxonomies: dict[str, tuple[str, ...]]) -> str:
    """La taxonomie voisine où cette valeur existe vraiment — NOTE-0005.

    « Hors taxonomie » ne dit pas d'où vient la valeur. Or le modèle ne l'a pas
    inventée : il l'a prise dans une liste voisine que le harness déclare aussi.
    Deux taxonomies qui se recouvrent produisent cette confusion-là, et un refus
    anonyme la rend indiscernable d'une valeur en l'air.

    Nommer la voisine change le refus en diagnostic : on sait alors s'il faut
    corriger le modèle, ou séparer deux listes qui se ressemblent trop.
    """
    for nom, valeurs in taxonomies.items():
        if valeur in valeurs:
            return nom
    return ""


def _dit_la_voisine(valeur, taxonomies: dict[str, tuple[str, ...]]) -> str:
    voisine = _voisine(valeur, taxonomies)
    return f" — valeur de `{voisine}`, pas de celle-ci" if voisine else ""


def fautes_de_bloc(
    harness: Harness, kata: Kata, champs_admis: tuple[str, ...], etat: dict,
    options_connues: set[str] | None = None,
    natures: tuple[str, ...] = (),
) -> list[tuple[str, str]]:
    """Les manquements d'un bloc à la structure imposée : (règle, message).

    `natures` — la taxonomie du RFC-003, déclarée par kata dans sa source. Elle
    n'est pas vérifiée ici : elle sert à **reconnaître** une valeur puisée dans
    la mauvaise liste, ce qui est le défaut réel de NOTE-0005.
    """
    if "__illisible__" in etat:
        return [("etat-bien-forme", "bloc illisible")]

    connues = options_connues if options_connues is not None else set()
    fautes: list[tuple[str, str]] = []

    champs = etat.get("champs")
    if not isinstance(champs, dict):
        fautes.append(("etat-bien-forme", "`champs` absent ou mal formé"))
    else:
        for nom, statut in champs.items():
            if nom not in set(champs_admis):
                fautes.append(("etat-champs-declares", f"champ hors gabarit — {nom!r}"))
            if statut not in set(harness.etat.statuts_champ):
                ailleurs = _dit_la_voisine(
                    statut,
                    {
                        "natures": natures,
                        "statuts_hypothese": harness.etat.statuts_hypothese,
                        "confiances": CONFIANCES,
                    },
                )
                fautes.append(
                    (
                        "etat-statuts-declares",
                        f"statut hors taxonomie — {nom}={statut!r}{ailleurs}",
                    )
                )

    for hypothese in etat.get("hypotheses") or []:
        if not isinstance(hypothese, dict):
            fautes.append(("etat-bien-forme", "hypothèse mal formée"))
            continue
        if hypothese.get("statut") not in set(harness.etat.statuts_hypothese):
            ailleurs = _dit_la_voisine(
                hypothese.get("statut"),
                {"natures": natures, "statuts_champ": harness.etat.statuts_champ},
            )
            fautes.append(
                ("etat-statuts-declares",
                 f"statut d'hypothèse hors taxonomie — {hypothese.get('statut')!r}{ailleurs}")
            )
        if hypothese.get("confiance") not in CONFIANCES:
            fautes.append(
                ("etat-statuts-declares",
                 f"confiance hors taxonomie — {hypothese.get('confiance')!r}")
            )

    suivants = {a.vers for a in harness.chaine.aretes if a.de == kata.id}
    pret = etat.get("pret_pour")
    if pret is not None and pret not in suivants:
        fautes.append(("etat-passage-declare", f"`pret_pour` hors chaîne — {pret!r}"))

    fautes += _fautes_options(harness, kata, etat, connues)
    return fautes


def _fautes_options(
    harness: Harness, kata: Kata, etat: dict, connues: set[str]
) -> list[tuple[str, str]]:
    """RFC-001 — ce que Kokaji impose aux options et aux décisions déclarées."""
    porte = "options" in etat or "decision" in etat
    if porte and not kata.emet_options:
        return [
            ("etat-options-declarees",
             "options ou décision émises par un kata qui ne les déclare pas")
        ]
    if not porte:
        return []

    noeuds = {n.id for n in harness.chaine.noeuds}
    fautes: list[tuple[str, str]] = []

    for option in etat.get("options") or []:
        if not isinstance(option, dict):
            fautes.append(("etat-options-declarees", "option mal formée"))
            continue
        identifiant = option.get("id")
        if not identifiant:
            fautes.append(("etat-options-declarees", "option sans identifiant"))
        else:
            connues.add(str(identifiant))
        if not str(option.get("libelle") or "").strip():
            fautes.append(
                ("etat-options-declarees", f"option sans libellé — {identifiant!r}")
            )
        if option.get("statut") not in STATUTS_OPTION:
            fautes.append(
                ("etat-statuts-declares",
                 f"statut d'option hors taxonomie — {option.get('statut')!r}")
            )
        noeud = option.get("noeud")
        if noeud and noeud not in noeuds:
            fautes.append(("etat-options-declarees", f"option hors chaîne — nœud {noeud!r}"))

    decision = etat.get("decision")
    if decision is None:
        return fautes
    if not isinstance(decision, dict):
        return fautes + [("etat-decision-coherente", "décision mal formée")]
    if not str(decision.get("libelle") or "").strip():
        fautes.append(("etat-decision-coherente", "décision sans libellé"))
    for sens in ("ferme", "ouvre"):
        for identifiant in decision.get(sens) or []:
            if str(identifiant) not in connues:
                fautes.append(
                    ("etat-decision-coherente",
                     f"`{sens}` cite une option jamais déclarée — {identifiant!r}")
                )
    return fautes
