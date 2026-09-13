"""Faire naître un harness, par copie d'une œuvre qui marche — RFC-006 §3.

Une semence vide validerait, et livrerait quatre cent quatre-vingts lignes à
écrire avant le premier échange. Le premier pas est le seul qui décide si
quelqu'un reste : on part donc d'un harness éprouvé, et l'on adapte.

**La définition se copie ; la pratique jamais.** Le corpus de la copie est vide.
Les ha appartiennent à leur praticien (R12.4) et ne suivent pas la définition —
sans cet invariant, copier deviendrait le contournement de tout le RFC-004 : il
suffirait de copier pour lire.

L'invariant de naissance (§7.5) : ce qui sort d'ici **valide, forge et trempe
sans retouche**. Une copie qu'il faudrait réparer avant de s'en servir ne serait
pas une naissance, mais un gabarit.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .conception import JOURNAL
from .hds import Harness, charger

__all__ = [
    "SEMENCE",
    "VERSION_INITIALE",
    "NaissanceRefusee",
    "copier",
    "naitre",
    "scelle",
    "semer",
]

# Le corpus ne se copie jamais : il est recréé vide. Tout le reste de la
# définition suit — template, registre, kata, personas.
#
# **Le journal des scellements ne suit pas non plus.** Il porte la lignée de
# l'original : qui l'a arrêté, quand, et pourquoi. Une copie qui l'emporterait
# naîtrait en revendiquant des versions signées par quelqu'un qui ne l'a jamais
# vue — et le §7 du RFC-006 l'a trouvée « déjà scellée » à sa naissance, ce
# qu'elle n'était pas. La définition se copie ; la lignée, comme la pratique,
# appartient à qui l'a faite.
HORS_COPIE = frozenset({".git", "__pycache__", JOURNAL})

# Une copie est une œuvre neuve, pas la suite de l'originale. Garder la version
# de la source lui ferait revendiquer une lignée de scellements qu'elle n'a pas.
VERSION_INITIALE = "0.1.0"

# Le squelette livré avec Kokaji : un harness sans domaine, qui vaut, se forge
# et se trempe tel quel. Ce n'est pas un second harness d'exemple (SPECS §9) —
# il ne décrit aucun métier, il n'en tient que la structure.
SEMENCE = Path(__file__).resolve().parent / "semence"


class NaissanceRefusee(Exception):
    """La copie n'a pas eu lieu, et rien n'a été écrit."""


def copier(source: Harness, vers: Path, identifiant: str, nom: str) -> Path:
    """Copie la définition de `source` sous un id neuf, avec un corpus vide.

    `vers` est le dossier **des** harness ; la copie y prend le nom de son id,
    parce que c'est ainsi que `charger_valides` la retrouvera.

    Rien n'est écrit tant que tout n'est pas décidé : un dossier à moitié né se
    lirait comme un harness cassé, et la vigie le compterait comme une panne.
    """
    vers = Path(vers)
    if not identifiant.strip() or not nom.strip():
        raise NaissanceRefusee("un id et un nom sont exigés")

    dossier = vers / identifiant
    if dossier.exists():
        raise NaissanceRefusee(f"un dossier porte déjà ce nom : {identifiant}")

    manifest = _manifest_recopie(source, identifiant, nom)

    dossier.mkdir(parents=True)
    try:
        for enfant in sorted(source.racine.iterdir()):
            if enfant.name in HORS_COPIE or enfant.name == "harness.yaml":
                continue
            if enfant.is_dir():
                shutil.copytree(
                    enfant, dossier / enfant.name,
                    ignore=shutil.ignore_patterns(*HORS_COPIE),
                )
            else:
                shutil.copy2(enfant, dossier / enfant.name)

        _vider_les_corpus(source, dossier)
        (dossier / "harness.yaml").write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    except OSError as err:
        # Une naissance à moitié faite est pire que pas de naissance : on retire.
        shutil.rmtree(dossier, ignore_errors=True)
        raise NaissanceRefusee(f"copie interrompue : {err}") from err

    return dossier


def _manifest_recopie(source: Harness, identifiant: str, nom: str) -> dict:
    """Le manifest de la source, sous une identité neuve.

    On relit le fichier plutôt que de re-sérialiser l'objet chargé : le manifest
    porte des choses que le modèle en mémoire ne garde pas — l'ordre des clés,
    les valeurs par défaut laissées implicites. Le recomposer les inventerait.
    """
    donnees = yaml.safe_load((source.racine / "harness.yaml").read_text(encoding="utf-8"))
    if not isinstance(donnees, dict):
        raise NaissanceRefusee("manifest source illisible")

    entete = dict(donnees.get("harness") or {})
    entete["id"] = identifiant
    entete["nom"] = nom
    entete["version"] = VERSION_INITIALE
    donnees["harness"] = entete
    return donnees


def _vider_les_corpus(source: Harness, dossier: Path) -> None:
    """Recrée les dossiers de corpus déclarés, vides.

    Les chemins viennent du manifest et non d'une convention : un harness peut
    déclarer plusieurs corpus, ailleurs que sous `corpus/`. Les deviner ferait
    naître une copie dont les corpus pointent sur des dossiers absents.
    """
    for corpus in source.corpus_nommes:
        relatif = corpus.chemin.relative_to(source.racine.resolve())
        cible = dossier / relatif
        shutil.rmtree(cible, ignore_errors=True)
        cible.mkdir(parents=True, exist_ok=True)


def naitre(source: Harness, vers: Path, identifiant: str, nom: str) -> Harness:
    """Copie, puis **charge la copie** — l'invariant du §7.5, tenu et non promis.

    Charger ce qu'on vient d'écrire est le seul moyen de savoir qu'une naissance
    a produit un harness et non un dossier. Si la copie ne tient pas, elle est
    retirée : mieux vaut aucune naissance qu'une naissance à réparer.
    """
    dossier = copier(source, vers, identifiant, nom)
    try:
        return charger(dossier)
    except Exception as err:
        shutil.rmtree(dossier, ignore_errors=True)
        raise NaissanceRefusee(f"la copie ne tient pas : {err}") from err


def scelle(harness: Harness) -> bool:
    """Ce harness a-t-il été scellé au moins une fois — RFC-006 §4 ?

    Un harness qui ne l'a jamais été est un **brouillon** : ses co-auteurs le
    pratiquent au QG, mais il n'offre aucun modèle au chat. Ce n'est pas une
    politique, c'est un fait — ses coupes ne sont pas forgées, et un modèle
    virtuel sans coupe répondrait 404.

    La preuve est le journal des scellements, qui vit dans le dossier du
    harness : une naissance en produit un vide, un scellement y écrit.
    """
    fichier = harness.template.parent / JOURNAL
    if not fichier.is_file():
        return False
    return any(ligne.strip() for ligne in fichier.read_text(encoding="utf-8").splitlines())


def semer(vers: Path, identifiant: str, nom: str) -> Harness:
    """Fait naître un harness **sans rien copier de personne** — RFC-006 §3.

    Partir d'une copie donne une forme qui marche ; partir d'une semence donne
    une page presque blanche. Les deux ont leur usage : on copie quand une
    méthode voisine existe, on sème quand la sienne ne ressemble à rien de ce
    qu'on a déjà.

    La semence n'est pas un harness d'exemple : elle ne décrit aucun métier. Ce
    qu'elle garantit est plus étroit et plus utile — elle **vaut, se forge et se
    trempe telle quelle**, si bien qu'on peut pratiquer avant d'avoir écrit une
    ligne, et remplacer ensuite.
    """
    return naitre(charger(SEMENCE), vers, identifiant, nom)
