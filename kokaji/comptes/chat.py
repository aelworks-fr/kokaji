"""Les comptes, côté chat — RFC-006, et le carnet du 16 août.

Trois portes gardaient l'entrée, et la troisième ne savait rien : Authelia
n'ouvre qu'aux inscrits du portail, Kokaji exige un compte pour servir quoi que
ce soit, et le chat créait malgré tout un compte **en attente** qu'il fallait
valider à la main. Cette troisième validation confirmait une décision déjà prise
en invitant — et elle a bloqué le forgeron sur son propre compte.

Deux gestes en découlent, et un seul est une routine :

- **inviter active** : consommer une invitation crée le compte du chat, actif.
  La décision se prend une fois, au moment où elle se prend vraiment.
- **la page d'administration montre les exceptions** : qui est arrivé sans
  invitation reste en attente, et devient alors un *signal* plutôt qu'un geste
  de plus à faire pour chaque client.

Kokaji écrit déjà dans le fichier d'utilisateurs du portail pour la même raison —
« consommer une invitation doit créer le compte des deux côtés, sinon l'invité
se fait arrêter à la porte juste après s'être inscrit ». Le chat est le
troisième côté, et l'oublier produisait exactement l'arrêt que ce couplage
existe pour éviter.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

__all__ = ["Chat", "ChatInjoignable"]


class ChatInjoignable(Exception):
    """Le chat n'a pas répondu, ou a refusé la clé d'administration."""


def _appeler(url: str, cle: str, corps: dict | None = None) -> object:
    requete = urllib.request.Request(
        url,
        data=json.dumps(corps).encode("utf-8") if corps is not None else None,
        headers={"authorization": f"Bearer {cle}", "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=20) as reponse:
            return json.loads(reponse.read() or b"{}")
    except urllib.error.HTTPError as err:
        raise ChatInjoignable(f"{err.code} — {err.read().decode()[:200]}") from err
    except OSError as err:
        raise ChatInjoignable(str(err)) from err


@dataclass(frozen=True)
class Chat:
    """L'administration des comptes du chat, vue de Kokaji."""

    base: str
    cle: str

    @classmethod
    def depuis_l_environnement(cls) -> Chat | None:
        """`None` si le chat n'est pas administrable — et c'est dit, pas supposé.

        Sans clé, Kokaji ne prétend pas gérer les comptes du chat : la page
        d'administration l'annonce au lieu d'afficher une liste vide qui se
        lirait « personne n'attend ».
        """
        base = (os.environ.get("KOKAJI_CHAT_API") or "").rstrip("/")
        cle = os.environ.get("KOKAJI_CHAT_ADMIN") or ""
        return cls(base, cle) if base and cle else None

    def comptes(self, appeler=_appeler) -> list[dict]:
        """Tous les comptes du chat, réduits à ce que l'administration regarde."""
        reponse = appeler(f"{self.base}/api/v1/users/", self.cle)
        gens = reponse.get("users") if isinstance(reponse, dict) else reponse
        return [
            {
                "id": u.get("id"),
                "nom": u.get("name"),
                "email": u.get("email"),
                "role": u.get("role"),
            }
            for u in (gens or [])
        ]

    def en_attente(self, appeler=_appeler) -> list[dict]:
        """Ceux qui sont arrivés sans invitation — les exceptions, et elles seules."""
        return [c for c in self.comptes(appeler) if c["role"] == "pending"]

    def activer(self, compte: dict, appeler=_appeler) -> None:
        """Passe un compte en attente à `user`.

        Le formulaire du chat remplace ce qu'on lui donne : on lui redonne donc
        le nom et l'email tels quels. Ne transmettre que le rôle les effacerait.
        """
        appeler(
            f"{self.base}/api/v1/users/{urllib.parse.quote(str(compte['id']))}/update",
            self.cle,
            {"role": "user", "name": compte.get("nom") or "", "email": compte.get("email") or ""},
        )

    def creer(self, email: str, nom: str, mot_de_passe: str, appeler=_appeler) -> None:
        """Crée un compte **actif**, au moment de l'invitation.

        Un compte déjà connu du chat n'est pas une erreur : la personne s'y est
        rendue avant de consommer son invitation, et le portail l'y a créée. On
        l'active alors plutôt que de refuser.
        """
        try:
            appeler(
                f"{self.base}/api/v1/auths/add",
                self.cle,
                {"name": nom, "email": email, "password": mot_de_passe, "role": "user"},
            )
        except ChatInjoignable as err:
            if "EMAIL_TAKEN" not in str(err) and "already" not in str(err).lower():
                raise
            connu = next((c for c in self.comptes(appeler) if c["email"] == email), None)
            if connu is not None and connu["role"] == "pending":
                self.activer(connu, appeler)
