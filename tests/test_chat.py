"""La façade que le chat consomme — RFC-005 §3.

Harness purement structurels (§0).

La moitié de ce fichier vérifie des **refus**. Une vérification de signature
qu'on n'attaque pas est une vérification qu'on croit sur parole — et les trois
manières de la rendre décorative (accepter `none`, accepter un autre
algorithme, oublier l'expiration) ne se voient pas à la lecture du chemin
nominal.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from test_hds import MINIMAL, _ecrire_harness

from kokaji.comptes import Comptes
from kokaji.hds import charger_tous
from kokaji.middleware.aiguilleur import creer_tous
from kokaji.middleware.chat import JetonInvalide, verifier_jeton

SECRET = "un-secret-partage-avec-le-chat"
MOT_DE_PASSE = "un-mot-de-passe-assez-long"


def _b64(donnees: dict) -> str:
    brut = json.dumps(donnees, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(brut).decode("ascii").rstrip("=")


def forger_jeton(charge: dict, secret: str = SECRET, alg: str = "HS256") -> str:
    """Un JWT, comme le chat en pose — y compris mal formé, pour l'attaquer."""
    entete = _b64({"alg": alg, "typ": "JWT"})
    corps = _b64(charge)
    signature = hmac.new(
        secret.encode("utf-8"), f"{entete}.{corps}".encode(), hashlib.sha256
    ).digest()
    return f"{entete}.{corps}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


class Signature(unittest.TestCase):
    """Ce que la vérification doit refuser, et pourquoi ça compte."""

    def test_un_jeton_valide_rend_sa_charge(self):
        charge = verifier_jeton(forger_jeton({"email": "un@exemple.test", "exp": 100}), SECRET, 50)
        self.assertEqual(charge["email"], "un@exemple.test")

    def test_alg_none_est_refuse(self):
        """L'attaque classique : se déclarer non signé pour n'être pas vérifié."""
        entete = _b64({"alg": "none", "typ": "JWT"})
        corps = _b64({"email": "un@exemple.test", "exp": 100})
        with self.assertRaises(JetonInvalide) as capture:
            verifier_jeton(f"{entete}.{corps}.", SECRET, 50)
        # Refusé sur l'algorithme, avant même de regarder la signature vide :
        # c'est l'ordre qui compte, pas seulement le refus.
        self.assertIn("algorithme refusé", str(capture.exception))

    def test_un_autre_algorithme_est_refuse_sans_examen(self):
        """`alg` est imposé, pas lu : sinon l'attaquant choisit la serrure."""
        jeton = forger_jeton({"email": "un@exemple.test", "exp": 100}, alg="HS512")
        with self.assertRaises(JetonInvalide) as capture:
            verifier_jeton(jeton, SECRET, 50)
        self.assertIn("algorithme refusé", str(capture.exception))

    def test_une_signature_d_un_autre_secret_est_refusee(self):
        jeton = forger_jeton({"email": "un@exemple.test", "exp": 100}, secret="pas-le-bon")
        with self.assertRaises(JetonInvalide):
            verifier_jeton(jeton, SECRET, 50)

    def test_une_charge_retouchee_ne_passe_pas(self):
        """Se renommer sans re-signer : le cas qui fait tout l'intérêt du JWT."""
        jeton = forger_jeton({"email": "un@exemple.test", "exp": 100})
        entete, _, signature = jeton.split(".")
        retouche = f"{entete}.{_b64({'email': 'deux@exemple.test', 'exp': 100})}.{signature}"
        with self.assertRaises(JetonInvalide):
            verifier_jeton(retouche, SECRET, 50)

    def test_un_jeton_sans_expiration_est_refuse(self):
        """Sans `exp`, c'est une clé permanente posée dans un en-tête."""
        with self.assertRaises(JetonInvalide) as capture:
            verifier_jeton(forger_jeton({"email": "un@exemple.test"}), SECRET, 50)
        self.assertIn("sans expiration", str(capture.exception))

    def test_un_jeton_perime_est_refuse(self):
        with self.assertRaises(JetonInvalide) as capture:
            verifier_jeton(forger_jeton({"email": "un@exemple.test", "exp": 100}), SECRET, 101)
        self.assertIn("périmé", str(capture.exception))


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        for identifiant in ("h", "h2"):
            _ecrire_harness(
                racine / identifiant, MINIMAL.replace("id: h\n", f"id: {identifiant}\n")
            )

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.un = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.un.id)
        self.comptes.choisir_harness(self.un.id, "h")

        self.client = TestClient(
            creer_tous(
                charger_tous(racine), racine / "journal", self.comptes, secret_chat=SECRET
            )
        )

    def signe(self, email: str = "un@exemple.test") -> dict:
        return {"X-OpenWebUI-User-Jwt": forger_jeton({"email": email, "exp": 2**31})}


class Modeles(Bac):
    def test_la_liste_est_celle_des_kata_du_harness_courant(self):
        vu = self.client.get("/v1/models", headers=self.signe()).json()
        self.assertEqual([m["id"] for m in vu["data"]], ["h/k1"])
        self.assertEqual(vu["data"][0]["name"], "K1")

    def test_changer_de_harness_change_la_liste(self):
        """Le chat suit le sélecteur du QG — c'est toute la demande."""
        self.comptes.choisir_harness(self.un.id, "h2")
        vu = self.client.get("/v1/models", headers=self.signe()).json()
        self.assertEqual([m["id"] for m in vu["data"]], ["h2/k1"])

    def test_sans_jeton_signe_la_liste_n_est_pas_servie(self):
        """Une façade qui filtre par personne ne peut pas croire sur parole."""
        self.assertEqual(self.client.get("/v1/models").status_code, 401)

    def test_un_jeton_refuse_ferme_la_porte(self):
        entetes = {"X-OpenWebUI-User-Jwt": forger_jeton({"email": "un@exemple.test", "exp": 1})}
        self.assertEqual(self.client.get("/v1/models", headers=entetes).status_code, 401)

    def test_un_inconnu_du_magasin_ne_devient_pas_un_compte(self):
        """Un jeton valide désigne un compte, il n'en crée aucun."""
        reponse = self.client.get("/v1/models", headers=self.signe("jamais-vu@exemple.test"))
        self.assertEqual(reponse.status_code, 403)


class Relais(Bac):
    def test_un_kata_hors_du_harness_courant_est_refuse(self):
        """§3.4 — sinon le filtrage n'est qu'un confort d'affichage.

        Le harness courant est `h` : un fil rouvert sur `h2/k1`, ou un nom de
        modèle forgé à la main, ne doit pas passer parce qu'il est absent de la
        liste — il doit être refusé.
        """
        reponse = self.client.post(
            "/v1/chat/completions", json={"model": "h2/k1", "messages": []}, headers=self.signe()
        )
        self.assertEqual(reponse.status_code, 403)

    def test_un_kata_inconnu_du_harness_est_refuse(self):
        reponse = self.client.post(
            "/v1/chat/completions",
            json={"model": "h/fantome", "messages": []},
            headers=self.signe(),
        )
        self.assertEqual(reponse.status_code, 403)

    def test_sans_passerelle_le_service_le_dit(self):
        """503 et non 500 : rien n'est cassé, quelque chose n'est pas configuré."""
        reponse = self.client.post(
            "/v1/chat/completions", json={"model": "h/k1", "messages": []}, headers=self.signe()
        )
        self.assertEqual(reponse.status_code, 503)


if __name__ == "__main__":
    unittest.main()


class ModelesNus(unittest.TestCase):
    """Ce qui n'est le kata de personne, et que le chat appelle quand même."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        _ecrire_harness(racine / "h")

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        qui = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("h", qui.id)

        from kokaji.middleware.chat import Passerelle

        self.client = TestClient(
            creer_tous(
                charger_tous(racine), racine / "journal", self.comptes,
                secret_chat=SECRET,
                passerelle=Passerelle("http://nulle-part", nus=frozenset({"banc/persona"})),
            )
        )

    def signe(self) -> dict:
        return {"X-OpenWebUI-User-Jwt": forger_jeton({"email": "un@exemple.test", "exp": 2**31})}

    def test_un_modele_nu_declare_passe(self):
        """Sans lui, basculer le chat ferait échouer chaque titre de conversation.

        La passerelle du bac ne mène nulle part : franchir la frontière se
        constate donc à l'échec de la *connexion*, qui n'arrive qu'après. Un
        refus se serait vu avant, sans qu'aucune socket ne soit ouverte.
        """
        import httpx

        with self.assertRaises(httpx.ConnectError):
            self.client.post(
                "/v1/chat/completions",
                json={"model": "banc/persona", "messages": []},
                headers=self.signe(),
            )

    def test_un_modele_nu_non_declare_est_refuse(self):
        """C'est la déclaration qui ouvre, jamais l'oubli."""
        reponse = self.client.post(
            "/v1/chat/completions",
            json={"model": "banc/autre", "messages": []},
            headers=self.signe(),
        )
        self.assertEqual(reponse.status_code, 403)

    def test_un_modele_nu_ne_figure_pas_dans_la_liste(self):
        """Un rouage d'interface n'est pas une étape à pratiquer."""
        vu = self.client.get("/v1/models", headers=self.signe()).json()
        self.assertEqual([m["id"] for m in vu["data"]], ["h/k1"])
