"""Les comptes du chat, administrés depuis Kokaji — RFC-006 et le 16 août.

Aucun réseau : l'appel HTTP est injecté. Ce qui est éprouvé ici est la règle,
pas la plomberie — inviter active, la page ne montre que les exceptions, et une
absence de clé se dit au lieu de se lire « personne n'attend ».
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.comptes.chat import Chat, ChatInjoignable

GENS = [
    {"id": "1", "name": "Un", "email": "un@exemple.test", "role": "admin"},
    {"id": "2", "name": "Deux", "email": "deux@exemple.test", "role": "pending"},
    {"id": "3", "name": "Trois", "email": "trois@exemple.test", "role": "user"},
]


class Faux:
    """Un chat de papier : il note ce qu'on lui demande."""

    def __init__(self, gens=None, refuse=None):
        self.gens = [dict(g) for g in (gens if gens is not None else GENS)]
        self.refuse = refuse
        self.appels = []

    def __call__(self, url, cle, corps=None):
        self.appels.append((url, corps))
        if self.refuse and self.refuse in url:
            raise ChatInjoignable(self.refuse)
        if url.endswith("/api/v1/users/"):
            return {"users": self.gens}
        if url.endswith("/add"):
            if any(g["email"] == corps["email"] for g in self.gens):
                raise ChatInjoignable("400 — EMAIL_TAKEN")
            self.gens.append({"id": "n", **corps, "name": corps["name"]})
            return {}
        if "/update" in url:
            for g in self.gens:
                if g["id"] in url:
                    g.update({k: v for k, v in corps.items() if k in ("role", "name", "email")})
            return {}
        return {}


class LesExceptions(unittest.TestCase):
    def setUp(self):
        self.chat = Chat("http://chat", "sk-x")

    def test_en_attente_ne_rend_que_ceux_qui_attendent(self):
        faux = Faux()
        self.assertEqual([c["email"] for c in self.chat.en_attente(faux)], ["deux@exemple.test"])

    def test_activer_redonne_nom_et_email(self):
        """Le formulaire du chat remplace ce qu'on lui donne : ne transmettre que
        le rôle effacerait le reste."""
        faux = Faux()
        self.chat.activer({"id": "2", "nom": "Deux", "email": "deux@exemple.test"}, faux)
        _, corps = faux.appels[-1]
        self.assertEqual(corps, {"role": "user", "name": "Deux", "email": "deux@exemple.test"})
        self.assertEqual([g["role"] for g in faux.gens if g["id"] == "2"], ["user"])

    def test_un_chat_muet_se_dit(self):
        with self.assertRaises(ChatInjoignable):
            self.chat.en_attente(Faux(refuse="/api/v1/users/"))


class InviterActive(unittest.TestCase):
    def setUp(self):
        self.chat = Chat("http://chat", "sk-x")

    def test_creer_pose_un_compte_actif(self):
        """La décision se prend en invitant : le chat n'a pas à la redemander."""
        faux = Faux()
        self.chat.creer("neuf@exemple.test", "Neuf", "un-mot-de-passe", faux)
        _, corps = faux.appels[-1]
        self.assertEqual(corps["role"], "user")
        self.assertEqual(corps["email"], "neuf@exemple.test")

    def test_un_compte_deja_connu_est_active_plutot_que_refuse(self):
        """La personne s'est rendue au chat avant de consommer son invitation :
        le portail l'y a créée en attente. On l'active."""
        faux = Faux()
        self.chat.creer("deux@exemple.test", "Deux", "un-mot-de-passe", faux)
        self.assertEqual([g["role"] for g in faux.gens if g["id"] == "2"], ["user"])

    def test_un_compte_deja_actif_n_est_pas_retouche(self):
        faux = Faux()
        self.chat.creer("trois@exemple.test", "Trois", "un-mot-de-passe", faux)
        self.assertNotIn("/update", " ".join(u for u, _ in faux.appels))

    def test_une_autre_faute_n_est_pas_avalee(self):
        """Confondre « déjà là » et « refusé » ferait passer une panne pour un
        succès — le motif que le carnet répète."""
        with self.assertRaises(ChatInjoignable):
            self.chat.creer("x@exemple.test", "X", "mdp", Faux(refuse="/add"))


class SansCle(unittest.TestCase):
    def test_sans_cle_le_chat_n_est_pas_administrable(self):
        """Et c'est dit : une liste vide se lirait « personne n'attend »."""
        import os

        for cle in ("KOKAJI_CHAT_API", "KOKAJI_CHAT_ADMIN"):
            ancien = os.environ.pop(cle, None)
            self.addCleanup(
                lambda c=cle, a=ancien: os.environ.__setitem__(c, a) if a else None
            )
        self.assertIsNone(Chat.depuis_l_environnement())


if __name__ == "__main__":
    unittest.main()
