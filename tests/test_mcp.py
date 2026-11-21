"""La surface de l'agent — RFC-022, lots C et D, et le critère du §7.

Harness purement structurels (§0) : deux harness adoptés, deux personnes.
Ce qui compte ici n'est pas qu'un outil réponde : c'est que le jeton soit la
seule identité qui vaille sur `/mcp`, qu'il soit plus étroit que la personne,
et que le geste reste celui de la route — mêmes droits, mêmes refus.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from kokaji.adoption import adopter_textes
from kokaji.comptes import CONCEPTION, LECTURE, Comptes
from kokaji.hds import charger_valides
from kokaji.middleware.aiguilleur import creer_tous

MOT_DE_PASSE = "un-mot-de-passe-assez-long"
PROPOSITION = {"kata": [
    {"id": "ouvrir", "produit": [{"ouvrir.sujet": "en_pause"}]},
    {"id": "relire", "amont": ["ouvrir"], "herite": ["ouvrir.sujet"]},
]}


class Surface(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.dossier = Path(self._tmp.name)
        for identifiant in ("adopte", "autre"):
            adopter_textes(
                {"ouvrir": "Tu ouvres.", "relire": "Tu relis."},
                self.dossier, identifiant, identifiant.capitalize(),
            )

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        # Un est administrateur de l'exploitation : D22.3 se prouve sur lui.
        self.un = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE, admin=True)
        self.deux = self.comptes.creer_utilisateur("Deux", "deux@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("adopte", self.un.id)
        self.comptes.enregistrer_harness("autre", self.deux.id)
        self.comptes.ajouter_contributeur("adopte", self.deux.id)

        charges, _ = charger_valides(self.dossier)
        self.client = TestClient(
            creer_tous(charges, self.dossier / "journal", self.comptes,
                       entete_identite="Remote-Email", dossier_harness=self.dossier)
        )
        self.conception, _ = self.comptes.emettre_jeton(self.un.id, "l'agent du poste", CONCEPTION)
        self.lecture, _ = self.comptes.emettre_jeton(self.un.id, "le relecteur", LECTURE)
        self.de_deux, _ = self.comptes.emettre_jeton(self.deux.id, "l'agent de Deux", CONCEPTION)

    def rpc(self, jeton: str | None, methode: str, params: dict | None = None, **entetes):
        if jeton:
            entetes["Authorization"] = f"Bearer {jeton}"
        return self.client.post(
            "/mcp", json={"jsonrpc": "2.0", "id": 1, "method": methode, "params": params or {}},
            headers=entetes,
        )

    def outil(self, jeton: str, outil: str, **arguments) -> dict:
        reponse = self.rpc(jeton, "tools/call", {"name": outil, "arguments": arguments})
        self.assertEqual(reponse.status_code, 200, reponse.text)
        return reponse.json()["result"]

    def texte(self, resultat: dict) -> str:
        return resultat["content"][0]["text"]

    # --- le protocole ---------------------------------------------------------

    def test_initialiser_puis_lister_les_outils(self):
        init = self.rpc(self.conception, "initialize", {"protocolVersion": "2025-06-18"}).json()
        self.assertEqual(init["result"]["protocolVersion"], "2025-06-18")
        self.assertEqual(init["result"]["serverInfo"]["name"], "kokaji")
        noms = {o["name"] for o in self.rpc(self.conception, "tools/list").json()["result"]["tools"]}
        self.assertIn("proposition_sceller", noms)
        self.assertIn("harness_lire", noms)
        notification = self.client.post(
            "/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers={"Authorization": f"Bearer {self.conception}"},
        )
        self.assertEqual(notification.status_code, 202)

    # --- le nominal du §7 -----------------------------------------------------

    def test_nominal_lire_eprouver_sceller_au_nom_du_compte(self):
        courant_avant = self.comptes.harness_courant(self.un.id)
        lu = self.outil(self.conception, "harness_lire", harness="adopte")
        self.assertFalse(lu["isError"], self.texte(lu))
        self.assertEqual(lu["structuredContent"]["harness"]["id"], "adopte")

        epreuve = self.outil(self.conception, "proposition_eprouver",
                             harness="adopte", proposition=PROPOSITION)
        self.assertTrue(epreuve["structuredContent"]["tient"], self.texte(epreuve))

        scelle = self.outil(self.conception, "proposition_sceller", harness="adopte",
                            proposition=PROPOSITION, motif="premier contrat")
        self.assertFalse(scelle["isError"], self.texte(scelle))
        self.assertEqual(scelle["structuredContent"]["auteur"], "Un")
        self.assertEqual(scelle["structuredContent"]["via"], "mcp : l'agent du poste")

        journal = (self.dossier / "adopte" / "scellements.jsonl").read_text(encoding="utf-8")
        derniere = json.loads(journal.strip().splitlines()[-1])
        self.assertEqual((derniere["auteur"], derniere["via"]), ("Un", "mcp : l'agent du poste"))
        # Sabotage 9 — le harness courant n'a pas bougé.
        self.assertEqual(self.comptes.harness_courant(self.un.id), courant_avant)

    def test_semer_un_harness_neuf(self):
        ne = self.outil(self.conception, "harness_creer", id="neuf", nom="Neuf")
        self.assertFalse(ne["isError"], self.texte(ne))
        self.assertEqual(self.comptes.acl("neuf").proprietaire, self.un.id)
        lu = self.outil(self.conception, "harness_lire", harness="neuf")
        self.assertFalse(lu["isError"], self.texte(lu))

    # --- les sabotages du §7 --------------------------------------------------

    def test_sabotage_1_l_en_tete_du_portail_ne_vaut_rien_sur_mcp(self):
        sans_jeton = self.rpc(None, "tools/list", **{"Remote-Email": "un@exemple.test"})
        self.assertEqual(sans_jeton.status_code, 401)
        # Avec le jeton de Deux et l'en-tête de Un : c'est Deux qui agit.
        lu = self.rpc(self.de_deux, "tools/call",
                      {"name": "harness_lister", "arguments": {}},
                      **{"Remote-Email": "un@exemple.test"}).json()["result"]
        ids = {h["id"] for h in lu["structuredContent"]["harness"]}
        self.assertEqual(ids, {"adopte", "autre"})
        self.assertFalse(lu["structuredContent"]["administration"])

    def test_sabotage_1_bis_une_session_ne_vaut_rien_sur_mcp(self):
        session = self.comptes.ouvrir_session("un@exemple.test", MOT_DE_PASSE)
        self.assertEqual(self.rpc(session, "tools/list").status_code, 401)

    def test_sabotage_2_le_jeton_ne_vaut_rien_hors_de_mcp(self):
        agent = {"Authorization": f"Bearer {self.conception}"}
        for chemin in ("/conception", "/harness", "/profil", "/admin/donnees"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.get(chemin, headers=agent).status_code, 401)

    def test_sabotage_3_un_jeton_revoque_est_refuse(self):
        (emis,) = [j for j in self.comptes.jetons_de(self.un.id) if j.nom == "le relecteur"]
        self.comptes.revoquer_jeton(self.un.id, emis.id)
        self.assertEqual(self.rpc(self.lecture, "tools/list").status_code, 401)

    def test_sabotage_4_l_administration_est_inexprimable(self):
        lu = self.outil(self.conception, "harness_lister")
        self.assertFalse(lu["isError"], self.texte(lu))
        # La qualité est plafonnée : un geste de service d'administration,
        # appelé par la porte de l'agent, se refuse. Aucun outil n'y mène ;
        # on le prouve sur l'aiguilleur lui-même, dans la portée de l'agent.
        from types import SimpleNamespace

        from kokaji.middleware.identite import AGENT, Identification

        requete = SimpleNamespace(headers={}, cookies={}, scope={AGENT: (self.un, None)})
        self.assertEqual(Identification(self.comptes).qualite(requete), "compte")

    def test_sabotage_6_la_portee_lecture_ne_scelle_pas(self):
        noms = {o["name"] for o in self.rpc(self.lecture, "tools/list").json()["result"]["tools"]}
        self.assertNotIn("proposition_sceller", noms)
        self.assertIn("proposition_eprouver", noms)
        refus = self.outil(self.lecture, "proposition_sceller", harness="adopte",
                           proposition=PROPOSITION)
        self.assertTrue(refus["isError"])
        self.assertFalse((self.dossier / "adopte" / "scellements.jsonl").exists())
        epreuve = self.outil(self.lecture, "proposition_eprouver",
                             harness="adopte", proposition=PROPOSITION)
        self.assertFalse(epreuve["isError"], self.texte(epreuve))

    def test_sabotage_7_le_role_tient_sous_la_portee(self):
        refus = self.outil(self.de_deux, "harness_archiver", harness="adopte")
        self.assertTrue(refus["isError"])
        self.assertIn("403", self.texte(refus))
        self.assertIsNone(self.comptes.archive_le("adopte"))

    def test_sabotage_8_le_harness_d_autrui_n_existe_pas(self):
        autrui = self.outil(self.conception, "harness_lire", harness="autre")
        absent = self.outil(self.conception, "harness_lire", harness="nulle-part")
        self.assertTrue(autrui["isError"] and absent["isError"])
        self.assertEqual(
            self.texte(autrui).replace("autre", "X"), self.texte(absent).replace("nulle-part", "X")
        )

    def test_sabotage_10_on_ne_signe_pas_pour_un_autre(self):
        refus = self.outil(self.conception, "proposition_sceller", harness="adopte",
                           proposition=PROPOSITION, auteur="Deux")
        self.assertTrue(refus["isError"])
        self.assertIn("auteur", self.texte(refus))

    def test_sabotage_11_et_12_ni_pratique_ni_transfert(self):
        noms = {o["name"] for o in self.rpc(self.conception, "tools/list").json()["result"]["tools"]}
        self.assertFalse([n for n in noms if n.split("_")[0] == "ha"])
        for interdit in ("transcript", "sujet", "conversation", "transf", "courant", "admin"):
            self.assertFalse([n for n in noms if interdit in n], interdit)


if __name__ == "__main__":
    unittest.main()
