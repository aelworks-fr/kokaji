"""Importer une conversation jouée ailleurs — la pratique rapportée (RFC-020).

Des conversations utiles au harness se jouent hors du dojo : un autre outil,
un autre contexte, avant même que le kata existe. Ce module les fait entrer au
corpus **directement**, au statut `brut` du cycle de vie standard — ni
quarantaine, ni geste d'admission (D20.2) — à une seule condition : rester au
courant de leur source. Le ha naît `provenance: rapporte`, et le dépôt refuse
ensuite toute fiche qui le ferait passer pour observé.

Deux gestes, dans cet ordre :

1. **découper** le texte collé en tours (D20.1) — une heuristique simple, que
   la personne corrige avant d'enregistrer ; le découpage corrigé fait partie
   de sa déclaration ;
2. **rapporter** : écrire le ha — fiche, transcript au format que le
   middleware écrit, sortie, le texte collé en matériau.

La frontière (§2) : n'est importable que ce qui est re-percevable. Un kata
dont les effets dépassent le canal `modele` — qui lit ou écrit le monde — ne
reçoit aucune conversation rapportée : le monde d'alors ne peut plus être
échantillonné, et l'interdit n°2 de la RFC-016 bloque précisément ce cas.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ..comptes.modele import PRIVEE
from ..hds import Harness
from .depot import RefHa, depot_pour
from .provenance import RAPPORTE

__all__ = [
    "HUMAIN", "KATA", "Declaration", "HorsFrontiere", "Rapporte", "decouper", "rapporter",
]

HUMAIN = "humain"
KATA = "kata"
ROLES = (HUMAIN, KATA)

# Le texte collé, gardé tel quel à côté du ha : le découpage est une lecture,
# la matière d'origine reste là pour qui voudrait la relire autrement.
MATERIAU_TEXTE = "texte-colle.md"

# Les étiquettes qu'un outil de chat met devant chaque tour quand on copie une
# conversation. Reconnues en début de ligne, seules ou suivies du texte —
# `User:`, `**Assistant**`, `### Vous`, `> ChatGPT a dit :`. Rien d'autre :
# une heuristique qui devine trop se corrige plus mal qu'une qui devine peu.
ETIQUETTES_HUMAIN = frozenset({
    "user", "utilisateur", "utilisatrice", "humain", "human", "vous", "moi",
    "you", "me", "question", "porteur", "porteuse", "prompt", "q",
})
ETIQUETTES_KATA = frozenset({
    "assistant", "assistante", "ai", "ia", "chatgpt", "gpt", "claude", "gemini",
    "copilot", "mistral", "llama", "le chat", "bot", "kata", "reponse",
    "réponse", "answer", "modele", "modèle", "a", "r",
})
_ETIQUETTE = re.compile(
    r"^\s{0,3}(?:#{1,6}\s*|>\s*)?(?:\*\*|__)?\s*"
    r"(?P<nom>[^\s:：—–>*_#][^:：—–>*_#]{0,24}?)"
    r"(?:\s+(?:a\s+dit|said|wrote|a\s+écrit))?\s*(?:\*\*|__)?\s*"
    r"(?:(?P<sep>[:：—–>])\s*(?P<reste>.*))?$"
)


@dataclass(frozen=True)
class Declaration:
    """Ce que la personne affirme, à l'encre déclarée (D20.1).

    Le kata de rattachement est obligatoire ; tout le reste se dit si on le
    sait. `source` est l'axe existant de la matière — un sujet réel, un
    scénario, un persona — et n'a rien à voir avec la provenance.
    """

    kata: str
    kin: str = ""
    moteur_origine: str = ""
    date_origine: str = ""
    source_texte: str = ""
    version_kata_supposee: str = ""
    decoupage_corrige: bool = False
    source: str = "reel"


class HorsFrontiere(ValueError):
    """Un déroulé qu'on ne peut pas re-percevoir : refusé à l'import (RFC-020 §2)."""


@dataclass(frozen=True)
class Rapporte:
    """Le ha écrit, et ce qu'on en sait."""

    identifiant: str
    ref: RefHa
    kata: str
    tours: int
    praticien: str

    @property
    def dossier(self) -> Path:
        return self.ref.chemin


# --- 1. découper ----------------------------------------------------------------


def _role_de(nom: str) -> str | None:
    bas = re.sub(r"\s+", " ", nom).strip().lower().rstrip(".")
    if bas in ETIQUETTES_HUMAIN:
        return HUMAIN
    if bas in ETIQUETTES_KATA:
        return KATA
    return None


def _etiquette(ligne: str) -> tuple[str, str] | None:
    """(rôle, reste de la ligne) si la ligne commence par une étiquette connue."""
    trouve = _ETIQUETTE.match(ligne)
    if not trouve:
        return None
    role = _role_de(trouve.group("nom"))
    if role is None:
        return None
    # Sans séparateur, le motif a déjà exigé que la ligne ne soit que l'étiquette.
    return role, (trouve.group("reste") or "").strip()


def _par_etiquettes(lignes: list[str]) -> list[dict] | None:
    tours: list[dict] = []
    courant: list[str] | None = None
    role_courant = ""
    for ligne in lignes:
        marque = _etiquette(ligne)
        if marque is not None:
            if courant is not None:
                tours.append({"role": role_courant, "texte": "\n".join(courant).strip()})
            role_courant, reste = marque
            courant = [reste] if reste else []
        elif courant is not None:
            courant.append(ligne)
    if courant is not None:
        tours.append({"role": role_courant, "texte": "\n".join(courant).strip()})
    return [t for t in tours if t["texte"]] or None


def _par_paragraphes(texte: str) -> list[dict]:
    """Sans étiquette, une alternance : un paragraphe à l'un, le suivant à l'autre.

    C'est une supposition, pas une lecture — et c'est pour cela que le
    découpage se montre avant d'être enregistré (D20.1).
    """
    blocs = [b.strip() for b in re.split(r"\n\s*\n|\n\s*-{3,}\s*\n", texte) if b.strip()]
    return [{"role": ROLES[rang % 2], "texte": bloc} for rang, bloc in enumerate(blocs)]


def decouper(texte: str) -> list[dict]:
    """Le texte collé en tours `{"role": humain|kata, "texte": …}` — une proposition.

    Par les étiquettes des outils de chat quand il y en a ; sinon par
    paragraphes, en alternance. Deux tours consécutifs du même rôle se
    fondent : un tour est ce qu'une personne a dit avant que l'autre parle.
    """
    lignes = texte.replace("\r\n", "\n").split("\n")
    tours = _par_etiquettes(lignes) or _par_paragraphes(texte.replace("\r\n", "\n"))
    return fondre(tours)


def fondre(tours: list[dict]) -> list[dict]:
    """Deux tours consécutifs du même rôle n'en font qu'un ; les vides tombent."""
    fondus: list[dict] = []
    for tour in tours:
        role, texte = str(tour.get("role") or ""), str(tour.get("texte") or "").strip()
        if not texte:
            continue
        if fondus and fondus[-1]["role"] == role:
            fondus[-1] = {"role": role, "texte": fondus[-1]["texte"] + "\n\n" + texte}
        else:
            fondus.append({"role": role, "texte": texte})
    return fondus


# --- 2. rapporter ---------------------------------------------------------------


def _paires(tours: list[dict]) -> list[tuple[str, str]]:
    """(porteur, kata) tour par tour. Un kata qui parle d'abord ouvre un tour au
    porteur muet ; un porteur qui parle en dernier reste sans réponse."""
    paires: list[tuple[str, str]] = []
    porteur: str | None = None
    for tour in tours:
        if tour["role"] == HUMAIN:
            if porteur is not None:
                paires.append((porteur, ""))
            porteur = tour["texte"]
        else:
            paires.append((porteur or "", tour["texte"]))
            porteur = None
    if porteur is not None:
        paires.append((porteur, ""))
    return paires


def rendre_transcript(identifiant: str, paires: list[tuple[str, str]]) -> str:
    """Le transcript au format que le middleware écrit — les mêmes lecteurs le lisent."""
    lignes = [f"# Transcript — {identifiant}", ""]
    for rang, (porteur, reponse) in enumerate(paires, start=1):
        lignes += [f"## Tour {rang}", "", f"**Porteur** — {porteur}", "", "**Kata** —", "", reponse, ""]
    return "\n".join(lignes)


def _verifier(harness: Harness, tours: list[dict], declaration: Declaration) -> None:
    kata = harness.kata_par_id(declaration.kata)
    if kata is None:
        connus = ", ".join(k.id for k in harness.kata)
        raise ValueError(f"kata inconnu : {declaration.kata!r} (connus : {connus})")
    if kata.agit_sur_le_monde:
        canaux = ", ".join(
            c for c in ("monde_lecture", "monde_ecriture") if getattr(kata.effets, c)
        )
        raise HorsFrontiere(
            f"le kata `{kata.id}` agit sur le monde ({canaux}) : une conversation rapportée"
            " n'est importable que si tout ce qui s'y est passé peut être re-perçu après"
            " coup, ce qui n'est vrai que des effets `modele` seuls (RFC-020 §2 —"
            " pas de monde auto-rapporté, RFC-016 interdit n°2)"
        )
    if not tours:
        raise ValueError("aucun tour : rien à rapporter")
    for tour in tours:
        if tour.get("role") not in ROLES:
            raise ValueError(f"rôle hors liste : {tour.get('role')!r} (attendu : {', '.join(ROLES)})")
    if declaration.source not in ("reel", "scenario", "simule"):
        raise ValueError(f"source hors liste : {declaration.source!r}")


def _fiche(identifiant: str, harness: Harness, declaration: Declaration, praticien: str,
           quand: str, paires: list[tuple[str, str]], ecrit_par: str) -> str:
    entete = {
        "harness": harness.id,
        "kata": declaration.kata,
        "version_kata": declaration.version_kata_supposee,
        "version_coupe": "",
        "cible": "",
        "moteur": declaration.moteur_origine or "inconnu",
        "date": declaration.date_origine or quand,
        "praticien": praticien,
        "visibilite": PRIVEE,
        "fil": "",
        "interface": False,
        "racine": "",
        "amorce": (paires[0][0] or paires[0][1])[:120],
        "source": declaration.source,
        # Indélébile : le dépôt refuse toute fiche qui la changerait (D20.2).
        "provenance": RAPPORTE,
        "statut": "brut",
        "en_cours": False,
        "completude": "B",
        "design_exerce": [],
        "verdict": "",
        "scores": {"tours": len(paires), "blocs_etat": 0, "jetons_entree": 0, "jetons_sortie": 0},
        # Tout ceci est à l'encre déclarée : c'est ce que la personne affirme.
        "declaration": {
            "kata": declaration.kata,
            "version_kata_supposee": declaration.version_kata_supposee,
            "kin": declaration.kin,
            "moteur_origine": declaration.moteur_origine or "inconnu",
            "date_origine": declaration.date_origine,
            "source_texte": declaration.source_texte,
            "decoupage_corrige": bool(declaration.decoupage_corrige),
            "rapporte_le": quand,
            "rapporte_par": ecrit_par,
        },
    }
    yaml_entete = yaml.safe_dump(entete, allow_unicode=True, sort_keys=False, width=1000)
    titre = f"{declaration.kata} rapporté"
    return (
        f"---\n{yaml_entete}---\n\n"
        f"# {identifiant} — {titre}\n\n"
        "Rapporté : conversation jouée hors du dojo, collée et déclarée par une personne —"
        " jamais versée depuis le journal (RFC-020).\n\n"
        "## Constats\n\n*À renseigner — ce ha est brut.*\n\n"
        "## Enseignements\n\n*À renseigner — ce ha est brut.*\n\n"
        "## Réserves sur ce ha\n\n"
        "- **Pratique rapportée** (RFC-020) : ce déroulé n'a pas été joué dans la version"
        " courante du kata, ni sous une coupe injectée par la passerelle. Le rattachement"
        " au kata est une déclaration de la personne qui l'a rapporté ; la trempe a"
        " posteriori peut la contester, à côté, jamais à sa place.\n"
        "- Aucun bloc d'état : les vérifications qui en supposent sont éteintes.\n"
        "- Le découpage en tours est une lecture du texte collé, "
        + ("corrigée par la personne." if declaration.decoupage_corrige else "proposée par l'heuristique, non corrigée.")
        + "\n"
    )


def rapporter(
    harness: Harness,
    tours: list[dict],
    declaration: Declaration,
    corpus: Path | None = None,
    praticien: str = "",
    texte_colle: str | None = None,
    quand: str | None = None,
) -> Rapporte:
    """Écrit un ha `brut`, `provenance: rapporte`, depuis des tours déclarés.

    `praticien` : le compte de la personne qui rapporte — sans lui, le ha naît
    orphelin de porte, comme toute conversation sans praticien (RFC-004 §5).
    `texte_colle` : la matière d'origine, gardée en matériau.

    Refuse — et n'écrit rien — un kata inconnu, un kata qui agit sur le monde
    (§2), des tours vides ou d'un rôle inconnu.
    """
    tours = fondre(tours)
    _verifier(harness, tours, declaration)
    quand = quand or datetime.now(UTC).isoformat(timespec="seconds")
    chemin = Path(corpus) if corpus is not None else harness.corpus
    chemin.mkdir(parents=True, exist_ok=True)
    depot = depot_pour(harness)

    identifiant = f"CAS-{depot.numero_suivant(chemin):04d}"
    ref = depot.creer(chemin, f"{identifiant}-{declaration.kata}-rapporte")
    paires = _paires(tours)

    depot.ecrire_fiche(ref, _fiche(identifiant, harness, declaration, praticien, quand, paires, praticien))
    depot.ecrire_transcript(ref, rendre_transcript(identifiant, paires))
    derniere = next((reponse for _, reponse in reversed(paires) if reponse), "")
    depot.ecrire_sortie(ref, f"# Dernière réponse — {identifiant}\n\n{derniere}\n")
    if texte_colle is not None:
        depot.ecrire_materiau(ref, MATERIAU_TEXTE, texte_colle)
    depot.ecrire_materiau(
        ref, "declaration.json",
        json.dumps({**asdict(declaration), "rapporte_le": quand}, ensure_ascii=False, indent=2) + "\n",
    )
    return Rapporte(identifiant=identifiant, ref=ref, kata=declaration.kata, tours=len(paires), praticien=praticien)
