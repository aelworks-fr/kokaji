"""Le QG — le fil d'ariane d'hypothèses (SPECS §8, RFC-001 R8.4).

Le QG **lit et n'évalue pas**. Il agrège ce que les blocs d'état déclarent, il
n'en tire aucun score, aucun indice composite, aucun jugement. Une lecture
normative — « ce sujet brûle ses options » — reste un jugement humain devant les
données (carnet de vigilances #8).

Il ne connaît aucune chaîne en dur : la topologie vient du manifest (R8.1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from ..corpus.depot import depot_pour
from ..corpus.journal import journal_pour
from ..forge.coupe import champ_nu
from ..hds import Harness

__all__ = ["Option", "VueNoeud", "VueQG", "composer", "rendre_texte", "sujets"]


@dataclass(frozen=True)
class Option:
    id: str
    libelle: str
    noeud: str
    statut: str
    naissance: str
    age_jours: float | None

    @property
    def vivante(self) -> bool:
        return self.statut == "ouverte"


@dataclass
class VueNoeud:
    id: str
    type: str
    nom: str
    champs: dict[str, str] = field(default_factory=dict)
    attendus: tuple[str, ...] = ()
    hypotheses: list[dict] = field(default_factory=list)
    options: list[Option] = field(default_factory=list)
    dernier_etat: str | None = None
    etape: str | None = None
    provenance: dict = field(default_factory=dict)
    sessions: list[dict] = field(default_factory=list)
    # RFC-003 §5.5 — la dernière nature diagnostiquée sur ce nœud (valeur,
    # confiance, révisée le). Transportée, jamais interprétée (§5.2) : une
    # donnée de plus au détail du nœud, pas une vue nouvelle.
    nature: dict = field(default_factory=dict)
    # RFC-011 D11.3 — un kata en texte n'a pas de contrat : son carré est
    # éteint, jamais vert ni rouge, et le nœud le dit.
    sans_contrat: bool = False

    @property
    def options_vivantes(self) -> list[Option]:
        return [o for o in self.options if o.vivante]

    @property
    def pratique(self) -> bool:
        """Un nœud qu'aucune session n'a touché ne se colore pas — il se tait."""
        return bool(self.champs or self.hypotheses or self.dernier_etat)

    @property
    def refutees(self) -> int:
        return sum(1 for h in self.hypotheses if h.get("statut") == "infirmee")

    def chaleur(self, harness: Harness) -> float | None:
        """R8.2 — la part de ce qui est acquis dans ce qui est connu.

            chaleur = (champs établis + hypothèses validées)
                      ÷ (champs connus + hypothèses non en pause)

        Les hypothèses **infirmées** et **en pause** sortent des deux termes :
        une réfutation est un gain de connaissance, elle ne doit jamais refroidir
        un nœud en silence.

        Un nœud jamais pratiqué ne rend pas zéro mais `None` : ne pas savoir
        n'est pas un savoir nul.
        """
        if not self.pratique:
            return None

        fort = harness.etat.statuts_champ[0] if harness.etat.statuts_champ else ""
        connus = [s for s in self.champs.values() if s in harness.etat.statuts_champ]
        acquis = sum(1 for s in connus if s == fort)

        comptees = [h for h in self.hypotheses if h.get("statut") not in ("en_pause", "infirmee")]
        acquis += sum(1 for h in comptees if h.get("statut") == "validee")

        total = len(connus) + len(comptees)
        return acquis / total if total else 0.0


@dataclass
class VueQG:
    harness: str
    sujet: str
    noeuds: list[VueNoeud]
    aretes: list[dict]
    decisions: list[dict]
    observe_le: str | None = None
    # Vrai si au moins un bloc vient d'une session que la capture n'a pas
    # encore close : la vue suit une conversation vivante.
    en_cours: bool = False
    # Vrai si au moins un bloc a été reconstruit après coup plutôt qu'émis en
    # session : ce qui est montré est une lecture, pas une observation.
    reabstrait: bool = False

    @property
    def options_vivantes(self) -> list[Option]:
        return [o for n in self.noeuds for o in n.options_vivantes]

    def age_median(self) -> float | None:
        """Médiane des âges des options vivantes — une des trois métriques v1."""
        ages = sorted(o.age_jours for o in self.options_vivantes if o.age_jours is not None)
        if not ages:
            return None
        milieu = len(ages) // 2
        if len(ages) % 2:
            return ages[milieu]
        return (ages[milieu - 1] + ages[milieu]) / 2

    def as_dict(self, harness: Harness) -> dict:
        return {
            "harness": self.harness,
            "sujet": self.sujet,
            "observe_le": self.observe_le,
            "en_cours": self.en_cours,
            "reabstrait": self.reabstrait,
            "noeuds": [
                {
                    "id": n.id,
                    "type": n.type,
                    "nom": n.nom,
                    "pratique": n.pratique,
                    "chaleur": None if n.chaleur(harness) is None else round(n.chaleur(harness), 4),
                    "refutees": n.refutees,
                    "etape": n.etape,
                    "provenance": n.provenance,
                    "sessions": n.sessions,
                    "champs": n.champs,
                    "attendus": list(n.attendus),
                    "sans_contrat": n.sans_contrat,
                    "nature": n.nature,
                    "hypotheses": n.hypotheses,
                    "options_vivantes": len(n.options_vivantes),
                    "options": [vars(o) for o in n.options],
                    "dernier_etat": n.dernier_etat,
                }
                for n in self.noeuds
            ],
            "aretes": self.aretes,
            "decisions": self.decisions,
            "possibles_vivants": {
                "total": len(self.options_vivantes),
                "age_median_jours": self.age_median(),
                "options": [vars(o) for o in self.options_vivantes],
            },
        }


def _releves_corpus(
    harness: Harness, corpus: Path | None = None, lisible=None
) -> tuple[list[dict], set[str]]:
    """Les blocs d'état des ha capturés, et les sessions qu'ils couvrent.

    `lisible` est un prédicat sur le dossier d'un ha (RFC-004 §5). Sans lui, le
    QG lit tout le corpus — c'est le mode mono-utilisateur. Avec lui, un ha non
    versé d'autrui ne peuple ni les sujets, ni la chaleur, ni les possibles :
    l'état est de la pratique, et la pratique ne se prend pas.
    """
    racine = Path(corpus) if corpus is not None else harness.corpus
    depot = depot_pour(harness)
    releves, sessions = [], set()
    for dossier in depot.tous(racine):
        if lisible is not None and not lisible(dossier):
            continue
        texte = depot.fiche(dossier)
        if texte and "session `" in texte:
            sessions.add(texte.split("session `")[-1].split("`")[0])
        for releve in depot.etats(dossier):
            if "__illisible__" in (releve.get("etat") or {}):
                continue  # un bloc illisible ne colore rien
            releve["ha"] = dossier.nom
            releves.append(releve)
    return releves, sessions


def _releves_en_cours(
    harness: Harness, journal: Path, deja: set[str],
    cles: tuple[str, ...] = (), cles_exclues: tuple[str, ...] = (),
) -> list[dict]:
    """Les blocs des sessions encore ouvertes — celles que la capture n'a pas vues.

    Sans ça, le QG ne se colore qu'à la clôture d'une session : cinq minutes de
    silence après la dernière réplique. La conversation en cours n'apparaîtrait
    nulle part, alors que c'est elle qu'on regarde.
    """
    from ..corpus.journal import lire_journal
    from ..etat import extraire

    releves = []
    for ligne in lire_journal(journal, harness.id):
        identite = ligne.get("identite") or {}
        if identite.get("harness") != harness.id:
            continue
        if ligne.get("session") in deja:
            continue
        # Une session vivante n'apparaît que dans le corpus qui la revendique.
        cle = identite.get("cle")
        if cles and cle not in cles:
            continue
        if not cles and cle in cles_exclues:
            continue
        for etat in extraire(ligne.get("reponse") or ""):
            if "__illisible__" in etat:
                continue
            releves.append(
                {
                    "horodatage": ligne.get("fin") or ligne.get("debut"),
                    "etat": etat,
                    "ha": None,  # pas encore capturé
                    "en_cours": True,
                }
            )
    return releves


def _releves(
    harness: Harness, journal: Path | None = None, corpus: Path | None = None, lisible=None
) -> list[dict]:
    """Tous les blocs d'état, capturés puis en cours, dans l'ordre du temps."""
    releves, sessions = _releves_corpus(harness, chemin_corpus(harness, corpus), lisible)
    if journal is not None and (Path(journal).is_dir() or journal_pour() is not None):
        vise = corpus if isinstance(corpus, str) else None
        declare = harness.corpus_par_nom(vise) if vise else harness.corpus_nommes[0]
        releves += _releves_en_cours(
            harness, Path(journal), sessions,
            cles=declare.cles if declare else (),
            cles_exclues=harness.cles_des_autres(declare.nom) if declare else (),
        )
    return sorted(releves, key=lambda r: r.get("horodatage") or "")


def chemin_corpus(harness: Harness, corpus) -> Path | None:
    """Un nom de corpus, un chemin, ou rien — on rend toujours un chemin."""
    if corpus is None:
        return None
    if isinstance(corpus, str):
        declare = harness.corpus_par_nom(corpus)
        return declare.chemin if declare else None
    return Path(corpus)


TOUR = re.compile(r"^## Tour (\d+)(.*)$", re.MULTILINE)


def _tours_du_transcript(texte: str) -> list[dict]:
    """Les tours d'un transcript — le format que le middleware écrit."""
    tours, marques = [], list(TOUR.finditer(texte))
    for rang, marque in enumerate(marques):
        fin = marques[rang + 1].start() if rang + 1 < len(marques) else len(texte)
        bloc = texte[marque.end() : fin]
        porteur, _, suite = bloc.partition("**Kata** —")
        porteur = porteur.replace("**Porteur** —", "").strip()
        if porteur:
            tours.append({"role": "humain", "texte": porteur})
        if suite.strip():
            tours.append({"role": "kata", "texte": suite.strip()})
    return tours


def _sessions_du_corpus(
    harness: Harness, sujet: str, corpus: Path | None, lisible=None
) -> dict[str, list[dict]]:
    """Les sessions de pratique, par nœud — chaque état renvoie à sa source."""
    racine = Path(corpus) if corpus is not None else harness.corpus
    depot = depot_pour(harness)
    par_noeud: dict[str, list[dict]] = {}

    for dossier in depot.tous(racine):
        if lisible is not None and not lisible(dossier):
            continue
        if not depot.a_des_etats(dossier) or depot.fiche(dossier) is None:
            continue

        releves = depot.etats(dossier)
        if not any((r.get("etat") or {}).get("sujet") == sujet for r in releves):
            continue
        blocs = len(releves)

        entete = depot.entete(dossier)
        transcript = depot.transcript(dossier)
        tours = _tours_du_transcript(transcript) if transcript is not None else []
        par_noeud.setdefault(str(entete.get("kata")), []).append(
            {
                "id": dossier.nom,
                "titre": dossier.nom,
                "date": entete.get("date"),
                "tours": tours,
                "nombre_tours": (entete.get("scores") or {}).get("tours"),
                "version_kata": entete.get("version_kata"),
                "moteur": entete.get("moteur"),
                "blocs": blocs,
                "reabstrait": bool(entete.get("etat_reabstrait")),
                "fil": entete.get("fil") or "",
            }
        )
    return par_noeud


def sujets(
    harness: Harness, journal: Path | None = None, corpus: Path | None = None, lisible=None
) -> list[str]:
    """Les sujets que les blocs d'état déclarent — le QG n'en invente aucun.

    « Les sujets appartiennent à leur praticien : le QG montre *mes* sujets »
    (RFC-004 §5). Le filtre `lisible` est ce qui rend cette phrase vraie.
    """
    vus = {(r.get("etat") or {}).get("sujet") for r in _releves(harness, journal, corpus, lisible)}
    return sorted(s for s in vus if s)


def _ligne_conversation(dossier, entete: dict, releves: list[dict], noms: dict[str, str]) -> dict:
    """Ce qu'on sait d'une conversation sans l'ouvrir — sa fiche, et son sujet s'il existe."""
    sujet = next(
        (s for s in ((r.get("etat") or {}).get("sujet") for r in reversed(releves)) if s), ""
    )
    kata = str(entete.get("kata") or "")
    return {
        "id": dossier.nom,
        "date": str(entete.get("date") or ""),
        "kata": kata,
        "kata_nom": noms.get(kata, kata),
        "cible": str(entete.get("cible") or ""),
        "sujet": str(sujet or ""),
        "tours": (entete.get("scores") or {}).get("tours"),
        "blocs": len(releves),
        "en_cours": bool(entete.get("en_cours")),
        "reabstrait": bool(entete.get("etat_reabstrait")),
        "fil": str(entete.get("fil") or ""),
    }


def conversations(harness: Harness, corpus=None, lisible=None) -> list[dict]:
    """Les conversations d'un corpus, une par ha, la plus récente en tête.

    Lues dans les fiches, pas dans les états. Le QG est organisé par sujet, et
    un sujet n'existe que si une session a émis un bloc d'état : une
    conversation sur une cible sans bloc n'y apparaît donc jamais. Ici elle se
    retrouve — avec ou sans état ; le sujet, s'il existe, n'est qu'une
    information affichée. Le filtre `lisible` s'applique ha par ha, comme
    partout (RFC-004 §5).
    """
    racine = chemin_corpus(harness, corpus) or harness.corpus
    depot = depot_pour(harness)
    noms = {k.id: k.nom for k in harness.kata}
    lignes = []
    for dossier in depot.tous(racine):
        if lisible is not None and not lisible(dossier):
            continue
        entete = depot.entete(dossier)
        if not entete:
            continue
        lignes.append(_ligne_conversation(dossier, entete, depot.etats(dossier), noms))
    lignes.sort(key=lambda ligne: ligne["date"], reverse=True)
    return lignes


def conversation(harness: Harness, corpus, identifiant: str, lisible=None) -> dict | None:
    """Une conversation ouverte : sa ligne, et ses tours.

    `None` si elle est inconnue — ou illisible, ce qui ne se distingue pas :
    dire « elle existe, mais pas pour toi » renseignerait déjà sur la pratique
    d'autrui (RFC-004 §5).
    """
    racine = chemin_corpus(harness, corpus) or harness.corpus
    depot = depot_pour(harness)
    dossier = next((d for d in depot.tous(racine) if d.nom == identifiant), None)
    if dossier is None or (lisible is not None and not lisible(dossier)):
        return None
    entete = depot.entete(dossier) or {}
    transcript = depot.transcript(dossier)
    noms = {k.id: k.nom for k in harness.kata}
    ligne = _ligne_conversation(dossier, entete, depot.etats(dossier), noms)
    return {
        **ligne,
        "nombre_tours": ligne["tours"],
        "tours": _tours_du_transcript(transcript) if transcript else [],
        "version_kata": str(entete.get("version_kata") or ""),
        "moteur": str(entete.get("moteur") or ""),
    }


def _instant(valeur: str | None):
    try:
        return datetime.fromisoformat(valeur) if valeur else None
    except (TypeError, ValueError):
        return None


def composer(
    harness: Harness,
    sujet: str,
    journal: Path | None = None,
    corpus: Path | None = None,
    lisible=None,
) -> VueQG:
    """La vue d'un sujet : la chaîne déclarée, peuplée de ce qui a été observé.

    Avec `journal`, les sessions encore ouvertes sont prises en compte : le QG
    suit la conversation en cours, sans attendre sa clôture.
    """
    produits = {
        k.id: tuple(champ_nu(r) for r, _ in k.produit) for k in harness.kata
    }
    # Le nom d'affichage d'un nœud est celui de son kata — la seule source,
    # reprise partout (RFC-013, K-06). Le nom de la chaîne ne sert qu'aux
    # nœuds qui ne sont pas des kata : un jalon, une étape externe.
    noms_de_kata = {k.id: k.nom for k in harness.kata}
    orphelins = {k.id for k in harness.kata if k.orphelin or harness.exogene}
    noeuds = {
        n.id: VueNoeud(
            id=n.id, type=n.type, nom=noms_de_kata.get(n.id, n.nom),
            attendus=produits.get(n.id, ()),
            sans_contrat=n.id in orphelins and not produits.get(n.id),
        )
        for n in harness.chaine.noeuds
    }

    naissances: dict[str, tuple[str, str]] = {}  # id option → (horodatage, noeud)
    dernier_vu: dict[str, dict] = {}  # id option → dernier état connu
    decisions: list[dict] = []
    observe_le: str | None = None

    en_cours = reabstrait = False
    for releve in _releves(harness, journal, corpus, lisible):
        etat = releve.get("etat") or {}
        if etat.get("sujet") != sujet:
            continue
        horodatage = releve.get("horodatage")
        observe_le = horodatage or observe_le
        en_cours = en_cours or bool(releve.get("en_cours"))
        reabstrait = reabstrait or bool(releve.get("reabstrait"))

        noeud = noeuds.get(etat.get("kata"))
        if noeud is not None:
            champs = etat.get("champs")
            if isinstance(champs, dict):
                noeud.champs.update(champs)
            hypotheses = etat.get("hypotheses")
            if isinstance(hypotheses, list):
                noeud.hypotheses = [h for h in hypotheses if isinstance(h, dict)]
            noeud.dernier_etat = horodatage
            noeud.etape = etat.get("etape") or noeud.etape
            nature = etat.get("nature")
            if isinstance(nature, dict) and str(nature.get("valeur") or "").strip():
                noeud.nature = nature  # la dernière émise l'emporte (RFC-003 §4)
            noeud.provenance = {
                "harness": etat.get("harness"),
                "kata": etat.get("kata"),
                "version": etat.get("version"),
                "ha": releve.get("ha"),
                "reabstrait": bool(releve.get("reabstrait")),
            }

        for option in etat.get("options") or []:
            if not isinstance(option, dict) or not option.get("id"):
                continue
            identifiant = str(option["id"])
            ou = str(option.get("noeud") or etat.get("kata") or "")
            naissances.setdefault(identifiant, (horodatage or "", ou))
            dernier_vu[identifiant] = {**option, "noeud": ou}

        decision = etat.get("decision")
        if isinstance(decision, dict) and str(decision.get("libelle") or "").strip():
            decisions.append(
                {
                    "horodatage": horodatage,
                    "noeud": etat.get("kata"),
                    "libelle": decision.get("libelle"),
                    "ferme": list(decision.get("ferme") or []),
                    "ouvre": list(decision.get("ouvre") or []),
                }
            )

    # Chaque nœud renvoie aux sessions qui l'ont pratiqué : un état sans sa
    # source serait invérifiable.
    sessions = _sessions_du_corpus(harness, sujet, chemin_corpus(harness, corpus), lisible)
    for id_kata, liste in sessions.items():
        if id_kata in noeuds:
            noeuds[id_kata].sessions = sorted(liste, key=lambda s: s.get("date") or "")

    reference = _instant(observe_le)
    for identifiant, option in dernier_vu.items():
        naissance, ou = naissances.get(identifiant, ("", ""))
        debut = _instant(naissance)
        age = None
        if reference and debut:
            ecart: timedelta = reference - debut
            age = round(ecart.total_seconds() / 86400, 3)
        cible = noeuds.get(ou) or noeuds.get(option.get("noeud", ""))
        if cible is None:
            continue
        cible.options.append(
            Option(
                id=identifiant,
                libelle=str(option.get("libelle") or ""),
                noeud=cible.id,
                statut=str(option.get("statut") or ""),
                naissance=naissance,
                age_jours=age,
            )
        )

    # Une décision se lit par ce qu'elle referme, pas par des identifiants.
    libelles = {i: o.get("libelle") or i for i, o in dernier_vu.items()}
    for decision in decisions:
        for sens in ("ferme", "ouvre"):
            decision[sens] = [libelles.get(str(i), str(i)) for i in decision[sens]]

    return VueQG(
        harness=harness.id,
        sujet=sujet,
        en_cours=en_cours,
        reabstrait=reabstrait,
        noeuds=list(noeuds.values()),
        aretes=[{"de": a.de, "vers": a.vers, "label": a.label} for a in harness.chaine.aretes],
        decisions=decisions,
        observe_le=observe_le,
    )


def rendre_texte(harness: Harness, vue: VueQG) -> str:
    """La même vue, au terminal — sans couleur, mais avec la même graduation."""
    lignes = [f"sujet : {vue.sujet}", f"observé le : {vue.observe_le or '—'}"]
    if vue.reabstrait:
        lignes.append("⚠ état ré-abstrait depuis le transcript — une lecture, pas une observation")
    lignes.append("")

    for noeud in vue.noeuds:
        part = noeud.chaleur(harness)
        if part is None:
            jauge, mesure = "·" * 10, "    —"
        else:
            plein = round(part * 10)
            jauge, mesure = "█" * plein + "·" * (10 - plein), f"{part:>5.0%}"
        vivantes = len(noeud.options_vivantes)
        badge = f"  ○ {vivantes}" if vivantes else ""
        marque = "  ◇" if noeud.refutees else ""
        lignes.append(f"  {jauge} {mesure}  {noeud.id:<16} {noeud.nom}{badge}{marque}")
        for champ in noeud.attendus:
            lignes.append(f"      {champ:<26} {noeud.champs.get(champ) or '—'}")
        for hypothese in noeud.hypotheses:
            lignes.append(
                f"      ? {str(hypothese.get('libelle'))[:44]:<44} "
                f"{hypothese.get('statut')} / {hypothese.get('confiance')}"
            )

    vivantes = vue.options_vivantes
    lignes += ["", f"possibles vivants : {len(vivantes)}"]
    median = vue.age_median()
    if median is not None:
        lignes.append(f"âge médian : {median:.2f} jour(s)")
    for option in vivantes:
        age = f"{option.age_jours:.2f}j" if option.age_jours is not None else "—"
        lignes.append(f"  [{option.noeud}] {option.libelle[:56]:<56} {age}")

    if vue.decisions:
        lignes += ["", "décisions :"]
        for decision in vue.decisions:
            lignes.append(
                f"  {decision['libelle'][:50]:<50} "
                f"ferme {len(decision['ferme'])} / ouvre {len(decision['ouvre'])}"
            )
    return "\n".join(lignes)


def racine_html() -> Path:
    return Path(__file__).parent / "vue.html"


def activites(
    harness: Harness, journal: Path | None = None, corpus=None, lisible=None
) -> list[dict]:
    """Les sujets qu'une personne peut observer, et par quel harness.

    C'est le fond du module « Profil » du design : un sujet, le harness qui l'a
    porté, combien de sessions l'ont travaillé, et quand pour la dernière fois.

    Rien n'est déduit : un sujet n'existe que si un bloc d'état l'a nommé, et sa
    date de dernière pratique est celle du dernier ha qui l'a touché. Un sujet
    jamais pratiqué ne figure pas — il n'existe pas encore.
    """
    racine = chemin_corpus(harness, corpus)
    dossier_racine = Path(racine) if racine is not None else harness.corpus
    depot = depot_pour(harness)

    par_sujet: dict[str, dict] = {}
    for dossier in depot.tous(dossier_racine):
        if lisible is not None and not lisible(dossier):
            continue
        if not depot.a_des_etats(dossier) or depot.fiche(dossier) is None:
            continue

        sujets_du_ha = set()
        for releve in depot.etats(dossier):
            nom = (releve.get("etat") or {}).get("sujet")
            if nom:
                sujets_du_ha.add(str(nom))
        if not sujets_du_ha:
            continue

        entete = depot.entete(dossier)
        quand = str(entete.get("date") or "")
        for nom in sujets_du_ha:
            vu = par_sujet.setdefault(
                nom,
                {
                    "sujet": nom,
                    "harness": harness.nom,
                    "version": harness.version,
                    "sessions": 0,
                    "derniere": "",
                    "praticiens": set(),
                },
            )
            vu["sessions"] += 1
            vu["derniere"] = max(vu["derniere"], quand)
            if entete.get("praticien"):
                vu["praticiens"].add(str(entete["praticien"]))

    return [
        {**v, "praticiens": sorted(v.pop("praticiens"))}
        for v in sorted(par_sujet.values(), key=lambda x: x["sujet"])
    ]


def composition(harness: Harness) -> str:
    """« 3 kata, 1 jalon » — ce dont la chaîne est faite, sans rien inventer."""
    comptes: dict[str, int] = {}
    for noeud in harness.chaine.noeuds:
        comptes[noeud.type] = comptes.get(noeud.type, 0) + 1
    return ", ".join(f"{n} {t}" for t, n in sorted(comptes.items()))
