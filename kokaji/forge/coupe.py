"""Résolution d'un kata en coupe, pour une cible (SPECS §4).

Une coupe est l'incarnation d'un kata : le template commun du harness, ses
`{{ variables }}` remplacées par les valeurs du kata et le profil de la cible.

Le rendu est **déterministe** : aucune horodate, aucun aléa, aucun parcours de
dictionnaire non ordonné. Deux forges successives sur une source inchangée
produisent des octets identiques — c'est ce qui permet d'attribuer un écart
mesuré à la forme ou à son incarnation (§1.1).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from ..hds import Cible, Harness, Kata

VARIABLE = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


class ForgeImpossible(Exception):
    """Le kata ne peut pas être incarné : il manque de quoi résoudre le template."""


@dataclass(frozen=True)
class Estampille:
    """Ce qui identifie une coupe (R4.3). Sérialisée à côté d'elle."""

    harness: str
    kata: str
    version_kata: str
    version_coupe: str
    cible: str

    def as_dict(self) -> dict:
        return {
            "harness": self.harness,
            "kata": self.kata,
            "version_kata": self.version_kata,
            "version_coupe": self.version_coupe,
            "cible": self.cible,
        }


@dataclass(frozen=True)
class Coupe:
    kata: str
    cible: str
    texte: str
    estampille: Estampille


def _puces(valeurs) -> str:
    return "\n".join(f"- {str(v).strip()}" for v in valeurs)


def _numerotees(valeurs) -> str:
    return "\n".join(f"{rang}. {str(v).strip()}" for rang, v in enumerate(valeurs, 1))


def _bloc_heritage(harness: Harness, kata: Kata, champs: dict) -> str:
    """La section qui dit au kata ce que l'amont a déjà établi."""
    if not kata.amont:
        return ""

    noms_amont = []
    for id_amont in kata.amont:
        amont = harness.kata_par_id(id_amont)
        noms_amont.append(amont.nom if amont else id_amont)

    lignes = []
    for reference in kata.herite:
        champ = champ_nu(reference)
        description = champs.get(champ)
        if not description:
            raise ForgeImpossible(
                f"{kata.id} : champ hérité absent du registre — {reference!r}"
            )
        lignes.append(f"- **{champ}** — {description}")

    return (
        "## Ce que tu reçois de l'amont\n\n"
        f"L'étape précédente — {', '.join(noms_amont)} — a établi :\n\n"
        f"{chr(10).join(lignes)}\n\n"
        "Tu pars de là. Tu ne redemandes pas ce qui est établi ; si un point te\n"
        "paraît fragile, tu le signales sans le rouvrir d'office."
    )


CONFIANCES = ("faible", "moyen", "eleve")

# RFC-001 : les statuts d'option appartiennent à Kokaji, comme les confiances.
# Un harness choisit quels kata en émettent, pas ce qu'ils peuvent valoir.
STATUTS_OPTION = ("ouverte", "engagee", "ecartee")


def champ_nu(reference: str) -> str:
    """`<kata>.<champ>` → `<champ>` — la forme que porte le bloc d'état."""
    return reference.split(".", 1)[-1]


def champs_du_kata(harness: Harness, kata: Kata, source: dict, registre: dict) -> tuple[str, ...]:
    """Les champs dont ce kata rend compte : ceux hérités, puis ceux qu'il produit.

    Une seule source de vérité : le contrat f♯ du manifest (RFC-002 §3). La clé
    `champs:` de la source du kata décrivait la même chose à un second endroit —
    elle est refusée pour que les deux ne divergent jamais.
    """
    if "champs" in source:
        raise ForgeImpossible(
            f"{kata.id} : `champs` dans {kata.source.name} — remplacé par `produit:` "
            "au manifest (RFC-002 §3)"
        )

    # RFC-008 §4 (amendé) : un exogène sans contrat tire ses champs du
    # manifest — le registre est encore vide, il n'y a rien à croiser. Le
    # manifest garantit déjà que les deux sources ne coexistent pas.
    if harness.exogene and not kata.produit and not kata.herite:
        return tuple(harness.etat.champs)

    connus = registre.get("champs") or {}
    champs: list[str] = []
    for reference in (*kata.herite, *(r for r, _ in kata.produit)):
        champ = champ_nu(reference)
        if champ not in connus:
            raise ForgeImpossible(f"{kata.id} : champ absent du registre — {reference!r}")
        if champ not in champs:
            champs.append(champ)
    return tuple(champs)


def _suivants(harness: Harness, kata: Kata) -> tuple[str, ...]:
    """Les nœuds que la chaîne place immédiatement après ce kata."""
    return tuple(a.vers for a in harness.chaine.aretes if a.de == kata.id)


def _natures(source: dict) -> tuple[str, ...]:
    """Les natures que ce kata sait distinguer, telles que le harness les nomme.

    Kokaji ne connaît pas cette liste et n'a pas à la connaître : elle vit dans
    la source du kata, comme toute la matière de domaine. Un kata qui n'en
    déclare aucune n'a simplement pas de clé `nature` — la mécanique est un
    pattern de template, pas une structure de manifest.
    """
    declarees = source.get("natures") or []
    if isinstance(declarees, str) or not isinstance(declarees, list | tuple):
        raise ForgeImpossible("`natures:` doit être une liste de valeurs")
    return tuple(str(n).strip() for n in declarees if str(n).strip())


def _valeurs_admises(intitule: str, valeurs, porte: str = "") -> str:
    """Un marqueur, ce qu'il gouverne, et ses valeurs.

    Nommer ce que le marqueur gouverne n'est pas décoratif : les taxonomies se
    recouvrent partiellement — le défaut de Kokaji met `en_pause` dans celle des
    champs comme dans celle des hypothèses — et une liste sans son point
    d'application se lit comme un vivier commun où puiser.
    """
    tete = (
        f"`{intitule}` — il gouverne {porte}, et rien d'autre.\nIl vaut exactement "
        "l'une de ces valeurs :"
        if porte
        else f"`{intitule}` vaut exactement l'une de ces valeurs :"
    )
    return tete + "\n" + "\n".join(f"- `{v}`" for v in valeurs)


def _declencheurs(kata: Kata) -> str:
    """Quand le bloc s'émet — énuméré, pas laissé à l'appréciation.

    « À chaque point d'étape » se lit comme une intention : le kata atteint des
    points d'étape, les signale en prose, et n'émet rien. Les cas sont donc
    listés, et la place du bloc dans la réponse est imposée — une consigne de
    position se tient, une consigne d'opportunité se perd.
    """
    cas = [
        "tu récapitules ce qui est établi",
        "tu demandes confirmation d'une section du livrable",
        "un champ change de statut",
        "tu rends le livrable",
        "tu déclares le passage vers l'étape suivante",
    ]
    if kata.emet_options:
        cas += [
            "une possibilité est nommée, engagée ou écartée",
            "une décision referme ou ouvre des possibles",
        ]

    return (
        "Tu émets ce bloc **en tête de ta réponse**, avant toute prose, dans\n"
        "chacun de ces cas :\n\n"
        + "\n".join(f"- {c} ;" for c in cas[:-1])
        + f"\n- {cas[-1]}.\n\n"
        "Hors de ces cas, tu n'émets rien. Le bloc précède ta réponse : il ne la\n"
        "remplace pas, ne la résume pas, et tu ne le commentes jamais."
    )


def _gabarit_options(kata: Kata) -> str:
    """Les deux sections facultatives de RFC-001, pour les kata qui en émettent."""
    if not kata.emet_options:
        return ""
    return (
        '    "options": [\n'
        '      { "id": "OPT-1", "libelle": "", "noeud": "<noeud>",'
        ' "statut": "<statut_option>" }\n'
        "    ],\n"
        '    "decision": { "libelle": "", "ferme": ["OPT-2"], "ouvre": ["OPT-4"] },\n'
    )


def _consignes_options(harness: Harness, kata: Kata) -> str:
    """Ce qui encadre les options — y compris ce qui les protège de Goodhart.

    La vigilance #8 du carnet est inscrite dans la coupe elle-même : sans quoi
    elle ne vit que dans la documentation, et le kata invente des options pour
    remplir un tableau que personne ne lui a demandé de remplir.
    """
    if not kata.emet_options:
        return ""

    noeuds = ", ".join(f"`{n.id}`" for n in harness.chaine.noeuds)
    return (
        "\n\n"
        "Une **option** est une possibilité que ton interlocuteur a nommée sans\n"
        "s'y engager. Tu ne la comptes pas, tu la nommes : une option n'existe que\n"
        "si elle a été articulée en clair pendant l'échange. **Tu n'as aucun quota**\n"
        "— ni minimum, ni cible. Ne jamais en inventer pour étoffer la liste.\n\n"
        "`decision` n'apparaît que le tour où une coupe est réellement opérée : un\n"
        "choix de périmètre, de piste, de prochain pas. `ferme` et `ouvre` ne citent\n"
        "que des identifiants d'options déjà déclarées. Les autres tours n'ont pas\n"
        "de `decision`.\n\n"
        f"{_valeurs_admises('<statut_option>', STATUTS_OPTION, 'la clé `statut` des entrées de `options`')}\n\n"
        f"`<noeud>` désigne une étape de la chaîne : {noeuds}."
    )


def _bloc_etat(
    harness: Harness, kata: Kata, cible: Cible, champs: tuple[str, ...], natures: tuple[str, ...] = ()
) -> str:
    """R4.2 — n'existe que pour les cibles qui le demandent.

    Les autres cibles n'en portent aucune trace : la variable est résolue par du
    vide, et la normalisation efface jusqu'à la ligne.

    Les listes sont **fermées** : le gabarit ne montre que des marqueurs, et les
    valeurs admises sont énumérées à part. Une énumération glissée dans le
    gabarit lui-même se lit comme un exemple à compléter, pas comme une
    contrainte — et le modèle invente alors ses propres statuts.
    """
    if not cible.etat_structure:
        return ""

    if champs:
        gabarit_champs = (
            "    \"champs\": {\n"
            + ",\n".join(f'      "{c}": "<statut_champ>"' for c in champs)
            + "\n    },\n"
        )
    else:
        gabarit_champs = '    "champs": {},\n'
    suivants = _suivants(harness, kata)
    admis_pret = ", ".join(f"`{s}`" for s in suivants) if suivants else "aucune"

    # Le kata déclare-t-il des natures ? Kokaji n'en connaît aucune : il ferme la
    # liste que le harness lui donne, transporte la valeur, et n'en interprète
    # jamais le sens. Sans déclaration, la clé n'existe pas dans le gabarit.
    gabarit_nature = (
        '    "nature": { "valeur": "<nature>", "confiance": "<confiance>",'
        ' "revisee_le": "" },\n'
        if natures
        else ""
    )
    # `<confiance>` gouverne deux endroits dès que `nature` existe. Lui laisser
    # dire « et rien d'autre » ferait mentir le texte à côté du gabarit qui
    # l'emploie ailleurs — et un texte qui se contredit se résout au hasard.
    porte_confiance = "la clé `confiance` des entrées de `hypotheses`"
    if natures:
        porte_confiance += " **et** celle de `nature`"

    consignes_nature = (
        "\n\n`nature` est renseignée **dès ton premier bloc**, et révisée dès que\n"
        "ce que tu apprends la change. `revisee_le` nomme l'étape où tu l'as\n"
        "posée ou changée. Une nature qu'on n'a pas encore su lire se déclare,\n"
        "elle ne se devine pas."
        if natures
        else ""
    )

    # Toutes les listes fermées, d'affilée. Une seule exilée plus bas se lit
    # comme un ajout facultatif, et ses valeurs se mettent à circuler ailleurs.
    enumerations = [
        _valeurs_admises("<statut_champ>", harness.etat.statuts_champ, "les entrées de `champs`"),
        _valeurs_admises(
            "<statut_hypothese>",
            harness.etat.statuts_hypothese,
            "la clé `statut` des entrées de `hypotheses`",
        ),
        _valeurs_admises("<confiance>", CONFIANCES, porte_confiance),
    ]
    if natures:
        enumerations.append(
            _valeurs_admises("<nature>", natures, "la clé `valeur` de `nature`")
        )
    admises = "\n\n".join(enumerations)

    return (
        "## Le bloc d'état\n\n"
        f"{_declencheurs(kata)}\n\n"
        "```json kokaji_state\n"
        "{\n"
        '  "kokaji_state": {\n'
        f'    "harness": "{harness.id}", "kata": "{kata.id}", "version": "{harness.version}",\n'
        '    "sujet": "", "objet": "", "etape": "",\n'
        f"{gabarit_champs}"
        '    "hypotheses": [\n'
        '      { "id": "", "libelle": "", "statut": "<statut_hypothese>",'
        ' "confiance": "<confiance>" }\n'
        "    ],\n"
        f"{_gabarit_options(kata)}"
        f"{gabarit_nature}"
        '    "pret_pour": null\n'
        "  }\n"
        "}\n"
        "```\n\n"
        "Les clés de `champs` sont exactement celles du gabarit : tu n'en ajoutes\n"
        "aucune, tu n'en retires aucune, tu n'en renommes aucune.\n\n"
        "Chaque marqueur a sa propre liste. Ces listes sont **étanches** : une\n"
        "valeur admise pour l'un n'est jamais valable pour un autre, même si elle\n"
        "y ressemble ou qu'elle apparaît dans les deux.\n\n"
        "Ce que gouverne un marqueur est écrit avec lui. **Ne prends jamais une\n"
        "valeur dans la liste d'un autre marqueur**, même quand aucune de la\n"
        "bonne liste ne te satisfait : ces listes décrivent des choses de nature\n"
        "différente, et une valeur empruntée n'y veut rien dire.\n\n"
        f"{admises}\n\n"
        "Aucune variante, aucun raccourci, aucune nuance intermédiaire : si un\n"
        "statut ne convient pas exactement, tu prends le plus proche et tu le dis\n"
        "en clair dans ta réponse, hors du bloc.\n\n"
        f"`pret_pour` vaut `null` tant que le passage n'est pas atteint. Une fois\n"
        f"atteint, il vaut l'étape suivante : {admis_pret}."
        f"{_consignes_options(harness, kata)}"
        f"{consignes_nature}\n\n"
        "Un bloc mal formé n'interrompt jamais l'échange : tu poursuis."
    )


def _normaliser(texte: str) -> str:
    """Efface les cicatrices des variables vides et fige la mise en forme."""
    texte = "\n".join(ligne.rstrip() for ligne in texte.split("\n"))
    texte = re.sub(r"\n{3,}", "\n\n", texte)
    return texte.strip() + "\n"


def forger(harness: Harness, kata: Kata, cible: Cible, template: str, registre: dict) -> Coupe:
    if harness.exogene:
        return _forger_orpheline(harness, kata, cible)
    source = yaml.safe_load(kata.source.read_text(encoding="utf-8")) or {}
    if not isinstance(source, dict):
        raise ForgeImpossible(f"{kata.id} : {kata.source.name} ne décrit pas une section")

    champs = registre.get("champs") or {}
    champs_kata = champs_du_kata(harness, kata, source, registre)
    valeurs = {
        "en_tete": cible.en_tete,
        "kata_nom": kata.nom,
        "role": str(source.get("role") or "").strip(),
        "interdits": _puces(source.get("interdits") or []),
        "questions": _numerotees(source.get("questions") or []),
        "heritage": _bloc_heritage(harness, kata, champs),
        "livrable_nom": str(source.get("livrable_nom") or kata.livrable).strip(),
        "livrable_structure": _puces(source.get("livrable_structure") or []),
        "etat": _bloc_etat(harness, kata, cible, champs_kata, _natures(source)),
        "passage": str(source.get("passage") or "").strip(),
    }

    attendues = set(VARIABLE.findall(template))
    manquantes = sorted(attendues - set(valeurs))
    if manquantes:
        raise ForgeImpossible(
            f"{kata.id} : variable(s) du template sans valeur — {', '.join(manquantes)}"
        )

    obligatoires = ("role", "questions", "livrable_structure", "passage")
    vides = [v for v in obligatoires if v in attendues and not valeurs[v]]
    if vides:
        raise ForgeImpossible(f"{kata.id} : variable(s) vide(s) — {', '.join(vides)}")

    texte = _normaliser(VARIABLE.sub(lambda m: valeurs[m.group(1)], template))

    # La version de coupe est l'empreinte de tout ce qui l'a produite : elle
    # change si le template ou la cible bougent, même à kata inchangé.
    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()[:12]
    estampille = Estampille(
        harness=harness.id,
        kata=kata.id,
        version_kata=str(source.get("version") or harness.version),
        version_coupe=empreinte,
        cible=cible.id,
    )
    marque = (
        f"\n<!-- {estampille.harness}/{estampille.kata} "
        f"kata {estampille.version_kata} · coupe {estampille.version_coupe} "
        f"· cible {estampille.cible} -->\n"
    )
    return Coupe(kata=kata.id, cible=cible.id, texte=texte + marque, estampille=estampille)


def _forger_orpheline(harness: Harness, kata: Kata, cible: Cible) -> Coupe:
    """La coupe d'un kata exogène : le texte importé, tel quel — RFC-008 §5.

    Rien n'est assemblé : la forme source n'existe pas, c'est la définition
    d'une coupe orpheline. Le template et le registre du harness ne sont pas
    consultés — les toucher serait réécrire un texte dont la promesse est
    précisément qu'il n'est pas réécrit. Seule l'estampille s'ajoute : sans
    elle, ni la passerelle ni la capture ne sauraient dire ce qui a servi.
    """
    texte = kata.source.read_text(encoding="utf-8").strip() + "\n"

    # N2 — la coupe instrumentée s'obtient par enrichissement : le texte n'est
    # pas réécrit, l'instruction d'émission s'ajoute (RFC-008 §6). Le bloc est
    # celui de la forge ordinaire, adossé aux champs du manifest : deux harness
    # instrumentés parlent la même langue, natif ou adopté.
    if cible.etat_structure:
        champs = champs_du_kata(harness, kata, {}, {})
        if not champs:
            raise ForgeImpossible(
                f"{kata.id} : cible `{cible.id}` sans vocabulaire de champs — "
                "déclare `etat.champs` au manifest, on n'invente jamais de champs "
                "(RFC-008 §6)"
            )
        texte += "\n" + _bloc_etat(harness, kata, cible, champs).strip() + "\n"

    empreinte = hashlib.sha256(texte.encode("utf-8")).hexdigest()[:12]
    estampille = Estampille(
        harness=harness.id,
        kata=kata.id,
        version_kata=harness.version,
        version_coupe=empreinte,
        cible=cible.id,
    )
    marque = (
        f"\n<!-- {estampille.harness}/{estampille.kata} "
        f"kata {estampille.version_kata} · coupe {estampille.version_coupe} "
        f"· cible {estampille.cible} -->\n"
    )
    return Coupe(kata=kata.id, cible=cible.id, texte=texte + marque, estampille=estampille)


def charger_registre(chemin: Path) -> dict:
    donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    if not isinstance(donnees, dict):
        raise ForgeImpossible(f"{chemin.name} ne décrit pas une section")
    return donnees
