"""L'accès à la passerelle du Dojo.

Le banc parle aux kata comme n'importe quel client : par l'API, avec sa propre
clé. Il ne lit jamais une coupe directement — sinon il éprouverait autre chose
que ce que vit une vraie session (SPECS §5 R5.4).
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class PasserelleInjoignable(Exception):
    """La passerelle n'a pas répondu, ou a refusé."""


@dataclass(frozen=True)
class Passerelle:
    """Où le banc appelle, et avec quelle clé.

    Les deux défauts sont lus **à chaque construction**, pas au chargement du
    module : un `os.environ.get` en valeur de champ fige la valeur à l'import,
    si bien que poser la variable ensuite n'a plus aucun effet. Le piège est
    silencieux — on croit avoir dirigé la passerelle ailleurs, et l'on appelle
    toujours la même.

    Et le défaut vise `127.0.0.1:4000`, c'est-à-dire **la passerelle du poste**.
    Sur une machine où le dojo tourne, oublier de le remplacer appelle la vraie.
    """

    base: str = field(
        default_factory=lambda: os.environ.get("KOKAJI_PASSERELLE", "http://127.0.0.1:4000")
    )
    cle: str = field(default_factory=lambda: os.environ.get("DOJO_CLE_BANC", ""))
    delai: int = 180

    def completer(self, modele: str, messages: list, temperature: float | None = None) -> str:
        corps: dict = {"model": modele, "messages": messages}
        if temperature is not None:
            corps["temperature"] = temperature

        requete = urllib.request.Request(
            f"{self.base}/v1/chat/completions",
            data=json.dumps(corps).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.cle}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(requete, timeout=self.delai) as reponse:
                charge = json.load(reponse)
        except urllib.error.HTTPError as err:
            raise PasserelleInjoignable(
                f"{modele} — {err.code} {err.read()[:300].decode('utf-8', 'replace')}"
            ) from err
        except OSError as err:
            raise PasserelleInjoignable(f"{modele} — {err}") from err

        try:
            return charge["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as err:
            raise PasserelleInjoignable(f"{modele} — réponse inattendue : {charge}") from err
