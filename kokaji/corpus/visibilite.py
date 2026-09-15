"""La pratique reste à celui qui pratique — RFC-004 §5, SPECS R12.4.

Un ha porte désormais deux champs de plus dans son en-tête : son **praticien**,
et sa **visibilité**. Le second n'a que deux valeurs, `privee` et `verse`, et le
défaut est `privee` — y compris pour un ha écrit avant ce RFC, qui n'a aucun de
ces champs. Un ha muet est un ha privé : c'est la seule lecture qui ne crée pas
de fuite rétroactive.

Attention au mot. Kokaji employait déjà **verser** au sens « faire entrer un ha
au corpus depuis le journal ». Le RFC-004 lui donne un second sens, « rendre
visible aux co-auteurs ». Les deux gestes existent et ne se recouvrent pas : un
ha est versé au corpus dès sa capture, et versé aux co-auteurs seulement si son
praticien le décide. Le code ne nomme donc jamais le second `verser` — il parle
de `visibilite`, et rien d'autre.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from ..comptes.modele import PRIVEE, VERSE, VISIBILITES
from .depot import depot_pour, ref_de

__all__ = ["Acces", "acces", "lisible_par", "regler_visibilite"]


@dataclass(frozen=True)
class Acces:
    """Ce que l'en-tête d'un ha dit de son appartenance."""

    praticien: str
    visibilite: str

    @property
    def orpheline(self) -> bool:
        """Aucun praticien inscrit — un ha d'avant le RFC-004.

        On ne peut ni l'attribuer ni le rendre public par défaut. Il reste donc
        lisible du seul praticien connu : personne. C'est volontairement
        inconfortable — une reprise se fait à la main, en connaissance de cause.
        """
        return not self.praticien


def _entete(dossier) -> dict:
    return depot_pour().entete(ref_de(dossier))


def acces(dossier: Path) -> Acces:
    """Le praticien et la visibilité d'un ha. Privé par défaut, toujours."""
    entete = _entete(dossier)
    visibilite = str(entete.get("visibilite") or PRIVEE)
    return Acces(
        praticien=str(entete.get("praticien") or ""),
        # Une valeur qu'on ne reconnaît pas est traitée comme privée : devant
        # une donnée abîmée, on se ferme, on ne s'ouvre pas.
        visibilite=visibilite if visibilite in VISIBILITES else PRIVEE,
    )


def lisible_par(dossier: Path, utilisateur_id: str, role: str) -> bool:
    """Cette personne peut-elle lire ce ha en entier — transcript et kin compris ?

    Trois cas, et le troisième est l'exigence R12.4 :

    - son praticien, toujours ;
    - un membre du harness, si le ha est versé ;
    - **le propriétaire du harness, non**, tant que le ha n'est pas versé.
      Posséder le harness ne donne pas la pratique d'autrui.
    """
    porte = acces(dossier)
    if porte.orpheline:
        return False
    if porte.praticien == utilisateur_id:
        return True
    if porte.visibilite != VERSE:
        return False
    return role in ("proprietaire", "contributeur")


def regler_visibilite(dossier: Path, visibilite: str, par: str) -> None:
    """Verse un ha aux co-auteurs, ou le reprend. Geste du praticien seul.

    Le versement est révocable — le RFC le dit — mais reprendre n'efface pas ce
    qui a déjà été calculé : les agrégats demeurent. On ne réécrit donc rien
    d'autre que l'en-tête.
    """
    if visibilite not in VISIBILITES:
        raise ValueError(f"visibilité hors liste : {visibilite!r} (attendu : {VISIBILITES})")

    porte = acces(dossier)
    if porte.praticien != par or not par:
        raise PermissionError("seul le praticien d'un ha règle sa visibilité")

    depot = depot_pour()
    ref = ref_de(dossier)
    texte = depot.fiche(ref) or ""
    avant, entete, apres = texte.split("---", 2)
    donnees = yaml.safe_load(entete) or {}
    donnees["visibilite"] = visibilite
    depot.ecrire_fiche(
        ref, avant + "---" + yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False) + "---" + apres
    )
