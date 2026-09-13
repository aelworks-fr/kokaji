"""Injection des coupes côté passerelle + estampille d'identité de ha.

Ce hook ne connaît aucun domaine : il ne lit que la structure `<harness>/<kata>`
du nom de modèle virtuel et l'arborescence des coupes produite par la forge
(SPECS §3 R3.1, R3.3 ; §0 principe de découplage).

Arborescence attendue sous KOKAJI_COUPES_DIR :

    <harness>/<cible>/<kata>.md      la coupe injectée comme prompt système
    <harness>/<cible>/<kata>.json    l'estampille posée par la forge (R4.3)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from litellm.integrations.custom_logger import CustomLogger

logger = logging.getLogger("kokaji.coupe_injector")

COUPES_DIR = Path(os.environ.get("KOKAJI_COUPES_DIR", "/coupes"))
CIBLE_DEFAUT = os.environ.get("KOKAJI_CIBLE_DEFAUT", "base")

# Les modèles servis sans coupe. Le banc en a besoin : le persona qu'il joue
# n'est pas un kata, il ne s'incarne pas. Tout le reste passe par la forge.
MODELES_NUS = frozenset(
    m.strip() for m in os.environ.get("KOKAJI_MODELES_NUS", "").split(",") if m.strip()
)


class CoupeIntrouvable(Exception):
    """Aucune coupe ne correspond au modèle virtuel demandé."""


class CoupeInjector(CustomLogger):
    """Remplace le prompt système par la coupe et estampille la session."""

    def _resoudre(self, modele: str, cible_defaut: str) -> tuple[str, str, str, Path]:
        """`<harness>/<kata>` — ou `<harness>/<kata>@<cible>` pour forcer la cible.

        Sans suffixe, la cible est celle du Dojo. Le suffixe sert à exposer deux
        incarnations d'un même kata côte à côte, pour les comparer (§5.6).
        """
        reference, _, cible = modele.partition("@")
        if "/" not in reference:
            raise CoupeIntrouvable(
                f"modèle virtuel '{modele}' : forme attendue <harness>/<kata>[@<cible>]"
            )
        harness, kata = reference.split("/", 1)
        if not cible:
            cible = cible_defaut
            # La cible du Dojo est un défaut global, et tous les harness ne la
            # forgent pas : un harness adopté n'a que `nue`, et `<harness>/<kata>`
            # échouait pendant que `<harness>/<kata>@nue` marchait. Quand le défaut n'existe pas
            # et qu'une seule cible est forgée, elle est sans ambiguïté — on la
            # prend. À plusieurs, on refuse en les nommant : choisir en silence
            # ferait converser sur une coupe que personne n'a désignée.
            if not (COUPES_DIR / harness / cible).is_dir():
                forgees = sorted(
                    d.name for d in (COUPES_DIR / harness).iterdir() if d.is_dir()
                ) if (COUPES_DIR / harness).is_dir() else []
                if len(forgees) == 1:
                    cible = forgees[0]
                elif forgees:
                    raise CoupeIntrouvable(
                        f"'{modele}' : cible '{cible_defaut}' non forgée pour "
                        f"{harness}, et plusieurs au choix — précise "
                        + " ou ".join(f"@{f}" for f in forgees)
                    )
        chemin = COUPES_DIR / harness / cible / f"{kata}.md"
        if not chemin.is_file():
            raise CoupeIntrouvable(f"coupe absente : {chemin}")
        return harness, kata, cible, chemin

    def _estampille(self, chemin: Path) -> dict:
        sidecar = chemin.with_suffix(".json")
        if not sidecar.is_file():
            return {}
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as err:
            # Une estampille illisible dégrade l'observabilité, jamais la session.
            logger.warning("estampille illisible %s : %s", sidecar, err)
            return {}

    async def async_pre_call_hook(self, user_api_key_dict, cache, data, call_type):
        if call_type not in ("completion", "acompletion"):
            return data

        modele = data.get("model", "")
        if modele in MODELES_NUS:
            return data

        metadata = data.setdefault("metadata", {})

        harness, kata, cible, chemin = self._resoudre(modele, CIBLE_DEFAUT)
        coupe = chemin.read_text(encoding="utf-8")
        estampille = self._estampille(chemin)

        # Le client ne fournit jamais la posture : toute consigne système entrante
        # est écartée au profit de la coupe.
        messages = [m for m in data.get("messages", []) if m.get("role") != "system"]
        data["messages"] = [{"role": "system", "content": coupe}] + messages

        # Identité de ha (R3.3). Elle passe par `spend_logs_metadata` : c'est la
        # seule clé de métadonnée que la passerelle recopie jusque dans sa charge
        # de logging standard — une clé posée à la racine y est filtrée.
        # Le moteur effectivement appelé n'est pas connu ici : la passerelle le
        # résout après ce hook et l'inscrit dans son propre champ `model`.
        metadata.setdefault("spend_logs_metadata", {}).update(
            {
                "harness": harness,
                "kata": kata,
                "version_kata": estampille.get("version_kata"),
                "version_coupe": estampille.get("version_coupe"),
                "cible": cible,
                "modele_virtuel": modele,
                # Qui a appelé : le chat, le banc, le QG. C'est ce qui permet de
                # ranger un ha dans le bon corpus sans deviner.
                "cle": getattr(user_api_key_dict, "key_alias", None),
                # Le fil de conversation et la personne, tels que le chat les
                # annonce. Open WebUI retire ses métadonnées du corps mais les
                # transmet en en-têtes — encore faut-il qu'il y soit autorisé
                # (`ENABLE_FORWARD_USER_INFO_HEADERS`). Sans eux, ces deux champs
                # restent absents : on ne devine pas un fil.
                "fil": _entete(data, "x-openwebui-chat-id"),
                "praticien_email": _entete(data, "x-openwebui-user-email"),
                "date": datetime.now(timezone.utc).isoformat(),
            }
        )
        return data


def _entete(data: dict, nom: str) -> str | None:
    """Un en-tête de la requête d'origine, si la passerelle l'a conservé.

    LiteLLM range la requête entrante dans `proxy_server_request`. Ce qui n'y
    est pas n'est pas cherché ailleurs : un identifiant qu'on reconstruit est un
    identifiant qu'on invente.
    """
    entetes = ((data.get("proxy_server_request") or {}).get("headers") or {})
    for cle, valeur in entetes.items():
        if str(cle).lower() == nom:
            return str(valeur) or None
    return None


injector = CoupeInjector()
