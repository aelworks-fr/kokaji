"""L'aiguilleur remet chaque requête au harness de son appelant — RFC-005 §5.

Harness purement structurels (§0) : aucun nom de domaine ici.

Le sabotage qui compte est le dernier : deux personnes de harness différents
interrogent le même chemin et reçoivent chacune le sien. C'est lui qui prouve
que le harness est une propriété de la personne et non du déploiement.
"""

from __future__ import annotations

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

MOT_DE_PASSE = "un-mot-de-passe-assez-long"


class Bac(unittest.TestCase):
    """Deux harness servis, deux personnes, une seule porte."""

    ids = ("h", "h2")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)

        for identifiant in self.ids:
            manifest = MINIMAL.replace("id: h\n", f"id: {identifiant}\n")
            _ecrire_harness(racine / identifiant, manifest)

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.un = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.deux = self.comptes.creer_utilisateur("Deux", "deux@exemple.test", MOT_DE_PASSE)

        self.client = TestClient(
            creer_tous(charger_tous(racine), racine / "journal", self.comptes)
        )

    def cle(self, qui) -> dict:
        courriel = {self.un.id: "un", self.deux.id: "deux"}[qui.id]
        reponse = self.client.post(
            "/session",
            json={"email": f"{courriel}@exemple.test", "mot_de_passe": MOT_DE_PASSE},
        )
        return {"Authorization": f"Bearer {reponse.json()['jeton']}"}


class Aiguillage(Bac):
    def test_chacun_est_servi_par_son_harness(self):
        """Le sabotage central : même chemin, deux réponses, aucune fuite."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.deux.id)

        vu_un = self.client.get("/definition", headers=self.cle(self.un)).json()
        vu_deux = self.client.get("/definition", headers=self.cle(self.deux)).json()
        self.assertEqual(vu_un["harness"], "h")
        self.assertEqual(vu_deux["harness"], "h2")

    def test_changer_de_harness_courant_change_la_reponse(self):
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.un.id)
        entetes = self.cle(self.un)

        self.comptes.choisir_harness(self.un.id, "h2")
        self.assertEqual(self.client.get("/definition", headers=entetes).json()["harness"], "h2")

        self.comptes.choisir_harness(self.un.id, "h")
        self.assertEqual(self.client.get("/definition", headers=entetes).json()["harness"], "h")

    def test_sans_harness_courant_le_refus_ne_nomme_personne(self):
        """Lister les harness servis les rendrait découvrables (RFC-004 §7)."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.un.id)
        reponse = self.client.get("/definition", headers=self.cle(self.un))
        self.assertEqual(reponse.status_code, 409)
        self.assertNotIn("h2", reponse.text)

    def test_un_harness_du_magasin_absent_du_service_se_dit(self):
        """Panne d'exploitation, pas refus de droit : on la nomme."""
        self.comptes.enregistrer_harness("ailleurs", self.un.id)
        reponse = self.client.get("/definition", headers=self.cle(self.un))
        self.assertEqual(reponse.status_code, 404)
        self.assertIn("ailleurs", reponse.json()["detail"])

    def test_les_routes_communes_ne_demandent_aucun_harness(self):
        """Sinon il faudrait choisir un harness pour avoir le droit de se connecter."""
        for chemin in ("/", "/qg", "/qg/organic-styles.css"):
            with self.subTest(chemin=chemin):
                self.assertEqual(self.client.get(chemin).status_code, 200)
        self.assertEqual(self.client.get("/profil", headers=self.cle(self.un)).status_code, 200)

    def test_un_jeton_invalide_est_refuse_avant_tout_aiguillage(self):
        reponse = self.client.get("/definition", headers={"Authorization": "Bearer faux"})
        self.assertEqual(reponse.status_code, 401)


class Exploitation(Bac):
    """Ce qui regarde le service entier ne passe pas par un harness."""

    def test_la_sante_repond_sans_session(self):
        """La régression qu'a produite l'aiguilleur, et qui ne se voyait pas.

        Servie depuis un harness, `/sante` exigeait d'abord d'identifier
        l'appelant pour savoir *quel* harness lui répondre : elle répondait 401
        à un moniteur. Une sonde de santé qui demande à se connecter ne mesure
        plus rien.
        """
        reponse = self.client.get("/sante")
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()["partage"])
        self.assertEqual(reponse.json()["harness_servis"], 2)

    def test_la_sante_ne_nomme_aucun_harness(self):
        """Ouverte : les énumérer les rendrait découvrables (RFC-004 §7)."""
        corps = self.client.get("/sante").json()
        self.assertEqual(corps["harness_servis"], 2)
        # Sur les valeurs et non sur le texte brut : `journal` porte un dossier
        # temporaire au nom tiré au sort, où « h2 » finit par apparaître une
        # fois sur deux cents. Le test tombait alors sans rien dire du service.
        self.assertNotIn("h2", [v for c, v in corps.items() if c != "journal"])

    def test_l_offre_dit_si_l_on_administre(self):
        """Sans ce mot, la page ne peut pas mener à `/admin` sans le proposer à tous."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.assertFalse(self.client.get("/harness", headers=self.cle(self.un)).json()
                         ["administration"])

        self.comptes.promouvoir(self.un.id)
        self.assertTrue(self.client.get("/harness", headers=self.cle(self.un)).json()
                        ["administration"])

    def test_l_administration_voit_tous_les_harness(self):
        """Son métier est de réparer : lui n'en montrer qu'un la rendrait inutile."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.deux.id)
        self.comptes.promouvoir(self.un.id)

        vu = self.client.get("/admin/donnees", headers=self.cle(self.un)).json()
        self.assertEqual([h["id"] for h in vu["harness"]], ["h", "h2"])
        self.assertEqual(vu["harness"][1]["autorat"]["proprietaire"], self.deux.id)

    def test_l_administration_repond_sans_harness_courant(self):
        """Deux harness, aucun choisi : l'admin doit passer quand même."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.un.id)
        self.comptes.promouvoir(self.un.id)
        reponse = self.client.get("/admin/donnees", headers=self.cle(self.un))
        self.assertEqual(reponse.status_code, 200)

    def test_un_non_admin_n_administre_pas(self):
        self.assertEqual(
            self.client.get("/admin/donnees", headers=self.cle(self.deux)).status_code, 403
        )

    def test_un_harness_sans_proprietaire_se_dit_sans_autorat(self):
        self.comptes.promouvoir(self.un.id)
        vu = self.client.get("/admin/donnees", headers=self.cle(self.un)).json()
        self.assertIsNone(vu["harness"][0]["autorat"])


class Selecteur(Bac):
    """RFC-005 §2 — ce que le QG offre à choisir, et ce qu'il tait."""

    def test_la_liste_ne_contient_que_les_miens(self):
        """Un harness où je n'ai aucun rôle n'est pas proposé — ni révélé."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.deux.id)
        vu = self.client.get("/harness", headers=self.cle(self.un)).json()
        self.assertEqual([h["id"] for h in vu["harness"]], ["h"])

    def test_la_liste_porte_le_nom_et_le_role(self):
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.ajouter_contributeur("h", self.deux.id)
        vu = self.client.get("/harness", headers=self.cle(self.deux)).json()
        self.assertEqual(vu["harness"][0]["nom"], "H")
        self.assertEqual(vu["harness"][0]["role"], "contributeur")

    def test_un_harness_mien_mais_non_servi_n_est_pas_propose(self):
        """Le proposer mènerait à un choix qui ne peut pas aboutir."""
        self.comptes.enregistrer_harness("ailleurs", self.un.id)
        vu = self.client.get("/harness", headers=self.cle(self.un)).json()
        self.assertEqual(vu["harness"], [])

    def test_choisir_puis_relire(self):
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.un.id)
        entetes = self.cle(self.un)

        pose = self.client.post("/harness/courant", json={"id_harness": "h2"}, headers=entetes)
        self.assertEqual(pose.json()["courant"], "h2")
        self.assertEqual(self.client.get("/harness", headers=entetes).json()["courant"], "h2")

    def test_choisir_un_harness_ou_l_on_est_etranger_est_refuse(self):
        """Le magasin tranche : le sélecteur n'est pas le seul garde."""
        self.comptes.enregistrer_harness("h2", self.deux.id)
        reponse = self.client.post(
            "/harness/courant", json={"id_harness": "h2"}, headers=self.cle(self.un)
        )
        self.assertEqual(reponse.status_code, 403)

    def test_choisir_un_harness_non_servi_est_refuse(self):
        self.comptes.enregistrer_harness("ailleurs", self.un.id)
        reponse = self.client.post(
            "/harness/courant", json={"id_harness": "ailleurs"}, headers=self.cle(self.un)
        )
        self.assertEqual(reponse.status_code, 404)

    def test_effacer_le_choix_rend_au_defaut(self):
        self.comptes.enregistrer_harness("h", self.un.id)
        entetes = self.cle(self.un)
        self.client.post("/harness/courant", json={"id_harness": "h"}, headers=entetes)
        rendu = self.client.post("/harness/courant", json={"id_harness": None}, headers=entetes)
        self.assertEqual(rendu.json()["courant"], "h")  # seul harness mien : le défaut

    def test_le_choix_commande_l_aiguillage(self):
        """Le sélecteur et l'aiguilleur lisent le même champ, ou l'un ment."""
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.enregistrer_harness("h2", self.un.id)
        entetes = self.cle(self.un)
        self.client.post("/harness/courant", json={"id_harness": "h2"}, headers=entetes)
        self.assertEqual(
            self.client.get("/definition", headers=entetes).json()["harness"], "h2"
        )


class UnSeulHarness(Bac):
    """Une installation mono-harness ne doit rien avoir à choisir."""

    ids = ("h",)

    def test_le_seul_harness_sert_sans_qu_on_ait_rien_choisi(self):
        """Aucun `choisir_harness` ici : l'installation d'hier marche telle quelle."""
        self.comptes.enregistrer_harness("h", self.un.id)
        reponse = self.client.get("/definition", headers=self.cle(self.un))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["harness"], "h")

    def test_un_non_membre_reste_refuse_par_le_harness(self):
        """L'aiguillage aboutit, puis l'ACL tranche — sabotage n°2 du RFC-004 §8.

        L'aiguilleur ne pèse aucun droit : il désigne une application, il n'en
        ouvre pas la porte. Confondre les deux ferait du repli mono-harness une
        dérobade.
        """
        self.comptes.enregistrer_harness("h", self.deux.id)
        reponse = self.client.get("/definition", headers=self.cle(self.un))
        self.assertEqual(reponse.status_code, 403)


if __name__ == "__main__":
    unittest.main()


class EtapeAdoptee(Bac):
    """La route qui fait grandir un harness adopté — et remonte l'application."""

    def setUp(self):
        super().setUp()
        from kokaji.adoption import adopter_textes

        self.dossier = Path(self._tmp.name)
        adopter_textes({"ouvrir": "Tu ouvres."}, self.dossier, "adopte", "Adopté")
        self.comptes.enregistrer_harness("adopte", self.un.id)
        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous

        charges, _ = charger_valides(self.dossier)
        self.client = TestClient(
            creer_tous(charges, self.dossier / "journal", self.comptes,
                       dossier_harness=self.dossier)
        )

    def ajouter(self, qui, **corps):
        defauts = {"nom": "relire", "texte": "Tu relis."}
        return self.client.post(
            "/harness/adopte/etape-adoptee", json={**defauts, **corps},
            headers=self.cle(qui),
        )

    def test_l_etape_entre_et_la_definition_servie_suit(self):
        vu = self.ajouter(self.un)
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertEqual(vu.json()["kata"], ["ouvrir", "relire"])
        # Sans remontage, le design servirait l'ancienne forme en silence.
        self.client.post("/harness/courant", json={"id_harness": "adopte"},
                         headers=self.cle(self.un))
        vu = self.client.get("/conception", headers=self.cle(self.un)).json()
        self.assertEqual([k["id"] for k in vu["kata"]], ["ouvrir", "relire"])

    def test_un_etranger_n_ajoute_rien(self):
        self.assertEqual(self.ajouter(self.deux).status_code, 403)

    def test_un_harness_natif_repond_409(self):
        self.comptes.enregistrer_harness("h", self.un.id)
        refus = self.client.post(
            "/harness/h/etape-adoptee", json={"nom": "x", "texte": "y"},
            headers=self.cle(self.un),
        )
        self.assertEqual(refus.status_code, 409)
        self.assertIn("module design", refus.json()["detail"])


class LeScellementSeSert(Bac):
    """Ce que le scellement écrit, la définition servie le montre — sans redémarrer.

    Le contraire est arrivé : un scellement de contrats parfaitement écrit au
    manifest, et le module design qui rechargeait l'instantané du démarrage —
    « il n'est jamais persisté », disait à raison celui qui regardait l'écran.
    """

    def setUp(self):
        super().setUp()
        from kokaji.adoption import adopter_textes

        self.dossier = Path(self._tmp.name)
        adopter_textes(
            {"ouvrir": "Tu ouvres.", "relire": "Tu relis."},
            self.dossier, "adopte", "Adopté",
        )
        self.comptes.enregistrer_harness("adopte", self.un.id)
        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous

        charges, _ = charger_valides(self.dossier)
        self.client = TestClient(
            creer_tous(charges, self.dossier / "journal", self.comptes,
                       dossier_harness=self.dossier)
        )
        self.client.post("/harness/courant", json={"id_harness": "adopte"},
                         headers=self.cle(self.un))

    def test_les_contrats_scelles_se_lisent_aussitot(self):
        scelle = self.client.post(
            "/conception/scellement",
            json={"proposition": {"kata": [
                {"id": "ouvrir", "produit": [{"ouvrir.sujet": "en_pause"}]},
                {"id": "relire", "amont": ["ouvrir"], "herite": ["ouvrir.sujet"]},
            ]}, "auteur": "Un"},
            headers=self.cle(self.un),
        )
        self.assertEqual(scelle.status_code, 200, scelle.text)

        vu = self.client.get("/conception", headers=self.cle(self.un)).json()
        ouvre = next(k for k in vu["kata"] if k["id"] == "ouvrir")
        relit = next(k for k in vu["kata"] if k["id"] == "relire")
        self.assertEqual(ouvre["produit"], [{"champ": "ouvrir.sujet", "statut": "en_pause"}])
        self.assertEqual([h["champ"] for h in relit["herite"]], ["ouvrir.sujet"])
        self.assertEqual(vu["harness"]["version"], "1.0.0")

    def test_la_trempe_scellee_se_lit_aussitot(self):
        """Le geste du forgeron : ajouter un check et un critère, sceller, relire."""
        scelle = self.client.post(
            "/conception/scellement",
            json={"proposition": {"trempe": {
                "checks_session": [
                    {"id": "une-question", "type": "regex-par-bloc", "motif": "\\?", "maximum": 1}
                ],
                "grille_judge": [
                    {"id": "clarte", "question": "L'échange est-il clair ?", "echelle": "1-5"}
                ],
            }}, "auteur": "Un"},
            headers=self.cle(self.un),
        )
        self.assertEqual(scelle.status_code, 200, scelle.text)

        vu = self.client.get("/conception", headers=self.cle(self.un)).json()["trempe"]
        self.assertEqual(vu["checks_session"][0]["id"], "une-question")
        self.assertEqual(vu["grille_judge"],
                         [{"id": "clarte", "question": "L'échange est-il clair ?",
                           "echelle": "1-5"}])

    def test_une_echelle_fautive_refuse_le_scellement_en_le_nommant(self):
        refus = self.client.post(
            "/conception/scellement",
            json={"proposition": {"trempe": {"grille_judge": [
                {"id": "clarte", "question": "Q", "echelle": "5-1"}
            ]}}, "auteur": "Un"},
            headers=self.cle(self.un),
        )
        self.assertEqual(refus.status_code, 409, refus.text)
        self.assertIn("bornes croissantes", refus.json()["detail"])


class Rejoindre(Bac):
    """L'administration s'ouvre un harness — soi seulement, à découvert."""

    def setUp(self):
        super().setUp()
        self.comptes.enregistrer_harness("h", self.deux.id)
        self.comptes.promouvoir(self.un.id)

    def test_l_admin_devient_co_auteur_et_le_selecteur_suit(self):
        vu = self.client.post("/admin/harness/h/rejoindre", headers=self.cle(self.un))
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertEqual(vu.json()["role"], "contributeur")
        offre = self.client.get("/harness", headers=self.cle(self.un)).json()
        self.assertIn("h", [x["id"] for x in offre["harness"]])

    def test_jamais_proprietaire_et_rien_n_est_retire(self):
        self.client.post("/admin/harness/h/rejoindre", headers=self.cle(self.un))
        self.assertEqual(self.comptes.acl("h").proprietaire, self.deux.id)

    def test_un_non_admin_ne_se_l_ouvre_pas(self):
        refus = self.client.post("/admin/harness/h/rejoindre", headers=self.cle(self.deux))
        self.assertEqual(refus.status_code, 403)

    def test_un_harness_inconnu_repond_404(self):
        refus = self.client.post("/admin/harness/nulle-part/rejoindre", headers=self.cle(self.un))
        self.assertEqual(refus.status_code, 404)

    def test_le_geste_est_idempotent_et_ne_degrade_pas_un_proprietaire(self):
        """Le modèle est idempotent, et un propriétaire ne devient pas contributeur."""
        self.comptes.transferer("h", self.un.id, garder_ancien=False)
        vu = self.client.post("/admin/harness/h/rejoindre", headers=self.cle(self.un))
        self.assertEqual(vu.status_code, 200)
        self.assertEqual(vu.json()["role"], "proprietaire")
        self.assertEqual(self.comptes.acl("h").contributeurs, ())

    def test_la_page_sait_qui_regarde(self):
        vu = self.client.get("/admin/donnees", headers=self.cle(self.un)).json()
        self.assertEqual(vu["moi"], self.un.id)


class Adoption(Bac):
    """RFC-008 N0 par la page — la troisième voie de la création."""

    def setUp(self):
        super().setUp()
        self.dossier = Path(self._tmp.name)
        self.comptes.enregistrer_harness("h", self.un.id)
        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous

        charges, _ = charger_valides(self.dossier)
        self.client = TestClient(
            creer_tous(
                charges, self.dossier / "journal", self.comptes,
                dossier_harness=self.dossier,
            )
        )

    def adopter(self, qui, **corps):
        defauts = {
            "id_harness": "adopte", "nom": "Un harness adopté",
            "provenance": "faits main",
            "prompts": [{"nom": "ouvrir", "texte": "Tu ouvres le sujet."}],
        }
        return self.client.post(
            "/harness/adoption", json={**defauts, **corps}, headers=self.cle(qui)
        )

    def test_adopter_par_la_page_et_en_etre_proprietaire(self):
        vu = self.adopter(self.un)
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertEqual(self.comptes.role("adopte", self.un.id), "proprietaire")
        # Servi sans redémarrage, comme toute naissance.
        self.client.post(
            "/harness/courant", json={"id_harness": "adopte"}, headers=self.cle(self.un)
        )
        vu = self.client.get("/definition", headers=self.cle(self.un)).json()
        self.assertEqual(vu["harness"], "adopte")

    def test_la_provenance_est_estampillee(self):
        self.adopter(self.un, provenance="collés depuis un carnet")
        manifest = (self.dossier / "adopte" / "harness.yaml").read_text(encoding="utf-8")
        self.assertIn("collés depuis un carnet", manifest)
        self.assertIn("checksum_import", manifest)

    def test_un_texte_vide_est_refuse_avec_son_motif(self):
        refus = self.adopter(self.un, prompts=[{"nom": "ouvrir", "texte": "  "}])
        self.assertEqual(refus.status_code, 400)
        self.assertIn("non vides", refus.json()["detail"])
        self.assertFalse((self.dossier / "adopte").exists())

    def test_un_id_deja_porte_est_refuse(self):
        refus = self.adopter(self.un, id_harness="h")
        self.assertEqual(refus.status_code, 409)

    def test_un_anonyme_n_adopte_pas(self):
        reponse = self.client.post(
            "/harness/adoption",
            json={"id_harness": "x", "nom": "X",
                  "prompts": [{"nom": "a", "texte": "b"}]},
        )
        self.assertEqual(reponse.status_code, 401)


class Naissance(Bac):
    """RFC-006 §7 — créer par copie, et être servi sans redémarrage."""

    def setUp(self):
        super().setUp()
        self.dossier = Path(self._tmp.name)
        self.comptes.enregistrer_harness("h", self.un.id)

    def client_avec_naissance(self, exemple: str = ""):
        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous

        charges, _ = charger_valides(self.dossier)
        return TestClient(
            creer_tous(
                charges, self.dossier / "journal", self.comptes,
                dossier_harness=self.dossier, exemple=exemple,
            )
        )

    def test_naitre_avec_un_depot_nu_l_enregistre_et_y_pousse(self):
        """RFC-012 D12.4 — enregistrer un dépôt nu tout de suite."""
        import os
        from unittest.mock import patch

        from kokaji.depot import est_depot_nu, reference

        depots = self.dossier / "depots"
        depots.mkdir()
        client = self.client_avec_naissance()
        with patch.dict(os.environ, {"KOKAJI_DEPOTS": str(depots)}):
            vu = client.post(
                "/harness",
                json={"source": "h", "id_harness": "neuf", "nom": "Neuf", "depot": {"chemin": "neuf.git"}},
                headers=self.cle(self.un),
            )
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertTrue(vu.json()["depot"]["enregistre"], vu.json())
        self.assertTrue(est_depot_nu(depots / "neuf.git"))
        self.assertEqual(self.comptes.depot("neuf").commit_reference, reference(depots / "neuf.git", "main"))

    def test_un_depot_hors_du_dossier_refuse_avant_la_naissance(self):
        """Sabotage 2 : un refus ne laisse pas un harness né à moitié."""
        import os
        from unittest.mock import patch

        client = self.client_avec_naissance()
        with patch.dict(os.environ, {"KOKAJI_DEPOTS": str(self.dossier / "depots")}):
            vu = client.post(
                "/harness",
                json={"source": "h", "id_harness": "neuf", "nom": "Neuf", "depot": {"chemin": "/tmp/x.git"}},
                headers=self.cle(self.un),
            )
        self.assertEqual(vu.status_code, 409)
        self.assertFalse((self.dossier / "neuf").exists())
        self.assertIsNone(self.comptes.acl("neuf"))

    def test_cloner_un_depot_nu_fait_naitre_et_un_non_harness_ne_laisse_rien(self):
        """RFC-012 D12.4, sabotage 1."""
        import os
        import subprocess
        from unittest.mock import patch

        from kokaji.depot import lier

        depots = self.dossier / "depots"
        depots.mkdir()
        # Un vrai harness poussé à un dépôt nu, sous un autre id.
        source = self.dossier / "h"
        manifest = (source / "harness.yaml").read_text(encoding="utf-8")
        (source / "harness.yaml").write_text(manifest.replace("id: h\n", "id: venu\n", 1), encoding="utf-8")
        lier(source, depots / "venu.git")
        (source / "harness.yaml").write_text(manifest, encoding="utf-8")
        # Et un dépôt nu qui n'est pas un harness du tout : un texte, poussé.
        subprocess.run(["git", "init", "--bare", "-q", "-b", "main", str(depots / "vide.git")], check=True)
        brouillon = self.dossier / "brouillon"
        brouillon.mkdir()
        (brouillon / "notes.md").write_text("pas un harness", encoding="utf-8")
        for commande in (["init", "-q", "-b", "main"], ["add", "-A"],
                         ["-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "notes"],
                         ["push", "-q", str(depots / "vide.git"), "HEAD:main"]):
            subprocess.run(["git", "-C", str(brouillon), *commande], check=True)

        client = self.client_avec_naissance()
        with patch.dict(os.environ, {"KOKAJI_DEPOTS": str(depots)}):
            vu = client.post(
                "/harness",
                json={"id_harness": "venu", "cloner_depuis": {"chemin": "venu.git"}},
                headers=self.cle(self.un),
            )
            self.assertEqual(vu.status_code, 200, vu.text)
            self.assertEqual(self.comptes.role("venu", self.un.id), "proprietaire")
            self.assertEqual(self.comptes.depot("venu").chemin, str(depots / "venu.git"))
            self.assertTrue((self.dossier / "venu" / "harness.yaml").is_file())

            rien = client.post(
                "/harness",
                json={"id_harness": "rien", "cloner_depuis": {"chemin": "vide.git"}},
                headers=self.cle(self.un),
            )
        self.assertEqual(rien.status_code, 409, rien.text)
        self.assertIn("n'est pas un harness", rien.json()["detail"])
        self.assertFalse((self.dossier / "rien").exists())
        self.assertIsNone(self.comptes.acl("rien"))

    def test_creer_par_copie_et_en_etre_proprietaire(self):
        client = self.client_avec_naissance()
        vu = client.post(
            "/harness",
            json={"source": "h", "id_harness": "neuf", "nom": "Un harness neuf"},
            headers=self.cle(self.un),
        )
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertEqual(vu.json()["copie_de"], "h")
        self.assertEqual(self.comptes.role("neuf", self.un.id), "proprietaire")

    def test_le_nouveau_ne_est_servi_sans_redemarrage(self):
        """Sinon il existerait sur disque sans que personne puisse l'ouvrir."""
        client = self.client_avec_naissance()
        entetes = self.cle(self.un)
        client.post(
            "/harness", json={"source": "h", "id_harness": "neuf", "nom": "Neuf"}, headers=entetes
        )
        self.comptes.choisir_harness(self.un.id, "neuf")
        self.assertEqual(
            client.get("/definition", headers=entetes).json()["harness"], "neuf"
        )

    def test_l_exemple_se_copie_sans_en_etre_membre(self):
        """Ce qui rend un compte neuf autonome dès l'inscription."""
        client = self.client_avec_naissance(exemple="h2")
        vu = client.post(
            "/harness",
            json={"source": "h2", "id_harness": "neuf", "nom": "Neuf"},
            headers=self.cle(self.deux),
        )
        self.assertEqual(vu.status_code, 200, vu.text)

    def test_copier_ce_dont_on_n_est_pas_membre_est_refuse_sans_le_confirmer(self):
        """Distinguer « inconnu » de « fermé » dirait qu'un harness existe."""
        client = self.client_avec_naissance()
        fermee = client.post(
            "/harness", json={"source": "h", "id_harness": "a", "nom": "A"},
            headers=self.cle(self.deux),
        )
        inconnue = client.post(
            "/harness", json={"source": "jamais-vu", "id_harness": "b", "nom": "B"},
            headers=self.cle(self.deux),
        )
        self.assertEqual(fermee.status_code, 404)
        self.assertEqual(inconnue.status_code, 404)
        self.assertEqual(fermee.json()["detail"][:20], inconnue.json()["detail"][:20])

    def test_un_id_deja_porte_est_refuse(self):
        client = self.client_avec_naissance()
        vu = client.post(
            "/harness", json={"source": "h", "id_harness": "h2", "nom": "Neuf"},
            headers=self.cle(self.un),
        )
        self.assertEqual(vu.status_code, 409)

    def test_un_anonyme_ne_cree_rien(self):
        """401 et non 403 : avec un magasin, on ne refuse pas un geste à
        quelqu'un — on constate d'abord qu'on ignore qui demande.

        La qualité `anonyme` n'est donc atteignable qu'en mode mono-utilisateur,
        où il n'y a personne à identifier. Avec un magasin, on est identifié ou
        arrêté à la porte, et c'est plus précis qu'un refus de geste.
        """
        client = self.client_avec_naissance()
        vu = client.post("/harness", json={"source": "h", "id_harness": "x", "nom": "X"})
        self.assertEqual(vu.status_code, 401)

    def test_semer_part_de_rien(self):
        """Source vide : on part du squelette, sans rien copier de personne."""
        client = self.client_avec_naissance()
        vu = client.post(
            "/harness",
            json={"source": "", "id_harness": "neuf", "nom": "Parti de rien"},
            headers=self.cle(self.un),
        )
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertIsNone(vu.json()["copie_de"])
        self.assertEqual(self.comptes.role("neuf", self.un.id), "proprietaire")

    def test_un_semis_est_servi_comme_une_copie(self):
        client = self.client_avec_naissance()
        entetes = self.cle(self.un)
        client.post("/harness", json={"source": "", "id_harness": "neuf", "nom": "Neuf"},
                    headers=entetes)
        self.comptes.choisir_harness(self.un.id, "neuf")
        self.assertEqual(client.get("/definition", headers=entetes).json()["harness"], "neuf")

    def test_la_copie_nait_brouillon(self):
        client = self.client_avec_naissance()
        vu = client.post(
            "/harness", json={"source": "h", "id_harness": "neuf", "nom": "Neuf"},
            headers=self.cle(self.un),
        ).json()
        self.assertFalse(vu["scelle"])


class Archivage(Bac):
    """RFC-006 §5 — archiver retire du service, et ne détruit rien."""

    def setUp(self):
        super().setUp()
        self.comptes.enregistrer_harness("h", self.un.id)
        self.comptes.ajouter_contributeur("h", self.deux.id)
        self.comptes.choisir_harness(self.un.id, "h")

    def archiver(self, qui, archive: bool = True):
        return self.client.post(
            "/harness/h/archive", json={"archive": archive}, headers=self.cle(qui)
        )

    def test_le_proprietaire_archive(self):
        vu = self.archiver(self.un)
        self.assertEqual(vu.status_code, 200, vu.text)
        self.assertIsNotNone(vu.json()["archive_le"])
        self.assertIsNotNone(self.comptes.archive_le("h"))

    def test_un_contributeur_n_archive_pas(self):
        """Le geste porte sur la possession, pas sur l'œuvre : un co-auteur
        édite et scelle, il ne retire pas du service ce qu'il ne possède pas."""
        self.assertEqual(self.archiver(self.deux).status_code, 403)

    def test_un_harness_archive_n_offre_aucun_modele(self):
        self.archiver(self.un)
        vu = self.client.get("/v1/models", headers=self.cle(self.un)).json()
        self.assertEqual(vu["data"], [])

    def test_un_harness_archive_refuse_les_completions(self):
        self.archiver(self.un)
        vu = self.client.post(
            "/v1/chat/completions",
            json={"model": "h/k1", "messages": []},
            headers=self.cle(self.un),
        )
        self.assertEqual(vu.status_code, 403)
        self.assertIn("archivé", vu.json()["detail"])

    def test_il_reste_au_selecteur_mais_marque(self):
        """Le cacher rendrait ses ha illisibles — le §5 promet l'inverse."""
        self.archiver(self.un)
        vu = self.client.get("/harness", headers=self.cle(self.un)).json()
        entree = next(h for h in vu["harness"] if h["id"] == "h")
        self.assertIsNotNone(entree["archive_le"])

    def test_ses_ha_restent_lisibles(self):
        """« Ce qui a été observé ne se détruit pas parce que la forme qui l'a
        produit ne sert plus. »"""
        self.archiver(self.un)
        self.assertEqual(
            self.client.get("/definition", headers=self.cle(self.un)).status_code, 200
        )
        self.assertEqual(self.client.get("/ha", headers=self.cle(self.un)).status_code, 200)

    def test_archiver_n_est_pas_un_aller_simple(self):
        self.archiver(self.un)
        self.archiver(self.un, archive=False)
        self.assertIsNone(self.comptes.archive_le("h"))
        vu = self.client.get("/v1/models", headers=self.cle(self.un)).json()
        self.assertEqual([m["id"] for m in vu["data"]], ["h/k1"])

    def test_archiver_prend_effet_sans_redemarrage(self):
        """Lu à chaque requête et non au montage, comme la naissance."""
        avant = self.client.get("/v1/models", headers=self.cle(self.un)).json()
        self.assertTrue(avant["data"])
        self.archiver(self.un)
        apres = self.client.get("/v1/models", headers=self.cle(self.un)).json()
        self.assertEqual(apres["data"], [])
