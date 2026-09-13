"""Le lint de resserrage — ce que la pratique tient vraiment (RFC-002 §6.4).

Le régime « prudence » permet de sous-promettre : un `produit` en dessous de ce
que la pratique livre reste conforme. C'est ce qui rend les contrats stables
pendant que les kata s'améliorent.

Le prix en est nommé par la RFC elle-même : **la composition du slack**. Trois
kata qui sous-promettent un peu font un contrat de bout en bout très en dessous
de la pratique — sur une chaîne longue, le savoir *déclaré* s'appauvrit par
accumulation.

Ce lint mesure l'écart et **propose** un resserrage. Il ne l'applique jamais :
modifier un f♯ est une version majeure du kata, et cette décision appartient au
forgeron du harness (RFC-002 §3).

Une garantie est un **minimum** : ce qu'on peut promettre est donc le statut le
plus faible observé, jamais le plus fréquent. Un seul ha en dessous suffit à
retenir la promesse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from ...forge.coupe import champ_nu
from ...hds import Harness, Kata

__all__ = ["Observation", "Proposition", "observer", "proposer"]

MINIMUM_DEFAUT = 3


@dataclass(frozen=True)
class Observation:
    """Ce qu'un champ a atteint, ha par ha."""

    champ: str
    declare: str
    statuts: tuple[str, ...]  # un par ha, dans l'ordre du corpus

    @property
    def observes(self) -> int:
        return len(self.statuts)


@dataclass(frozen=True)
class Proposition:
    champ: str
    declare: str
    propose: str
    sur: int
    total: int

    def __str__(self) -> str:
        return (
            f"{self.champ} : déclaré `{self.declare}`, tenu à `{self.propose}` "
            f"sur {self.sur}/{self.total} ha"
        )


def _etat_final(dossier: Path) -> dict | None:
    """Le dernier bloc lisible d'un ha — l'état qu'il laisse."""
    fichier = dossier / "etats.jsonl"
    if not fichier.is_file():
        return None
    dernier = None
    for ligne in fichier.read_text(encoding="utf-8").splitlines():
        if not ligne.strip():
            continue
        try:
            releve = json.loads(ligne)
        except json.JSONDecodeError:
            continue
        etat = releve.get("etat") or {}
        if "__illisible__" not in etat and isinstance(etat.get("champs"), dict):
            dernier = etat
    return dernier


def _kata_du_ha(dossier: Path) -> str:
    fiche = dossier / "fiche.md"
    if not fiche.is_file():
        return ""
    texte = fiche.read_text(encoding="utf-8")
    entete = yaml.safe_load(texte.split("---")[1]) if texte.startswith("---") else {}
    return str((entete or {}).get("kata") or "")


def observer(harness: Harness, kata: Kata, corpus: Path | None = None) -> list[Observation]:
    """Ce que chaque champ promis a réellement atteint, à travers le corpus."""
    racine = Path(corpus) if corpus is not None else harness.corpus
    finaux = [
        etat
        for dossier in sorted(racine.glob("CAS-*"))
        if _kata_du_ha(dossier) == kata.id and (etat := _etat_final(dossier)) is not None
    ]

    observations = []
    for reference, declare in kata.produit:
        champ = champ_nu(reference)
        statuts = tuple(
            str(etat["champs"].get(champ))
            for etat in finaux
            if etat["champs"].get(champ) is not None
        )
        observations.append(Observation(champ=reference, declare=declare, statuts=statuts))
    return observations


def proposer(
    harness: Harness, observation: Observation, minimum: int = MINIMUM_DEFAUT
) -> Proposition | None:
    """Le statut qu'on pourrait garantir — s'il excède durablement le déclaré.

    « Durablement » veut dire : observé sur au moins `minimum` ha, et **jamais
    démenti**. Une garantie qu'un seul ha contredit n'est pas une garantie.
    """
    if observation.observes < minimum:
        return None

    connus = [s for s in observation.statuts if s in harness.etat.statuts_champ]
    if len(connus) < minimum:
        return None  # un statut hors taxonomie ne garantit rien

    # Le plus faible observé : c'est le seul qu'on puisse promettre.
    plancher = max(connus, key=harness.rang_statut)
    if plancher == observation.declare or not harness.couvre(plancher, observation.declare):
        return None  # égal, ou en dessous — le carré s'en occupe

    return Proposition(
        champ=observation.champ,
        declare=observation.declare,
        propose=plancher,
        sur=len(connus),
        total=observation.observes,
    )


def fragment(kata: Kata, propositions: list[Proposition]) -> str:
    """Le `produit` qu'on obtiendrait — à coller, jamais appliqué d'office."""
    resserres = {p.champ: p.propose for p in propositions}
    lignes = [f"  - id: {kata.id}", "    produit:"]
    for reference, declare in kata.produit:
        statut = resserres.get(reference, declare)
        marque = "   # resserré" if reference in resserres else ""
        lignes.append(f"      - {reference}: {statut}{marque}")
    return "\n".join(lignes)
