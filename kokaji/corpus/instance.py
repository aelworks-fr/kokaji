"""L'instance s'exporte entière, et s'importe — rien de captif (RFC-014 D14.8).

`exporter` écrit tout ce que la base contient au format fichiers : un dossier
`CAS-XXXX/` par ha, rangé par harness et par corpus ; les écartés à côté ; le
journal en JSONL, un fichier par jour. `importer` fait l'inverse — depuis un
export, ou depuis le dossier des harness d'une instance en régime fichiers et
son journal : c'est le chemin de la migration (§6).

Le manifeste de l'export retient où chaque corpus vivait sur l'instance : un
ha est nommé par le chemin de son corpus, et l'import le remet au même endroit
— ou ailleurs, si on le lui dit.

Ce module ne connaît aucun domaine : il déplace des pièces, il n'en lit pas le
sens.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ..comptes import Comptes, transvaser
from ..hds import ManifestInvalide, charger
from .base import DepotBase, JournalBase
from .depot import DepotFichiers, RefHa, transferer
from .journal import lire_fichiers

__all__ = ["MANIFESTE", "Bilan", "exporter", "importer"]

MANIFESTE = "manifeste.json"
COMPTES = "comptes.sqlite3"


@dataclass
class Bilan:
    """Ce qui a été déplacé — à comparer des deux côtés (sabotage 4)."""

    ha: int = 0
    appels: int = 0
    ecartes: int = 0
    comptes: dict[str, int] = field(default_factory=dict)
    corpus: list[str] = field(default_factory=list)
    identifiants: list[str] = field(default_factory=list)


def _dossier_de(harness: str, corpus_nom: str, chemin: str) -> str:
    """Où ranger un corpus dans l'export : `<harness>/<nom>`, ou le chemin
    aplati quand il n'a pas cette forme."""
    if harness and corpus_nom:
        return f"{harness}/{corpus_nom}"
    return chemin.strip("/").replace("/", "__") or "corpus"


def exporter(
    base: DepotBase, journal: JournalBase, dossier: Path, comptes: Comptes | None = None
) -> Bilan:
    """Tout ce que la base contient, au format fichiers, sous `dossier` — les
    comptes, s'ils sont donnés, en un fichier SQLite (D14.7 : même schéma)."""
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    fichiers = DepotFichiers()
    bilan = Bilan()
    manifeste: dict[str, str] = {}

    for chemin, harness, corpus_nom in base.corpus_connus():
        ou = _dossier_de(harness, corpus_nom, chemin)
        manifeste[ou] = chemin
        corpus_source = Path(chemin)
        corpus_cible = dossier / "ha" / ou
        corpus_cible.mkdir(parents=True, exist_ok=True)
        for ref in base.tous(corpus_source):
            transferer(ref, base, fichiers, corpus=corpus_cible)
            bilan.ha += 1
            bilan.identifiants.append(f"{ou}/{ref.nom}")
        for ecart in base.ecartes(corpus_source):
            fichiers.ecarter(corpus_cible, ecart["session"], ecart["raison"], ecart["le"])
            bilan.ecartes += 1
        bilan.corpus.append(ou)

    par_jour: dict[str, list[dict]] = {}
    for ligne in journal.appels():
        jour = str(ligne.get("debut") or "")[:10] or "sans-date"
        par_jour.setdefault(jour, []).append(ligne)
    if par_jour:
        (dossier / "journal").mkdir(parents=True, exist_ok=True)
    for jour, lignes in sorted(par_jour.items()):
        (dossier / "journal" / f"{jour}.jsonl").write_text(
            "".join(json.dumps(l, ensure_ascii=False, default=str) + "\n" for l in lignes),
            encoding="utf-8",
        )
        bilan.appels += len(lignes)

    if comptes is not None:
        fichier = dossier / COMPTES
        fichier.unlink(missing_ok=True)
        vers = Comptes(fichier)
        try:
            bilan.comptes = transvaser(comptes, vers)
        finally:
            vers.fermer()

    (dossier / MANIFESTE).write_text(
        json.dumps({"corpus": manifeste}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return bilan


def _corpus_d_un_export(dossier: Path) -> list[tuple[Path, str]]:
    """(dossier du corpus dans l'export, chemin d'origine) — par le manifeste."""
    manifeste = json.loads((dossier / MANIFESTE).read_text(encoding="utf-8"))
    return [(dossier / "ha" / ou, chemin) for ou, chemin in (manifeste.get("corpus") or {}).items()]


def _corpus_des_harness(dossier: Path) -> list[tuple[Path, str]]:
    """(corpus, son propre chemin) pour chaque harness valide sous `dossier` —
    la migration d'une instance en régime fichiers. Un manifest invalide est
    sauté : on migre ce qui se lit, on ne devine pas le reste."""
    trouves = []
    for manifest in sorted(dossier.glob("*/harness.yaml")):
        try:
            harness = charger(manifest.parent)
        except ManifestInvalide:
            continue
        for corpus in harness.corpus_nommes:
            trouves.append((corpus.chemin, str(corpus.chemin.resolve())))
    return trouves


def importer(
    base: DepotBase,
    journal: JournalBase,
    dossier: Path,
    journal_fichiers: Path | None = None,
    vers: Path | None = None,
    comptes: Comptes | None = None,
    comptes_fichier: Path | None = None,
) -> Bilan:
    """Dans la base : un export (`manifeste.json`) ou le dossier des harness
    d'une instance. `journal_fichiers` : le journal en JSONL, s'il est ailleurs
    que dans l'export. `vers` : le dossier des harness de l'instance d'arrivée,
    quand ce n'est pas celui d'origine — les chemins de corpus y sont
    transposés (`<vers>/<harness>/corpus/<nom>`). `comptes` : le magasin
    d'arrivée, rempli depuis `comptes_fichier` ou le SQLite de l'export."""
    dossier = Path(dossier)
    fichiers = DepotFichiers()
    bilan = Bilan()

    est_export = (dossier / MANIFESTE).is_file()
    corpus = _corpus_d_un_export(dossier) if est_export else _corpus_des_harness(dossier)
    for source, chemin in corpus:
        cible = Path(chemin)
        if vers is not None and "corpus" in Path(chemin).parts[1:]:
            morceaux = Path(chemin).parts
            i = len(morceaux) - 1 - morceaux[::-1].index("corpus")
            cible = Path(vers, morceaux[i - 1], *morceaux[i:])
        for ref in fichiers.tous(source):
            transferer(ref, fichiers, base, corpus=cible)
            bilan.ha += 1
            bilan.identifiants.append(f"{cible}/{ref.nom}")
        for ecart in fichiers.ecartes(source):
            base.ecarter(cible, ecart["session"], ecart["raison"], ecart["le"])
            bilan.ecartes += 1
        bilan.corpus.append(str(cible))

    for ou in (dossier / "journal" if est_export else None, journal_fichiers):
        for ligne in lire_fichiers(ou):
            journal.ecrire(ligne)
            bilan.appels += 1

    source_comptes = comptes_fichier or (dossier / COMPTES if est_export else None)
    if comptes is not None and source_comptes is not None and Path(source_comptes).is_file():
        de = Comptes(source_comptes)
        try:
            bilan.comptes = transvaser(de, comptes)
        finally:
            de.fermer()
    return bilan


def ref_dans_les_fichiers(ref: RefHa, base: DepotBase) -> RefHa:
    """Un ha de la base, écrit au même chemin sur le disque — la promotion
    (D14.5) : le clone du harness reçoit le `CAS-XXXX/` que le scellement
    suivant commitera."""
    return transferer(ref, base, DepotFichiers())
