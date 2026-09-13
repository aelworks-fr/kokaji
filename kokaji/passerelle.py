"""L'autorisation de la passerelle, dérivée de la forge — NOTE-0002, NOTE-0010.

Deux registres décidaient de ce qu'un harness pouvait réellement servir, et
tous deux étaient tenus à la main, séparément de la définition : la liste des
modèles de la passerelle, et **l'autorisation portée par la clé appelante**.
Trois fois la même panne en est sortie — une coupe forgée que rien ne laissait
passer, des titres de conversation qui échouaient depuis toujours — et les trois
fois, rien ne l'a signalé. Un modèle refusé se lit comme un modèle absent.

Kokaji calcule désormais la liste (RFC-005 §3.2). Ce module s'occupe de l'autre
registre, et son geste le plus utile n'est pas d'écrire : **constater est le
défaut, écrire demande `--publier`**. Réparer règle une fois ; constater dit
quand ça recommence, ce qu'aucune des trois pannes n'a su faire.

Rien ici ne parle du domaine : un modèle virtuel est `<harness>/<kata>`, une
forme, pas un sujet.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .hds import Harness

DEBUT = "# >>> engendré par `kokaji passerelle --config` — ne pas éditer à la main"
FIN = "# <<< fin de la part engendrée"

__all__ = [
    "Ecart",
    "PasserelleInjoignable",
    "autorisation_de_la_cle",
    "ecart_d_autorisation",
    "modeles_servis",
    "modeles_virtuels",
    "publier_autorisation",
    "publier_modeles",
]


class PasserelleInjoignable(Exception):
    """La passerelle n'a pas répondu, ou a refusé la clé d'administration."""


def modeles_virtuels(harness: Harness, cibles: bool = True) -> tuple[str, ...]:
    """Les modèles virtuels qu'un harness déclare — SPECS R3.1.

    La forme nue `<harness>/<kata>` s'incarne dans la cible du Dojo ; la forme
    suffixée `<harness>/<kata>@<cible>` en force une, ce qui sert à exposer deux
    incarnations côte à côte pour les comparer (§5.6).

    Les deux sont déclarées : une autorisation qui ne couvrirait que la forme
    nue refuserait le banc, et l'on retomberait exactement sur la panne que ce
    module existe pour empêcher.
    """
    noms: list[str] = []
    for kata in harness.kata:
        noms.append(harness.espace(kata.id))
        if cibles:
            noms.extend(f"{harness.espace(kata.id)}@{cible.id}" for cible in harness.cibles)
    return tuple(noms)


@dataclass(frozen=True)
class Ecart:
    """Ce que la forge déclare et que la clé ignore, et l'inverse."""

    manquants: tuple[str, ...] = ()  # forgés, mais non autorisés
    surnumeraires: tuple[str, ...] = ()  # autorisés, mais plus forgés

    def __bool__(self) -> bool:
        return bool(self.manquants or self.surnumeraires)

    def rendre(self) -> str:
        lignes = []
        for nom in self.manquants:
            lignes.append(f"  - forgé mais non autorisé : {nom}")
        for nom in self.surnumeraires:
            lignes.append(f"  - autorisé mais plus forgé : {nom}")
        return "\n".join(lignes)


def ecart_d_autorisation(attendus: tuple[str, ...], autorises: tuple[str, ...]) -> Ecart:
    """Le décrochage entre la forge et la clé, dans les deux sens.

    Les surnuméraires comptent autant que les manquants : une autorisation qui
    survit à un kata retiré laisse une porte ouverte sur une coupe qui n'existe
    plus, et personne ne la referme puisque personne ne la voit.
    """
    return Ecart(
        manquants=tuple(sorted(set(attendus) - set(autorises))),
        surnumeraires=tuple(sorted(set(autorises) - set(attendus))),
    )


def entrees_de_la_passerelle(harness: dict, moteurs: dict, nus=()) -> list[dict]:
    """La `model_list` de la passerelle, dérivée des harness — NOTE-0002.

    Le moteur n'est pas dans le harness et n'a rien à y faire : quel modèle
    incarne un kata est une décision de **déploiement**, pas de définition.
    Il vient donc de `moteurs`, qui garde la promesse R3.2 — changer le moteur
    sous un kata reste une ligne, elle a seulement changé de fichier.

    `par_modele` l'emporte sur `defaut` : c'est ce qui permet d'exposer deux
    incarnations d'un même kata sur deux moteurs, et de les comparer (§5.6).
    """
    defaut = moteurs.get("defaut") or {}
    par_modele = moteurs.get("par_modele") or {}

    noms = [nom for _, h in sorted(harness.items()) for nom in modeles_virtuels(h)]
    noms += [nom for nom in nus if nom not in noms]
    return [
        {"model_name": nom, "litellm_params": dict(par_modele.get(nom) or defaut)}
        for nom in noms
    ]


def rendre_model_list(entrees: list[dict]) -> str:
    """Le bloc YAML à poser dans la configuration, entre ses deux marques.

    Les marques disent que ce bloc est engendré. Sans elles, quelqu'un l'édite
    un jour à la main, et l'on retombe très exactement sur NOTE-0002.
    """
    import yaml

    corps = yaml.safe_dump(
        {"model_list": entrees}, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    return f"{DEBUT}\n{corps.rstrip()}\n{FIN}\n"


def poser_model_list(chemin: Path, bloc: str) -> None:
    """Remplace la part engendrée du fichier, et elle seule.

    Le reste — les rappels, les réglages généraux, les commentaires — est écrit
    à la main et le reste. On engendre une part, pas un fichier.
    """
    chemin = Path(chemin)
    texte = chemin.read_text(encoding="utf-8") if chemin.is_file() else ""
    if DEBUT in texte and FIN in texte:
        avant = texte[: texte.index(DEBUT)]
        apres = texte[texte.index(FIN) + len(FIN) :]
        # Le bloc porte déjà le saut de ligne qui suit sa marque de fin. Sans
        # cette coupe, chaque pose en ajoutait un : le fichier grossissait d'une
        # ligne vide à chaque publication, ce qui ne casse rien et ne se voit
        # jamais — donc exactement la forme de dérive qu'on refuse.
        apres = apres.removeprefix("\n")
        chemin.write_text(avant + bloc + apres, encoding="utf-8")
        return
    # Première pose : le bloc prend la place de l'ancienne `model_list` tenue à
    # la main, et le reste du fichier ne bouge pas.
    lignes = texte.splitlines(keepends=True)
    debut = next((i for i, l in enumerate(lignes) if l.startswith("model_list:")), None)
    if debut is None:
        chemin.write_text(texte + ("\n" if texte and not texte.endswith("\n") else "") + bloc,
                          encoding="utf-8")
        return
    fin = debut + 1
    while fin < len(lignes) and (lignes[fin].startswith((" ", "\t", "#")) or not lignes[fin].strip()):
        fin += 1
    chemin.write_text("".join(lignes[:debut]) + bloc + "".join(lignes[fin:]), encoding="utf-8")


def modeles_de_la_configuration(chemin: Path) -> tuple[str, ...]:
    """Les modèles que la passerelle déclare servir, lus dans sa configuration."""
    import yaml

    chemin = Path(chemin)
    if not chemin.is_file():
        return ()
    donnees = yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}
    return tuple(str(e.get("model_name")) for e in (donnees.get("model_list") or []))


def modeles_servis(base: str, admin: str, appeler=None) -> tuple[str, ...]:
    """Ce que la passerelle sait router **en ce moment** — configuration et base.

    `/model/info` dit l'état réel, là où lire `config.yaml` ne dirait que ce qui
    était vrai au démarrage. Un modèle ajouté à chaud n'y figurerait pas, et l'on
    republierait indéfiniment ce qui existe déjà.
    """
    appeler = appeler or _appeler
    reponse = appeler(f"{base.rstrip('/')}/model/info", admin)
    return tuple(str(m.get("model_name")) for m in (reponse.get("data") or []))


def publier_modeles(
    base: str, admin: str, entrees: list[dict], appeler=None
) -> tuple[str, ...]:
    """Ajoute à la passerelle ce qu'elle ne route pas encore. Rend les ajoutés.

    On n'ajoute que le manquant : republier un modèle existant en créerait un
    double, et deux entrées du même nom rendraient le routage indécidable.

    C'est ce qui manquait pour qu'un harness créé serve sans qu'on lance une
    commande — sceller forgeait ses coupes, et la passerelle continuait de les
    ignorer (NOTE-0016).
    """
    appeler = appeler or _appeler
    connus = set(modeles_servis(base, admin, appeler))
    ajoutes = []
    for entree in entrees:
        nom = str(entree.get("model_name"))
        if nom in connus:
            continue
        appeler(
            f"{base.rstrip('/')}/model/new",
            admin,
            {"model_name": nom, "litellm_params": dict(entree.get("litellm_params") or {})},
        )
        ajoutes.append(nom)
    return tuple(ajoutes)


def _appeler(url: str, admin: str, corps: dict | None = None) -> dict:
    requete = urllib.request.Request(
        url,
        data=json.dumps(corps).encode("utf-8") if corps is not None else None,
        headers={"authorization": f"Bearer {admin}", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            return json.loads(reponse.read() or b"{}")
    except urllib.error.HTTPError as err:
        raise PasserelleInjoignable(f"{err.code} — {err.read().decode()[:200]}") from err
    except OSError as err:
        raise PasserelleInjoignable(str(err)) from err


def autorisation_de_la_cle(base: str, admin: str, cle: str, appeler=_appeler) -> tuple[str, ...]:
    """Les modèles que cette clé peut appeler, tels que la passerelle les tient."""
    reponse = appeler(f"{base.rstrip('/')}/key/info?key={urllib.parse.quote(cle)}", admin)
    info = reponse.get("info", reponse)
    return tuple(info.get("models") or ())


def publier_autorisation(
    base: str, admin: str, cle: str, modeles: tuple[str, ...], appeler=_appeler
) -> None:
    """Écrit l'autorisation. Elle **remplace**, elle n'ajoute pas.

    Ajouter laisserait vivre les surnuméraires — les autorisations d'un kata
    retiré, que personne ne pense à retirer parce que personne ne les voit.
    La clé dit exactement ce que la forge déclare, ou elle ment.
    """
    appeler(
        f"{base.rstrip('/')}/key/update", admin, {"key": cle, "models": list(modeles)}
    )
