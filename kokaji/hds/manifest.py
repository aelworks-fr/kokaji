"""Chargement et validation d'un manifest HDS v0 (SPECS §2, R2.1).

La validation ne s'arrête pas à la première faute : elle les rassemble toutes et
les rend d'un coup, chacune située par son chemin dans le manifest. Un harness
incomplet est refusé — jamais complété en silence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .modele import Arete, Chaine, Cible, Corpus, Etat, Harness, Kata, Noeud, Trempe

SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# RFC-002 §3 — un champ se nomme toujours par le kata qui l'établit.
CHAMP_QUALIFIE = re.compile(r"^([a-z0-9]+(?:[-_][a-z0-9]+)*)\.([a-z0-9]+(?:[-_][a-z0-9]+)*)$")
TYPES_NOEUD = frozenset({"kata", "jalon", "externe"})
PACKAGINGS = frozenset({"dossier", "zip"})


@dataclass(frozen=True)
class Faute:
    ou: str
    quoi: str

    def __str__(self) -> str:
        return f"{self.ou} : {self.quoi}"


class ManifestInvalide(Exception):
    """Le manifest ne décrit pas un harness exploitable."""

    def __init__(self, racine: Path, fautes: list[Faute]):
        self.racine = racine
        self.fautes = fautes
        detail = "\n".join(f"  - {f}" for f in fautes)
        super().__init__(f"{racine}/harness.yaml — {len(fautes)} faute(s)\n{detail}")


class _Lecture:
    """Accumule les fautes en parcourant le manifest."""

    def __init__(self, racine: Path, donnees: dict):
        self.racine = racine
        self.d = donnees
        self.fautes: list[Faute] = []

    def faute(self, ou: str, quoi: str) -> None:
        self.fautes.append(Faute(ou, quoi))

    @staticmethod
    def _situer(ou: str, cle: str) -> str:
        """Le chemin d'une clé — sans point en tête à la racine du manifest."""
        return f"{ou}.{cle}" if ou else cle

    def texte(self, bloc: dict, ou: str, cle: str) -> str:
        valeur = bloc.get(cle)
        if not isinstance(valeur, str) or not valeur.strip():
            self.faute(self._situer(ou, cle), "attendu : un texte non vide")
            return ""
        return valeur.strip()

    def liste(self, bloc: dict, ou: str, cle: str, *, obligatoire: bool = False) -> list:
        valeur = bloc.get(cle, [])
        if valeur is None:
            valeur = []
        if not isinstance(valeur, list):
            self.faute(self._situer(ou, cle), "attendu : une liste")
            return []
        if obligatoire and not valeur:
            self.faute(self._situer(ou, cle), "attendu : une liste non vide")
        return valeur

    def booleen(self, bloc: dict, ou: str, cle: str, *, defaut: bool = False) -> bool:
        valeur = bloc.get(cle, defaut)
        if not isinstance(valeur, bool):
            self.faute(self._situer(ou, cle), "attendu : true ou false")
            return defaut
        return valeur

    def bloc(self, ou: str, cle: str, *, obligatoire: bool = True) -> dict:
        valeur = self.d.get(cle)
        if valeur is None:
            if obligatoire:
                self.faute(ou, "section absente")
            return {}
        if not isinstance(valeur, dict):
            self.faute(ou, "attendu : une section")
            return {}
        return valeur

    def chemin(self, ou: str, valeur: str, *, dossier: bool = False) -> Path:
        """Un chemin relatif à la racine du harness, dont l'existence est exigée."""
        p = (self.racine / valeur).resolve()
        try:
            p.relative_to(self.racine.resolve())
        except ValueError:
            self.faute(ou, f"sort du harness : {valeur}")
            return p
        if dossier and not p.is_dir():
            self.faute(ou, f"dossier absent : {valeur}")
        elif not dossier and not p.is_file():
            self.faute(ou, f"fichier absent : {valeur}")
        return p

    def slug(self, ou: str, valeur: str) -> str:
        if valeur and not SLUG.match(valeur):
            self.faute(ou, f"slug attendu (minuscules, tirets) : {valeur!r}")
        return valeur


def charger(racine: str | Path) -> Harness:
    """Charge un harness depuis son dossier. Lève `ManifestInvalide` si besoin."""
    racine = Path(racine)
    fichier = racine / "harness.yaml"
    if not fichier.is_file():
        raise ManifestInvalide(racine, [Faute("harness.yaml", "manifest absent")])

    try:
        donnees = yaml.safe_load(fichier.read_text(encoding="utf-8"))
    except yaml.YAMLError as err:
        raise ManifestInvalide(racine, [Faute("harness.yaml", f"YAML illisible : {err}")])
    if not isinstance(donnees, dict):
        raise ManifestInvalide(racine, [Faute("harness.yaml", "attendu : une section racine")])

    lecture = _Lecture(racine, donnees)
    harness = _composer(lecture)
    if lecture.fautes:
        raise ManifestInvalide(racine, lecture.fautes)
    return harness


def charger_tous(racine: str | Path) -> dict[str, Harness]:
    """Les harness d'un dossier, indexés par leur id — RFC-005 §5.

    Deux formes sont acceptées, et c'est délibéré : un dossier **qui est** un
    harness donne ce seul harness, un dossier **qui en contient** les donne tous.
    Sans cette compatibilité, servir plusieurs harness obligerait à réécrire
    chaque appel existant — le multi-harness deviendrait une migration au lieu
    d'être une extension.

    Deux dossiers qui déclarent le même id sont une faute, pas un choix : le
    second masquerait le premier, et le corpus des deux se mélangerait sous une
    seule clé d'archive.
    """
    charges, refuses = charger_valides(racine)
    # Le nom du dossier fautif tient lieu de lieu : sans lui on saurait qu'un
    # harness ne tient pas, sans savoir lequel ouvrir.
    for nom, motif in refuses:
        raise ManifestInvalide(Path(racine), [Faute(nom, motif)])
    if not charges:
        raise ManifestInvalide(Path(racine), [Faute("harness.yaml", "aucun harness dans ce dossier")])
    return charges


def charger_valides(racine: str | Path) -> tuple[dict[str, Harness], list[tuple[str, str]]]:
    """Les harness qui tiennent, et le motif de ceux qui ne tiennent pas.

    **Un harness cassé n'emporte pas les autres.** Un service qui refuse de
    démarrer parce qu'un seul manifest est fautif met tous les autres à terre
    avec lui — c'est exactement ce qui s'est produit à NOTE-0009, où un
    validateur périmé sur un manifest a coûté deux jours de capture, en silence.

    Le refus est donc **rendu, jamais avalé** : c'est l'appelant qui décide
    d'arrêter (une validation) ou de continuer en le signalant (un service).
    """
    racine = Path(racine)
    if (racine / "harness.yaml").is_file():
        try:
            seul = charger(racine)
        except ManifestInvalide as err:
            return {}, [(racine.name, str(err))]
        return {seul.id: seul}, []

    charges: dict[str, Harness] = {}
    origines: dict[str, str] = {}
    refuses: list[tuple[str, str]] = []
    for dossier in sorted(p for p in racine.iterdir() if p.is_dir()):
        if not (dossier / "harness.yaml").is_file():
            continue
        try:
            harness = charger(dossier)
        except ManifestInvalide as err:
            refuses.append((dossier.name, str(err)))
            continue
        if harness.id in charges:
            # Le second masquerait le premier et leurs corpus se mélangeraient
            # sous une seule clé d'archive : on écarte l'arrivant, pas le tenant.
            refuses.append(
                (dossier.name, f"id déjà porté par {origines[harness.id]} : {harness.id}")
            )
            continue
        charges[harness.id] = harness
        origines[harness.id] = dossier.name
    return charges, refuses


def _composer(l: _Lecture) -> Harness | None:
    entete = l.bloc("harness", "harness")
    id_harness = l.slug("harness.id", l.texte(entete, "harness", "id"))

    # L'état se lit d'abord : c'est lui qui fixe l'ordre de D, dont `produit` a
    # besoin pour valider ses statuts (RFC-002 §2).
    etat = _etat(l)
    # RFC-008 : un harness exogène assouplit deux exigences, nommées là où
    # elles s'exercent — le livrable d'un kata, et la nature de sa source.
    exogene = l.booleen(entete, "harness", "exogene")
    kata = _kata(l, etat.statuts_champ, exogene=exogene)
    cibles = _cibles(l)
    chaine = _chaine(l, kata)
    trempe = _trempe(l)

    template = l.chemin("template", l.texte(l.d, "", "template") or "template.md")
    personas = l.chemin("personas", str(l.d.get("personas") or "personas/"), dossier=True)
    corpus = _corpus(l)

    provenance = _provenance(l, entete, exogene)

    # RFC-008 §4 (amendé) — l'exception des champs exogènes, et sa fermeture.
    # La règle générale (RFC-002 §3) dérive les champs des contrats, seule
    # source de vérité. `etat.champs` n'existe que pour un harness exogène qui
    # n'a encore aucun contrat ; dès qu'un f♯ apparaît, elle redevient une
    # faute — deux déclarations du même savoir finissent toujours par diverger.
    if etat.champs:
        if not exogene:
            l.faute("etat.champs", "réservé aux harness exogènes — "
                    "les champs se dérivent des contrats (RFC-002 §3)")
        elif any(k.produit or k.herite for k in kata):
            l.faute("etat.champs", "un contrat est déclaré : les champs s'en "
                    "dérivent, cette clé se retire (RFC-008 §4)")

    if l.fautes:
        return None
    return Harness(
        racine=l.racine,
        id=id_harness,
        nom=l.texte(entete, "harness", "nom"),
        version=l.texte(entete, "harness", "version"),
        langue=entete.get("langue", "fr"),
        domaine=l.texte(entete, "harness", "domaine"),
        kata=kata,
        chaine=chaine,
        template=template,
        cibles=cibles,
        trempe=trempe,
        etat=etat,
        personas=personas,
        corpus_nommes=corpus,
        exogene=exogene,
        provenance=provenance,
    )


def _provenance(l: _Lecture, entete: dict, exogene: bool) -> tuple[tuple[str, str], ...]:
    """D'où le harness est parti — exigée dès qu'il se dit exogène.

    Sans elle, « exogène » ne serait qu'un mot : on saurait qu'il vient
    d'ailleurs sans jamais pouvoir dire d'où, ni si le texte a divergé depuis.
    L'estampille est le prix de l'éditabilité (RFC-008 §5).
    """
    brut = entete.get("provenance")
    if not exogene:
        if brut is not None:
            l.faute("harness.provenance", "réservée aux harness `exogene: true`")
        return ()
    if not isinstance(brut, dict):
        l.faute("harness.provenance", "section absente — un exogène dit d'où il vient")
        return ()
    for cle in ("source", "checksum_import", "date_import"):
        if not str(brut.get(cle) or "").strip():
            l.faute(f"harness.provenance.{cle}", "attendu : un texte non vide")
    return tuple((str(c), str(v)) for c, v in brut.items())


def _herite(
    l: _Lecture, item: dict, ou: str, statuts_champ: tuple[str, ...]
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Le domaine de f♯ — des champs qualifiés `<kata>.<champ>` (RFC-002 §3).

    Deux écritures, et la seconde est un ajout à l'application du RFC :

    - `idee.besoin` — ce champ doit être présent, quel que soit son statut ;
    - `idee.besoin: fait_etabli` — et au moins à ce niveau-là.

    Le RFC-002 §6.2 promet que « le `produit` de l'amont couvre le `herite` de
    l'aval **au sens de l'ordre des statuts** ». Sans seuil déclaré quelque part,
    cette clause n'a rien à comparer : elle se réduit à une présence. Le seuil
    est donc facultatif — l'écriture nue reste valide et garde exactement le sens
    qu'elle avait.
    """
    if "heritage" in item:
        l.faute(f"{ou}.heritage", "renommé `herite` en HDS v0.1 (RFC-002 §3)")

    references: list[str] = []
    exigences: dict[str, str] = {}
    for rang, valeur in enumerate(l.liste(item, ou, "herite")):
        if isinstance(valeur, str):
            if not CHAMP_QUALIFIE.match(valeur):
                l.faute(f"{ou}.herite[{rang}]", f"attendu : <kata>.<champ> — {valeur!r}")
                continue
            references.append(valeur)
            continue

        if not isinstance(valeur, dict) or len(valeur) != 1:
            l.faute(
                f"{ou}.herite[{rang}]",
                f"attendu : <kata>.<champ> ou <kata>.<champ>: <statut> — {valeur!r}",
            )
            continue

        (reference, minimum), = valeur.items()
        if not isinstance(reference, str) or not CHAMP_QUALIFIE.match(reference):
            l.faute(f"{ou}.herite[{rang}]", f"attendu : <kata>.<champ> — {reference!r}")
            continue
        if minimum not in statuts_champ:
            l.faute(
                f"{ou}.herite[{rang}]",
                f"statut hors `etat.statuts_champ` — {minimum!r} "
                f"(admis : {', '.join(statuts_champ)})",
            )
            continue
        references.append(reference)
        exigences[reference] = str(minimum)
    return tuple(references), exigences


def _produit(
    l: _Lecture, item: dict, ou: str, statuts_champ: tuple[str, ...]
) -> tuple[tuple[str, str], ...]:
    """Le codomaine de f♯ — chaque champ avec son statut minimal garanti."""
    engagements: list[tuple[str, str]] = []

    for rang, valeur in enumerate(l.liste(item, ou, "produit")):
        situe = f"{ou}.produit[{rang}]"
        if not isinstance(valeur, dict) or len(valeur) != 1:
            l.faute(situe, f"attendu : <kata>.<champ>: <statut> — {valeur!r}")
            continue
        (reference, statut), = valeur.items()
        if not isinstance(reference, str) or not CHAMP_QUALIFIE.match(reference):
            l.faute(situe, f"attendu : <kata>.<champ> — {reference!r}")
            continue
        if statut not in statuts_champ:
            l.faute(situe, f"statut hors `etat.statuts_champ` — {statut!r}")
            continue
        engagements.append((reference, str(statut)))
    return tuple(engagements)


def _corpus(l: _Lecture) -> tuple[Corpus, ...]:
    """Un chemin, ou plusieurs corpus nommés (HDS v0.2).

    La forme simple reste valide : `corpus: corpus/` vaut un unique corpus
    nommé `reel`. La forme nommée sépare ce qui doit l'être — les cas réels des
    essais — sans que Kokaji sache ce que ces noms veulent dire.
    """
    valeur = l.d.get("corpus") or "corpus/"
    if isinstance(valeur, str):
        return (Corpus("reel", l.chemin("corpus", valeur, dossier=True)),)
    if not isinstance(valeur, dict) or not valeur:
        l.faute("corpus", "attendu : un chemin, ou des corpus nommés")
        return (Corpus("reel", l.racine / "corpus"),)

    nommes = []
    for nom, detail in valeur.items():
        ou = f"corpus.{nom}"
        l.slug(ou, str(nom))
        if isinstance(detail, str):
            nommes.append(Corpus(str(nom), l.chemin(ou, detail, dossier=True)))
            continue
        if not isinstance(detail, dict) or not detail.get("chemin"):
            l.faute(ou, "attendu : un chemin, ou une section avec `chemin`")
            continue
        nommes.append(
            Corpus(
                nom=str(nom),
                chemin=l.chemin(f"{ou}.chemin", str(detail["chemin"]), dossier=True),
                cles=tuple(str(c) for c in l.liste(detail, ou, "cles")),
            )
        )
    return tuple(nommes)


def _kata(
    l: _Lecture, statuts_champ: tuple[str, ...], exogene: bool = False
) -> tuple[Kata, ...]:
    brut = l.liste(l.d, "", "kata", obligatoire=True)
    vus: set[str] = set()
    kata: list[Kata] = []

    for rang, item in enumerate(brut):
        ou = f"kata[{rang}]"
        if not isinstance(item, dict):
            l.faute(ou, "attendu : une section")
            continue
        id_kata = l.slug(f"{ou}.id", l.texte(item, ou, "id"))
        if id_kata in vus:
            l.faute(f"{ou}.id", f"id déjà utilisé : {id_kata!r}")
        vus.add(id_kata)
        references, exigences = _herite(l, item, ou, statuts_champ)
        kata.append(
            Kata(
                id=id_kata,
                nom=(nom_kata := l.texte(item, ou, "nom")),
                source=l.chemin(f"{ou}.source", l.texte(item, ou, "source") or "."),
                # Une coupe orpheline n'a pas de livrable déclaré : le texte
                # importé dit ce qu'il dit, et on ne lui invente rien. Le nom
                # tient lieu d'étiquette (RFC-008 §4).
                livrable=(
                    str(item.get("livrable") or "").strip() or nom_kata
                    if exogene
                    else l.texte(item, ou, "livrable")
                ),
                amont=tuple(l.liste(item, ou, "amont")),
                herite=references,
                exigences=exigences,
                produit=_produit(l, item, ou, statuts_champ),
                emet_options=l.booleen(item, ou, "emet_options"),
            )
        )

    for rang, k in enumerate(kata):
        for amont in k.amont:
            if amont not in vus:
                l.faute(f"kata[{rang}].amont", f"kata inconnu : {amont!r}")
        if k.herite and not k.amont:
            l.faute(f"kata[{rang}].herite", "hérite sans amont déclaré")
        for reference in k.herite:
            proprietaire = reference.split(".", 1)[0]
            if proprietaire not in k.amont:
                l.faute(
                    f"kata[{rang}].herite",
                    f"{reference!r} : {proprietaire!r} n'est pas un amont de ce kata",
                )
        for reference, _ in k.produit:
            proprietaire = reference.split(".", 1)[0]
            if proprietaire != k.id:
                l.faute(
                    f"kata[{rang}].produit",
                    f"{reference!r} : un kata ne produit que ses propres champs",
                )
    _detecter_cycle(l, kata)
    return tuple(kata)


def _detecter_cycle(l: _Lecture, kata: list[Kata]) -> None:
    amonts = {k.id: [a for a in k.amont if a] for k in kata}
    etat: dict[str, int] = {}

    def descendre(id_kata: str, chemin: list[str]) -> None:
        if etat.get(id_kata) == 2:
            return
        if etat.get(id_kata) == 1:
            boucle = " → ".join(chemin[chemin.index(id_kata) :] + [id_kata])
            l.faute("kata.amont", f"héritage circulaire : {boucle}")
            return
        etat[id_kata] = 1
        for suivant in amonts.get(id_kata, []):
            if suivant in amonts:
                descendre(suivant, chemin + [id_kata])
        etat[id_kata] = 2

    for k in kata:
        descendre(k.id, [])


def _cibles(l: _Lecture) -> tuple[Cible, ...]:
    brut = l.liste(l.d, "", "cibles", obligatoire=True)
    vues: set[str] = set()
    cibles: list[Cible] = []

    for rang, item in enumerate(brut):
        ou = f"cibles[{rang}]"
        if not isinstance(item, dict):
            l.faute(ou, "attendu : une section")
            continue
        id_cible = l.slug(f"{ou}.id", l.texte(item, ou, "id"))
        if id_cible in vues:
            l.faute(f"{ou}.id", f"id déjà utilisé : {id_cible!r}")
        vues.add(id_cible)

        etat_structure = item.get("etat_structure", False)
        if not isinstance(etat_structure, bool):
            l.faute(f"{ou}.etat_structure", "attendu : true ou false")
            etat_structure = False

        packaging = item.get("packaging", "dossier")
        if packaging not in PACKAGINGS:
            l.faute(f"{ou}.packaging", f"attendu : {' | '.join(sorted(PACKAGINGS))}")
            packaging = "dossier"

        cibles.append(
            Cible(
                id=id_cible,
                etat_structure=etat_structure,
                en_tete=str(item.get("en_tete") or ""),
                packaging=packaging,
            )
        )
    return tuple(cibles)


def _chaine(l: _Lecture, kata: tuple[Kata, ...]) -> Chaine:
    bloc = l.bloc("chaine", "chaine")
    noeuds: list[Noeud] = []
    vus: set[str] = set()

    for rang, item in enumerate(l.liste(bloc, "chaine", "noeuds", obligatoire=True)):
        ou = f"chaine.noeuds[{rang}]"
        if not isinstance(item, dict):
            l.faute(ou, "attendu : une section")
            continue
        id_noeud = l.slug(f"{ou}.id", l.texte(item, ou, "id"))
        if id_noeud in vus:
            l.faute(f"{ou}.id", f"id déjà utilisé : {id_noeud!r}")
        vus.add(id_noeud)
        type_noeud = item.get("type")
        if type_noeud not in TYPES_NOEUD:
            l.faute(f"{ou}.type", f"attendu : {' | '.join(sorted(TYPES_NOEUD))}")
        if type_noeud == "kata" and id_noeud not in {k.id for k in kata}:
            l.faute(f"{ou}.id", f"nœud de type kata sans kata déclaré : {id_noeud!r}")
        noeuds.append(Noeud(id=id_noeud, type=str(type_noeud), nom=l.texte(item, ou, "nom")))

    aretes: list[Arete] = []
    for rang, item in enumerate(l.liste(bloc, "chaine", "aretes")):
        ou = f"chaine.aretes[{rang}]"
        if not isinstance(item, dict):
            l.faute(ou, "attendu : une section")
            continue
        de, vers = l.texte(item, ou, "de"), l.texte(item, ou, "vers")
        for extremite, valeur in (("de", de), ("vers", vers)):
            if valeur and valeur not in vus:
                l.faute(f"{ou}.{extremite}", f"nœud inconnu : {valeur!r}")
        aretes.append(Arete(de=de, vers=vers, label=str(item.get("label") or "")))

    for k in kata:
        if k.id not in vus:
            l.faute("chaine.noeuds", f"kata absent de la chaîne : {k.id!r}")

    return Chaine(noeuds=tuple(noeuds), aretes=tuple(aretes))


def _trempe(l: _Lecture) -> Trempe:
    bloc = l.bloc("trempe", "trempe")
    checks = []
    for rang, item in enumerate(l.liste(bloc, "trempe", "checks_session")):
        ou = f"trempe.checks_session[{rang}]"
        if not isinstance(item, dict):
            l.faute(ou, "attendu : une section")
            continue
        for cle in ("id", "type"):
            l.texte(item, ou, cle)
        checks.append(dict(item))

    interdits = l.liste(bloc, "trempe", "vocabulaire_interdit")
    for rang, mot in enumerate(interdits):
        if not isinstance(mot, str) or not mot.strip():
            l.faute(f"trempe.vocabulaire_interdit[{rang}]", "attendu : un texte non vide")

    defaut, par_kata = _justesse(l, bloc)
    return Trempe(
        grille_judge=_grille_judge(l, bloc),
        vocabulaire_interdit=tuple(str(m) for m in interdits),
        registre=l.chemin("trempe.registre", str(bloc.get("registre") or "registre.yaml")),
        checks_session=tuple(checks),
        justesse_defaut=defaut,
        justesse_par_kata=par_kata,
    )


ECHELLE = re.compile(r"^(\d+)-(\d+)$")


def _grille_judge(l: _Lecture, bloc: dict) -> tuple:
    """`trempe.grille_judge` — les critères du judge (RFC-008 §7).

    L'échelle se valide ici, pas au moment de juger : une grille fausse doit
    refuser le harness au chargement, quand on peut encore la corriger — pas
    au milieu d'une campagne de jugement.
    """
    from .modele import Critere

    criteres = []
    vus: set[str] = set()
    for rang, item in enumerate(l.liste(bloc, "trempe", "grille_judge")):
        ou = f"trempe.grille_judge[{rang}]"
        if not isinstance(item, dict):
            l.faute(ou, "attendu : une section")
            continue
        id_critere = l.slug(f"{ou}.id", l.texte(item, ou, "id"))
        if id_critere in vus:
            l.faute(f"{ou}.id", f"id déjà utilisé : {id_critere!r}")
        vus.add(id_critere)
        echelle = str(item.get("echelle") or "")
        trouve = ECHELLE.match(echelle)
        if not trouve or int(trouve.group(1)) >= int(trouve.group(2)):
            l.faute(f"{ou}.echelle", f"attendu : « bas-haut », bornes croissantes — {echelle!r}")
            continue
        criteres.append(
            Critere(id=id_critere, question=l.texte(item, ou, "question"), echelle=echelle)
        )
    return tuple(criteres)


def _taux(l: _Lecture, ou: str, valeur) -> float | None:
    """Un seuil est une proportion : entre 0 et 1, bornes comprises."""
    if not isinstance(valeur, int | float) or isinstance(valeur, bool):
        l.faute(ou, f"attendu : un nombre entre 0 et 1 — {valeur!r}")
        return None
    if not 0 <= valeur <= 1:
        l.faute(ou, f"un seuil est une proportion, entre 0 et 1 — {valeur!r}")
        return None
    return float(valeur)


def _justesse(l: _Lecture, bloc: dict) -> tuple[float, dict[str, float]]:
    """`trempe.justesse` — le seuil du diagnostic de nature (RFC-003 §5.4).

    Absent, le seuil vaut zéro : aucun seuil n'a été posé, et le rapport le dit
    plutôt que d'en supposer un. Kokaji ne se donne pas d'exigence à la place du
    harness (carnet #9).
    """
    donnees = bloc.get("justesse")
    if donnees is None:
        return 0.0, {}
    if not isinstance(donnees, dict):
        l.faute("trempe.justesse", "attendu : une section")
        return 0.0, {}

    defaut = 0.0
    if "defaut" in donnees:
        defaut = _taux(l, "trempe.justesse.defaut", donnees["defaut"]) or 0.0

    par_kata: dict[str, float] = {}
    brut = donnees.get("par_kata") or {}
    if not isinstance(brut, dict):
        l.faute("trempe.justesse.par_kata", "attendu : une section <kata>: <seuil>")
        return defaut, {}
    for kata, valeur in brut.items():
        seuil = _taux(l, f"trempe.justesse.par_kata.{kata}", valeur)
        if seuil is not None:
            par_kata[str(kata)] = seuil
    return defaut, par_kata


def _etat(l: _Lecture) -> Etat:
    bloc = l.bloc("etat", "etat", obligatoire=False)
    defauts = Etat()
    statuts = {}
    for cle, defaut in (
        ("statuts_champ", defauts.statuts_champ),
        ("statuts_hypothese", defauts.statuts_hypothese),
    ):
        valeurs = l.liste(bloc, "etat", cle) if bloc else []
        if not valeurs:
            statuts[cle] = defaut
            continue
        if any(not isinstance(v, str) or not v.strip() for v in valeurs):
            l.faute(f"etat.{cle}", "attendu : des textes non vides")
        statuts[cle] = tuple(str(v) for v in valeurs)

    champs = l.liste(bloc, "etat", "champs") if bloc else []
    if any(not isinstance(v, str) or not v.strip() for v in champs):
        l.faute("etat.champs", "attendu : des textes non vides")
        champs = []
    return Etat(**statuts, champs=tuple(str(v) for v in champs))
