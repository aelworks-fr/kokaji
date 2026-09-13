"""Le banc — rejouer un kata contre un persona, et l'évaluer (SPECS §5).

Une session de banc n'a rien de particulier : elle passe par le Dojo, elle est
journalisée comme toute autre, elle produit un ha. Ce que le banc ajoute, c'est
un interlocuteur reproductible et une lecture de ce qui s'est passé.
"""

from __future__ import annotations

from dataclasses import dataclass

import yaml

from ...forge.coupe import champs_du_kata, charger_registre
from ...hds import Harness, Kata
from .checks import Constat, blocs_etat, checks_du_harness, invariants_kokaji
from .client import Passerelle, PasserelleInjoignable
from .juge import Verdict, grille, juger
from .persona import Persona, charger, charger_tous

__all__ = [
    "Constat",
    "Passerelle",
    "PasserelleInjoignable",
    "Persona",
    "Resultat",
    "Tour",
    "Verdict",
    "charger",
    "charger_tous",
    "evaluer",
    "grille",
    "jouer",
    "juger",
    "rapport",
]

OUVERTURE = "Bonjour."


@dataclass(frozen=True)
class Tour:
    rang: int
    porteur: str
    reponse: str


@dataclass(frozen=True)
class Resultat:
    harness: str
    kata: str
    persona: str
    modele: str
    tours: tuple[Tour, ...]
    constats: tuple[Constat, ...]
    interrompu: str | None = None
    # Deuxième étage : les verdicts du juge, s'il a été appelé (R5.5).
    verdicts: tuple[Verdict, ...] = ()

    @property
    def blocs(self) -> int:
        return sum(len(blocs_etat(t.reponse)) for t in self.tours)

    @property
    def regles_en_faute(self) -> tuple[str, ...]:
        return tuple(sorted({c.regle for c in self.constats}))


def jouer(
    persona: Persona,
    modele_kata: str,
    modele_persona: str,
    passerelle: Passerelle,
    tours_max: int | None = None,
    temperature: float | None = 0.0,
) -> tuple[tuple[Tour, ...], str | None]:
    """Déroule une session, tour par tour, jusqu'au plafond.

    Le persona ouvre : c'est lui qui apporte le sujet. Chacun des deux ne voit
    que ce qu'il aurait vu en vrai — le persona ignore la coupe, le kata ignore
    la consigne du persona.
    """
    plafond = tours_max or persona.tours_max
    echange_kata: list[dict] = []
    echange_persona: list[dict] = [{"role": "system", "content": persona.consigne}]
    tours: list[Tour] = []
    dit = OUVERTURE

    for rang in range(1, plafond + 1):
        echange_persona.append({"role": "user", "content": dit})
        try:
            porteur = passerelle.completer(modele_persona, echange_persona, temperature)
        except PasserelleInjoignable as err:
            return tuple(tours), f"persona injoignable au tour {rang} : {err}"
        echange_persona.append({"role": "assistant", "content": porteur})

        echange_kata.append({"role": "user", "content": porteur})
        try:
            reponse = passerelle.completer(modele_kata, echange_kata, temperature)
        except PasserelleInjoignable as err:
            return tuple(tours), f"kata injoignable au tour {rang} : {err}"
        echange_kata.append({"role": "assistant", "content": reponse})

        tours.append(Tour(rang=rang, porteur=porteur, reponse=reponse))
        dit = reponse

    return tuple(tours), None


def evaluer(harness: Harness, kata: Kata, tours: tuple[Tour, ...]) -> tuple[Constat, ...]:
    """Étage déterministe : les checks du harness, puis les invariants de Kokaji."""
    registre = charger_registre(harness.trempe.registre)
    source = yaml.safe_load(kata.source.read_text(encoding="utf-8")) or {}
    champs = champs_du_kata(harness, kata, source, registre)

    constats = list(checks_du_harness(harness, list(tours)))
    constats += invariants_kokaji(harness, kata, champs, list(tours))
    return tuple(constats)


def rapport(resultats: list[Resultat]) -> str:
    """La table comparative — versions × moteurs (R5.6)."""
    if not resultats:
        return "aucune session."

    juge = any(r.verdicts for r in resultats)
    entetes = ("persona", "kata", "modèle", "tours", "blocs", "constats", "règles en faute")
    if juge:
        entetes += ("non tenues", "indécidables")

    lignes = []
    for r in resultats:
        ligne = (
            r.persona,
            r.kata,
            r.modele,
            str(len(r.tours)),
            str(r.blocs),
            str(len(r.constats)),
            ", ".join(r.regles_en_faute) or "—",
        )
        if juge:
            ligne += (
                ", ".join(v.variable for v in r.verdicts if v.verdict == "non-tenue") or "—",
                str(sum(1 for v in r.verdicts if v.verdict == "indecidable")),
            )
        lignes.append(ligne)

    largeurs = [max(len(e), *(len(l[i]) for l in lignes)) for i, e in enumerate(entetes)]
    trace = lambda vals: "  ".join(v.ljust(largeurs[i]) for i, v in enumerate(vals)).rstrip()

    sortie = [trace(entetes), "  ".join("─" * w for w in largeurs)]
    sortie += [trace(l) for l in lignes]

    interrompus = [r for r in resultats if r.interrompu]
    if interrompus:
        sortie.append("")
        sortie += [f"! {r.persona}/{r.modele} — {r.interrompu}" for r in interrompus]
    return "\n".join(sortie)
