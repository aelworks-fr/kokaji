"""Les objets du HDS — la structure d'un harness, sans rien de son domaine.

Kokaji ne manipule que ces formes (SPECS §0). Le champ `domaine` est transporté
tel quel et n'est jamais interprété : il ne sert qu'à la documentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

VERSION_HDS = "0"


# RFC-016 §2 — le triplet. Un kata est une étape qui agit : il perçoit, il porte
# une intention méta, il produit des effets. Deux systèmes, trois canaux.
CANAUX = ("modele", "monde_lecture", "monde_ecriture")

# Les raccourcis du manifeste (RFC-016 §2) : des noms d'usage qui se développent
# mécaniquement en canaux. `echange` (le kata conversationnel) est le cas par
# défaut — un manifeste d'avant la RFC-016 le vaut sans retouche. Un raccourci
# n'ajoute aucune sémantique : il dit seulement quels canaux du monde s'ouvrent.
RACCOURCIS = {
    "echange": (),
    "sonde": ("monde_lecture",),
    "production": ("monde_ecriture",),
    "commande": ("monde_ecriture",),
}


@dataclass(frozen=True)
class Effets:
    """Ce qu'une étape change, par canal (RFC-016 §2).

    `modele` est universel : tout kata émet un bloc d'état, c'est cet effet-là,
    et il se lit dans le `produit` du contrat f♯ — on ne le redéclare pas ici.
    Les deux canaux du monde sont optionnels et nommés champ par champ.
    """

    monde_lecture: tuple[str, ...] = ()
    monde_ecriture: tuple[str, ...] = ()

    @property
    def touche_le_monde(self) -> bool:
        return bool(self.monde_lecture or self.monde_ecriture)

    @property
    def sur_le_monde(self) -> tuple[str, ...]:
        """Tous les effets du monde, lecture et écriture — ce que la perception
        doit pouvoir constater (interdit n°1, RFC-016 §2)."""
        return self.monde_lecture + self.monde_ecriture


@dataclass(frozen=True)
class Perception:
    """Ce qu'une étape perçoit (RFC-016 §2) : ses entrées, et les **retours**
    par lesquels elle constate ce que son action a fait."""

    entrees: tuple[str, ...] = ()
    retours: tuple[str, ...] = ()


@dataclass(frozen=True)
class Kata:
    """Une forme codifiée d'étape décisionnelle qui agit (RFC-016 §2)."""

    id: str
    nom: str
    source: Path
    livrable: str
    amont: tuple[str, ...]
    # RFC-002 §3 — le contrat f♯, en deux moitiés. Les deux parlent le même
    # vocabulaire : les champs des blocs d'état, qualifiés par le kata qui les
    # établit. `herite` est le domaine, `produit` le codomaine avec, pour chaque
    # champ, le statut minimal garanti.
    herite: tuple[str, ...]
    produit: tuple[tuple[str, str], ...]
    # Le seuil que ce kata exige d'un champ hérité, quand il en exige un.
    # Sans seuil, hériter veut dire « ce champ doit être présent, quel que soit
    # son statut » ; avec, il veut dire « et au moins à ce niveau-là ». C'est ce
    # qui rend vérifiable la clause d'ordre du RFC-002 §6.2 — sans seuil déclaré,
    # « couvre au sens de l'ordre des statuts » n'a rien à comparer.
    exigences: dict[str, str] = field(default_factory=dict)
    # RFC-001 : ce kata élicite et suit des options. Kokaji ne sait pas ce qu'est
    # une option dans ce domaine — il sait seulement que ce kata en déclare.
    emet_options: bool = False
    # RFC-011 D11.2 — un kata dont la source est un texte, servi tel quel : il
    # n'est pas assemblé depuis le gabarit, il porte sa provenance, et la
    # forge le choisit par kata. Un harness exogène (RFC-008) est le cas où
    # tous le sont.
    orphelin: bool = False
    provenance: tuple[tuple[str, str], ...] = ()
    # RFC-016 §2 — le triplet. Absents, ils valent l'échange : un kata qui ne
    # touche que le modèle (le bloc d'état). `raccourci` est le nom d'usage,
    # `effets` la déclaration par canal, `perception` les entrées et les retours,
    # `intention` l'objet décisionnel de l'étape (le champ `objet` du bloc).
    raccourci: str = "echange"
    intention: str = ""
    perception: Perception = field(default_factory=Perception)
    effets: Effets = field(default_factory=Effets)

    @property
    def agit_sur_le_monde(self) -> bool:
        """Ce kata dépasse-t-il l'échange — touche-t-il le monde ? (RFC-016)"""
        return self.effets.touche_le_monde


@dataclass(frozen=True)
class Cible:
    """Un profil de forge — une manière d'incarner les kata en coupes."""

    id: str
    etat_structure: bool
    en_tete: str
    packaging: str


@dataclass(frozen=True)
class Noeud:
    id: str
    type: str
    nom: str


@dataclass(frozen=True)
class Arete:
    de: str
    vers: str
    label: str


@dataclass(frozen=True)
class Chaine:
    """La topologie rendue par le QG (§8). Kokaji ne l'interprète pas."""

    noeuds: tuple[Noeud, ...]
    aretes: tuple[Arete, ...]


@dataclass(frozen=True)
class Critere:
    """Un critère de la grille de jugement — RFC-008 §7.

    L'échelle est déclarée avec la question : un score sans son échelle ne se
    relit pas, et une échelle implicite finit par varier d'un critère à
    l'autre sans que personne ne l'ait décidé.
    """

    id: str
    question: str
    echelle: str  # « 1-5 » — bornes comprises

    @property
    def bornes(self) -> tuple[int, int]:
        bas, haut = self.echelle.split("-", 1)
        return int(bas), int(haut)


@dataclass(frozen=True)
class Trempe:
    vocabulaire_interdit: tuple[str, ...]
    registre: Path
    checks_session: tuple[dict, ...]
    # RFC-003 §5.4 — ce que le harness tient pour un diagnostic acceptable.
    # Le seuil appartient au domaine : Kokaji compare et rapporte, il ne décide
    # pas de ce qui est bon. Il est écrit ici, donc **avant** la campagne qu'il
    # juge — un seuil ajusté après coup ne mesure plus le kata (carnet #9).
    justesse_defaut: float = 0.0
    justesse_par_kata: dict[str, float] = field(default_factory=dict)
    # RFC-008 §7 — la grille du judge, déclarée par le harness. Kokaji fournit
    # le mécanisme ; aucune question n'est écrite dans le code.
    grille_judge: tuple[Critere, ...] = ()

    def seuil_justesse(self, kata: str) -> float:
        """Le seuil de ce kata, ou celui du harness. Zéro si rien n'est déclaré.

        Zéro n'est pas une indulgence : c'est l'aveu qu'aucun seuil n'a été posé,
        et le rapport le dit tel quel plutôt que d'en inventer un.
        """
        return self.justesse_par_kata.get(kata, self.justesse_defaut)


@dataclass(frozen=True)
class Corpus:
    """Un corpus nommé, et les clés appelantes qui l'alimentent (HDS v0.2).

    Sans `cles`, le corpus prend tout ce qui n'appartient à aucun autre : c'est
    le corpus de repli.
    """

    nom: str
    chemin: Path
    cles: tuple[str, ...] = ()


@dataclass(frozen=True)
class Etat:
    """Spécialisation du bloc d'état (§7). Les défauts sont ceux de Kokaji."""

    statuts_champ: tuple[str, ...] = ("fait_etabli", "hypothese", "en_pause")
    statuts_hypothese: tuple[str, ...] = ("en_cours", "validee", "infirmee", "en_pause")
    # RFC-008 §4 (amendé) — le vocabulaire de champs d'un harness exogène à N2.
    # Lu seulement tant qu'aucun kata ne déclare de contrat : dès qu'un f♯
    # apparaît (N3), les champs se dérivent des contrats et cette clé devient
    # une faute — les deux sources ne coexistent jamais.
    champs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Harness:
    racine: Path
    id: str
    nom: str
    version: str
    langue: str
    domaine: str
    kata: tuple[Kata, ...]
    chaine: Chaine
    template: Path
    cibles: tuple[Cible, ...]
    trempe: Trempe
    etat: Etat
    personas: Path
    # HDS v0.2 — un harness peut déclarer plusieurs corpus nommés : les cas
    # réels ne se mélangent pas aux essais. Le premier déclaré fait défaut.
    corpus_nommes: tuple[Corpus, ...]
    # RFC-008 — un harness né hors de la forge. Ses kata sont des coupes
    # orphelines : leur source est le texte importé, pas une source de forge.
    exogene: bool = False
    # Estampillée une fois à l'import — une trace, pas un verrou (RFC-008 §5).
    provenance: tuple[tuple[str, str], ...] = ()

    @property
    def corpus(self) -> Path:
        return self.corpus_nommes[0].chemin

    def corpus_par_nom(self, nom: str) -> Corpus | None:
        return next((c for c in self.corpus_nommes if c.nom == nom), None)

    def cles_des_autres(self, nom: str) -> tuple[str, ...]:
        """Les clés revendiquées par les autres corpus — celles qu'on exclut."""
        return tuple(
            cle for c in self.corpus_nommes if c.nom != nom for cle in c.cles
        )

    def rang_statut(self, statut: str) -> int:
        """La force d'un statut de champ — RFC-002 §2, l'ordre de D.

        L'ordre est celui de la déclaration : `statuts_champ` est surchargeable
        par le harness, c'est donc lui qui range ses statuts du plus fort au plus
        faible. Un statut inconnu est le plus faible de tous.
        """
        try:
            return self.etat.statuts_champ.index(statut)
        except ValueError:
            return len(self.etat.statuts_champ)

    def couvre(self, statut: str, minimum: str) -> bool:
        """`statut` est-il au moins aussi fort que `minimum` ?"""
        return self.rang_statut(statut) <= self.rang_statut(minimum)

    def kata_par_id(self, id_kata: str) -> Kata | None:
        return next((k for k in self.kata if k.id == id_kata), None)

    def cible_par_id(self, id_cible: str) -> Cible | None:
        return next((c for c in self.cibles if c.id == id_cible), None)

    def espace(self, *parties: str) -> str:
        """Le nom qualifié d'une ressource de ce harness.

        L'id préfixe tout — modèles virtuels, journaux, ha, corpus — pour que
        plusieurs harness chargés côte à côte restent isolés (R2.2).
        """
        return "/".join((self.id, *parties))
