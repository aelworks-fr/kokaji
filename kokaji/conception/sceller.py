"""Sceller — écrire la définition, décider les versions, signer.

Trois règles, toutes venues d'ailleurs :

- **Un brouillon qui ne tient pas ne se scelle pas** (le principe du module).
- **Un f♯ qui change est une version majeure du kata** — RFC-002 §3 : la
  modification invalide mécaniquement les certifications de ce kata.
- **Un scellement porte le nom de son auteur** — RFC-004 §3 : c'est la
  traçabilité qui tient la responsabilité, non la rareté du droit. Sans auteur,
  on ne scelle pas.

Ce que sceller ne fait pas : forger. La définition change, les coupes sont
périmées, et c'est `kokaji forge` puis `kokaji regression` qui diront ce que le
changement a fait à la pratique. Mélanger les deux gestes cacherait le moment où
le corpus devient périmé.
"""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..yaml_source import charger_source, ecrire_source
from .brouillon import (
    _poser_au_registre,
    a_declarer_au_registre,
    appliquer,
    chemin_du_template,
    juger,
    source_neuve,
)
from .depot import commiter
from .modele import Proposition, Scellement, Verdict

__all__ = ["JOURNAL", "ScellementRefuse", "sceller", "version_suivante", "versions_prevues"]

JOURNAL = "scellements.jsonl"


class ScellementRefuse(Exception):
    """Le brouillon ne tient pas, ou personne ne le signe."""


def version_suivante(version: str, majeure: bool) -> str:
    """`1.2.3` → `2.0.0` si le contrat bouge, `1.3.0` sinon.

    Une version illisible n'est pas devinée : on refuse plutôt que d'inventer un
    numéro à la place de l'auteur du harness.
    """
    morceaux = str(version or "").split(".")
    if len(morceaux) != 3 or not all(m.isdigit() for m in morceaux):
        raise ScellementRefuse(f"version illisible : {version!r} (attendu : x.y.z)")
    grand, moyen, _ = (int(m) for m in morceaux)
    return f"{grand + 1}.0.0" if majeure else f"{grand}.{moyen + 1}.0"


def sceller(
    racine: Path,
    proposition: Proposition,
    auteur: str,
    motif: str = "",
    quand: datetime | None = None,
) -> Scellement:
    """Vérifie, puis écrit. Rien n'est touché si le verdict ne tient pas."""
    racine = Path(racine)
    if not auteur.strip():
        raise ScellementRefuse(
            "un scellement porte le nom de son auteur (RFC-004 §3) — sans auteur, rien n'est scellé"
        )
    # Une proposition vide n'est plus un refus : c'est **arrêter la version
    # courante** (RFC-006). Sceller n'était jusqu'ici que « sceller un
    # changement » — on ne pouvait donc pas arrêter une définition qu'on n'avait
    # pas modifiée, et un harness qui vient de naître, copie exacte, ne pouvait
    # jamais l'être. Le geste manquait, pas le droit.
    arret = proposition.vide

    verdict: Verdict = juger(racine, proposition)
    if not verdict.tient:
        # Les fautes sont nommées, pas comptées : « 1 faute(s) » laisse le
        # forgeron chercher laquelle — le refus doit porter de quoi corriger.
        dites = [*verdict.fautes, *(str(a) for a in verdict.anomalies)]
        raise ScellementRefuse(
            "la définition proposée ne tient pas — "
            + " ; ".join(dites[:5])
            + (f" ; et {len(dites) - 5} de plus" if len(dites) > 5 else "")
        )

    # Chargé en aller-retour : un manifest est une source, et ses commentaires
    # portent les raisons de ses décisions. Les recopier par YAML les effacerait
    # tous — c'est arrivé au premier scellement réel, et il n'y en avait eu
    # aucun jusque-là pour le montrer.
    avant = charger_source(racine / "harness.yaml")

    if arret:
        # Rien n'est réécrit, et **aucune version ne bouge** : la version
        # actuelle nomme déjà cet état. En produire une nouvelle, identique à la
        # précédente, dirait qu'il y a eu un changement — alors que l'arrêt dit
        # exactement l'inverse. Ce qui est écrit est la trace : à cette date,
        # cette définition a été arrêtée par quelqu'un, et elle tient.
        entete = dict(avant.get("harness") or {})
        return _commiter(_tracer(
            racine,
            auteur=auteur,
            motif=motif,
            quand=quand,
            versions={str(entete.get("id") or "harness"): str(entete.get("version") or "")},
            changements=(),
        ))

    apres = appliquer(avant, proposition, copier=False)

    # Les versions de kata : majeure pour ceux dont le contrat bouge, mineure
    # pour ceux qu'on a seulement retouchés.
    versions: dict[str, str] = {}
    touches = set(verdict.kata_touches)
    retouches = {c.ou.split(".")[1] for c in verdict.changements if c.ou.startswith("kata.")}
    retouches |= set(proposition.source)
    # Le registre suit le manifest : un champ nommé et non déclaré ferait
    # refuser la coupe qui le cite.
    fichier_registre = racine / str(apres.get("trempe", {}).get("registre") or "registre.yaml")
    if fichier_registre.is_file():
        registre = charger_source(fichier_registre)
        if _poser_au_registre(registre, a_declarer_au_registre(apres, registre)):
            ecrire_source(fichier_registre, registre)

    # Un harness adopté n'a pas de sources de forge : ses kata sont des textes
    # dans `prompts/`, leurs contrats vivent au manifest, et la version d'un
    # kata est celle du harness (RFC-008). Écrire une page `kata/<id>.yaml` à
    # remplir lui inventerait une forme qu'il n'a pas encore — c'est le geste
    # de N4, pas du scellement.
    exogene = bool((apres.get("harness") or {}).get("exogene"))
    if exogene:
        retouches = set()

    # Les kata déclarés au manifest et sans source : ils viennent d'arriver.
    retouches |= {
        str(k.get("id"))
        for k in (apres.get("kata") or [])
        if not exogene and not (racine / "kata" / f"{k.get('id')}.yaml").is_file()
        # Un orphelin (source `.md`, RFC-011) est un texte : pas de page à semer.
        and not str(k.get("source") or "").endswith(".md")
    }
    # Et un orphelin retouché au manifest ne reçoit pas de densho pour autant.
    orphelins = {
        str(k.get("id")) for k in (apres.get("kata") or [])
        if str(k.get("source") or "").endswith(".md")
    }
    retouches -= orphelins
    for id_kata in sorted(retouches):
        fichier = racine / "kata" / f"{id_kata}.yaml"
        # Un kata neuf reçoit sa page à remplir : la sauter laisserait au
        # manifest une étape qui ne pointe nulle part.
        source = charger_source(fichier) if fichier.is_file() else source_neuve()
        source["version"] = version_suivante(
            str(source.get("version") or ""), majeure=id_kata in touches
        )
        versions[id_kata] = source["version"]
        for cle, valeur in (proposition.source.get(id_kata) or {}).items():
            source[cle] = valeur
        ecrire_source(fichier, source)

    # Le gabarit : écrit tel quel, à l'endroit que le manifest désigne. Sa
    # version est celle du harness — c'est la doctrine commune qui bouge, aucun
    # kata en particulier (RFC-010 D10.1).
    if proposition.template is not None:
        fichier_template = racine / chemin_du_template(apres)
        if not fichier_template.is_file() or (
            fichier_template.read_text(encoding="utf-8") != proposition.template
        ):
            fichier_template.write_text(proposition.template, encoding="utf-8")

    # Le harness suit ses kata : majeur si l'un d'eux l'est devenu.
    apres["harness"] = dict(apres.get("harness") or {})
    apres["harness"]["version"] = version_suivante(
        str(apres["harness"].get("version") or ""), majeure=bool(touches)
    )
    versions[str(apres["harness"].get("id") or "harness")] = apres["harness"]["version"]
    ecrire_source(racine / "harness.yaml", apres)

    return _commiter(_tracer(
        racine,
        auteur=auteur,
        motif=motif,
        quand=quand,
        versions=versions,
        changements=tuple(str(c) for c in verdict.changements),
    ))


def _commiter(trace: Scellement) -> Scellement:
    """Le commit suit la trace : le journal des scellements en fait partie."""
    sha, motif = commiter(trace.racine, trace.auteur, trace.motif, trace.versions)
    return replace(trace, commit=sha, commit_motif=motif)


def _tracer(
    racine: Path,
    auteur: str,
    motif: str,
    quand: datetime | None,
    versions: dict[str, str],
    changements: tuple[str, ...],
) -> Scellement:
    """Écrit la trace au journal des scellements — la seule chose qu'un arrêt écrit.

    Un scellement sans changement laisse donc une entrée dont `changements` est
    vide : c'est ainsi qu'un arrêt se lit, sans qu'il faille un second concept.
    """
    trace = Scellement(
        auteur=auteur.strip(),
        motif=motif.strip(),
        quand=(quand or datetime.now(UTC)).isoformat(),
        versions=versions,
        changements=changements,
        racine=racine,
    )
    with (racine / JOURNAL).open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "auteur": trace.auteur,
                    "motif": trace.motif,
                    "le": trace.quand,
                    "versions": trace.versions,
                    "changements": list(trace.changements),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return trace


def versions_prevues(racine: Path, verdict) -> dict[str, str]:
    """Ce que sceller déciderait, sans rien sceller.

    Le design demande d'annoncer les versions **avant** le scellement : une
    version décidée après coup se découvre, et découvrir qu'un kata est passé en
    majeure est exactement ce qu'on ne veut pas laisser arriver.
    """
    racine = Path(racine)
    manifest = yaml.safe_load((racine / "harness.yaml").read_text(encoding="utf-8")) or {}
    touches = set(verdict.kata_touches)
    retouches = {c.ou.split(".")[1] for c in verdict.changements if c.ou.startswith("kata.")}
    retouches |= {c.ou.split(".")[1] for c in verdict.changements if c.ou.startswith("source.")}

    prevues: dict[str, str] = {}
    for id_kata in sorted(retouches):
        fichier = racine / "kata" / f"{id_kata}.yaml"
        if not fichier.is_file():
            continue
        source = yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
        try:
            prevues[id_kata] = version_suivante(
                str(source.get("version") or ""), majeure=id_kata in touches
            )
        except ScellementRefuse:
            continue
    if verdict.changements:
        entete = manifest.get("harness") or {}
        try:
            prevues[str(entete.get("id") or "harness")] = version_suivante(
                str(entete.get("version") or ""), majeure=bool(touches)
            )
        except ScellementRefuse:
            pass
    return prevues
