"""Le middleware — capture, état, et le carré continu (SPECS §7, RFC-002 §6.3).

Trois gestes, dans cet ordre :

1. **capturer** — toute session close devient un ha `brut`, sans geste humain
   (R7.3). La promotion en `annote` reste humaine ; la capture ne l'est jamais.
2. **extraire l'état** — les blocs `kokaji_state` sont sortis des réponses,
   validés contre le schéma spécialisé par le manifest, horodatés et rattachés
   au ha (R7.1). Un bloc malformé est consigné, **jamais bloquant** (R7.2).
3. **vérifier le carré** — pour chaque ha, l'état final livre-t-il au moins ce
   que `produit` promet ? Check de données pur, sans modèle (RFC-002 §6.3).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from ..corpus import lire_journal, verser
from ..etat import extraire, fautes_de_bloc
from ..forge.coupe import champ_nu, champs_du_kata, charger_registre
from ..hds import Harness, Kata

__all__ = [
    "Carre", "Passe", "Veille",
    "carre_attendu", "carre_du_ha", "etats_du_ha", "veiller",
]

REPOS_DEFAUT = 300.0  # secondes de silence après quoi une session est close


@dataclass(frozen=True)
class Carre:
    """Le verdict de naturalité d'un ha (RFC-002 §4)."""

    verdict: str  # conforme | sur-promesse | hors-premisse | sans-etat
    manquants: tuple[tuple[str, str, str], ...] = ()  # (champ, promis, livré)
    motif: str = ""

    def rendre(self) -> str:
        lignes = [f"# Carré de naturalité — {self.verdict}", ""]
        if self.motif:
            lignes += [self.motif, ""]
        if self.manquants:
            lignes += ["| champ | promis | livré |", "|---|---|---|"]
            lignes += [f"| {c} | {p} | {l} |" for c, p, l in self.manquants]
        return "\n".join(lignes).rstrip() + "\n"


def etats_du_ha(
    harness: Harness, kata: Kata, appels: list[dict], champs_admis: tuple[str, ...],
    natures: tuple[str, ...] = (),
) -> list[dict]:
    """Les blocs d'état d'une session, horodatés et validés (R7.1, R7.2).

    `natures` sert à reconnaître une valeur puisée dans la taxonomie voisine
    plutôt qu'à la refuser deux fois (NOTE-0005).
    """
    connues: set[str] = set()
    releves: list[dict] = []

    for appel in appels:
        for rang, etat in enumerate(extraire(appel.get("reponse") or "")):
            fautes = fautes_de_bloc(harness, kata, champs_admis, etat, connues, natures)
            releves.append(
                {
                    "horodatage": appel.get("fin") or appel.get("debut"),
                    "id_appel": appel.get("id_appel"),
                    "rang_dans_la_reponse": rang,
                    "etat": etat,
                    # Un bloc malformé est consigné, jamais bloquant (R7.2).
                    "fautes": [{"regle": r, "message": m} for r, m in fautes],
                }
            )
    return releves


def _relu(etats: Path) -> bool:
    """Ce fichier d'état vient-il d'une ré-abstraction ? — RFC-002 §7.2."""
    return etats.is_file() and '"reabstrait": true' in etats.read_text(encoding="utf-8")


def carre_attendu(harness: Harness, id_cible: str, kata: Kata | None = None) -> bool:
    """Un carré se prononce-t-il sur ce ha ? Deux conditions, même raison.

    Une cible `etat_structure: false` ne demande **aucun** bloc d'état : sa
    coupe ne mentionne même pas le bloc. Lui écrire `sans-etat` lui reproche
    une absence conforme — et le corpus l'a fait 52 fois, si bien qu'une
    absence voulue et un manquement portaient le même mot. Sur les 107
    `sans-etat` de l'Atelier, huit seulement étaient des manquements.

    Un kata **sans aucun contrat** ne se juge pas non plus, et le piège est
    pire : avec un `produit` vide, la boucle des manquants ne trouve rien et
    conclut `conforme` — un harness adopté à N0/N2 (RFC-008) aurait affiché
    vert partout, précisément la simulation que son §8 interdit. Le carré est
    la vérification d'une promesse ; sans promesse, il n'a pas d'objet.

    Une cible inconnue est jugée plutôt que passée : ne pas prononcer sur ce
    qu'on ne reconnaît pas rétablirait le silence qu'on vient d'ôter.
    """
    if kata is not None and not kata.produit and not kata.herite:
        return False
    cible = harness.cible_par_id(id_cible)
    return cible is None or cible.etat_structure


def carre_du_ha(harness: Harness, kata: Kata, releves: list[dict]) -> Carre:
    """La loi du RFC-002 §4, sur un ha.

    `état_final ≥ produit`, pour tout ha dont `état_initial ≥ herite`.

    La prémisse se lit sur le **premier** bloc émis : les champs hérités doivent
    y figurer. Un kata sans amont la satisfait par vacuité. Faute de prémisse, le
    carré n'est pas violé — il n'est pas évaluable, et c'est une information
    différente d'une conformité.
    """
    lisibles = [r for r in releves if "__illisible__" not in r["etat"]]
    if not lisibles:
        return Carre("sans-etat", motif="Aucun bloc d'état lisible dans ce ha.")

    def champs(releve: dict) -> dict:
        valeur = releve["etat"].get("champs")
        return valeur if isinstance(valeur, dict) else {}

    attendus = [champ_nu(r) for r in kata.herite]
    manquants_amont = [c for c in attendus if c not in champs(lisibles[0])]
    if manquants_amont:
        return Carre(
            "hors-premisse",
            motif=(
                "L'état d'entrée ne satisfait pas `herite` : "
                f"{', '.join(manquants_amont)} absent(s) du premier bloc. "
                "Le carré n'est pas évaluable sur ce ha."
            ),
        )

    final = champs(lisibles[-1])
    manquants = []
    for reference, minimum in kata.produit:
        champ = champ_nu(reference)
        livre = final.get(champ)
        if livre is None or not harness.couvre(livre, minimum):
            manquants.append((champ, minimum, livre or "absent"))

    if manquants:
        return Carre(
            "sur-promesse",
            manquants=tuple(manquants),
            motif=(
                "L'état final ne livre pas ce que `produit` promet. "
                "Sous-promettre est permis ; sur-promettre ne l'est pas."
            ),
        )
    return Carre("conforme", motif="L'état final livre au moins la promesse.")


@dataclass(frozen=True)
class Veille:
    ha: str
    session: str
    kata: str
    blocs: int
    fautes: int
    carre: str
    en_cours: bool = False


@dataclass(frozen=True)
class Passe:
    """Ce qu'un tour de veille a capturé — et ce qu'il a refusé de capturer.

    La capture continue est le chemin où un refus se paie le plus cher : elle
    tourne sans personne devant, et une session sautée en silence ne se
    remarque qu'au moment où l'on cherche un ha qui n'a jamais été écrit.
    """

    veilles: list[Veille]
    doubles: dict[str, Path]


def _toutes(lignes: list[dict], id_harness: str) -> set[str]:
    """Toutes les sessions de ce harness, closes ou non."""
    return {
        ligne["session"]
        for ligne in lignes
        if (ligne.get("identite") or {}).get("harness") == id_harness
        and ligne.get("session")
        and ligne.get("reponse")
    }


def _closes(lignes: list[dict], id_harness: str, repos: float, maintenant: str | None) -> set[str]:
    """Les sessions restées silencieuses assez longtemps pour être dites closes."""
    derniere: dict[str, str] = {}
    for ligne in lignes:
        if (ligne.get("identite") or {}).get("harness") != id_harness:
            continue
        session = ligne.get("session")
        fin = ligne.get("fin") or ligne.get("debut") or ""
        if session and fin > derniere.get(session, ""):
            derniere[session] = fin

    if maintenant is None or repos <= 0:
        return set(derniere)

    reference = _instant(maintenant)
    if reference is None:
        return set(derniere)
    limite = reference - timedelta(seconds=repos)
    closes = set()
    for session, fin in derniere.items():
        instant = _instant(fin)
        # Une date illisible ne retient pas une session : mieux vaut capturer
        # trop tôt que ne jamais capturer.
        if instant is None or instant <= limite:
            closes.add(session)
    return closes


def _instant(valeur: str):
    """Les horodatages du journal mélangent naïf et aware — on aligne sur UTC."""
    try:
        lu = datetime.fromisoformat(valeur)
    except (TypeError, ValueError):
        return None
    return lu if lu.tzinfo else lu.replace(tzinfo=UTC)


def _a_rattraper(harness: Harness, corpus: Path | None = None) -> list:
    """Les ha déjà au corpus mais sans état extrait — versés avant le middleware."""
    from ..corpus import Ha

    racine = Path(corpus) if corpus is not None else harness.corpus
    en_retard = []
    for dossier in sorted(racine.glob("CAS-*")):
        fiche = dossier / "fiche.md"
        if (dossier / "etats.jsonl").is_file() or not fiche.is_file():
            continue
        texte = fiche.read_text(encoding="utf-8")
        if "session `" not in texte:
            continue
        session = texte.split("session `")[-1].split("`")[0]
        identifiant, _, reste = dossier.name.partition("-")
        en_retard.append(
            Ha(
                identifiant=f"{identifiant}-{reste.split('-')[0]}"
                if identifiant == "CAS"
                else dossier.name,
                dossier=dossier,
                session=session,
                kata=_kata_de_la_fiche(texte),
                cible="",
                tours=0,
                blocs=0,
            )
        )
    return en_retard


def _kata_de_la_fiche(texte: str) -> str:
    for ligne in texte.splitlines():
        if ligne.startswith("kata:"):
            return ligne.split(":", 1)[1].strip()
    return ""


def veiller(
    harness: Harness,
    journal: Path,
    repos: float = REPOS_DEFAUT,
    maintenant: str | None = None,
    source: str = "reel",
    rattraper: bool = False,
    vivantes: bool = True,
    corpus: Path | None = None,
    cles: tuple[str, ...] = (),
    praticiens: dict[str, str] | None = None,
) -> Passe:
    """Capture les sessions, en extrait l'état, vérifie le carré.

    Avec `vivantes`, les conversations **en cours** entrent au corpus elles
    aussi, et leur ha se rafraîchit à chaque passage. Sans quoi il faudrait
    attendre la clôture — et baisser le délai de clôture figerait un ha au
    milieu d'une conversation, en perdant les tours suivants.

    Un ha annoté n'est jamais réécrit : la promotion humaine prime sur la
    capture.

    `rattraper` traite en plus les ha déjà au corpus qui n'ont pas d'état
    extrait — ceux versés avant que le middleware existe.
    """
    lignes = lire_journal(journal)
    closes = _closes(lignes, harness.id, repos, maintenant)
    toutes = _toutes(lignes, harness.id) if vivantes else closes
    ouvertes = toutes - closes
    retard = _a_rattraper(harness, corpus) if rattraper else []
    if not toutes and not retard:
        return Passe(veilles=[], doubles={})

    registre = charger_registre(harness.trempe.registre)
    versement = verser(
        harness,
        journal,
        sessions=tuple(sorted(toutes)),
        source=source,
        rafraichir=True,
        en_cours=tuple(sorted(ouvertes)),
        corpus=corpus,
        cles=cles,
        praticiens=praticiens,
    )
    verses = versement.ha + retard
    closes = toutes | {ha.session for ha in retard}

    par_session: dict[str, list[dict]] = {}
    for ligne in lignes:
        if ligne.get("session") in closes and ligne.get("reponse"):
            par_session.setdefault(ligne["session"], []).append(ligne)

    veilles: list[Veille] = []
    for ha in verses:
        appels = par_session.get(ha.session, [])
        kata = harness.kata_par_id(ha.kata)
        if kata is None:
            continue
        champs = champs_du_kata(harness, kata, _source_du_kata(kata), registre)

        source = _source_du_kata(kata)
        releves = etats_du_ha(harness, kata, appels, champs, _natures_du_kata(source))
        # Rien à observer et une lecture déjà là : on la garde. La veille
        # écrasait l'état ré-abstrait par un fichier vide à chaque passage — le
        # ha gardait sa marque et son carré, et perdait ce qu'ils décrivent. Un
        # ha qui annonce une lecture sans la porter ment mieux qu'un ha muet.
        # Une observation, elle, l'emporte toujours sur une lecture.
        etats = ha.dossier / "etats.jsonl"
        if releves or not _relu(etats):
            etats.write_text(
                "".join(json.dumps(r, ensure_ascii=False, default=str) + "\n" for r in releves),
                encoding="utf-8",
            )

        fichier = ha.dossier / "carre.md"
        if carre_attendu(harness, ha.cible, kata):
            carre = carre_du_ha(harness, kata, releves)
            fichier.write_text(carre.rendre(), encoding="utf-8")
        else:
            # Le verdict écrit avant cette règle est retiré : le laisser en
            # place ferait vivre un reproche que plus rien ne réécrit, et un
            # fichier périmé se lit comme un fichier à jour. Sauf s'il vient
            # d'une ré-abstraction : celle-ci porte précisément sur les cibles
            # non instrumentées, et son verdict est le seul qui ait un sens ici
            # (RFC-002 §7.2). La marque est cherchée dans le carré lui-même et
            # non dans la fiche : la fiche d'un ha `brut` est réécrite à chaque
            # passage, ce qui efface tout ce qu'on y ajoute.
            carre = None
            garde = fichier.is_file() and "ré-abstrait" in fichier.read_text(encoding="utf-8")
            if not garde:
                fichier.unlink(missing_ok=True)

        veilles.append(
            Veille(
                ha=ha.identifiant,
                session=ha.session,
                kata=ha.kata,
                blocs=len(releves),
                fautes=sum(len(r["fautes"]) for r in releves),
                carre=carre.verdict if carre is not None else "",
                en_cours=ha.session in ouvertes,
            )
        )
    return Passe(veilles=veilles, doubles=versement.doubles)


def _natures_du_kata(source: dict) -> tuple[str, ...]:
    """La taxonomie des natures que ce kata déclare (RFC-003).

    Elle vit dans la source du kata et non dans le manifest : un kata tardif
    peut en restreindre l'usage sans toucher aux autres.
    """
    valeurs = source.get("natures") or []
    return tuple(str(v) for v in valeurs if isinstance(v, (str, int)))


def _source_du_kata(kata: Kata) -> dict:
    donnees = yaml.safe_load(kata.source.read_text(encoding="utf-8")) or {}
    return donnees if isinstance(donnees, dict) else {}
