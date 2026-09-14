"""Le brouillon — appliquer une proposition sur une copie, et la juger.

La vérification ne s'écrit nulle part dans le harness réel : la proposition est
appliquée à une **copie** du dossier, qui est ensuite chargée et forgée comme
n'importe quel harness. Les lints qui gardent la forge gardent donc la
conception, sans qu'aucun d'eux ait à être redit ici.

C'est ce qui rend le verdict crédible : ce n'est pas un contrôle de formulaire,
c'est la trempe elle-même, sur la définition qu'on s'apprête à sceller.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import yaml

from ..forge import ForgeImpossible
from ..forge.coupe import charger_registre, forger
from ..hds import ManifestInvalide, charger
from ..trempe.statique import verifier
from .modele import Changement, Proposition, Verdict

__all__ = ["appliquer", "juger"]

# Les clés d'un kata qui portent son contrat. Les toucher est un changement de
# version majeure (RFC-002 §3) — le reste ne l'est pas.
CONTRAT = ("herite", "produit", "amont")


def _entree(kata: list[dict], id_kata: str) -> dict | None:
    return next((k for k in kata if str(k.get("id")) == id_kata), None)


SEMENCE_KATA = Path(__file__).resolve().parents[1] / "semence" / "kata" / "premiere-etape.yaml"


def source_neuve() -> dict:
    """Les variables qu'un kata neuf doit porter pour que sa coupe se forge.

    Sans elles, la forge s'arrête sur « variable(s) du template sans valeur » :
    un kata déclaré au manifest mais sans source ne produit rien. On sème donc
    la même page à remplir que la semence — « à écrire » partout, et une coupe
    qui tient dès le premier instant.
    """
    return yaml.safe_load(SEMENCE_KATA.read_text(encoding="utf-8")) or {}


def a_declarer_au_registre(manifest: dict, registre: dict) -> dict:
    """Ce qu'un manifest nomme et que le registre ignore encore — RFC-006.

    Le registre est la liste des noms que ce harness s'autorise à citer, et la
    trempe s'en sert pour refuser une coupe qui parlerait d'autre chose. Un kata
    qui arrive avec un `produit` neuf nomme donc un champ que rien ne déclare —
    et le verdict accuse le kata au lieu de dire qu'il manque une ligne.

    Trois sections suivent le manifest : le nom du kata, son livrable, et les
    champs qu'il s'engage à établir. Une seule oubliée fait refuser la coupe.

    On rend ce qui manque plutôt que de l'ajouter ici : c'est à l'appelant
    d'écrire, et une lecture ne doit pas modifier un registre.
    """
    kata_connus = set(registre.get("kata") or {})
    livrables = list(registre.get("livrables") or [])
    champs_connus = set(registre.get("champs") or {})
    manque: dict = {"kata": {}, "livrables": [], "champs": {}}

    for kata in manifest.get("kata") or []:
        identifiant = str(kata.get("id") or "")
        if identifiant and identifiant not in kata_connus:
            manque["kata"][identifiant] = kata.get("nom") or identifiant
        livrable = kata.get("livrable")
        if livrable and livrable not in livrables and livrable not in manque["livrables"]:
            manque["livrables"].append(livrable)
        for engagement in kata.get("produit") or []:
            if not isinstance(engagement, dict):
                continue
            for reference in engagement:
                nu = str(reference).split(".", 1)[-1]
                if nu not in champs_connus:
                    manque["champs"][nu] = "À décrire — ce que ce champ établit."
    return manque


def _poser_au_registre(registre: dict, manque: dict) -> bool:
    """Écrit au registre ce qui lui manque. Rend `True` si quelque chose a bougé.

    On n'écrit que ce qui manque : réécrire une section intacte emporterait ses
    commentaires sans rien changer d'autre.
    """
    bouge = False
    if manque["kata"]:
        if not isinstance(registre.get("kata"), dict):
            registre["kata"] = {}
        registre["kata"].update(manque["kata"])
        bouge = True
    if manque["livrables"]:
        registre["livrables"] = list(registre.get("livrables") or []) + manque["livrables"]
        bouge = True
    if manque["champs"]:
        if not isinstance(registre.get("champs"), dict):
            registre["champs"] = {}
        registre["champs"].update(manque["champs"])
        bouge = True
    return bouge


def appliquer(manifest: dict, proposition: Proposition, copier: bool = True) -> dict:
    """Le manifest tel qu'il serait après la proposition. Ne touche rien sur disque.

    Une proposition est partielle : un kata déjà présent est **fusionné** clé à
    clé, jamais remplacé. Remplacer effacerait silencieusement ce que le
    formulaire n'a pas renvoyé.

    `copier=False` applique **sur le document reçu**, sans le recopier. C'est ce
    qui permet à un scellement de travailler sur un manifest chargé en
    aller-retour, commentaires compris : recopier par YAML les effacerait tous,
    et un manifest est une source — ses raisons sont écrites à côté de ses
    décisions, et les perdre au premier scellement serait les perdre pour de
    bon. `juger` garde la copie : il compare l'avant et l'après.

    Rien n'est réassigné qui n'a pas bougé, pour la même raison : remplacer une
    section inchangée emporterait ses commentaires sans rien changer d'autre.
    """
    apres = yaml.safe_load(yaml.safe_dump(manifest)) or {} if copier else manifest
    avant_kata = list(apres.get("kata") or [])
    liste = list(avant_kata)
    connus = {str(k.get("id")) for k in avant_kata}
    arrivants: list[dict] = []

    for propose in proposition.kata:
        id_kata = str(propose.get("id") or "").strip()
        if not id_kata:
            raise ValueError("un kata proposé sans `id`")
        existant = _entree(liste, id_kata)
        if existant is None:
            entree = dict(propose)
            # Une source par défaut, pour que le kata neuf pointe quelque part.
            entree.setdefault("source", f"kata/{id_kata}.yaml")
            liste.append(entree)
            if id_kata not in connus:
                arrivants.append(entree)
        else:
            existant.update(propose)

    if proposition.retirer:
        partants = set(proposition.retirer)
        liste = [k for k in liste if str(k.get("id")) not in partants]
        # Un kata retiré ne laisse ni arête ni amont derrière lui : une chaîne
        # qui pointe vers un absent est une chaîne fausse, et le lint le dirait
        # — autant ne pas la produire.
        for k in liste:
            k["amont"] = [a for a in (k.get("amont") or []) if a not in partants]
            k["herite"] = [
                h for h in (k.get("herite") or [])
                if str(next(iter(h)) if isinstance(h, dict) else h).split(".")[0] not in partants
            ]
        chaine = apres.get("chaine") or {}
        chaine["noeuds"] = [n for n in (chaine.get("noeuds") or []) if n.get("id") not in partants]
        chaine["aretes"] = [
            a for a in (chaine.get("aretes") or [])
            if a.get("de") not in partants and a.get("vers") not in partants
        ]
        apres["chaine"] = chaine

    # Un kata qui arrive **entre dans la chaîne**, comme un kata retiré en sort.
    # Sans ça, le manifest déclare une étape que la topologie ignore, et le lint
    # le dit — autant ne pas produire une chaîne fausse.
    if arrivants:
        chaine = apres.get("chaine")
        if not isinstance(chaine, dict):
            chaine = {}
            apres["chaine"] = chaine
        noeuds = list(chaine.get("noeuds") or [])
        aretes = list(chaine.get("aretes") or [])
        deja = {str(n.get("id")) for n in noeuds}
        for entree in arrivants:
            id_kata = str(entree.get("id"))
            if id_kata not in deja:
                noeuds.append({"id": id_kata, "type": "kata", "nom": entree.get("nom") or id_kata})
            for amont in entree.get("amont") or []:
                if not any(a.get("de") == amont and a.get("vers") == id_kata for a in aretes):
                    aretes.append({"de": amont, "vers": id_kata, "label": "à décrire"})
        chaine["noeuds"], chaine["aretes"] = noeuds, aretes

    # Les entrées existantes ont été fusionnées en place : la liste n'est
    # réécrite que si sa composition a changé.
    if liste != avant_kata:
        apres["kata"] = liste
    for section, propose in (("chaine", proposition.chaine), ("trempe", proposition.trempe)):
        if not propose:
            continue
        courant = apres.get(section)
        if isinstance(courant, dict):
            courant.update(propose)
        else:
            apres[section] = dict(propose)
    return apres


def chemin_du_template(manifest: dict) -> str:
    """Le fichier que le manifest désigne comme gabarit — `template.md` sans lui."""
    return str(manifest.get("template") or "template.md")


def _changements(
    avant: dict, apres: dict, proposition: Proposition, template_avant: str | None = None
) -> list[Changement]:
    """Ce qui a bougé, nommé assez précisément pour être relu."""
    trouves: list[Changement] = []

    # Le gabarit ne se diffe pas ligne à ligne ici : il est long, et ce qui
    # compte pour la relecture est qu'il a bougé — la coupe rendue montre le
    # reste (RFC-010 D10.3). Un gabarit renvoyé identique n'est pas un changement.
    if proposition.template is not None and proposition.template != template_avant:
        trouves.append(Changement("template", "…", "…"))

    ids_avant = [str(k.get("id")) for k in (avant.get("kata") or [])]
    ids_apres = [str(k.get("id")) for k in (apres.get("kata") or [])]
    for id_kata in ids_apres:
        if id_kata not in ids_avant:
            trouves.append(Changement("chaine.kata", "absent", id_kata, touche_contrat=True))
    for id_kata in ids_avant:
        if id_kata not in ids_apres:
            trouves.append(Changement("chaine.kata", id_kata, "retiré", touche_contrat=True))

    for id_kata in ids_apres:
        a, b = _entree(avant.get("kata") or [], id_kata), _entree(apres.get("kata") or [], id_kata)
        if a is None or b is None:
            continue
        for cle in sorted(set(a) | set(b)):
            if a.get(cle) == b.get(cle):
                continue
            trouves.append(
                Changement(
                    f"kata.{id_kata}.{cle}",
                    yaml.safe_dump(a.get(cle), default_flow_style=True).strip(),
                    yaml.safe_dump(b.get(cle), default_flow_style=True).strip(),
                    touche_contrat=cle in CONTRAT,
                )
            )

    for cle in sorted(set(avant.get("trempe") or {}) | set(apres.get("trempe") or {})):
        a, b = (avant.get("trempe") or {}).get(cle), (apres.get("trempe") or {}).get(cle)
        if a != b:
            trouves.append(
                Changement(
                    f"trempe.{cle}",
                    yaml.safe_dump(a, default_flow_style=True).strip(),
                    yaml.safe_dump(b, default_flow_style=True).strip(),
                )
            )

    for id_kata, variables in proposition.source.items():
        for cle in sorted(variables):
            trouves.append(Changement(f"source.{id_kata}.{cle}", "…", "…"))
    return trouves


def juger(racine: Path, proposition: Proposition) -> Verdict:
    """Applique la proposition sur une copie, charge, forge, trempe, rend le verdict.

    Rien n'est écrit dans `racine`. Les corpus ne sont pas copiés — ils peuvent
    peser lourd et la conception ne les regarde pas.
    """
    racine = Path(racine)
    avant = yaml.safe_load((racine / "harness.yaml").read_text(encoding="utf-8")) or {}
    apres = appliquer(avant, proposition)

    # Un harness adopté n'a ni gabarit ni densho : ses kata sont des textes
    # servis tels quels (RFC-008). Y écrire l'un ou l'autre lui inventerait une
    # forme qu'il n'a pas — c'est le geste du RFC-011, pas de celui-ci.
    if bool((apres.get("harness") or {}).get("exogene")) and proposition.touche_le_texte:
        return Verdict(
            fautes=(
                (
                    "un harness adopté n'a ni gabarit ni densho : rien à écrire par cet axe "
                    "(RFC-010 D10.4)"
                ),
            ),
            changements=tuple(_changements(avant, apres, proposition)),
        )

    fichier_template = racine / chemin_du_template(apres)
    template_avant = (
        fichier_template.read_text(encoding="utf-8") if fichier_template.is_file() else None
    )
    changements = tuple(_changements(avant, apres, proposition, template_avant))

    with tempfile.TemporaryDirectory() as tmp:
        copie = Path(tmp) / racine.name
        shutil.copytree(racine, copie, ignore=shutil.ignore_patterns("CAS-*"))
        (copie / "harness.yaml").write_text(
            yaml.safe_dump(apres, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        if proposition.template is not None:
            (copie / chemin_du_template(apres)).write_text(proposition.template, encoding="utf-8")
        # Un kata neuf n'a pas de source : on la sème, sinon la forge s'arrête
        # sur une variable sans valeur et le verdict accuse le kata au lieu de
        # dire qu'il lui manque une page à remplir.
        neufs = {
            str(k.get("id"))
            for k in (apres.get("kata") or [])
            if not (copie / "kata" / f"{k.get('id')}.yaml").is_file()
        }
        # Le registre suit : un champ nommé par un kata neuf doit y être déclaré,
        # sinon la trempe refuse une coupe qui cite un nom qu'elle ne connaît pas.
        fichier_registre = copie / str(apres.get("trempe", {}).get("registre") or "registre.yaml")
        if fichier_registre.is_file():
            registre = yaml.safe_load(fichier_registre.read_text(encoding="utf-8")) or {}
            if _poser_au_registre(registre, a_declarer_au_registre(apres, registre)):
                fichier_registre.write_text(
                    yaml.safe_dump(registre, allow_unicode=True, sort_keys=False),
                    encoding="utf-8",
                )

        for id_kata in sorted(neufs | set(proposition.source)):
            variables = proposition.source.get(id_kata) or {}
            fichier = copie / "kata" / f"{id_kata}.yaml"
            source = (
                yaml.safe_load(fichier.read_text(encoding="utf-8")) or {}
                if fichier.is_file()
                else source_neuve()
            )
            source.update(variables)
            fichier.parent.mkdir(parents=True, exist_ok=True)
            fichier.write_text(
                yaml.safe_dump(source, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )

        try:
            harness = charger(copie)
        except ManifestInvalide as err:
            return Verdict(
                fautes=tuple(str(f) for f in err.fautes), changements=changements
            )

        try:
            template = harness.template.read_text(encoding="utf-8")
            registre = charger_registre(harness.trempe.registre)
            coupes = [
                forger(harness, kata, cible, template, registre)
                for cible in harness.cibles
                for kata in harness.kata
            ]
        except ForgeImpossible as err:
            # Assembler est déjà un test : un template dont une variable n'a pas
            # de valeur ne produit pas une coupe fautive, il ne produit rien.
            return Verdict(fautes=(str(err),), changements=changements)

        # La trempe statique ne s'applique qu'à ce que la forge assemble : sur
        # un harness adopté, elle jugerait des règles de plein citoyen (registre
        # canonique, contrat complet) que l'échelle d'adoption n'exige qu'à N4 —
        # et refuserait précisément le geste qui fait avancer vers N3 (RFC-008
        # §3). La forge l'écarte déjà pour la même raison ; l'épreuve suit.
        return Verdict(
            anomalies=()
            if harness.exogene
            else tuple(str(a) for a in verifier(harness, coupes, registre)),
            changements=changements,
        )
