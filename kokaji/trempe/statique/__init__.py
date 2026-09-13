"""La trempe statique — ce qui bloque la forge (SPECS §5, RFC-002 §6.2).

Deux familles, comme au banc :

- ce qui porte sur les **coupes produites** — marqueurs résiduels, vocabulaire
  interdit, décomptes ;
- ce qui porte sur le **contrat** et sa cohérence avec le registre — les lints
  du RFC-002.

Aucune règle de domaine n'est écrite ici : les interdits viennent du manifest,
les noms canoniques du registre. Kokaji ne fournit que les mécanismes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import yaml

from ...forge.coupe import champ_nu
from ...hds import Harness

__all__ = ["Anomalie", "TrempeEchouee", "verifier"]

# `{{ … }}` non résolu, et les crochets de gabarit — hors liens markdown.
GABARIT = re.compile(r"\{\{[^}]*\}\}")
CROCHET = re.compile(r"\[[^\]\n]{2,}\](?!\()")
CHANTIER = re.compile(r"\b(TODO|FIXME|TBD|XXX|À FAIRE|A FAIRE)\b", re.IGNORECASE)
BLOC_CODE = re.compile(r"```.*?```", re.DOTALL)

# « trois questions : » suivi d'une liste — le seul décompte qu'on sache lire.
NOMBRES = {
    "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
    "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10,
}
DECOMPTE = re.compile(
    r"\b(\d+|" + "|".join(NOMBRES) + r")\s+([a-zà-ÿ]+)\s*:\s*\n+((?:\s*(?:[-*]|\d+\.)\s+.*\n?)+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Anomalie:
    regle: str
    ou: str
    message: str

    def __str__(self) -> str:
        return f"[{self.regle}] {self.ou} : {self.message}"


class TrempeEchouee(Exception):
    """Des anomalies bloquent la forge."""

    def __init__(self, anomalies: tuple[Anomalie, ...]):
        self.anomalies = anomalies
        detail = "\n".join(f"  - {a}" for a in anomalies)
        super().__init__(f"{len(anomalies)} anomalie(s)\n{detail}")


# --- Ce qui porte sur les coupes ---------------------------------------------


def _marqueurs_residuels(ou: str, texte: str) -> list[Anomalie]:
    """R5.1 — une coupe est un produit fini, pas un gabarit à trous.

    Les blocs de code sont exclus du repérage des crochets : un tableau JSON
    `["OPT-2"]` n'est pas un crochet de gabarit. Une variable `{{ … }}` reste
    fautive partout, y compris dans un bloc de code.
    """
    anomalies = []
    hors_code = BLOC_CODE.sub("", texte)

    for trouve in GABARIT.findall(texte):
        anomalies.append(Anomalie("marqueur-residuel", ou, f"variable non résolue : {trouve}"))
    for trouve in CROCHET.findall(hors_code):
        anomalies.append(Anomalie("marqueur-residuel", ou, f"crochet de gabarit : {trouve}"))
    for trouve in CHANTIER.findall(texte):
        anomalies.append(Anomalie("marqueur-residuel", ou, f"marque de chantier : {trouve}"))
    return anomalies


def _vocabulaire_interdit(harness: Harness, ou: str, texte: str) -> list[Anomalie]:
    """R5.2 — les interdits appartiennent au harness, Kokaji ne fait que chercher."""
    minuscules = texte.lower()
    return [
        Anomalie("vocabulaire-interdit", ou, f"terme banni : « {mot} »")
        for mot in harness.trempe.vocabulaire_interdit
        if mot.lower() in minuscules
    ]


def _decomptes(ou: str, texte: str) -> list[Anomalie]:
    """R5.3 — un décompte annoncé doit correspondre à ce qui suit.

    Volontairement étroit : seul le motif « <nombre> <mot> : » immédiatement
    suivi d'une liste est lu. Un check large produirait des faux positifs, et un
    check faux est pire que pas de check.
    """
    anomalies = []
    for annonce, mot, liste in DECOMPTE.findall(texte):
        attendu = int(annonce) if annonce.isdigit() else NOMBRES[annonce.lower()]
        compte = len([l for l in liste.splitlines() if l.strip()])
        if compte != attendu:
            anomalies.append(
                Anomalie(
                    "decompte",
                    ou,
                    f"« {annonce} {mot} » annoncé(e)s, {compte} listé(e)s",
                )
            )
    return anomalies


# --- Ce qui porte sur le contrat et le registre -------------------------------


def _registre_canonique(harness: Harness, registre: dict) -> list[Anomalie]:
    """R5.3 — tout nom déclaré doit exister au registre canonique."""
    anomalies = []
    connus_kata = set(registre.get("kata") or {})
    connus_jalons = set(registre.get("jalons") or {})
    connus_livrables = set(registre.get("livrables") or [])
    connus_champs = set(registre.get("champs") or {})

    for kata in harness.kata:
        if kata.id not in connus_kata:
            anomalies.append(
                Anomalie("registre-canonique", f"kata.{kata.id}", "absent de `kata:` au registre")
            )
        if kata.livrable not in connus_livrables:
            anomalies.append(
                Anomalie(
                    "registre-canonique",
                    f"kata.{kata.id}",
                    f"livrable absent de `livrables:` — {kata.livrable!r}",
                )
            )
        for reference in (*kata.herite, *(r for r, _ in kata.produit)):
            if champ_nu(reference) not in connus_champs:
                anomalies.append(
                    Anomalie(
                        "registre-canonique",
                        f"kata.{kata.id}",
                        f"champ absent de `champs:` — {reference!r}",
                    )
                )

    for noeud in harness.chaine.noeuds:
        if noeud.type == "jalon" and noeud.id not in connus_jalons:
            anomalies.append(
                Anomalie(
                    "registre-canonique",
                    f"chaine.{noeud.id}",
                    "jalon absent de `jalons:` au registre",
                )
            )
    return anomalies


def _contrat(harness: Harness) -> list[Anomalie]:
    """RFC-002 §6.2 — les lints du contrat f♯."""
    anomalies = []
    produits = {k.id: {r for r, _ in k.produit} for k in harness.kata}
    engagements = {k.id: dict(k.produit) for k in harness.kata}

    for kata in harness.kata:
        if not kata.produit:
            anomalies.append(
                Anomalie("contrat-complet", f"kata.{kata.id}", "`produit` vide : ce kata ne garantit rien")
            )
        if kata.amont and not kata.herite:
            anomalies.append(
                Anomalie(
                    "contrat-complet",
                    f"kata.{kata.id}",
                    "amont déclaré mais `herite` vide : le contrat est à moitié écrit",
                )
            )
        # Le chemin vide promet le vide : sans amont, rien n'est hérité.
        if not kata.amont and kata.herite:
            anomalies.append(
                Anomalie("chemin-vide", f"kata.{kata.id}", "hérite sans amont : couplage caché")
            )

        for reference in kata.herite:
            proprietaire = reference.split(".", 1)[0]
            if reference not in produits.get(proprietaire, set()):
                anomalies.append(
                    Anomalie(
                        "typage-chaine",
                        f"kata.{kata.id}",
                        f"{reference!r} n'est pas dans le `produit` de {proprietaire!r}",
                    )
                )
                continue

            # RFC-002 §6.2 — « au sens de l'ordre des statuts ». Hériter d'un
            # champ ne suffit pas : si l'aval exige un seuil, l'amont doit le
            # garantir. Un kata qui demande un fait établi là où l'amont ne
            # promet qu'une hypothèse construit sur du sable, et rien à
            # l'exécution ne le dira — le carré de l'amont sera conforme, celui
            # de l'aval aussi, et la chaîne fausse.
            minimum = kata.exigences.get(reference)
            if minimum is None:
                continue
            garanti = engagements.get(proprietaire, {}).get(reference)
            if garanti is not None and not harness.couvre(garanti, minimum):
                anomalies.append(
                    Anomalie(
                        "ordre-des-statuts",
                        f"kata.{kata.id}",
                        f"exige {reference} au moins en `{minimum}`, "
                        f"mais {proprietaire!r} ne garantit que `{garanti}`",
                    )
                )
    return anomalies


def _contrebande(harness: Harness, registre: dict) -> list[Anomalie]:
    """RFC-002 §6.2 — la source d'un kata ne parle que de son propre vocabulaire.

    Un kata qui nomme dans son texte un champ qu'il n'hérite ni ne produit
    s'appuie sur un savoir hors contrat. La contrebande se lit avant de se voir.
    """
    connus = set(registre.get("champs") or {})
    anomalies = []

    for kata in harness.kata:
        autorises = {champ_nu(r) for r in kata.herite} | {champ_nu(r) for r, _ in kata.produit}
        texte = kata.source.read_text(encoding="utf-8")
        for champ in sorted(connus - autorises):
            if re.search(rf"\b{re.escape(champ)}\b", texte):
                anomalies.append(
                    Anomalie(
                        "contrebande",
                        f"kata.{kata.id}",
                        f"{kata.source.name} cite {champ!r}, hors de son contrat",
                    )
                )
    return anomalies


def verifier(harness: Harness, coupes, registre: dict) -> tuple[Anomalie, ...]:
    """Toutes les anomalies, d'un coup — comme la validation du manifest."""
    anomalies: list[Anomalie] = []
    anomalies += _registre_canonique(harness, registre)
    anomalies += _contrat(harness)
    anomalies += _contrebande(harness, registre)

    for coupe in coupes:
        ou = f"{coupe.cible}/{coupe.kata}"
        anomalies += _marqueurs_residuels(ou, coupe.texte)
        anomalies += _vocabulaire_interdit(harness, ou, coupe.texte)
        anomalies += _decomptes(ou, coupe.texte)
    return tuple(anomalies)


def charger_registre(harness: Harness) -> dict:
    donnees = yaml.safe_load(harness.trempe.registre.read_text(encoding="utf-8")) or {}
    return donnees if isinstance(donnees, dict) else {}
