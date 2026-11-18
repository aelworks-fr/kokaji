"""Les jetons d'agent — RFC-021 lot A, D21.1 et D21.2.

Ce qui compte ici n'est pas qu'un jeton s'émette : c'est qu'il ne vaille rien
hors de ce qu'on lui a confié. Les sabotages 3 (jeton révoqué, expiré,
inconnu — un seul refus) et 5 (un jeton qui s'étend) du §7 sont les tests
qui portent ce lot ; le reste prouve qu'on n'a rien gardé qu'on ne devait.
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI
from fastapi.testclient import TestClient

from kokaji.cli import main
from kokaji.comptes import CONCEPTION, LECTURE, AclInvalide, Comptes, IdentiteInconnue, transvaser
from kokaji.middleware.identite import Identification, routeur_comptes

MOT_DE_PASSE = "un-mot-de-passe-assez-long"


class Magasin(unittest.TestCase):
    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.qui = self.comptes.creer_utilisateur("Une", "une@exemple.test", MOT_DE_PASSE)
        self.autre = self.comptes.creer_utilisateur("Autre", "autre@exemple.test", MOT_DE_PASSE)

    def test_le_jeton_designe_son_compte_et_dit_sa_portee(self):
        jeton, emis = self.comptes.emettre_jeton(self.qui.id, "l'agent du poste", CONCEPTION)
        self.assertTrue(jeton.startswith("kkj_"))
        qui, lu = self.comptes.par_jeton_agent(jeton)
        self.assertEqual(qui.id, self.qui.id)
        self.assertEqual(lu.portee, CONCEPTION)
        self.assertEqual(lu.id, emis.id)
        self.assertIsNotNone(lu.dernier_usage_le)

    def test_le_magasin_ne_garde_pas_le_jeton(self):
        jeton, _ = self.comptes.emettre_jeton(self.qui.id, "agent", LECTURE)
        lignes = self.comptes._db.execute("SELECT * FROM jetons_agent").fetchall()
        self.assertEqual(len(lignes), 1)
        self.assertNotIn(jeton, [str(v) for v in lignes[0].values()])

    def test_sabotage_3_revoque_expire_inconnu_un_seul_refus(self):
        revoque, emis = self.comptes.emettre_jeton(self.qui.id, "révoqué", LECTURE)
        self.comptes.revoquer_jeton(self.qui.id, emis.id)
        expire, emis = self.comptes.emettre_jeton(self.qui.id, "expiré", LECTURE)
        hier = (datetime.now(UTC) - timedelta(days=1)).isoformat()
        self.comptes._db.execute(
            "UPDATE jetons_agent SET expire_le = ? WHERE id = ?", (hier, emis.id)
        )
        messages = set()
        for jeton in (revoque, expire, "kkj_" + "x" * 43, "pas-un-jeton", ""):
            with self.assertRaises(IdentiteInconnue) as refus:
                self.comptes.par_jeton_agent(jeton)
            messages.add(str(refus.exception))
        self.assertEqual(len(messages), 1, messages)

    def test_un_jeton_sans_nom_sans_portee_ou_sans_echeance_ne_s_emet_pas(self):
        for nom, portee, jours in (
            ("", LECTURE, 90),
            ("agent", "administration", 90),
            ("agent", LECTURE, 0),
            ("agent", LECTURE, 366),
        ):
            with self.subTest(nom=nom, portee=portee, jours=jours), self.assertRaises(AclInvalide):
                self.comptes.emettre_jeton(self.qui.id, nom, portee, jours)

    def test_on_ne_revoque_pas_le_jeton_d_un_autre(self):
        jeton, emis = self.comptes.emettre_jeton(self.autre.id, "le sien", LECTURE)
        with self.assertRaises(IdentiteInconnue):
            self.comptes.revoquer_jeton(self.qui.id, emis.id)
        self.comptes.par_jeton_agent(jeton)  # il vaut toujours

    def test_la_revocation_se_lit_et_ne_s_efface_pas(self):
        _, emis = self.comptes.emettre_jeton(self.qui.id, "agent", LECTURE)
        self.comptes.revoquer_jeton(self.qui.id, emis.id)
        (lu,) = self.comptes.jetons_de(self.qui.id)
        self.assertIsNotNone(lu.revoque_le)

    def test_le_transvasement_emporte_les_jetons(self):
        jeton, _ = self.comptes.emettre_jeton(self.qui.id, "agent", LECTURE)
        vers = Comptes()
        self.addCleanup(vers.fermer)
        transvaser(self.comptes, vers)
        self.assertEqual(vers.par_jeton_agent(jeton)[0].id, self.qui.id)


def _client(comptes: Comptes) -> TestClient:
    app = FastAPI()
    app.include_router(routeur_comptes(Identification(comptes, entete_identite="Remote-Email"), comptes))
    return TestClient(app)


class Routes(unittest.TestCase):
    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.qui = self.comptes.creer_utilisateur("Une", "une@exemple.test", MOT_DE_PASSE)
        self.client = _client(self.comptes)
        session = self.comptes.ouvrir_session("une@exemple.test", MOT_DE_PASSE)
        self.humain = {"Authorization": f"Bearer {session}"}

    def _emettre(self, **corps) -> dict:
        r = self.client.post(
            "/moi/jetons", json={"nom": "agent", "portee": "conception", **corps}, headers=self.humain
        )
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_emettre_lister_revoquer(self):
        emis = self._emettre()
        self.assertTrue(emis["jeton"].startswith("kkj_"))
        liste = self.client.get("/moi/jetons", headers=self.humain).json()["jetons"]
        self.assertEqual([j["id"] for j in liste], [emis["id"]])
        self.assertNotIn("jeton", liste[0])
        self.assertNotIn("empreinte", liste[0])
        r = self.client.delete(f"/moi/jetons/{emis['id']}", headers=self.humain)
        self.assertIsNotNone(r.json()["revoque_le"])

    def test_une_portee_inconnue_est_refusee(self):
        r = self.client.post(
            "/moi/jetons", json={"nom": "agent", "portee": "administration"}, headers=self.humain
        )
        self.assertEqual(r.status_code, 400)

    def test_sabotage_5_un_jeton_ne_cree_jamais_un_jeton(self):
        agent = {"Authorization": f"Bearer {self._emettre()['jeton']}"}
        r = self.client.post("/moi/jetons", json={"nom": "fils", "portee": "conception"}, headers=agent)
        self.assertEqual(r.status_code, 401)
        self.assertEqual(len(self.comptes.jetons_de(self.qui.id)), 1)
        self.assertEqual(self.client.get("/moi/jetons", headers=agent).status_code, 401)

    def test_un_jeton_d_agent_ne_vaut_rien_hors_de_sa_surface(self):
        """D21.2 — ni le profil, ni le changement de mot de passe ; et un
        en-tête de portail glissé à côté ne lui prête pas d'identité."""
        jeton = self._emettre()["jeton"]
        agent = {"Authorization": f"Bearer {jeton}", "Remote-Email": "une@exemple.test"}
        self.assertEqual(self.client.get("/profil", headers=agent).status_code, 401)
        r = self.client.post("/moi/mot-de-passe", json={"nouveau": "x" * 20}, headers=agent)
        self.assertEqual(r.status_code, 401)


class Commande(unittest.TestCase):
    def test_creer_lister_revoquer(self):
        with tempfile.TemporaryDirectory() as dossier:
            magasin = Path(dossier) / "comptes.db"
            comptes = Comptes(magasin)
            comptes.creer_utilisateur("Une", "une@exemple.test", MOT_DE_PASSE)
            comptes.fermer()
            base = ["jeton", "creer", "--comptes", str(magasin), "--email", "une@exemple.test"]

            sortie = io.StringIO()
            with redirect_stdout(sortie), redirect_stderr(io.StringIO()):
                code = main([*base, "--nom", "agent", "--portee", "lecture"])
            self.assertEqual(code, 0)
            jeton = sortie.getvalue().strip()
            self.assertTrue(jeton.startswith("kkj_"))

            comptes = Comptes(magasin)
            self.addCleanup(comptes.fermer)
            qui, emis = comptes.par_jeton_agent(jeton)
            self.assertEqual(qui.email, "une@exemple.test")

            liste = io.StringIO()
            with redirect_stdout(liste):
                main(["jeton", "lister", "--comptes", str(magasin), "--email", "une@exemple.test"])
            self.assertIn(emis.id, liste.getvalue())
            self.assertNotIn(jeton, liste.getvalue())

            with redirect_stdout(io.StringIO()):
                main(["jeton", "revoquer", "--comptes", str(magasin),
                      "--email", "une@exemple.test", "--id", emis.id])
            with self.assertRaises(IdentiteInconnue):
                comptes.par_jeton_agent(jeton)


if __name__ == "__main__":
    unittest.main()
