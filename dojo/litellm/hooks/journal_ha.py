"""Journal des ha — la trace durable de toute session (SPECS §3 R3.3).

La passerelle tient ses propres logs, mais sa table par requête ne se remplit
qu'au-delà d'un seuil de file d'attente : une session isolée peut n'y jamais
apparaître. L'observabilité étant fondatrice (§0), le Dojo écrit sa propre
trace, en append seul, indépendante de ce mécanisme.

Une ligne JSON par appel, dans `<KOKAJI_JOURNAL_DIR>/<AAAA-MM-JJ>.jsonl`. Le
middleware (§7) lit ce journal pour composer les ha ; le journal lui-même ne
juge, n'agrège et ne supprime rien.

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
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger("kokaji.journal_ha")

JOURNAL_DIR = Path(os.environ.get("KOKAJI_JOURNAL_DIR", "/journal"))

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


def _ecrire(ligne: dict) -> None:
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    jour = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with (JOURNAL_DIR / f"{jour}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(ligne, ensure_ascii=False, default=str) + "\n")


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
