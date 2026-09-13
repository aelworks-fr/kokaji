"""Lire et réécrire un YAML **de source**, sans perdre ce qui l'entoure.

Un manifest de harness, une source de kata, le fichier d'utilisateurs du
portail : ce ne sont pas des données, ce sont des **sources**, et ce projet
écrit ses raisons à côté de ses décisions. Le
premier scellement réel de l'Atelier a réécrit son manifest par `yaml.safe_dump`
et emporté quarante lignes de commentaires — l'en-tête, le pourquoi de
`non_requis`, celui des seuils explicites, celui des deux corpus. Le fichier est
passé de 155 lignes à 122, et l'ordre des clés avec.

Rien ne l'avait montré jusque-là parce qu'aucun scellement n'avait jamais eu
lieu : le défaut attendait le premier usage réel du geste. Le fichier du portail
a perdu son en-tête le même jour, par la même cause, à la première inscription
réelle — d'où ce module remonté d'un cran : ce n'est pas une affaire de
conception, c'est une affaire d'écriture.

L'aller-retour ne rend pas le fichier au caractère près — les accolades des
mappages en ligne perdent leurs espaces intérieurs. C'est cosmétique, stable, et
sans commune mesure avec ce qu'on gardait avant : rien.
"""

from __future__ import annotations

import io
from pathlib import Path

from ruamel.yaml import YAML

__all__ = ["charger_source", "charger_texte", "ecrire_source", "rendre_source"]


def _yaml(largeur: int | None = None) -> YAML:
    y = YAML()
    y.preserve_quotes = True
    # L'indentation des séquences du projet : deux espaces de plus que leur clé.
    y.indent(mapping=2, sequence=4, offset=2)
    if largeur is not None:
        y.width = largeur
    return y


def charger_source(chemin: Path):
    """Le document, avec ses commentaires et l'ordre de ses clés."""
    return _yaml().load(Path(chemin).read_text(encoding="utf-8")) or {}


def charger_texte(texte: str):
    """Comme `charger_source`, sur un texte déjà en main.

    Une fiche de ha porte son YAML entre deux `---`, au milieu d'un markdown :
    il n'y a pas de fichier à charger, seulement une part de fichier.
    """
    return _yaml().load(texte) or {}


def rendre_source(document, largeur: int | None = None) -> str:
    """Le document en texte, sans l'écrire — pour qui écrit d'abord à côté.

    Le portail écrit dans un brouillon, relit, puis bascule : un fichier à
    moitié écrit enferme tout le monde dehors. Il lui faut donc le texte, pas
    une écriture.

    `largeur` évite qu'une valeur longue se replie sur deux lignes. On ne la
    force pas partout : sur un manifest, une largeur généreuse déplierait les
    scalaires repliés à la main, et le fichier changerait sans qu'on l'ait
    voulu. Là où aucun humain ne relit — le fichier du portail — on la force,
    parce qu'un hachage coupé en deux se lit mal et ne se répare pas à l'œil.
    """
    sortie = io.StringIO()
    _yaml(largeur).dump(document, sortie)
    return sortie.getvalue()


def ecrire_source(chemin: Path, document) -> None:
    """Réécrit le document en gardant ce que l'aller-retour a préservé."""
    Path(chemin).write_text(rendre_source(document), encoding="utf-8")
