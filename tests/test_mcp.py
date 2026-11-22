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

        # Un harness qui existe ailleurs, hors du dossier servi : cette instance
        # ne le connaît pas, et c'est de là qu'un clone a un sens.
        self.ailleurs = self.dossier / "ailleurs"
        adopter_textes({"ouvrir": "Tu ouvres."}, self.ailleurs, "venu", "Venu")

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
        # Inexprimable, pas seulement refusée : la surface ne l'**annonce** pas
        # non plus. Le jeton est celui de Un, qui porte l'administration — le
        # champ lisait le drapeau du compte et répondait donc `true` à un
        # appelant qui ne peut en aucun cas l'exercer, ce qui invitait au geste
        # refusé. Il répond désormais sur la qualité de l'appelant.
        #
        # Le même `assertFalse` existe au sabotage 1, mais avec le jeton de Deux,
        # qui n'est pas administrateur : il y passait à vide.
        self.assertFalse(lu["structuredContent"]["administration"])
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

    def test_la_surface_est_celle_du_4_2_ni_plus_ni_moins(self):
        """Le garde qui a manqué : trois outils du §4.2 sont restés non construits
        pendant que le tableau d'application disait le lot « appliqué en partie ».

        La liste est écrite ici à la main, depuis la RFC, et non dérivée de
        `OUTILS` : une liste qui se déduit du code ne peut pas constater qu'il
        manque quelque chose au code.
        """
        noms = {o["name"] for o in self.rpc(self.conception, "tools/list").json()["result"]["tools"]}
        self.assertEqual(noms, {
            # lire
            "harness_lister", "harness_lire", "coupe_voir", "depot_etat", "membres_lister",
            "proposition_eprouver",
            # créer
            "harness_creer", "harness_cloner", "harness_adopter", "etape_adoptee_ajouter",
            # concevoir
            "proposition_sceller", "depot_pousser", "depot_tirer",
            # posséder
            "harness_archiver", "membres_candidats", "membre_ajouter", "membre_retirer",
            "depot_enregistrer", "depot_desenregistrer",
        })

    def test_lier_un_depot_le_cloner_puis_delier(self):
        """Les trois derniers outils du §4.2, de bout en bout.

        Le dépôt nu naît de `depot_enregistrer`, sert de source à
        `harness_cloner`, et `depot_desenregistrer` n'efface que la ligne.
        """
        import os
        from unittest.mock import patch

        from kokaji.depot import est_depot_nu, lier

        # `adopter_textes` a déjà initié le dépôt du harness : on ne lui en
        # refait pas un, on lui donne un dépôt **nu** où se pousser.
        depots = self.dossier / "depots"
        depots.mkdir()

        with patch.dict(os.environ, {"KOKAJI_DEPOTS": str(depots)}):
            # Hors du dossier déclaré, le chemin se refuse, et aucune ligne ne s'écrit.
            hors = self.outil(self.conception, "depot_enregistrer",
                              harness="adopte", chemin="/tmp/ailleurs.git")
            self.assertTrue(hors["isError"], self.texte(hors))
            self.assertIsNone(self.comptes.depot("adopte"))

            lie = self.outil(self.conception, "depot_enregistrer",
                             harness="adopte", chemin="adopte.git")
            self.assertFalse(lie["isError"], self.texte(lie))
            self.assertTrue(est_depot_nu(depots / "adopte.git"))
            self.assertEqual(self.comptes.depot("adopte").chemin, str(depots / "adopte.git"))
            self.assertTrue(self.comptes.depot("adopte").pousser_au_scellement)

            # Un dépôt nu qui porte un harness que cette instance n'a pas :
            # c'est le cas d'usage de `harness_cloner` (RFC-012 D12.4).
            self.assertFalse((self.dossier / "venu").exists())
            lier(self.ailleurs / "venu", depots / "venu.git", "main")
            clone = self.outil(self.conception, "harness_cloner",
                               id="venu", chemin="venu.git")
            self.assertFalse(clone["isError"], self.texte(clone))
            self.assertEqual(self.comptes.acl("venu").proprietaire, self.un.id)
            # Le dépôt nu est enregistré d'office : on vient de là.
            self.assertEqual(self.comptes.depot("venu").chemin, str(depots / "venu.git"))
            lu = self.outil(self.conception, "harness_lire", harness="venu")
            self.assertFalse(lu["isError"], self.texte(lu))

            # L'id est celui du manifest cloné, pas un nom qu'on choisit : un id
            # qui ne correspond pas se refuse, en nommant les deux, et ne laisse
            # rien. Ce refus levait un TypeError avant ce lot.
            discordant = self.outil(self.conception, "harness_cloner",
                                    id="autre-nom", chemin="venu.git")
            self.assertTrue(discordant["isError"])
            self.assertIn("porte l'id « venu »", self.texte(discordant))
            self.assertIn("autre-nom", self.texte(discordant))
            self.assertFalse((self.dossier / "autre-nom").exists())

            # Délier n'efface que la ligne : le dépôt nu reste, et on relie.
            delie = self.outil(self.conception, "depot_desenregistrer", harness="adopte")
            self.assertFalse(delie["isError"], self.texte(delie))
            self.assertIsNone(self.comptes.depot("adopte"))
            self.assertTrue(est_depot_nu(depots / "adopte.git"))
            relie = self.outil(self.conception, "depot_enregistrer",
                               harness="adopte", chemin="adopte.git")
            self.assertFalse(relie["isError"], self.texte(relie))

    def test_sabotage_7_un_contributeur_n_enregistre_pas_de_depot(self):
        """Le rôle tient sous la portée : Deux a `conception`, mais il n'est que
        contributeur d'`adopte` — enregistrer est au propriétaire (RFC-004 §3)."""
        import os
        from unittest.mock import patch

        depots = self.dossier / "depots"
        depots.mkdir()
        with patch.dict(os.environ, {"KOKAJI_DEPOTS": str(depots)}):
            for outil in ("depot_enregistrer", "depot_desenregistrer"):
                with self.subTest(outil=outil):
                    arguments = {"harness": "adopte"}
                    if outil == "depot_enregistrer":
                        arguments["chemin"] = "adopte.git"
                    refus = self.outil(self.de_deux, outil, **arguments)
                    self.assertTrue(refus["isError"], self.texte(refus))
            self.assertIsNone(self.comptes.depot("adopte"))

    def test_sabotage_6_la_portee_lecture_ne_touche_pas_au_depot(self):
        noms = {o["name"] for o in self.rpc(self.lecture, "tools/list").json()["result"]["tools"]}
        self.assertIn("depot_etat", noms)
        for interdit in ("depot_enregistrer", "depot_desenregistrer", "harness_cloner"):
            self.assertNotIn(interdit, noms)
        refus = self.outil(self.lecture, "depot_desenregistrer", harness="adopte")
        self.assertTrue(refus["isError"])
        self.assertIn("aucun outil à ce nom", self.texte(refus))

    def test_sabotage_11_et_12_ni_pratique_ni_transfert(self):
        noms = {o["name"] for o in self.rpc(self.conception, "tools/list").json()["result"]["tools"]}
        self.assertFalse([n for n in noms if n.split("_")[0] == "ha"])
        for interdit in ("transcript", "sujet", "conversation", "transf", "courant", "admin"):
            self.assertFalse([n for n in noms if interdit in n], interdit)


if __name__ == "__main__":
    unittest.main()
