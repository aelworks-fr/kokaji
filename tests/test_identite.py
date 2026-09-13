"""Ce qui ne dépend d'aucun harness le prouve — RFC-005 §5.

Le test qui compte ici est celui du montage : les deux routeurs sont assemblés
**sans qu'aucun harness existe**, et servent quand même. Une dépendance qui
reviendrait par mégarde ne se lirait pas dans une revue — elle tomberait ici,
au montage, avant même la première requête.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kokaji.comptes import Comptes
from kokaji.middleware.identite import Identification, routeur_comptes, routeur_pages

MOT_DE_PASSE = "un-mot-de-passe-assez-long"


def _app(comptes: Comptes | None = None) -> FastAPI:
    """L'application des routes hors harness — aucun harness n'est chargé."""
    app = FastAPI()
    app.include_router(routeur_pages())
    app.include_router(routeur_comptes(Identification(comptes), comptes))
    return app


class SansHarness(unittest.TestCase):
    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.qui = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.client = TestClient(_app(self.comptes))

    def jeton(self) -> dict:
        reponse = self.client.post(
            "/session", json={"email": "un@exemple.test", "mot_de_passe": MOT_DE_PASSE}
        )
        return {"Authorization": f"Bearer {reponse.json()['jeton']}"}

    def test_les_pages_sont_servies_sans_harness(self):
        for chemin in ("/", "/qg", "/admin", "/qg/organic-styles.css"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.get(chemin).status_code, 200)

    def test_ouvrir_et_fermer_une_session(self):
        entetes = self.jeton()
        self.assertEqual(self.client.delete("/session", headers=entetes).status_code, 200)

    def test_le_profil_liste_les_harness_du_magasin_pas_ceux_du_disque(self):
        """Le profil parle d'autorat : il n'a jamais eu besoin d'un harness chargé."""
        self.comptes.enregistrer_harness("h", self.qui.id)
        vu = self.client.get("/profil", headers=self.jeton()).json()
        self.assertEqual(vu["harness"], [{"harness": "h", "role": "proprietaire"}])

    def test_changer_son_mot_de_passe(self):
        reponse = self.client.post(
            "/moi/mot-de-passe", json={"nouveau": "un-autre-assez-long"}, headers=self.jeton()
        )
        self.assertEqual(reponse.status_code, 200)


class SansMagasin(unittest.TestCase):
    """Sans comptes non plus : les pages restent, les gestes se taisent."""

    def setUp(self):
        self.client = TestClient(_app(None))

    def test_les_pages_tiennent_encore(self):
        self.assertEqual(self.client.get("/").status_code, 200)

    def test_la_session_n_est_pas_declaree(self):
        """Une porte absente vaut mieux qu'une porte qui répond 500."""
        self.assertEqual(self.client.post("/session", json={}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
