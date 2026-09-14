"""Les deux relations du RFC-004 §2 — l'autorat et la pratique.

Kokaji lie une personne au système de deux façons qui n'obéissent pas aux mêmes
règles, et tout ce module existe pour qu'on ne les confonde jamais :

- **L'autorat** — on possède ou on contribue à la *définition* d'un harness.
  C'est l'ACL, et elle se partage.
- **La pratique** — on déroule des sessions sur ses propres sujets. Elle ne se
  partage pas : elle se verse, ha par ha, au choix de celui qui a pratiqué.

Contribuer à un harness ne donne donc aucun droit sur la pratique des autres.
C'est l'exigence R12.4, et c'est celle dont tout le reste dépend.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

__all__ = [
    "CONTRIBUTEUR",
    "ETRANGER",
    "PRIVEE",
    "PROPRIETAIRE",
    "ROLES",
    "VERSE",
    "VISIBILITES",
    "Acl",
    "AclInvalide",
    "Utilisateur",
    "email_plausible",
]

PROPRIETAIRE = "proprietaire"
CONTRIBUTEUR = "contributeur"
ETRANGER = "etranger"
ROLES = (PROPRIETAIRE, CONTRIBUTEUR, ETRANGER)

# La visibilité d'un ha. Deux valeurs, et un axe **orthogonal** au cycle de vie
# `brut → anonymise → annote` du RFC-001 : un ha peut être annoté et privé, ou
# brut et versé. Les empiler sur un seul axe reviendrait à dire qu'annoter,
# c'est publier — ce n'est pas vrai, et ce serait une fuite.
PRIVEE = "privee"
VERSE = "verse"
VISIBILITES = (PRIVEE, VERSE)

# Assez pour attraper une faute de frappe, pas assez pour prétendre valider une
# adresse : seul un envoi le prouve. Le RFC dit « vérifiable », pas « vérifié ».
COURRIEL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AclInvalide(Exception):
    """Un invariant d'autorat qu'on a tenté d'enfreindre (RFC-004 §2.2)."""


def email_plausible(email: str) -> bool:
    return bool(COURRIEL.match((email or "").strip()))


@dataclass(frozen=True)
class Utilisateur:
    """RFC-004 §2.1.

    `id` est un uuid **stable et indépendant de tout fournisseur**. C'est ce qui
    permettra de rattacher un compte OAuth plus tard sans rien réécrire : le
    lien se fera dans `identites_externes`, et l'email servira de clé de
    rapprochement. Rien de tout cela n'est codé en v1 — seule la place est
    tenue.
    """

    id: str
    nom: str
    email: str
    cree_le: datetime

    def __post_init__(self):
        if not self.nom.strip():
            raise AclInvalide("un utilisateur sans nom")
        if not email_plausible(self.email):
            raise AclInvalide(f"email invraisemblable : {self.email!r}")


@dataclass(frozen=True)
class Acl:
    """RFC-004 §2.2 — qui co-forge un harness.

    Trois invariants, tenus ici plutôt qu'au magasin, pour qu'aucun chemin ne
    puisse fabriquer une ACL malformée — pas même un test :

    1. **Exactement un propriétaire, toujours.** Pas zéro, pas deux.
    2. **Le propriétaire n'est pas dans les contributeurs.** Sinon son rôle
       dépendrait de l'ordre de lecture.
    3. Le transfert est un geste explicite : voir `transferee_a`.
    """

    harness_id: str
    proprietaire: str
    contributeurs: tuple[str, ...] = field(default=())

    def __post_init__(self):
        if not self.harness_id.strip():
            raise AclInvalide("une ACL sans harness")
        if not self.proprietaire.strip():
            raise AclInvalide("une ACL sans propriétaire : un harness en a toujours un")
        if self.proprietaire in self.contributeurs:
            raise AclInvalide(
                "le propriétaire figure aussi dans les contributeurs : "
                "son rôle dépendrait de l'ordre de lecture"
            )
        if len(set(self.contributeurs)) != len(self.contributeurs):
            raise AclInvalide("un contributeur listé deux fois")

    def role(self, utilisateur_id: str) -> str:
        if utilisateur_id == self.proprietaire:
            return PROPRIETAIRE
        if utilisateur_id in self.contributeurs:
            return CONTRIBUTEUR
        return ETRANGER

    @property
    def membres(self) -> tuple[str, ...]:
        return (self.proprietaire, *self.contributeurs)

    def avec(self, utilisateur_id: str) -> Acl:
        """Ajoute un contributeur. Idempotent ; le propriétaire n'en devient pas un."""
        if utilisateur_id == self.proprietaire or utilisateur_id in self.contributeurs:
            return self
        return Acl(self.harness_id, self.proprietaire, (*self.contributeurs, utilisateur_id))

    def sans(self, utilisateur_id: str) -> Acl:
        """Retire un contributeur. Retirer le propriétaire est impossible."""
        if utilisateur_id == self.proprietaire:
            raise AclInvalide(
                "on ne retire pas le propriétaire d'un harness : "
                "il faut d'abord transférer la propriété"
            )
        return Acl(
            self.harness_id,
            self.proprietaire,
            tuple(c for c in self.contributeurs if c != utilisateur_id),
        )

    def transferee_a(self, utilisateur_id: str, garder_ancien: bool = True) -> Acl:
        """Transfère la propriété (RFC-004 §2.2).

        L'ancien propriétaire devient contributeur — sauf retrait explicite.
        Le défaut est de garder : perdre son accès à un harness qu'on a écrit
        parce qu'on en a confié la barre serait une surprise, pas une règle.
        """
        if not utilisateur_id.strip():
            raise AclInvalide("un transfert sans destinataire")
        if utilisateur_id == self.proprietaire:
            return self
        restants = [c for c in self.contributeurs if c != utilisateur_id]
        if garder_ancien:
            restants.append(self.proprietaire)
        return Acl(self.harness_id, utilisateur_id, tuple(restants))


@dataclass(frozen=True)
class Enregistrement:
    """RFC-012 D12.2 — le dépôt nu auquel un harness est enregistré.

    Une métadonnée d'instance, jamais du manifest : le dépôt ne sait pas où il
    est enregistré. `commit_reference` est le dernier commit connu du dépôt nu
    pour cette branche — ce qui permet de dire « à jour » ou « en avance » sans
    le relire à chaque page.
    """

    harness_id: str
    chemin: str
    branche: str = "main"
    commit_reference: str = ""
    pousser_au_scellement: bool = True
    enregistre_le: str = ""
