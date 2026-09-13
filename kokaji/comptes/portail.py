"""Inscrire au portail — une seule identité pour tout (RFC-004 §6, amendé).

Kokaji, le chat et le portail sont trois logiciels ; une personne ne doit
connaître qu'un mot de passe et ne le taper qu'une fois. C'est le portail qui
tient l'identité : les deux autres lui font confiance par en-tête. Reste à ce
qu'un compte créé chez Kokaji existe aussi chez lui — sinon l'invité crée son
compte et se fait arrêter à la porte.

Ce module écrit donc dans le fichier d'utilisateurs du portail. C'est un
**couplage assumé** entre l'application et son infrastructure, et il a un prix :
un fichier à moitié écrit ferme le portail **pour tout le monde**. D'où deux
précautions qui ne sont pas négociables :

- on écrit à côté, on relit ce qu'on a écrit, et on ne bascule qu'ensuite —
  `os.replace` est atomique sur le même système de fichiers ;
- on n'écrase jamais une entrée existante : inscrire quelqu'un qui est déjà là
  est une erreur, pas une mise à jour silencieuse de son mot de passe.

Kokaji ne lit jamais ce fichier pour authentifier : il ne fait qu'y ajouter.
L'authentification appartient au portail, et rien ici ne la contourne.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml
from argon2 import PasswordHasher

from ..yaml_source import charger_source, rendre_source

__all__ = ["PortailIndisponible", "inscrire"]


class PortailIndisponible(Exception):
    """Le fichier du portail est absent, illisible, ou déjà occupé par ce nom."""


def inscrire(
    fichier: Path,
    email: str,
    nom: str,
    mot_de_passe: str,
    groupes: tuple[str, ...] = ("praticiens",),
) -> str:
    """Ajoute une personne au portail. Rend l'identifiant retenu.

    L'identifiant **est l'email** : un seul mot à retenir, le même partout, et
    aucune règle de nommage à inventer.
    """
    chemin = Path(fichier)
    if not chemin.is_file():
        raise PortailIndisponible(f"fichier du portail introuvable : {chemin}")

    # Chargé en aller-retour : ce fichier porte trois lignes qui disent ce qu'il
    # est et pourquoi ce n'est pas une base. `yaml.safe_dump` les effaçait à
    # chaque inscription — même cause que le manifest, trouvée le même jour.
    try:
        donnees = charger_source(chemin)
    except Exception as err:
        raise PortailIndisponible(f"fichier du portail illisible : {err}") from err

    utilisateurs = donnees.get("users")
    if not isinstance(utilisateurs, dict):
        raise PortailIndisponible("le fichier du portail ne déclare pas de section `users`")

    identifiant = email.strip().lower()
    if identifiant in utilisateurs:
        raise PortailIndisponible(f"le portail connaît déjà {identifiant}")

    utilisateurs[identifiant] = {
        "disabled": False,
        "displayname": nom.strip() or identifiant,
        "password": PasswordHasher().hash(mot_de_passe),
        "email": email.strip(),
        "groups": list(groupes),
    }

    # Écrire à côté, relire, puis basculer. Un portail cassé enferme tout le
    # monde dehors, y compris celui qui pourrait le réparer.
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=chemin.parent, prefix=chemin.name + ".", delete=False
    ) as brouillon:
        # Large : un hachage argon2 replié sur deux lignes reste valide, mais
        # ne se relit pas et ne se répare pas à l'œil.
        brouillon.write(rendre_source(donnees, largeur=4096))
        provisoire = Path(brouillon.name)

    try:
        relu = yaml.safe_load(provisoire.read_text(encoding="utf-8")) or {}
        if identifiant not in (relu.get("users") or {}):
            raise PortailIndisponible("le fichier réécrit ne contient pas l'inscription")
        os.replace(provisoire, chemin)
    except Exception:
        provisoire.unlink(missing_ok=True)
        raise

    return identifiant
