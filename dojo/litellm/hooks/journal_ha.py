"""Journal des ha — la trace durable de toute session (SPECS §3 R3.3).

La passerelle tient ses propres logs, mais sa table par requête ne se remplit
qu'au-delà d'un seuil de file d'attente : une session isolée peut n'y jamais
apparaître. L'observabilité étant fondatrice (§0), le Dojo écrit sa propre
trace, en append seul, indépendante de ce mécanisme.

Une ligne JSON par appel — **en base**, table `appel`, quand l'instance déclare
`KOKAJI_BASE_URL` (RFC-014 D14.4) ; sinon, ou si la base ne répond pas, dans
`<KOKAJI_JOURNAL_DIR>/<AAAA-MM-JJ>.jsonl`. Rien ne se perd : un appel qui n'a
pas pu entrer en base est dans le fichier, et la lecture (`kokaji.corpus.journal`)
lit les deux sans compter deux fois. Le middleware (§7) lit ce journal pour
composer les ha ; le journal lui-même ne juge, n'agrège et ne supprime rien.

Ce module ne connaît aucun domaine : l'identité qu'il inscrit vient telle quelle
du hook d'injection.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from collections import OrderedDict
from datetime import UTC, datetime
from pathlib import Path

try:
    from litellm.integrations.custom_logger import CustomLogger
except ImportError:  # hors passerelle — les tests lisent ce module sans litellm
    CustomLogger = object  # type: ignore[misc,assignment]

logger = logging.getLogger("kokaji.journal_ha")

JOURNAL_DIR = Path(os.environ.get("KOKAJI_JOURNAL_DIR", "/journal"))
BASE_URL = os.environ.get("KOKAJI_BASE_URL", "").strip()

# La table `appel`, la même que `kokaji/corpus/base.py` déclare — écrite ici
# aussi parce que la passerelle démarre avant tout le reste et n'importe pas
# le produit. Ce qui n'est pas colonne est dans `ligne`, entier.
TABLE_APPEL = """
CREATE TABLE IF NOT EXISTS appel (
    id          text PRIMARY KEY,
    session     text NOT NULL DEFAULT '',
    harness     text NOT NULL DEFAULT '',
    kata        text NOT NULL DEFAULT '',
    cible       text NOT NULL DEFAULT '',
    moteur      text NOT NULL DEFAULT '',
    cle         text NOT NULL DEFAULT '',
    statut      text NOT NULL DEFAULT '',
    etat_avant  text,
    etat_apres  text,
    debut       text NOT NULL DEFAULT '',
    fin         text NOT NULL DEFAULT '',
    ligne       json NOT NULL
);
CREATE INDEX IF NOT EXISTS appel_harness_debut ON appel (harness, debut);
CREATE INDEX IF NOT EXISTS appel_session ON appel (session);
"""

# La chaîne des conversations : empreinte d'un état → session qui l'a produit.
CHAINE_MAX = int(os.environ.get("KOKAJI_CHAINE_MAX", "4096"))
_CHAINE: OrderedDict[str, str] = OrderedDict()


def _identite(kwargs: dict) -> dict:
    """L'identité de ha posée par le hook d'injection, ou rien."""
    metadata = (kwargs.get("litellm_params") or {}).get("metadata") or {}
    return dict(metadata.get("spend_logs_metadata") or {})


def _empreinte(messages: list) -> str:
    """L'empreinte d'un état de conversation — la suite exacte des tours."""
    graine = json.dumps(
        [[m.get("role"), m.get("content")] for m in messages],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(graine.encode("utf-8")).hexdigest()[:16]


def _session_declaree(kwargs: dict) -> str | None:
    """Ce que le client déclare fait foi — la passerelle sait le transporter."""
    params = kwargs.get("litellm_params") or {}
    metadata = params.get("metadata") or {}
    for source in (params.get("litellm_session_id"), metadata.get("session_id")):
        if source:
            return str(source)
    return None


def _resoudre_session(kwargs: dict, messages: list, etat_avant: str | None) -> str:
    """Rattache l'appel à sa conversation.

    L'API est sans état : chaque appel rejoue l'historique. Un appel appartient
    donc à la conversation dont il prolonge l'état — `etat_avant` est l'empreinte
    de tout ce qui précédait son dernier tour, et c'est cette empreinte que
    l'appel précédent a laissée derrière lui.

    Une racine — un appel dont l'état amont n'est connu de personne — ouvre une
    conversation nouvelle, identifiée par son propre appel. Deux conversations
    identiques rejouées ne se confondent donc plus : elles ont deux racines.

    La chaîne vit en mémoire. Un redémarrage la perd et les conversations en
    cours repartent sur une racine neuve — le journal reste reconstructible hors
    ligne, puisque chaque ligne porte `etat_avant` et `etat_apres`.
    """
    declaree = _session_declaree(kwargs)
    if declaree:
        return declaree
    if etat_avant and etat_avant in _CHAINE:
        _CHAINE.move_to_end(etat_avant)
        return _CHAINE[etat_avant]
    return "s-" + str(kwargs.get("litellm_call_id") or _empreinte(messages))[:16]


def _prolonger(etat_apres: str, session: str) -> None:
    _CHAINE[etat_apres] = session
    _CHAINE.move_to_end(etat_apres)
    while len(_CHAINE) > CHAINE_MAX:
        _CHAINE.popitem(last=False)


def _dumps(ligne: dict) -> str:
    return json.dumps(ligne, ensure_ascii=False, default=str)


def _ecrire_fichier(ligne: dict, dossier: Path = JOURNAL_DIR) -> None:
    dossier.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(UTC).strftime("%Y-%m-%d")
    with (dossier / f"{jour}.jsonl").open("a", encoding="utf-8") as f:
        f.write(_dumps(ligne) + "\n")


class _Base:
    """La connexion à la base, ouverte à la première ligne, rouverte si elle tombe."""

    def __init__(self, url: str):
        self.url = url
        self._connexion = None
        self._prevenu = False

    def _co(self):
        import psycopg  # l'image de la passerelle l'embarque (dojo/litellm/Dockerfile)

        if self._connexion is None or self._connexion.closed:
            self._connexion = psycopg.connect(self.url, autocommit=True, connect_timeout=5)
            self._connexion.execute(TABLE_APPEL)
        return self._connexion

    def ecrire(self, ligne: dict) -> None:
        from psycopg.types.json import Json

        identite = ligne.get("identite") or {}
        identifiant = str(ligne.get("id_appel") or "") or (
            f"{ligne.get('session')}/{ligne.get('etat_apres')}"
        )
        self._co().execute(
            "INSERT INTO appel (id, session, harness, kata, cible, moteur, cle, statut,"
            " etat_avant, etat_apres, debut, fin, ligne)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (id) DO NOTHING",
            (
                identifiant, str(ligne.get("session") or ""), str(identite.get("harness") or ""),
                str(identite.get("kata") or ""), str(identite.get("cible") or ""),
                str(ligne.get("moteur") or ""), str(identite.get("cle") or ""),
                str(ligne.get("statut") or ""), ligne.get("etat_avant"), ligne.get("etat_apres"),
                str(ligne.get("debut") or ""), str(ligne.get("fin") or ""),
                Json(json.loads(_dumps(ligne)), dumps=_dumps),
            ),
        )


_BASE = _Base(BASE_URL) if BASE_URL else None


def _ecrire(ligne: dict, base: _Base | None = None, dossier: Path = JOURNAL_DIR) -> str:
    """La ligne en base si l'instance en a une, dans le fichier sinon — ou si
    la base n'a pas répondu : un appel ne se perd pas pour une base. Rend où."""
    base = _BASE if base is None else base
    if base is not None:
        try:
            base.ecrire(ligne)
            return "base"
        except Exception as err:  # noqa: BLE001 — la base tombée ne fait pas tomber le journal
            if not base._prevenu:
                logger.warning("journal : la base ne répond pas, écriture en fichier — %s", err)
                base._prevenu = True
            base._connexion = None
    _ecrire_fichier(ligne, dossier)
    return "fichier"


class JournalHa(CustomLogger):
    """Inscrit chaque appel, abouti ou non, dans le journal."""

    async def _consigner(self, kwargs, reponse, debut, fin, statut, erreur=None):
        try:
            messages = kwargs.get("messages") or []
            texte = self._texte(reponse)

            # L'état d'où part cet appel, et celui qu'il laisse derrière lui.
            etat_avant = _empreinte(messages[:-1]) if len(messages) > 1 else None
            suite = messages + ([{"role": "assistant", "content": texte}] if texte else [])
            etat_apres = _empreinte(suite)

            session = _resoudre_session(kwargs, messages, etat_avant)
            if texte:
                _prolonger(etat_apres, session)

            ligne = {
                "statut": statut,
                "id_appel": kwargs.get("litellm_call_id"),
                "session": session,
                "etat_avant": etat_avant,
                "etat_apres": etat_apres,
                "debut": debut,
                "fin": fin,
                # Le moteur réellement appelé, résolu par la passerelle après le
                # hook. Le fournisseur le qualifie : un même nom de modèle peut
                # être servi par deux hébergeurs, et le banc les compare (§5.6).
                "moteur": kwargs.get("model"),
                "fournisseur": (kwargs.get("litellm_params") or {}).get(
                    "custom_llm_provider"
                ),
                "identite": _identite(kwargs),
                "messages": messages,
                "reponse": texte,
                "usage": self._usage(reponse),
                "erreur": str(erreur) if erreur else None,
            }
            await asyncio.to_thread(_ecrire, ligne)
        except Exception as err:  # une session ne tombe jamais pour un journal
            logger.warning("journal non écrit : %s", err)

    @staticmethod
    def _texte(reponse) -> str | None:
        try:
            return reponse["choices"][0]["message"]["content"]
        except (TypeError, KeyError, IndexError):
            return None

    @staticmethod
    def _usage(reponse) -> dict | None:
        try:
            usage = reponse["usage"]
        except (TypeError, KeyError):
            return None
        return dict(usage) if usage else None

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await self._consigner(kwargs, response_obj, start_time, end_time, "abouti")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        await self._consigner(
            kwargs,
            None,
            start_time,
            end_time,
            "echoue",
            erreur=kwargs.get("exception") or response_obj,
        )


journal = JournalHa()
