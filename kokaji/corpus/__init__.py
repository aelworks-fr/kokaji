"""Verser le journal du Dojo dans le corpus d'un harness (SPECS §6).

Le journal est une suite d'appels ; un ha est une session. Ce module fait la
promotion du premier vers le second, à l'état `brut` — l'annotation reste un
geste humain, la capture n'en est jamais un (R7.3).

C'est une avance sur le middleware (§7), qui fera ce travail en continu. En
attendant, la même règle vaut : rien n'est jugé, rien n'est agrégé, rien n'est
supprimé.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..comptes.modele import PRIVEE
from ..hds import Harness
from ..yaml_source import charger_texte, rendre_source
from .depot import RefHa, depot_pour, ref_de
from .journal import lire_journal

__all__ = [
    "Ha", "Versement", "deja_ailleurs", "ecartees", "ecarter",
    "lire_journal", "rafraichir_fiche", "verser",
]

# Les sessions qu'un humain a décidé de ne pas garder au corpus. Le journal, lui,
# ne perd rien : supprimer un ha sans le déclarer le ferait recréer au passage
# suivant de la veille.
ECARTES = ".ecartes.jsonl"

GABARIT_FICHE = """---
harness: {harness}
kata: {kata}
version_kata: "{version_kata}"
version_coupe: "{version_coupe}"
cible: {cible}
moteur: {moteur}
date: "{date}"
praticien: {praticien}
visibilite: {visibilite}
fil: {fil}
source: {source}
statut: brut
en_cours: {en_cours}
completude: {completude}
design_exerce: []
verdict: ""
scores:
  tours: {tours}
  blocs_etat: {blocs}
  jetons_entree: {entree}
  jetons_sortie: {sortie}
---

# {identifiant} — {titre}

Versé depuis le journal du Dojo, session `{session}`.

## Constats

*À renseigner — ce ha est brut.*

## Enseignements

*À renseigner — ce ha est brut.*

## Réserves sur ce ha

- Session jouée par le banc ou conversée en vrai — voir `source`.
- {reserve_temperature}
"""


@dataclass(frozen=True)
class Ha:
    identifiant: str
    dossier: Path
    session: str
    kata: str
    cible: str
    tours: int
    blocs: int


@dataclass(frozen=True)
class Versement:
    """Ce qu'un passage a versé — et ce qu'il a refusé de verser.

    Les doubles sont rendus plutôt que tus. Un versement qui saute une session
    en silence produit exactement la lecture qu'on ne veut pas : « rien à
    verser » se lit comme « tout est à jour », alors que la session est ailleurs
    et que le corpus visé, lui, ne l'aura jamais.
    """

    ha: list[Ha]
    doubles: dict[str, Path]


def _sessions(lignes: list[dict], id_harness: str) -> dict[str, list[dict]]:
    """Groupe les appels par session, en ne gardant que ce harness."""
    par: dict[str, list[dict]] = {}
    for ligne in lignes:
        identite = ligne.get("identite") or {}
        if identite.get("harness") != id_harness or not ligne.get("reponse"):
            continue
        par.setdefault(ligne.get("session") or "sans-session", []).append(ligne)
    return par


def _numero_suivant(corpus: Path) -> int:
    return depot_pour().numero_suivant(corpus)


def _titre(appels: list[dict]) -> str:
    identite = appels[-1]["identite"]
    return f"{identite['kata']}-{identite['cible']}-{identite['version_coupe'][:6]}"


def existants(corpus: Path) -> dict[str, Path]:
    """Les ha déjà versés, par session."""
    depot = depot_pour()
    trouves: dict[str, Path] = {}
    for ref in depot.tous(corpus):
        texte = depot.fiche(ref)
        if texte and "session `" in texte:
            trouves[texte.split("session `")[-1].split("`")[0]] = ref.chemin
    return trouves


def deja_ailleurs(harness: Harness, corpus: Path) -> dict[str, Path]:
    """Les sessions de ce harness déjà versées dans un **autre** de ses corpus.

    Une session est une conversation, et une conversation n'a eu lieu qu'une
    fois : la verser deux fois fait de deux corpus deux vues qui se recouvrent,
    et de toute addition un compte faux. Le carnet en porte le cas — quinze ha
    de `decoupage` présents des deux côtés sous des identifiants différents,
    même coupe, même date à la microseconde, et 475 850 jetons comptés en trop.

    Les corpus sont censés se partager les sessions par leurs clés appelantes
    (HDS v0.2). Ce contrôle-ci ne remplace pas ce partage : il rattrape ce que
    le partage ne couvre pas — un versement à la main sans `--corpus`, ou des
    clés déclarées après coup, ce qui est précisément ce qui est arrivé.
    """
    vise = Path(corpus).resolve()
    trouve: dict[str, Path] = {}
    for autre in harness.corpus_nommes:
        if autre.chemin.resolve() == vise:
            continue
        for session, dossier in existants(autre.chemin).items():
            trouve.setdefault(session, dossier)
    return trouve


def ecartees(corpus: Path) -> set[str]:
    """Les sessions qu'un humain a écartées de ce corpus."""
    return {str(e.get("session") or "") for e in depot_pour().ecartes(corpus)}


def ecarter(corpus: Path, session: str, raison: str, quand: str) -> None:
    """Déclare qu'une session n'a pas sa place ici — en append, jamais en écrasant.

    Une session déjà écartée ne se redéclare pas : la première décision fait foi.
    """
    if session in ecartees(corpus):
        return
    depot_pour().ecarter(corpus, session, raison, quand)


# Ce que la capture possède dans une fiche. Tout le reste appartient à d'autres
# gestes — la visibilité au praticien (RFC-004 §5), la marque de ré-abstraction
# au relecteur (RFC-002 §7.2) — et se perdait à chaque rafraîchissement, parce
# que la fiche était réécrite entière depuis le gabarit.
CHAMPS_DE_LA_CAPTURE = frozenset({
    "harness", "kata", "version_kata", "version_coupe", "cible", "moteur",
    "date", "source", "completude", "en_cours", "scores",
})
# Ceux-là ne s'écrasent que s'ils ont quelque chose à dire : une passe qui ne
# connaît pas le praticien ne doit pas effacer celui qu'une autre a su nommer.
CHAMPS_SI_CONNUS = frozenset({"fil", "praticien"})


def _parts(texte: str) -> tuple[str, str] | None:
    """L'en-tête YAML et le corps d'une fiche, ou rien si elle n'en a pas."""
    if not texte.startswith("---"):
        return None
    morceaux = texte.split("---", 2)
    return (morceaux[1], morceaux[2]) if len(morceaux) == 3 else None


def rafraichir_fiche(ancienne: str, neuve: str) -> str:
    """Reporte dans la fiche déjà là ce que la capture possède, et rien d'autre.

    La capture réécrivait la fiche entière depuis son gabarit. Tout ce qu'un
    autre geste y avait ajouté disparaissait au passage suivant : la visibilité
    qu'un praticien venait de régler redevenait `privee`, et la marque d'une
    ré-abstraction — avec la réserve disant que cet état n'a pas été observé —
    s'effaçait. Rien ne l'aurait montré : la fiche restait bien formée.

    Le corps est gardé tel quel, l'en-tête clé par clé. Une fiche illisible se
    remplace plutôt que de bloquer la capture : perdre une annotation est un
    accident, perdre la capture est une panne.
    """
    avant, apres = _parts(ancienne), _parts(neuve)
    if avant is None or apres is None:
        return neuve
    vieux, corps = avant
    try:
        garde = charger_texte(vieux)
        frais = charger_texte(apres[0])
    except Exception:  # noqa: BLE001 — voir la docstring
        return neuve
    if not isinstance(garde, dict) or not isinstance(frais, dict):
        return neuve

    for cle, valeur in frais.items():
        connu = cle in CHAMPS_SI_CONNUS and bool(valeur)
        if cle in CHAMPS_DE_LA_CAPTURE or cle not in garde or connu:
            garde[cle] = valeur
    return "---\n" + rendre_source(garde) + "---" + corps


def _annote(dossier: Path | RefHa) -> bool:
    """Un ha annoté ne se réécrit jamais : la promotion humaine prime."""
    texte = depot_pour().fiche(ref_de(dossier))
    return texte is not None and "statut: brut" not in texte


def verser(
    harness: Harness,
    journal: Path,
    sessions: tuple[str, ...] = (),
    source: str = "simule",
    temperature: float | None = 0.0,
    rafraichir: bool = False,
    en_cours: tuple[str, ...] = (),
    corpus: Path | None = None,
    cles: tuple[str, ...] = (),
    praticiens: dict[str, str] | None = None,
) -> Versement:
    """Écrit un ha par session trouvée.

    Sans `rafraichir`, un ha déjà versé est laissé tel quel. Avec, il est
    réécrit tant qu'il est `brut` — ce qui permet de suivre une conversation
    vivante. **Un ha annoté n'est jamais réécrit** : la promotion humaine prime
    sur la capture.

    Une session déjà versée dans un autre corpus du harness n'entre pas ici :
    voir `deja_ailleurs`. Elle est rendue dans `doubles`, jamais écartée toute
    seule — ce qui est déjà sur le disque relève d'une décision humaine.
    """
    praticiens = praticiens or {}
    corpus = Path(corpus) if corpus is not None else harness.corpus
    corpus.mkdir(parents=True, exist_ok=True)
    depot = depot_pour(harness)
    deja = existants(corpus)
    hors_jeu = ecartees(corpus)
    ailleurs = deja_ailleurs(harness, corpus)

    trouvees = _sessions(lire_journal(journal, harness.id), harness.id)
    numero = _numero_suivant(corpus)
    verses: list[Ha] = []
    doubles: dict[str, Path] = {}

    for session, appels in sorted(trouvees.items(), key=lambda kv: kv[1][0]["debut"]):
        if sessions and session not in sessions:
            continue
        if session in hors_jeu:
            continue
        if cles and (appels[-1].get("identite") or {}).get("cle") not in cles:
            continue
        ancien = deja.get(session)
        if session in ailleurs:
            # Dit dans les deux cas, refusé dans un seul. Si le ha n'est pas
            # encore ici, on ne le crée pas ; s'il y est déjà, le rafraîchir
            # reste juste — figer une conversation vivante pour punir un double
            # ajouterait une perte à une redite. Le double est signalé, il n'est
            # pas réparé : effacer un ha est une décision humaine (R7.3).
            doubles[session] = ailleurs[session]
            if ancien is None:
                continue
        if ancien is not None and (not rafraichir or _annote(ancien)):
            continue

        identite = appels[-1]["identite"]
        dernier = appels[-1]
        blocs = sum(1 for a in appels if "kokaji_state" in (a["reponse"] or ""))
        if ancien is not None:
            ref = ref_de(ancien)
            identifiant = ref.identifiant
        else:
            identifiant = f"CAS-{numero:04d}"
            ref = depot.creer(corpus, f"{identifiant}-{_titre(appels)}")
            numero += 1
        dossier = ref.chemin

        neuve = GABARIT_FICHE.format(
                harness=identite["harness"],
                kata=identite["kata"],
                version_kata=identite.get("version_kata") or "",
                version_coupe=identite.get("version_coupe") or "",
                cible=identite.get("cible") or "",
                moteur=f"{dernier.get('fournisseur')}/{dernier.get('moteur')}",
                date=identite.get("date") or dernier.get("debut"),
                # RFC-004 §5 : le praticien vient de la clé appelante, via le
                # mapping que le middleware détient. Vide tant que le Dojo ne
                # sert qu'une personne — et un ha sans praticien reste privé.
                praticien=praticiens.get(str(identite.get("cle") or ""), ""),
                visibilite=PRIVEE,
                # Le fil de conversation, tel que le chat l'a annoncé. Absent
                # pour tout ha né avant que le chat ait le droit de le dire :
                # on ne le reconstruit pas, on le laisse vide.
                fil=identite.get("fil") or "",
                source=source,
                completude="C" if session in en_cours else "B",
                en_cours="true" if session in en_cours else "false",
                tours=len(appels),
                blocs=blocs,
                entree=sum((a["usage"] or {}).get("prompt_tokens", 0) for a in appels),
                sortie=sum((a["usage"] or {}).get("completion_tokens", 0) for a in appels),
                identifiant=identifiant,
                titre=_titre(appels).replace("-", " "),
                session=session,
                reserve_temperature=(
                    f"Température figée à {temperature}."
                    if temperature is not None
                    else "Température non fixée : ce ha est un tirage, pas une mesure."
                ),
        )
        ancienne_fiche = depot.fiche(ref) if ancien is not None else None
        if ancienne_fiche is not None:
            neuve = rafraichir_fiche(ancienne_fiche, neuve)
        depot.ecrire_fiche(ref, neuve)

        lignes = [f"# Transcript — {identifiant}", ""]
        messages = dernier["messages"]
        echanges = messages[1:]  # le premier message est la coupe injectée
        for rang in range(0, len(echanges), 2):
            porteur = echanges[rang]["content"]
            reponse = (
                echanges[rang + 1]["content"]
                if rang + 1 < len(echanges)
                else dernier["reponse"]
            )
            marque = " — bloc d'état" if "kokaji_state" in reponse else ""
            lignes += [
                f"## Tour {rang // 2 + 1}{marque}",
                "",
                f"**Porteur** — {porteur}",
                "",
                "**Kata** —",
                "",
                reponse,
                "",
            ]
        if len(echanges) % 2 == 1:
            lignes += ["## Dernier tour", "", "**Kata** —", "", dernier["reponse"], ""]
        depot.ecrire_transcript(ref, "\n".join(lignes))
        depot.ecrire_sortie(ref, f"# Dernière réponse — {identifiant}\n\n{dernier['reponse']}\n")
        depot.ecrire_materiau(ref, "coupe.md", messages[0]["content"] if messages else "")

        verses.append(
            Ha(
                identifiant=identifiant,
                dossier=dossier,
                session=session,
                kata=identite["kata"],
                cible=identite.get("cible") or "",
                tours=len(appels),
                blocs=blocs,
            )
        )

    return Versement(ha=verses, doubles=doubles)
