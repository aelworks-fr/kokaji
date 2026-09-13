"""La non-régression — rejouer un ha contre la coupe d'aujourd'hui (SPECS §5 R5.6).

Un ha porte la version de coupe qui l'a produit. Quand la source change, la
forge produit une autre coupe : les ha nés de l'ancienne deviennent **périmés**
— ils documentent une forme qui n'existe plus.

Le rejeu leur redonne la parole. Il reprend **les tours de l'interlocuteur tels
qu'ils ont été dits** et les rejoue contre la coupe actuelle. Même matière,
forme nouvelle : ce qui diffère vient de la forme, et de rien d'autre.

Deux règles :

- **Les deux côtés sont évalués avec les checks d'aujourd'hui.** Comparer un
  ancien verdict à un nouveau mêlerait deux changements — celui de la coupe et
  celui du check. On réévalue donc l'ancien transcript, on ne relit pas son
  ancienne note.
- **Un rejeu n'est pas la session d'origine.** L'interlocuteur y est une
  transcription, pas une personne : il ne réagit pas à ce que la nouvelle forme
  dit. Le rejeu montre ce que la forme fait d'une matière donnée, pas comment
  l'échange aurait tourné.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ...hds import Harness, Kata
from . import Tour, evaluer
from .client import Passerelle, PasserelleInjoignable

__all__ = ["Ecart", "Perime", "modele_virtuel", "perimes", "rejouer", "tours_du_ha"]

PORTEUR = re.compile(r"^\*\*Porteur\*\* — (.*?)(?=\n\n\*\*|\n## |\Z)", re.MULTILINE | re.DOTALL)
KATA = re.compile(r"^\*\*Kata\*\* —\s*\n\n(.*?)(?=\n## |\Z)", re.MULTILINE | re.DOTALL)


@dataclass(frozen=True)
class Perime:
    """Un ha né d'une coupe que la forge ne produit plus."""

    dossier: Path
    kata: str
    cible: str
    version_ha: str
    version_actuelle: str
    design_exerce: tuple[str, ...]


@dataclass(frozen=True)
class Ecart:
    """Ce que le rejeu a changé, règle par règle."""

    ha: str
    kata: str
    avant: tuple
    apres: tuple
    interrompu: str | None = None

    @staticmethod
    def _compte(constats) -> dict[str, int]:
        compte: dict[str, int] = {}
        for constat in constats:
            compte[constat.regle] = compte.get(constat.regle, 0) + 1
        return compte

    @property
    def mouvements(self) -> list[tuple[str, int, int]]:
        """(règle, avant, après) pour toute règle dont le compte a bougé."""
        avant, apres = self._compte(self.avant), self._compte(self.apres)
        return sorted(
            (regle, avant.get(regle, 0), apres.get(regle, 0))
            for regle in set(avant) | set(apres)
            if avant.get(regle, 0) != apres.get(regle, 0)
        )

    @property
    def regression(self) -> bool:
        """Une règle qui se met à mordre là où elle se taisait."""
        return any(apres > avant for _, avant, apres in self.mouvements)


def modele_virtuel(harness_id: str, kata: str, cible: str, cible_par_defaut: str = "") -> str:
    """Le modèle virtuel sous lequel la passerelle sert cette coupe.

    Le suffixe `@<cible>` **force** une cible autre que celle du Dojo ; la cible
    par défaut, elle, est servie sans suffixe. Coller le suffixe à tout le monde
    demande un modèle qui n'existe pas, et rend irrejouables tous les ha de la
    cible par défaut — c'est ce qui est arrivé.
    """
    suffixe = "" if cible == cible_par_defaut else f"@{cible}"
    return f"{harness_id}/{kata}{suffixe}"


def _entete(dossier: Path) -> dict:
    fiche = dossier / "fiche.md"
    if not fiche.is_file():
        return {}
    texte = fiche.read_text(encoding="utf-8")
    if not texte.startswith("---"):
        return {}
    return yaml.safe_load(texte.split("---")[1]) or {}


def tours_du_ha(dossier: Path) -> tuple[list[str], tuple[Tour, ...]]:
    """Les tours de l'interlocuteur, et l'échange complet tel qu'il a eu lieu."""
    transcript = dossier / "transcript.md"
    if not transcript.is_file():
        return [], ()
    texte = transcript.read_text(encoding="utf-8")
    porteurs = [p.strip() for p in PORTEUR.findall(texte)]
    katas = [k.strip() for k in KATA.findall(texte)]
    tours = tuple(
        Tour(rang, porteurs[rang - 1], katas[rang - 1] if rang <= len(katas) else "")
        for rang in range(1, len(porteurs) + 1)
    )
    return porteurs, tours


def perimes(harness: Harness, coupes: dict[tuple[str, str], str], corpus: Path | None = None) -> list[Perime]:
    """Les ha dont la coupe n'est plus celle que la forge produit.

    `coupes` : la version actuelle par (kata, cible), telle que la forge la rend.
    """
    racine = Path(corpus) if corpus is not None else harness.corpus
    trouves = []
    for dossier in sorted(racine.glob("CAS-*")):
        entete = _entete(dossier)
        kata, cible = str(entete.get("kata") or ""), str(entete.get("cible") or "")
        actuelle = coupes.get((kata, cible))
        version = str(entete.get("version_coupe") or "")
        if not actuelle or not version or actuelle == version:
            continue
        trouves.append(
            Perime(
                dossier=dossier,
                kata=kata,
                cible=cible,
                version_ha=version,
                version_actuelle=actuelle,
                design_exerce=tuple(entete.get("design_exerce") or ()),
            )
        )
    return trouves


def rejouer(
    harness: Harness,
    kata: Kata,
    perime: Perime,
    modele: str,
    passerelle: Passerelle,
    temperature: float | None = 0.0,
) -> Ecart:
    """Rejoue les tours de l'interlocuteur contre la coupe d'aujourd'hui."""
    porteurs, anciens = tours_du_ha(perime.dossier)
    if not porteurs:
        return Ecart(perime.dossier.name, kata.id, (), (), "transcript illisible")

    echange: list[dict] = []
    nouveaux: list[Tour] = []
    for rang, dit in enumerate(porteurs, 1):
        echange.append({"role": "user", "content": dit})
        try:
            reponse = passerelle.completer(modele, echange, temperature)
        except PasserelleInjoignable as err:
            return Ecart(
                perime.dossier.name, kata.id,
                evaluer(harness, kata, anciens), tuple(nouveaux),
                f"rejeu interrompu au tour {rang} : {err}",
            )
        echange.append({"role": "assistant", "content": reponse})
        nouveaux.append(Tour(rang, dit, reponse))

    # Les deux côtés passent par les checks d'aujourd'hui : sinon on mêlerait le
    # changement de coupe à celui du check.
    return Ecart(
        ha=perime.dossier.name,
        kata=kata.id,
        avant=evaluer(harness, kata, anciens),
        apres=evaluer(harness, kata, tuple(nouveaux)),
    )
