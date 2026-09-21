"""Le routage mécanique de la chaîne — RFC-016 D16.3.

La chaîne cesse d'être linéaire : une arête porte une **condition** sur le bloc
d'état émis par le kata amont. Le dojo l'évalue **mécaniquement** — il ne juge
pas. Si aucune condition ne tranche, la chaîne s'arrête sur un **checkpoint
humain** ; jamais de branche devinée (D16.3).

La condition est une expression déclarative, jamais du code : des comparaisons
`<chemin> <op> <valeur>` jointes par `and`/`or`, évaluées de gauche à droite.
Le chemin navigue le bloc d'état ; deux commodités calculées s'y ajoutent —
`verdict` (le verdict de la dernière action) et `nature` (la nature émise) —, et
`resultat` est un alias de la racine, pour que `resultat.verdict` se lise.

Ce module est pur : il lit un état, il rend un booléen ou une décision de
routage. Il n'exécute rien et ne touche rien.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = [
    "ConditionInvalide",
    "Etape",
    "Parcours",
    "Routage",
    "evaluer_condition",
    "parser_condition",
    "pas",
    "projeter",
    "router",
]

_OPS = {"==", "!=", "<=", ">=", "<", ">"}
_CONNECTEURS = {"and", "or"}
_TOKEN = re.compile(r"'[^']*'|\"[^\"]*\"|\S+")


class ConditionInvalide(ValueError):
    """Une condition d'arête qui ne se lit pas — refusée au manifeste (D16.3)."""


def _litteral(brut: str):
    if len(brut) >= 2 and brut[0] == brut[-1] and brut[0] in "'\"":
        return brut[1:-1]
    bas = brut.lower()
    if bas == "true":
        return True
    if bas == "false":
        return False
    if bas in ("null", "none"):
        return None
    try:
        return int(brut)
    except ValueError:
        pass
    try:
        return float(brut)
    except ValueError as err:
        raise ConditionInvalide(f"valeur illisible : {brut!r}") from err


def _naviguer(racine, chemin: str):
    """La valeur au bout d'un chemin pointé — ou None si la route se coupe.

    Gourmand : à chaque niveau, le chemin restant est d'abord tenté comme **clé
    entière**, puis découpé. C'est ce qui laisse lire un champ du bloc, dont la
    clé porte elle-même un point (`champs.cadrage.pret` → clé `cadrage.pret`).
    """
    courant, reste = racine, chemin
    while reste:
        if isinstance(courant, dict):
            if reste in courant:
                return courant[reste]
            tete, _, reste = reste.partition(".")
            if tete not in courant:
                return None
            courant = courant[tete]
        elif isinstance(courant, (list, tuple)):
            tete, _, reste = reste.partition(".")
            try:
                courant = courant[int(tete)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return courant


def projeter(etat: dict) -> dict:
    """Le bloc d'état, plus les commodités calculées du routage (RFC-016 D16.3).

    `verdict` — le verdict de la dernière action ; `nature` — la nature émise ;
    `resultat` — un alias de la racine, pour la forme `resultat.verdict`.
    """
    vue = dict(etat or {})
    actions = etat.get("actions") if isinstance(etat, dict) else None
    if isinstance(actions, list) and actions:
        dernier = actions[-1]
        if isinstance(dernier, dict) and isinstance(dernier.get("verdict"), dict):
            vue["verdict"] = dernier["verdict"].get("valeur")
    nature = etat.get("nature") if isinstance(etat, dict) else None
    if isinstance(nature, dict):
        vue["nature"] = nature.get("valeur")
    vue["resultat"] = vue
    return vue


def _comparer(gauche, op: str, droite) -> bool:
    if op == "==":
        return gauche == droite
    if op == "!=":
        return gauche != droite
    # Les ordres ne comparent que des nombres présents des deux côtés : comparer
    # un absent, ou un texte à un nombre, est faux, jamais une erreur.
    if not isinstance(gauche, (int, float)) or isinstance(gauche, bool):
        return False
    if not isinstance(droite, (int, float)) or isinstance(droite, bool):
        return False
    return {
        "<": gauche < droite, "<=": gauche <= droite,
        ">": gauche > droite, ">=": gauche >= droite,
    }[op]


def parser_condition(expr: str):
    """Compile une condition en un prédicat `etat -> bool`. Lève si elle ne se lit pas."""
    toks = _TOKEN.findall((expr or "").strip())
    if not toks:
        raise ConditionInvalide("condition vide")
    if len(toks) % 4 != 3:
        raise ConditionInvalide(f"condition mal formée : {expr!r}")

    comparaisons: list[tuple[str, str, object]] = []
    connecteurs: list[str] = []
    for i in range(0, len(toks), 4):
        chemin, op, brut = toks[i], toks[i + 1], toks[i + 2]
        if op not in _OPS:
            raise ConditionInvalide(f"opérateur inconnu : {op!r} (attendu : {', '.join(sorted(_OPS))})")
        comparaisons.append((chemin, op, _litteral(brut)))
        if i + 3 < len(toks):
            conn = toks[i + 3].lower()
            if conn not in _CONNECTEURS:
                raise ConditionInvalide(f"connecteur inconnu : {toks[i + 3]!r} (attendu : and, or)")
            connecteurs.append(conn)

    def predicat(etat: dict) -> bool:
        vue = projeter(etat)
        resultat = _comparer(_naviguer(vue, comparaisons[0][0]), comparaisons[0][1], comparaisons[0][2])
        for conn, (chemin, op, droite) in zip(connecteurs, comparaisons[1:]):
            suivant = _comparer(_naviguer(vue, chemin), op, droite)
            resultat = (resultat and suivant) if conn == "and" else (resultat or suivant)
        return resultat

    return predicat


def evaluer_condition(expr: str, etat: dict) -> bool:
    """Vrai si l'état satisfait la condition. Une condition vide est toujours vraie
    — une arête sans condition passe (chaîne linéaire d'avant la RFC-016)."""
    if not (expr or "").strip():
        return True
    return parser_condition(expr)(etat)


@dataclass(frozen=True)
class Routage:
    """La décision du dojo à la sortie d'un kata (RFC-016 D16.3).

    `vers` : le nœud suivant, ou `None` — et alors `checkpoint` dit pourquoi la
    main revient à l'humain : aucune condition n'a tranché, ou plusieurs.
    """

    vers: str | None
    checkpoint: str = ""
    candidats: tuple[str, ...] = ()

    @property
    def tranche(self) -> bool:
        return self.vers is not None


def router(harness, kata_id: str, etat: dict) -> Routage:
    """Le nœud suivant, en évaluant mécaniquement les conditions des arêtes.

    Une arête sans condition passe toujours. Si zéro arête tranche, ou si
    plusieurs le font, la main revient à l'humain — jamais de branche devinée.
    """
    sortantes = [a for a in harness.chaine.aretes if a.de == kata_id]
    if not sortantes:
        return Routage(vers=None, checkpoint="fin de chaîne — aucune arête sortante")
    passantes = [a for a in sortantes if evaluer_condition(getattr(a, "condition", ""), etat)]
    if not passantes:
        return Routage(
            vers=None, checkpoint="aucune condition ne tranche",
            candidats=tuple(a.vers for a in sortantes),
        )
    if len(passantes) > 1:
        return Routage(
            vers=None, checkpoint="plusieurs conditions tranchent — ambigu",
            candidats=tuple(a.vers for a in passantes),
        )
    return Routage(vers=passantes[0].vers)


@dataclass
class Parcours:
    """L'état vivant d'un parcours de chaîne : combien de fois chaque cycle a été
    repassé. Ce que le budget (RFC-016 D16.4) décompte à l'exécution."""

    passages: dict[int, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Etape:
    """Le résultat d'un pas de routage, budget compris (RFC-016 D16.3/D16.4)."""

    routage: Routage
    urgence: bool = False
    conduite: str = ""


def _cycle_de(harness, de: str, vers: str):
    """L'indice et le cycle déclaré dont cette arête reste à l'intérieur — ou None."""
    for i, c in enumerate(getattr(harness.chaine, "cycles", ())):
        if de in c.noeuds and vers in c.noeuds:
            return i, c
    return None, None


def pas(harness, kata_id: str, etat: dict, parcours: Parcours | None = None) -> Etape:
    """Un pas de chaîne : route mécaniquement, et décompte le budget d'un cycle.

    Router hors d'un cycle est un pas simple. Router **dans** un cycle déclaré
    consomme un passage ; le budget épuisé, la main revient à l'humain avec la
    conduite d'urgence (RFC-003 A16.3) — état gelé, jamais une boucle de plus.
    """
    parcours = parcours if parcours is not None else Parcours()
    routage = router(harness, kata_id, etat)
    if not routage.tranche:
        return Etape(routage)
    i, cycle = _cycle_de(harness, kata_id, routage.vers)
    if cycle is None:
        return Etape(routage)
    faits = parcours.passages.get(i, 0) + 1
    parcours.passages[i] = faits
    if cycle.budget.passages is not None and faits > cycle.budget.passages:
        return Etape(
            Routage(
                vers=None,
                checkpoint=f"budget de cycle épuisé — {cycle.budget.passages} passages",
                candidats=(routage.vers,),
            ),
            urgence=True,
            conduite="urgence : état gelé, main rendue à l'humain (RFC-003 A16.3, RFC-016 D16.4)",
        )
    return Etape(routage)
