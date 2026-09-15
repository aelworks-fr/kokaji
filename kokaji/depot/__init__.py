"""Un harness, un dépôt — RFC-012.

Chaque harness est un dépôt git à part entière sur la machine de l'instance :
`git init` à la naissance, un commit à chaque scellement (RFC-010), et un
état qu'on peut lire — propre ou non, dernier commit, avance sur le dernier
point connu du dépôt nu s'il y en a un. Tout ici tient sur la machine : aucune
émission réseau, la souveraineté (RFC-009 D9.4) reste entière.

Ce module ne fusionne jamais : une fusion est un jugement sur deux
définitions, ça se fait dans un éditeur, pas dans un service.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "IGNORES_DU_HARNESS", "DepotIndisponible", "DepotRefuse", "Etat", "chemin_admis", "cloner",
    "est_depot", "est_depot_nu", "etat", "git", "initier", "lier", "poser_les_ignores",
    "pousser", "promouvoir_au_depot", "reference", "tirer",
]


class DepotIndisponible(Exception):
    """git est absent, ou le dossier n'est pas un dépôt."""


def git(depot: Path, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    """Un appel git, sans jamais lever : le code de retour se lit.

    `safe.directory` : le dépôt est monté dans un conteneur qui n'en est pas
    le propriétaire, et git refuserait de le lire sans le dire clairement.
    """
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(depot), *args],
        capture_output=True, text=True, timeout=60, check=False,
        env={**os.environ, **(env or {})},
    )


def _identite(auteur: str = "Kokaji") -> dict:
    """L'identité git du dépôt si elle est réglée, sinon celle qu'on donne —
    pour que le commit existe plutôt que d'échouer sur un réglage absent."""
    return {
        "GIT_AUTHOR_NAME": os.environ.get("GIT_AUTHOR_NAME") or auteur,
        "GIT_AUTHOR_EMAIL": os.environ.get("GIT_AUTHOR_EMAIL") or "scellement@kokaji.local",
        "GIT_COMMITTER_NAME": os.environ.get("GIT_COMMITTER_NAME") or "Kokaji",
        "GIT_COMMITTER_EMAIL": os.environ.get("GIT_COMMITTER_EMAIL") or "scellement@kokaji.local",
    }


def est_depot(racine: Path) -> bool:
    """Ce dossier est-il **lui-même** la racine d'un dépôt — et non un sous-dossier d'un autre ?"""
    if shutil.which("git") is None:
        return False
    haut = git(racine, "rev-parse", "--show-toplevel")
    return haut.returncode == 0 and Path(haut.stdout.strip()).resolve() == Path(racine).resolve()


def initier(racine: Path, message: str, auteur: str = "Kokaji") -> str:
    """Fait du dossier un dépôt, avec un premier commit de tout ce qu'il contient.

    Un harness qui naît est aussitôt un dépôt (RFC-012 D12.1) : le scellement
    a ainsi un historique où commiter dès le premier jour, et l'enregistrement
    d'un dépôt nu, plus tard, n'aura qu'à pousser cet historique. Rend le sha.
    Sans git sur la machine, on le dit — on ne fait pas semblant.
    """
    racine = Path(racine)
    if shutil.which("git") is None:
        raise DepotIndisponible("git est absent : le harness naît sans dépôt")
    if est_depot(racine):
        raise DepotIndisponible(f"{racine.name} est déjà un dépôt")
    poser_les_ignores(racine)
    # La branche est nommée : sans `-b`, git prend `master` ou `main` selon
    # le poste, et le dépôt nu — qui reçoit `main` — ne s'y retrouverait pas.
    for etape in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", message)):
        fait = git(racine, *etape, env=_identite(auteur))
        if fait.returncode != 0:
            raise DepotIndisponible(f"git {etape[0]} a refusé : {fait.stderr.strip()}")
    return git(racine, "rev-parse", "--short", "HEAD").stdout.strip()


# RFC-014 D14.5, lot 0 — la donnée vivante ne se versionne pas : un ha brut
# reste hors du dépôt du harness ; la promotion l'y ajoute de force.
IGNORES_DU_HARNESS = """# Les ha capturés sont de la donnée vivante (RFC-014) : ils n'entrent au dépôt
# que promus — `kokaji promouvoir` les ajoute de force.
corpus/**/CAS-*/
corpus/**/.ecartes.jsonl
corpus/**/jugements.jsonl
"""


def poser_les_ignores(racine: Path) -> bool:
    """Le `.gitignore` d'un harness, s'il n'en a pas. Rend vrai s'il a été écrit."""
    fichier = Path(racine) / ".gitignore"
    if fichier.exists():
        return False
    fichier.write_text(IGNORES_DU_HARNESS, encoding="utf-8")
    return True


def promouvoir_au_depot(racine: Path, dossier_ha: Path) -> bool:
    """Un ha promu entre au dépôt malgré l'ignore — c'est le geste humain qui
    décide qu'il vaut d'être gardé avec la forme (D14.5). Rend vrai si ajouté."""
    racine = Path(racine)
    if not est_depot(racine):
        return False
    relatif = Path(dossier_ha).resolve().relative_to(racine.resolve())
    return git(racine, "add", "-f", "--", str(relatif)).returncode == 0


@dataclass(frozen=True)
class Etat:
    """Ce qu'on sait du dépôt d'un harness, sans rien toucher.

    `avance` compte les commits depuis la référence connue du dépôt nu ; `None`
    quand il n'y a pas de référence, ou qu'elle est inconnue du clone — on ne
    devine pas un retard qu'on n'a pas lu (le lot B tire, et saura).
    """

    est_depot: bool
    propre: bool = True
    branche: str = ""
    dernier_commit: str = ""
    dernier_message: str = ""
    dernier_le: str = ""
    avance: int | None = None
    reference_connue: bool = False

    @property
    def mot(self) -> str:
        """L'état en un mot, celui que le panneau et le badge affichent (D12.5)."""
        if not self.est_depot:
            return "sans dépôt"
        if not self.propre:
            return "modifications non scellées"
        if self.avance is None:
            return "non enregistré" if not self.reference_connue else "à jour"
        return "à jour" if self.avance == 0 else f"en avance de {self.avance}"


def etat(racine: Path, reference: str | None = None) -> Etat:
    """Sans référence donnée, celle du clone lui-même : ce que `origin` a
    de cette branche à la dernière poussée ou tirée. C'est ce qui permet à la
    ligne de commande — qui ne lit pas le magasin — de dire « à jour » plutôt
    que « non enregistré » quand un dépôt nu est bien lié."""
    racine = Path(racine)
    if not est_depot(racine):
        return Etat(est_depot=False)
    propre = git(racine, "status", "--porcelain").stdout.strip() == ""
    branche = git(racine, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if reference is None and git(racine, "remote", "get-url", "origin").returncode == 0:
        distante = git(racine, "rev-parse", "--short", f"refs/remotes/origin/{branche}")
        if distante.returncode == 0:
            reference = distante.stdout.strip()
    dernier = git(racine, "log", "-1", "--format=%h%x1f%s%x1f%cI").stdout.strip().split("\x1f")
    sha, message, quand = (dernier + ["", "", ""])[:3] if dernier != [""] else ("", "", "")
    avance: int | None = None
    connue = False
    if reference:
        connue = git(racine, "cat-file", "-e", f"{reference}^{{commit}}").returncode == 0
        if connue:
            compte = git(racine, "rev-list", "--count", f"{reference}..HEAD").stdout.strip()
            avance = int(compte) if compte.isdigit() else None
    return Etat(
        est_depot=True, propre=propre, branche=branche,
        dernier_commit=sha, dernier_message=message, dernier_le=quand,
        avance=avance, reference_connue=connue,
    )


# --- le dépôt nu et les trois gestes (RFC-012 D12.2, D12.3) ------------------
#
# Un dépôt nu est un chemin de la machine, sous le dossier que le déploiement
# déclare (`KOKAJI_DEPOTS`) : le service n'écrit ni ne clone n'importe où.
# Trois gestes — enregistrer, pousser, tirer — en avance rapide seulement.
# Kokaji ne fusionne jamais : une fusion est un jugement sur deux définitions.


class DepotRefuse(Exception):
    """Un geste sur un dépôt que l'on refuse, et pourquoi — jamais un silence."""


def chemin_admis(chemin: str | Path, racine_depots: Path | str | None) -> Path:
    """Le chemin d'un dépôt nu, s'il est sous le dossier déclaré.

    Un chemin relatif se lit depuis ce dossier ; un chemin absolu doit y être.
    Sans dossier déclaré, aucun dépôt nu n'est admis — et on le dit.
    """
    if not racine_depots:
        raise DepotRefuse(
            "aucun dossier de dépôts déclaré (KOKAJI_DEPOTS) : rien ne peut être enregistré"
        )
    racine = Path(racine_depots).resolve()
    brut = Path(str(chemin).strip())
    if not str(brut):
        raise DepotRefuse("un enregistrement sans chemin n'enregistre rien")
    cible = (brut if brut.is_absolute() else racine / brut).resolve()
    if cible != racine and racine not in cible.parents:
        raise DepotRefuse(f"chemin hors du dossier des dépôts : {chemin}")
    if cible == racine:
        raise DepotRefuse("le dossier des dépôts lui-même n'est pas un dépôt")
    return cible


def est_depot_nu(chemin: Path) -> bool:
    return Path(chemin).is_dir() and git(chemin, "rev-parse", "--is-bare-repository").stdout.strip() == "true"


def reference(chemin_nu: Path, branche: str) -> str:
    """Le dernier commit du dépôt nu sur cette branche — vide s'il n'en a pas."""
    lu = git(chemin_nu, "rev-parse", "--short", f"refs/heads/{branche}")
    return lu.stdout.strip() if lu.returncode == 0 else ""


def lier(racine: Path, chemin_nu: Path, branche: str = "main", auteur: str = "Kokaji") -> str:
    """Enregistre un harness auprès d'un dépôt nu : créé s'il n'existe pas,
    l'historique local y est poussé. Rend le commit de référence.

    Le harness devient un dépôt s'il ne l'est pas encore. Un dépôt nu qui
    porte déjà un autre historique sur cette branche refuse le push : on le
    dit, rien n'est fusionné.
    """
    racine = Path(racine)
    chemin_nu = Path(chemin_nu)
    if shutil.which("git") is None:
        raise DepotRefuse("git est absent")
    if not est_depot(racine):
        initier(racine, f"enregistrement : {racine.name}", auteur)
    if chemin_nu.exists() and not est_depot_nu(chemin_nu):
        raise DepotRefuse(f"{chemin_nu} existe et n'est pas un dépôt nu")
    if not chemin_nu.exists():
        chemin_nu.parent.mkdir(parents=True, exist_ok=True)
        fait = git(chemin_nu.parent, "init", "--bare", "-q", "-b", branche, str(chemin_nu))
        if fait.returncode != 0:
            raise DepotRefuse(f"git init --bare a refusé : {fait.stderr.strip()}")
    git(racine, "remote", "remove", "origin")
    fait = git(racine, "remote", "add", "origin", str(chemin_nu))
    if fait.returncode != 0:
        raise DepotRefuse(f"git remote a refusé : {fait.stderr.strip()}")
    return pousser(racine, branche)


def pousser(racine: Path, branche: str = "main") -> str:
    """Pousse la branche au dépôt nu, en avance rapide. Rend le commit poussé."""
    racine = Path(racine)
    if not est_depot(racine):
        raise DepotRefuse("ce harness n'est pas un dépôt")
    if git(racine, "remote", "get-url", "origin").returncode != 0:
        raise DepotRefuse("aucun dépôt nu enregistré")
    fait = git(racine, "push", "--quiet", "origin", f"HEAD:refs/heads/{branche}")
    if fait.returncode != 0:
        detail = fait.stderr.strip().splitlines()[-1] if fait.stderr.strip() else "refus sans motif"
        if "rejected" in fait.stderr or "non-fast-forward" in fait.stderr or "fetch first" in fait.stderr:
            raise DepotRefuse(
                f"le dépôt nu a avancé de son côté — divergé, et Kokaji ne fusionne jamais ({detail})"
            )
        raise DepotRefuse(f"git push a refusé : {detail[:200]}")
    return git(racine, "rev-parse", "--short", "HEAD").stdout.strip()


def tirer(racine: Path, branche: str = "main") -> str:
    """Tire la branche du dépôt nu, en avance rapide, clone propre exigé.

    Des modifications non scellées ? On refuse, le clone est intact. La
    branche a divergé ? On refuse, jamais de fusion. Rend le commit atteint.
    """
    racine = Path(racine)
    if not est_depot(racine):
        raise DepotRefuse("ce harness n'est pas un dépôt")
    if git(racine, "remote", "get-url", "origin").returncode != 0:
        raise DepotRefuse("aucun dépôt nu enregistré")
    if git(racine, "status", "--porcelain").stdout.strip():
        raise DepotRefuse("des modifications non scellées : tirer les écraserait — scelle d'abord")
    cherche = git(racine, "fetch", "--quiet", "origin", branche)
    if cherche.returncode != 0:
        raise DepotRefuse(f"git fetch a refusé : {cherche.stderr.strip()[:200]}")
    fusion = git(racine, "merge", "--ff-only", "--quiet", "FETCH_HEAD")
    if fusion.returncode != 0:
        raise DepotRefuse("la branche a divergé : Kokaji ne fusionne jamais — réconcilie dans un éditeur")
    return git(racine, "rev-parse", "--short", "HEAD").stdout.strip()


def cloner(chemin_nu: Path, vers: Path, branche: str = "main") -> Path:
    """Clone un dépôt nu pour faire naître un harness. Rend le dossier.

    Le dossier n'existe qu'une fois le clone lu et validé (R2.1) : un dépôt
    qui n'est pas un harness ne laisse ni dossier ni ligne — c'est à l'appelant
    de charger et, s'il refuse, de retirer.
    """
    vers = Path(vers)
    if vers.exists():
        raise DepotRefuse(f"le dossier existe déjà : {vers.name}")
    if not est_depot_nu(chemin_nu):
        raise DepotRefuse(f"pas un dépôt nu : {chemin_nu}")
    if not reference(chemin_nu, branche):
        raise DepotRefuse(f"le dépôt nu n'a pas de branche « {branche} » : rien à cloner")
    fait = git(vers.parent, "clone", "--quiet", "--branch", branche, str(chemin_nu), str(vers))
    if fait.returncode != 0:
        raise DepotRefuse(f"git clone a refusé : {fait.stderr.strip().splitlines()[-1][:200] if fait.stderr.strip() else '?'}")
    _redonner_les_dossiers_vides(vers)
    return vers


def _redonner_les_dossiers_vides(racine: Path) -> None:
    """git ne suit pas un dossier vide : un harness cloné arrive sans son
    `personas/` ou son `corpus/` s'ils n'avaient rien dedans, et le manifest
    refuse. On recrée ce que le manifest déclare — des dossiers, rien d'autre."""
    import yaml

    try:
        manifest = yaml.safe_load((racine / "harness.yaml").read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return
    chemins: list[str] = []
    for cle in ("personas", "corpus"):
        valeur = manifest.get(cle)
        if isinstance(valeur, str):
            chemins.append(valeur)
        elif isinstance(valeur, list):
            chemins.extend(str(c.get("chemin") or c.get("dossier") or "") for c in valeur if isinstance(c, dict))
    for chemin in chemins:
        if chemin and not chemin.startswith(("/", "..")):
            (racine / chemin).mkdir(parents=True, exist_ok=True)
