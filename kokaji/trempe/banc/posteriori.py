"""La trempe a posteriori d'une pratique rapportée (RFC-020 D20.3).

Un ha rapporté n'a pas été joué sous la coupe : personne ne l'a vu naître, il
n'a pas de bloc d'état, et son rattachement à un kata est une **déclaration**.
On ne le juge pas pour décider s'il mérite d'exister — il existe. On lui
applique des **critères neutres**, les mêmes pour tous, dont les résultats
s'attachent à lui sans commander son existence :

1. **déterministe** — les checks de session du harness tournent sur le
   transcript tel quel ; les invariants de Kokaji, qui supposent des blocs
   d'état émis, sont **éteints, et dits éteints** (l'honnêteté d'affichage
   de la RFC-008 §8) ;
2. **judge** — la conformité au kata déclaré, un invariant de Kokaji (une
   seule question, générique, posée devant la coupe du kata), puis la grille
   du harness s'il en déclare une ; le juge n'est jamais le moteur d'origine
   quand celui-ci est connu.

Le verdict de conformité s'écrit **à côté** de la déclaration — `conformite:`
dans la fiche, jamais à la place de `declaration:` — et chaque passage
s'ajoute aux jugements, daté et versionné. Un déroulé contesté reste au
corpus : les presque-conformes sont instructifs.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ...corpus.depot import depot_pour, ref_de
from ...corpus.provenance import RAPPORTE, provenance_de
from ...hds import Harness
from .checks import Constat, checks_du_harness
from .client import Passerelle, PasserelleInjoignable
from .jugement import BLOC, JugeRefuse, _matiere, juger_grille
from .rejeu import tours_du_ha

__all__ = ["CONFORME", "CONTESTE", "INDECIDABLE", "Trempe", "TrempeRefusee", "tremper"]

CONFORME, CONTESTE, INDECIDABLE = "conforme", "conteste", "indecidable"
VERDICTS = (CONFORME, CONTESTE, INDECIDABLE)
VERSION_GRILLE = "conformite-1"

# Les invariants que Kokaji impose au bloc d'état — ils n'ont rien à lire ici.
INVARIANTS_ETEINTS = (
    "etat-bien-forme", "etat-champs-declares", "etat-statuts-declares",
    "etat-passage-declare", "etat-options-declarees", "etat-decision-coherente",
    "etat-actions-declarees",
)
MOTIF_ETEINT = "aucun bloc d'état émis : ce ha est rapporté, pas joué sous la coupe"


class TrempeRefusee(Exception):
    """La trempe n'a pas eu lieu, et la raison est nommée."""


@dataclass(frozen=True)
class Conformite:
    verdict: str
    detail: str
    juge: str
    version_grille: str = VERSION_GRILLE


@dataclass(frozen=True)
class Trempe:
    """Ce qu'un passage a produit — chaque pièce dit d'où elle vient."""

    ha: str
    kata: str
    le: str
    constats: tuple[Constat, ...]
    eteints: tuple[str, ...]
    conformite: Conformite | None = None
    scores: tuple[dict, ...] = field(default_factory=tuple)

    @property
    def regles_en_faute(self) -> tuple[str, ...]:
        return tuple(sorted({c.regle for c in self.constats}))


def _consigne_conformite(kata_id: str, coupe: str) -> str:
    return (
        "Tu relis un échange déjà terminé, joué hors de ce dojo, qu'une personne\n"
        f"rattache au kata `{kata_id}`. Voici la coupe de ce kata — ce que le\n"
        "pratiquant aurait dû suivre :\n\n"
        f"{coupe}\n\n"
        "La question, une seule : cet échange est-il une pratique de ce kata ?\n"
        "Conforme si l'échange fait ce que le kata prescrit — même imparfaitement ;\n"
        "contesté si l'échange fait autre chose, ou dévie vers une autre étape ;\n"
        "indécidable si le transcript ne permet pas de trancher.\n"
        "Tu contestes une déclaration, tu ne juges pas la qualité — c'est un\n"
        "autre étage. Une contestation cite ce qui dévie.\n\n"
        "Réponds par ce bloc, seul, sans une ligne autour :\n\n"
        "```json\n"
        '{ "verdict": "conforme" | "conteste" | "indecidable", "detail": "<une ou deux phrases>" }\n'
        "```"
    )


def _lire_conformite(reponse: str, juge: str) -> Conformite:
    trouve = BLOC.search(reponse or "")
    try:
        brut = json.loads(trouve.group(1) if trouve else reponse)
    except (json.JSONDecodeError, TypeError):
        brut = None
    if not isinstance(brut, dict):
        return Conformite(INDECIDABLE, "le juge n'a pas rendu de bloc lisible", juge)
    verdict = str(brut.get("verdict") or "").strip().lower()
    detail = str(brut.get("detail") or "").strip()
    if verdict not in VERDICTS:
        return Conformite(INDECIDABLE, f"verdict hors liste — {verdict!r}", juge)
    return Conformite(verdict, detail, juge)


def _coupe_du_kata(harness: Harness, kata_id: str) -> str:
    """La coupe du kata déclaré, forgée en mémoire ; à défaut, sa source telle quelle."""
    try:
        from ...conception.brouillon import rendre_coupe

        cible = harness.cibles[0].id if harness.cibles else "sobre"
        return rendre_coupe(harness.racine, kata_id, cible).texte
    except Exception:  # noqa: BLE001 — la forge peut refuser ; la source reste lisible
        kata = harness.kata_par_id(kata_id)
        try:
            return Path(kata.source).read_text(encoding="utf-8") if kata else ""
        except OSError:
            return ""


def _poser_conformite(depot, ref, conformite: Conformite, quand: str) -> None:
    """`conformite:` dans la fiche — à côté de `declaration:`, jamais à sa place."""
    texte = depot.fiche(ref) or ""
    avant, entete, apres = texte.split("---", 2)
    donnees = yaml.safe_load(entete) or {}
    donnees["conformite"] = {
        "verdict": conformite.verdict,
        "detail": conformite.detail,
        "juge": conformite.juge,
        "version_grille": conformite.version_grille,
        "le": quand,
    }
    depot.ecrire_fiche(
        ref,
        avant + "---\n" + yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False, width=1000) + "---" + apres,
    )


def tremper(
    harness: Harness,
    dossier: Path,
    passerelle: Passerelle | None = None,
    juge: str = "",
    temperature: float | None = 0.0,
    quand: str | None = None,
) -> Trempe:
    """Un passage de trempe a posteriori sur un ha rapporté.

    Sans `juge`, seul l'étage déterministe tourne. Avec, la conformité est
    demandée, puis la grille du harness s'il en a une. Rien de tout cela ne
    change le statut du ha ni sa déclaration.
    """
    depot = depot_pour(harness)
    ref = ref_de(dossier)
    entete = depot.entete(ref)
    if not entete:
        raise TrempeRefusee(f"{ref.nom} : fiche absente ou illisible")
    if provenance_de(entete) != RAPPORTE:
        raise TrempeRefusee(
            f"{ref.nom} est `{provenance_de(entete)}` : la trempe a posteriori ne vaut que"
            " pour une pratique rapportée — un ha observé passe par le banc et la veille"
        )
    kata_id = str(entete.get("kata") or "")
    kata = harness.kata_par_id(kata_id)
    if kata is None:
        raise TrempeRefusee(f"{ref.nom} : kata déclaré inconnu du harness — {kata_id!r}")
    quand = quand or datetime.now(UTC).isoformat(timespec="seconds")

    _, tours = tours_du_ha(ref)
    if not tours:
        raise TrempeRefusee(f"{ref.nom} : transcript vide — rien à tremper")

    constats = tuple(checks_du_harness(harness, list(tours)))
    conformite: Conformite | None = None
    scores: tuple[dict, ...] = ()

    if juge:
        origine = str(entete.get("moteur") or "")
        if origine and origine != "inconnu" and juge == origine:
            raise JugeRefuse(
                f"juge et moteur d'origine confondus : {juge} — un modèle qui relit sa"
                " propre copie a un avis sur lui-même, pas sur elle"
            )
        passerelle = passerelle or Passerelle()
        matiere = _matiere(depot.transcript(ref) or "")
        try:
            reponse = passerelle.completer(
                juge,
                [
                    {"role": "system", "content": _consigne_conformite(kata_id, _coupe_du_kata(harness, kata_id))},
                    {"role": "user", "content": matiere},
                ],
                temperature,
            )
            conformite = _lire_conformite(reponse, juge)
        except PasserelleInjoignable as err:
            conformite = Conformite(INDECIDABLE, f"juge injoignable : {err}", juge)
        _poser_conformite(depot, ref, conformite, quand)
        if harness.trempe.grille_judge:
            scores = tuple(asdict(s) for s in juger_grille(harness, ref, passerelle, juge, temperature).scores)

    trempe = Trempe(
        ha=ref.identifiant, kata=kata_id, le=quand, constats=constats,
        eteints=INVARIANTS_ETEINTS, conformite=conformite, scores=scores,
    )
    depot.ajouter_jugement(ref, {
        "type": "trempe-posteriori",
        "ha": ref.identifiant,
        "kata": kata_id,
        "le": quand,
        "constats": [asdict(c) for c in constats],
        "eteints": {regle: MOTIF_ETEINT for regle in INVARIANTS_ETEINTS},
        "conformite": asdict(conformite) if conformite else None,
        "juge": juge,
    })
    return trempe


def rendre(trempe: Trempe) -> str:
    """Le passage au terminal — ce qui a mordu, ce qui est éteint, ce que le juge a dit."""
    lignes = [f"{trempe.ha}  {trempe.kata} · rapporté · trempe a posteriori du {trempe.le}"]
    if trempe.constats:
        for constat in trempe.constats:
            lignes.append(f"  ✗ {constat.regle} (tour {constat.tour}) — {constat.message}")
    else:
        lignes.append("  = aucun check du harness ne mord")
    lignes.append(f"  ○ éteints : {', '.join(trempe.eteints)} — {MOTIF_ETEINT}")
    if trempe.conformite:
        marque = {CONFORME: "✓", CONTESTE: "≠", INDECIDABLE: "?"}[trempe.conformite.verdict]
        lignes.append(
            f"  {marque} conformité au kata déclaré : {trempe.conformite.verdict}"
            f" — {trempe.conformite.detail} (juge {trempe.conformite.juge})"
        )
    for score in trempe.scores:
        note = score.get("note")
        lignes.append(f"  · {score.get('critere')} {note if note is not None else '—'} — {score.get('motif')}")
    return "\n".join(lignes)


