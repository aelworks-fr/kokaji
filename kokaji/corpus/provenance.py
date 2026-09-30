"""L'encre de provenance d'un ha — observé ou rapporté (RFC-020 D20.2).

Un ha est **observé** quand il a été joué au dojo et capturé depuis le journal ;
**rapporté** quand il a été joué ailleurs, collé et déclaré par une personne.
La différence n'est pas une porte d'entrée — les deux entrent au corpus, au
même statut `brut` — mais un axe de lecture : toute vue qui montre le ha
montre son encre, et rien ne l'efface.

C'est pour cela que la provenance ne se règle nulle part. Elle se pose une
fois, à la naissance du ha, et les deux dépôts refusent ensuite toute fiche
qui la changerait ou la tairait : anonymiser, annoter, régler la visibilité,
promouvoir, exporter puis réimporter — aucun de ces gestes ne fait passer un
`rapporte` pour un `observe`. Un ha muet est un ha observé : avant cette RFC,
seule la capture écrivait des fiches.
"""

from __future__ import annotations

import yaml

__all__ = [
    "OBSERVE", "PROVENANCES", "RAPPORTE", "ProvenanceInalterable",
    "provenance_de", "verifier_inalterable",
]

OBSERVE = "observe"
RAPPORTE = "rapporte"
PROVENANCES = (OBSERVE, RAPPORTE)


class ProvenanceInalterable(ValueError):
    """Une fiche tente de changer, ou de taire, l'encre de provenance d'un ha."""


def provenance_de(entete: dict | None) -> str:
    """L'encre d'un ha depuis son en-tête — `observe` s'il n'en dit rien."""
    valeur = str((entete or {}).get("provenance") or "").strip()
    return valeur if valeur in PROVENANCES else OBSERVE


def _declaree(texte: str | None) -> str | None:
    """Ce que la fiche **déclare** — ou rien si elle ne déclare rien, ou ne se lit pas."""
    if not texte or not texte.startswith("---"):
        return None
    morceaux = texte.split("---", 2)
    if len(morceaux) < 3:
        return None
    try:
        donnees = yaml.safe_load(morceaux[1]) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(donnees, dict) or "provenance" not in donnees:
        return None
    return str(donnees.get("provenance") or "").strip()


def verifier_inalterable(ancienne: str | None, neuve: str) -> None:
    """Refuse la fiche `neuve` si elle change ou efface la provenance de `ancienne`.

    Trois refus, et un seul passage libre :

    - une provenance hors liste ne s'écrit jamais ;
    - une fiche qui déclarait une encre et la déclare autre : refusée ;
    - une fiche qui déclarait une encre et ne la déclare plus : refusée —
      taire, c'est laisser lire `observe` par défaut, donc maquiller ;
    - une fiche qui ne déclarait rien reçoit ce qu'on lui pose : c'est le
      rafraîchissement des ha d'avant la RFC-020, tous observés.
    """
    avant, apres = _declaree(ancienne), _declaree(neuve)
    if apres is not None and apres not in PROVENANCES:
        raise ProvenanceInalterable(
            f"provenance hors liste : {apres!r} (attendu : {', '.join(PROVENANCES)})"
        )
    if avant is None or avant not in PROVENANCES:
        return
    if apres is None:
        raise ProvenanceInalterable(
            f"la provenance `{avant}` de ce ha ne peut pas être tue : l'encre est indélébile (RFC-020 D20.2)"
        )
    if apres != avant:
        raise ProvenanceInalterable(
            f"un ha `{avant}` ne devient pas `{apres}` : l'encre est indélébile (RFC-020 D20.2)"
        )
