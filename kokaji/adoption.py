"""Adopter un harness né hors de la forge — RFC-008, niveau N0.

Des harness existent avant Kokaji : des prompts faits main, joués en
copier-coller. L'adoption les fait entrer **tels quels** — chaque prompt
devient un kata dont la source est le texte lui-même, servi par la cible
`nue` qui ne demande aucun bloc d'état. Tout ce qui sait servir un kata sait
alors les servir : forge passe-plat, passerelle, chat, capture (§4, amendé).

Deux engagements, pris au même endroit :

- **La provenance s'estampille une fois.** L'import est une migration, pas une
  consignation : le harness devient éditable, propriété de l'importeur. En
  échange, l'empreinte des textes importés est écrite au manifest — on saura
  toujours d'où c'est parti et si ça a divergé, sans rien figer (§5).
- **Tout se lit avant que rien ne s'écrive.** Un fichier absent refuse
  l'import entier, et un import refusé ne laisse pas de dossier à moitié né —
  la règle de la naissance (RFC-006 §7.5), reprise ici : on charge ce qu'on
  vient d'écrire, et si ça ne tient pas, on retire.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from .hds import Harness, charger
from .yaml_source import charger_source, ecrire_source

__all__ = ["AdoptionRefusee", "adopter_etape", "adopter_textes", "importer"]


class AdoptionRefusee(Exception):
    """L'import n'a pas eu lieu, et rien n'a été écrit."""


# Ce que `charger` exige et qu'une coupe orpheline n'apporte pas : le strict
# nécessaire est engendré, vide et nommé comme tel. Le template et le registre
# ne servent à rien tant que la forge est passe-plat — ils existent pour que
# le harness reste un harness ordinaire aux yeux de tout le reste.
TEMPLATE_NEUTRE = "{{ role }}\n"
REGISTRE_NEUTRE = "# Vide à N0 — le vocabulaire de champs arrive à N2 (RFC-008 §6).\nchamps: {}\n"

MANIFEST = """\
# Harness adopté — RFC-008 N0. La définition est éditable ; la provenance, non.
harness:
  id: {id}
  nom: {nom}
  version: 0.1.0
  langue: fr
  domaine: À décrire — le processus que ce harness couvre, en une phrase.
  exogene: true
  provenance:
    source: {source}
    version_source: {version_source}
    checksum_import: {checksum}
    date_import: "{date}"
kata:
{kata}
chaine:
  noeuds:
{noeuds}
  aretes: []
template: template.md
cibles:
  # La seule incarnation de N0 : le texte importé, sans bloc d'état. La cible
  # `instrumentee` n'existe qu'à partir de N2 (RFC-008 §4, amendé).
  - id: nue
    etat_structure: false
    en_tete: {nom}
    packaging: dossier
trempe:
  vocabulaire_interdit: []
  registre: registre.yaml
  checks_session: []
personas: personas/
corpus: corpus/
"""

KATA = """\
  - id: {id}
    nom: {nom}
    source: prompts/{id}.md
    amont: []
    herite: []
    produit: []
"""

NOEUD = """\
    - {{ id: {id}, type: kata, nom: {nom} }}
"""


def _slug(nom: str) -> str:
    propre = re.sub(r"[^a-z0-9]+", "-", nom.lower()).strip("-")
    return propre or "etape"


def _nom_lisible(slug: str) -> str:
    return slug.replace("-", " ").strip().capitalize()


def importer(
    prompts: list[Path],
    vers: Path,
    identifiant: str,
    nom: str,
    source: str = "manuel",
    version_source: str = "",
) -> Harness:
    """Fait entrer des fichiers, dans l'ordre donné — un kata chacun.

    Tout se lit d'abord : un fichier absent refuse l'import entier.
    """
    textes: dict[str, str] = {}
    for chemin in prompts:
        chemin = Path(chemin)
        if not chemin.is_file():
            raise AdoptionRefusee(f"fichier absent : {chemin} — rien n'a été importé")
        texte = chemin.read_text(encoding="utf-8")
        if not texte.strip():
            raise AdoptionRefusee(f"fichier vide : {chemin} — rien n'a été importé")
        slug = _slug(chemin.stem)
        if slug in textes:
            raise AdoptionRefusee(f"deux prompts porteraient le kata {slug!r}")
        textes[slug] = texte
    return adopter_textes(textes, vers, identifiant, nom, source, version_source)


def adopter_textes(
    textes: dict[str, str],
    vers: Path,
    identifiant: str,
    nom: str,
    source: str = "manuel",
    version_source: str = "",
) -> Harness:
    """Le cœur du geste — des textes déjà en main, un kata chacun.

    L'ordre des textes est l'ordre des kata : c'est la seule structure qu'on
    connaisse d'un harness fait main, et on ne l'invente pas plus loin — la
    chaîne reste sans arête tant que l'importeur ne la déclare pas (N1).

    Séparé de `importer` parce que le web n'a pas de fichiers : la page envoie
    des textes, la commande envoie des chemins, et les deux passent ici.
    """
    textes = {_slug(cle): texte for cle, texte in textes.items()}
    if not textes or any(not t.strip() for t in textes.values()):
        raise AdoptionRefusee("chaque texte doit être non vide — rien n'a été importé")

    dossier = Path(vers) / identifiant
    if dossier.exists():
        raise AdoptionRefusee(f"le dossier existe déjà : {dossier}")

    # 2 · l'empreinte porte sur les textes tels qu'importés, dans un ordre
    # stable : le même import redonne le même checksum, quel que soit l'ordre
    # des arguments.
    empreinte = hashlib.sha256()
    for slug in sorted(textes):
        empreinte.update(slug.encode("utf-8"))
        empreinte.update(textes[slug].encode("utf-8"))

    # 3 · écrire, puis charger la copie — si elle ne tient pas, la retirer.
    try:
        (dossier / "prompts").mkdir(parents=True)
        (dossier / "personas").mkdir()
        (dossier / "corpus").mkdir()
        (dossier / "personas" / ".gardien").write_text("", encoding="utf-8")
        (dossier / "corpus" / ".gardien").write_text("", encoding="utf-8")
        (dossier / "template.md").write_text(TEMPLATE_NEUTRE, encoding="utf-8")
        (dossier / "registre.yaml").write_text(REGISTRE_NEUTRE, encoding="utf-8")
        for slug, texte in textes.items():
            (dossier / "prompts" / f"{slug}.md").write_text(texte, encoding="utf-8")
        (dossier / "harness.yaml").write_text(
            MANIFEST.format(
                id=identifiant,
                nom=nom,
                source=source or "manuel",
                version_source=version_source or '""',
                checksum=empreinte.hexdigest(),
                date=datetime.now(UTC).isoformat(),
                kata="".join(
                    KATA.format(id=slug, nom=_nom_lisible(slug)) for slug in textes
                ),
                noeuds="".join(
                    NOEUD.format(id=slug, nom=_nom_lisible(slug)) for slug in textes
                ),
            ),
            encoding="utf-8",
        )
        return charger(dossier)
    except AdoptionRefusee:
        raise
    except Exception as err:
        shutil.rmtree(dossier, ignore_errors=True)
        raise AdoptionRefusee(f"la copie ne tient pas : {err}") from err


def adopter_etape(racine: Path, nom: str, texte: str) -> Harness:
    """Ajoute un texte fait main comme étape d'un harness adopté **existant**.

    Le premier import crée la forme ; celle-ci grandit ensuite étape par
    étape — le geste est né du premier usage réel : un harness d'une étape,
    et le prompt suivant sans porte pour entrer.

    Réservé aux harness exogènes : dans un harness natif, une étape est une
    source de forge, et elle s'ajoute par le module design. Le manifest est
    réécrit par l'aller-retour qui garde ses commentaires ; le kata entre sans
    contrat ni arête, comme à l'import — la chaîne se déclare, elle ne se
    devine pas (N1).

    La provenance n'est pas retouchée : elle estampille *l'import*, pas l'état
    courant, et le harness est éditable par décision (RFC-008 §5).
    """
    racine = Path(racine)
    harness = charger(racine)
    if not harness.exogene:
        raise AdoptionRefusee(
            f"{harness.id} n'est pas un harness adopté — une étape s'y ajoute "
            "par le module design, avec sa source de forge"
        )
    if not texte.strip():
        raise AdoptionRefusee("le texte est vide — rien n'a été ajouté")
    slug = _slug(nom)
    if harness.kata_par_id(slug) is not None:
        raise AdoptionRefusee(f"l'étape {slug!r} existe déjà dans {harness.id}")
    prompt = racine / "prompts" / f"{slug}.md"
    if prompt.exists():
        raise AdoptionRefusee(f"un texte porte déjà ce nom : {prompt.name}")

    manifest = racine / "harness.yaml"
    avant = manifest.read_text(encoding="utf-8")
    prompt.parent.mkdir(exist_ok=True)
    prompt.write_text(texte, encoding="utf-8")
    try:
        document = charger_source(manifest)
        document["kata"].append({
            "id": slug, "nom": _nom_lisible(slug), "source": f"prompts/{slug}.md",
            "amont": [], "herite": [], "produit": [],
        })
        document["chaine"]["noeuds"].append(
            {"id": slug, "type": "kata", "nom": _nom_lisible(slug)}
        )
        ecrire_source(manifest, document)
        return charger(racine)
    except Exception as err:
        # Rien à moitié : le manifest revient à l'octet près, le texte repart.
        manifest.write_text(avant, encoding="utf-8")
        prompt.unlink(missing_ok=True)
        raise AdoptionRefusee(f"l'étape ne tient pas : {err}") from err
