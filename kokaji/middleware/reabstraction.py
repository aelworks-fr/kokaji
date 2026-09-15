"""Ré-abstraire un ha — reconstruire son état après coup (RFC-002 §7.2).

Un bloc d'état est normalement l'**auto-abstraction de la pratique** : le kata
déclare ce qu'il a établi, pendant qu'il l'établit. C'est ce qui en fait une
observation.

Un ha capturé sur une cible non instrumentée n'en porte aucun. On peut le
reconstruire depuis le transcript, par un appel de modèle — mais le résultat
n'est pas une observation, c'est une **lecture**. Tout ce qui en sort est marqué
`reabstrait: true`, dans le relevé comme dans la fiche, et le QG l'affiche.

Sans ce marquage, le corpus mentirait sur sa propre nature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..corpus.depot import depot_pour, ref_de
from ..etat import extraire, fautes_de_bloc
from ..forge.coupe import STATUTS_OPTION, champs_du_kata, charger_registre
from ..hds import Harness, Kata
from ..trempe.banc.client import Passerelle
from . import carre_du_ha

__all__ = ["Reabstraction", "reabstraire"]


@dataclass(frozen=True)
class Reabstraction:
    ha: str
    blocs: int
    fautes: int
    carre: str
    sujet: str | None


def _consigne(harness: Harness, kata: Kata, champs: tuple[str, ...]) -> str:
    """Ce qu'on demande au modèle — construit depuis le manifest, pas écrit ici."""
    lignes_champs = ",\n".join(f'      "{c}": "<statut_champ>"' for c in champs)
    valeurs = "\n".join(f"- `{s}`" for s in harness.etat.statuts_champ)
    hypotheses = "\n".join(f"- `{s}`" for s in harness.etat.statuts_hypothese)
    options = "\n".join(f"- `{s}`" for s in STATUTS_OPTION)
    suivants = ", ".join(
        f"`{a.vers}`" for a in harness.chaine.aretes if a.de == kata.id
    ) or "aucune"

    bloc_options = (
        '    "options": [ { "id": "OPT-1", "libelle": "", "noeud": "'
        + kata.id
        + '", "statut": "<statut_option>" } ],\n'
        if kata.emet_options
        else ""
    )
    admis_options = f"\n\n`<statut_option>` :\n{options}" if kata.emet_options else ""

    return (
        "Tu lis un échange déjà terminé et tu en rends l'état final, rien d'autre.\n\n"
        "Tu ne juges pas la qualité de l'échange. Tu ne complètes pas ce qui n'y\n"
        "est pas. Un champ dont l'échange ne dit rien vaut le statut le plus\n"
        "faible — ne pas savoir n'est pas un demi-savoir.\n\n"
        "Réponds par ce bloc, seul, sans une ligne autour :\n\n"
        "```json kokaji_state\n"
        "{\n"
        '  "kokaji_state": {\n'
        f'    "harness": "{harness.id}", "kata": "{kata.id}", "version": "{harness.version}",\n'
        '    "sujet": "", "objet": "", "etape": "",\n'
        "    \"champs\": {\n"
        f"{lignes_champs}\n"
        "    },\n"
        '    "hypotheses": [ { "id": "", "libelle": "", "statut": "<statut_hypothese>",'
        ' "confiance": "faible|moyen|eleve" } ],\n'
        f"{bloc_options}"
        '    "pret_pour": null\n'
        "  }\n"
        "}\n"
        "```\n\n"
        "Les clés de `champs` sont exactement celles du gabarit.\n\n"
        f"`<statut_champ>` :\n{valeurs}\n\n"
        f"`<statut_hypothese>` :\n{hypotheses}"
        f"{admis_options}\n\n"
        f"`pret_pour` vaut `null`, ou l'étape suivante : {suivants}.\n\n"
        "`sujet` est le sujet travaillé, en quelques mots, tel que l'échange le nomme."
    )


def reabstraire(
    harness: Harness,
    dossier: Path,
    passerelle: Passerelle,
    modele: str,
    temperature: float | None = 0.0,
) -> Reabstraction:
    """Reconstruit l'état final d'un ha depuis son transcript, et le marque."""
    depot = depot_pour(harness)
    ref = ref_de(dossier)
    fiche = depot.fiche(ref) or ""
    entete = yaml.safe_load(fiche.split("---")[1]) or {}
    kata = harness.kata_par_id(entete.get("kata"))
    if kata is None:
        raise ValueError(f"{ref.nom} : kata inconnu — {entete.get('kata')!r}")

    transcript = depot.transcript(ref) or ""
    registre = charger_registre(harness.trempe.registre)
    source = yaml.safe_load(kata.source.read_text(encoding="utf-8")) or {}
    champs = champs_du_kata(harness, kata, source, registre)

    reponse = passerelle.completer(
        modele,
        [
            {"role": "system", "content": _consigne(harness, kata, champs)},
            {"role": "user", "content": transcript},
        ],
        temperature,
    )

    horodatage = entete.get("date") or datetime.now(UTC).isoformat()
    releves = []
    for rang, etat in enumerate(extraire(reponse)):
        fautes = fautes_de_bloc(harness, kata, champs, etat, set())
        releves.append(
            {
                "horodatage": horodatage,
                "id_appel": None,
                "rang_dans_la_reponse": rang,
                "etat": etat,
                "fautes": [{"regle": r, "message": m} for r, m in fautes],
                # Ce relevé n'a pas été observé : il a été relu.
                "reabstrait": True,
                "reabstrait_par": modele,
            }
        )

    depot.ecrire_etats(ref, releves)

    carre = carre_du_ha(harness, kata, releves)
    depot.ecrire_carre(
        ref,
        carre.rendre()
        + "\n> État **ré-abstrait** depuis le transcript, non émis en session.\n"
        "> Ce verdict porte sur une lecture, pas sur une observation.\n",
    )

    if "etat_reabstrait:" not in fiche:
        fiche = fiche.replace("statut: brut", "statut: brut\netat_reabstrait: true", 1)
        fiche = fiche.replace(
            "## Réserves sur ce ha\n",
            "## Réserves sur ce ha\n\n- **L'état de ce ha n'a pas été observé.** La session s'est"
            f" déroulée sur une cible sans bloc d'état ; l'état a été reconstruit depuis le"
            f" transcript par `{modele}`. C'est une lecture, pas une auto-abstraction de la"
            " pratique — voir RFC-002 §7.2.\n",
            1,
        )
        depot.ecrire_fiche(ref, fiche)

    premier = next((r["etat"] for r in releves if "__illisible__" not in r["etat"]), {})
    return Reabstraction(
        ha=ref.nom,
        blocs=len(releves),
        fautes=sum(len(r["fautes"]) for r in releves),
        carre=carre.verdict,
        sujet=premier.get("sujet"),
    )
