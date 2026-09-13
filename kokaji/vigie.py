"""Les vérifications qui tournent seules, et se montrent — NOTE-0003, 0009, 0010.

Le carnet dit trois fois la même chose sous trois formes : **l'échec a la même
apparence que le repos.** Un rejeu qui échoue en 401 se lit « aucune
régression ». Une veille morte se lit « dojo calme ». Un titre refusé se lit
« titre pas encore généré ». Chaque fois, ce qui manquait n'était pas la mesure
— c'était qu'elle soit prise, et vue.

Une vérification qu'on lance à la main retombe donc exactement dans le silence
qu'elle combat. Ce module la fait tourner seule et **écrit son verdict** ; le
QG le montre à l'administration.

Deux choses en découlent, et la seconde est le cœur :

1. Un verdict est daté.
2. **Un verdict qui cesse d'être rafraîchi est lui-même une alarme.** C'est le
   seul mécanisme qui aurait attrapé les deux jours de veille morte : rien
   n'était faux, il n'y avait simplement plus personne pour écrire. Un fichier
   qui ne bouge plus se voit ; un processus mort, non.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

__all__ = [
    "Verdict",
    "ecrire_verdicts",
    "lire_verdicts",
    "peremption",
    "verifier_configuration",
    "verifier_passerelle",
]

# Au-delà de ce multiple de la période, un verdict n'est plus une mesure : c'est
# un souvenir. Trois tours ratés d'affilée, ce n'est plus un hasard de réseau.
TOLERANCE = 3


@dataclass(frozen=True)
class Verdict:
    """Ce qu'une vérification a constaté, daté."""

    quoi: str
    tient: bool
    detail: str = ""
    le: str = field(default_factory=lambda: datetime.now(UTC).isoformat(timespec="seconds"))


def verifier_passerelle(harness: dict, base: str, admin: str, cle: str, nus=()) -> Verdict:
    """La clé de la passerelle autorise-t-elle ce que la forge déclare ?

    Trois pannes en sont sorties, et aucune ne s'est signalée : un modèle
    refusé se lit comme un modèle absent.
    """
    from .passerelle import (
        PasserelleInjoignable,
        autorisation_de_la_cle,
        ecart_d_autorisation,
        modeles_virtuels,
    )

    attendus = tuple(
        nom for _, h in sorted(harness.items()) for nom in modeles_virtuels(h)
    ) + tuple(nus)
    try:
        autorises = autorisation_de_la_cle(base, admin, cle)
    except PasserelleInjoignable as err:
        # Injoignable n'est pas « conforme » : ne pas pouvoir mesurer et
        # mesurer que tout va bien sont deux états différents, et les
        # confondre est précisément la faute de NOTE-0003.
        return Verdict("autorisation de la passerelle", False, f"passerelle muette : {err}")

    ecart = ecart_d_autorisation(attendus, autorises)
    if not ecart:
        return Verdict(
            "autorisation de la passerelle", True, f"{len(attendus)} modèle(s), aucun écart"
        )
    return Verdict("autorisation de la passerelle", False, ecart.rendre())


def verifier_configuration(harness: dict, chemin, nus=()) -> Verdict:
    """La passerelle déclare-t-elle servir ce que la forge déclare produire ?

    L'autre moitié de NOTE-0002. La clé dit qui a le **droit** d'appeler ; cette
    liste dit ce que la passerelle sait **router**. Les deux peuvent décrocher
    séparément, et un modèle autorisé mais non routé répond 404 là où on
    attendait une conversation.
    """
    from .passerelle import ecart_d_autorisation, modeles_de_la_configuration, modeles_virtuels

    attendus = tuple(
        nom for _, h in sorted(harness.items()) for nom in modeles_virtuels(h)
    ) + tuple(nus)
    declares = modeles_de_la_configuration(chemin)
    if not declares:
        return Verdict("modèles servis par la passerelle", False, f"configuration illisible : {chemin}")
    ecart = ecart_d_autorisation(attendus, declares)
    if not ecart:
        return Verdict(
            "modèles servis par la passerelle", True, f"{len(attendus)} modèle(s), aucun écart"
        )
    return Verdict("modèles servis par la passerelle", False, ecart.rendre())


def ecrire_verdicts(chemin: Path, verdicts: list[Verdict], boucle: float) -> None:
    """Dépose les verdicts. L'écriture est atomique — un lecteur ne voit jamais
    un fichier à moitié écrit, et un fichier tronqué se lirait comme une panne."""
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    brouillon = chemin.with_suffix(chemin.suffix + ".part")
    brouillon.write_text(
        json.dumps(
            {
                "le": datetime.now(UTC).isoformat(timespec="seconds"),
                "boucle": boucle,
                "verdicts": [asdict(v) for v in verdicts],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    brouillon.replace(chemin)


def lire_verdicts(chemin: Path | None) -> dict | None:
    """Ce que la vigie a constaté, ou `None` si elle n'a jamais écrit."""
    if chemin is None:
        return None
    chemin = Path(chemin)
    if not chemin.is_file():
        return None
    try:
        return json.loads(chemin.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def peremption(releve: dict | None, maintenant: datetime | None = None) -> str:
    """Le verdict est-il encore une mesure, ou déjà un souvenir ?

    Rend le motif de la péremption, ou une chaîne vide si le relevé est frais.
    **C'est la vérification la plus importante du module** : elle est la seule
    qui attrape une vigie morte, et une vigie morte ne dit rien du tout — ce qui
    se lit comme si tout allait bien.
    """
    if releve is None:
        return "la vigie n'a jamais rien écrit"
    try:
        ecrit = datetime.fromisoformat(str(releve.get("le")))
    except (TypeError, ValueError):
        return "verdict sans date lisible"
    if ecrit.tzinfo is None:
        ecrit = ecrit.replace(tzinfo=UTC)

    boucle = float(releve.get("boucle") or 0)
    if boucle <= 0:
        return ""
    age = ((maintenant or datetime.now(UTC)) - ecrit).total_seconds()
    if age > boucle * TOLERANCE:
        return f"aucun verdict depuis {int(age)}s — la vigie ne tourne plus"
    return ""
