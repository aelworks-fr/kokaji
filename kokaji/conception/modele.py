"""Concevoir un harness — le brouillon, son verdict, son scellement.

Le module « Design du harness » édite trois choses, et elles ont déjà leur place
dans le HDS : **le partitionnement** (combien de kata, comment ils s'enchaînent),
**le contrat** de chacun (`herite` / `produit`, le f♯ du RFC-002) et **la
trempe** (vocabulaire interdit, checks de session, seuils). Rien de nouveau n'est
introduit ici : on édite de la donnée existante.

Le principe qui tient tout ce module :

> **Une modification qui ne tient pas ne s'enregistre pas.**

La forge refuse déjà d'écrire une coupe fautive — elle assemble en mémoire,
trempe, et lève avant d'avoir touché un fichier. La conception hérite de cette
garantie : un brouillon est vérifié sur une copie, et rien n'est écrit tant que
le verdict n'est pas net. Il n'y a donc pas de brouillon invalide enregistré
« pour plus tard » : ce serait une définition à laquelle plus personne ne peut
se fier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

__all__ = ["Changement", "Proposition", "Verdict"]


@dataclass(frozen=True)
class Changement:
    """Un écart entre la définition en place et celle qu'on propose."""

    ou: str  # `kata.idee.produit`, `trempe.checks_session`, `chaine.noeuds`…
    avant: str
    apres: str
    # Un changement de f♯ n'est pas un changement comme un autre : il invalide
    # les certifications du kata (RFC-002 §3). On le marque à la source plutôt
    # que de le redécouvrir au moment de sceller.
    touche_contrat: bool = False

    def __str__(self) -> str:
        marque = " [f♯]" if self.touche_contrat else ""
        return f"{self.ou}{marque} : {self.avant} → {self.apres}"


@dataclass(frozen=True)
class Verdict:
    """Ce que vaut un brouillon. Il n'y a pas de demi-verdict.

    `anomalies` vient de la trempe statique — les mêmes lints qui gardent la
    forge. `fautes` vient de la validation du manifest. Les deux doivent être
    vides pour que le brouillon puisse être scellé.
    """

    fautes: tuple[str, ...] = ()
    anomalies: tuple[str, ...] = ()
    changements: tuple[Changement, ...] = ()

    @property
    def tient(self) -> bool:
        return not self.fautes and not self.anomalies

    @property
    def touche_contrat(self) -> bool:
        """Un f♯ a-t-il bougé ? C'est ce qui décide de la version majeure."""
        return any(c.touche_contrat for c in self.changements)

    @property
    def kata_touches(self) -> tuple[str, ...]:
        """Les kata dont le contrat change — ceux dont la version devient majeure."""
        vus = {
            c.ou.split(".")[1]
            for c in self.changements
            if c.touche_contrat and c.ou.startswith("kata.")
        }
        return tuple(sorted(vus))

    def __str__(self) -> str:
        if not self.changements:
            return "rien ne change"
        if self.tient:
            return f"{len(self.changements)} changement(s), la définition tient"
        return (
            f"{len(self.changements)} changement(s) — "
            f"{len(self.fautes)} faute(s), {len(self.anomalies)} anomalie(s)"
        )


@dataclass(frozen=True)
class Proposition:
    """Ce qu'on veut changer, dans le vocabulaire du HDS lui-même.

    Une proposition est **partielle** : elle ne décrit que ce qui bouge. Ce qui
    n'y figure pas ne bouge pas — un formulaire qui renverrait l'intégralité de
    la définition à chaque geste ferait de toute lecture concurrente un écrasement.

    Trois entrées, une par axe du module :

    - `kata` — le partitionnement **et** les contrats : une entrée par kata
      touché, au format du manifest (`id`, `nom`, `amont`, `herite`, `produit`,
      `emet_options`…). Un kata absent du manifest est ajouté ; un id listé dans
      `retirer` est supprimé, avec ses arêtes.
    - `chaine` — les nœuds et arêtes, quand la topologie ne se déduit pas des
      seuls `amont`.
    - `trempe` — vocabulaire interdit, checks de session, seuils de justesse.

    `source` porte les variables de template d'un kata (rôle, questions,
    interdits, natures…) : c'est le fichier `kata/<id>.yaml`, pas le manifest —
    le densho du kata (RFC-010 D10.2).

    `template` porte le gabarit entier, texte brut avec ses variables : c'est le
    fichier que le manifest désigne, la doctrine commune à toute la chaîne
    (RFC-010 D10.1). Absent, le gabarit ne bouge pas.
    """

    kata: list[dict] = field(default_factory=list)
    retirer: list[str] = field(default_factory=list)
    chaine: dict = field(default_factory=dict)
    trempe: dict = field(default_factory=dict)
    source: dict[str, dict] = field(default_factory=dict)
    template: str | None = None

    @property
    def vide(self) -> bool:
        return not (
            self.kata
            or self.retirer
            or self.chaine
            or self.trempe
            or self.source
            or self.template is not None
        )

    @property
    def touche_le_texte(self) -> bool:
        """Le gabarit ou un densho bougent — ce qu'un harness adopté ne sait pas recevoir."""
        return self.template is not None or bool(self.source)

    CLES: ClassVar[tuple[str, ...]] = ("kata", "retirer", "chaine", "trempe", "source", "template")

    @classmethod
    def depuis(cls, donnees: dict) -> Proposition:
        if not isinstance(donnees, dict):
            raise TypeError("une proposition est une section, pas une valeur")
        inconnues = set(donnees) - set(cls.CLES)
        if inconnues:
            raise ValueError(
                f"clé(s) hors du vocabulaire d'une proposition : {', '.join(sorted(inconnues))} "
                f"(attendu : {', '.join(cls.CLES)})"
            )
        template = donnees.get("template")
        if template is not None and not isinstance(template, str):
            raise TypeError("`template` est le texte du gabarit, pas une structure")
        return cls(
            kata=list(donnees.get("kata") or []),
            retirer=[str(x) for x in (donnees.get("retirer") or [])],
            chaine=dict(donnees.get("chaine") or {}),
            trempe=dict(donnees.get("trempe") or {}),
            source={str(k): dict(v) for k, v in (donnees.get("source") or {}).items()},
            template=template,
        )


@dataclass(frozen=True)
class Scellement:
    """Un changement de définition, daté et signé.

    Le RFC-004 §3 ouvre le scellement à tout co-auteur, et le fait tenir par la
    traçabilité plutôt que par la rareté du droit : **chaque scellement porte le
    nom de son auteur**. Sans auteur, on ne scelle pas.
    """

    auteur: str
    motif: str
    quand: str
    versions: dict[str, str]
    changements: tuple[str, ...]
    racine: Path | None = None
    # Le commit qui porte ce scellement dans le dépôt du harness (D9.1), ou la
    # raison pour laquelle il n'y en a pas — jamais un silence.
    commit: str = ""
    commit_motif: str = ""
