"""Ce que la pratique a coûté, et ce qu'elle a rendu.

Harness purement structurels (§0). Les fiches sont écrites à la main : ce qu'on
éprouve est l'addition et les ratios, pas la capture — elle a ses propres tests.
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
from kokaji.hds import charger
from kokaji.middleware.service import creer
from kokaji.usage import Depense, mesurer, rendre

MOT_DE_PASSE = "un-mot-de-passe-assez-long"


class Ratios(unittest.TestCase):
    """Un total ne compare rien — ce sont les ratios qui comparent."""

    def test_le_prix_d_un_tour_et_d_une_observation(self):
        d = Depense()
        d.ajouter({"tours": 4, "blocs_etat": 2, "jetons_entree": 800, "jetons_sortie": 200}, "")
        self.assertEqual(d.jetons, 1000)
        self.assertEqual(d.par_tour, 250)
        self.assertEqual(d.par_bloc, 500)

    def test_sans_bloc_le_prix_d_une_observation_n_existe_pas(self):
        """Zéro n'est pas la bonne réponse : il n'y a pas eu d'observation."""
        d = Depense()
        d.ajouter({"tours": 2, "blocs_etat": 0, "jetons_entree": 900, "jetons_sortie": 100}, "")
        self.assertEqual(d.par_bloc, 0.0)


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        _ecrire_harness(self.racine / "h", MINIMAL)
        self.harness = charger(self.racine / "h")

    def ha(self, nom: str, kata: str, cible: str, scores: dict, carre: str = "conforme"):
        dossier = self.harness.corpus / nom
        dossier.mkdir(parents=True)
        entete = "\n".join(f"{c}: {v}" for c, v in {
            "harness": "h", "kata": kata, "cible": cible, "moteur": "un/moteur",
        }.items())
        lignes = "\n".join(f"  {c}: {v}" for c, v in scores.items())
        (dossier / "fiche.md").write_text(
            f"---\n{entete}\nscores:\n{lignes}\n---\n\n# {nom}\n", encoding="utf-8"
        )
        if carre:
            (dossier / "carre.md").write_text(f"# Carré de naturalité — {carre}\n", encoding="utf-8")


class Mesure(Bac):
    def test_le_harness_et_ses_kata(self):
        """Deux niveaux, parce que deux questions distinctes se posent."""
        self.ha("CAS-0001-a", "k1", "c1",
                {"tours": 2, "blocs_etat": 1, "jetons_entree": 400, "jetons_sortie": 100})
        self.ha("CAS-0002-b", "k1", "c1",
                {"tours": 2, "blocs_etat": 1, "jetons_entree": 400, "jetons_sortie": 100})
        self.ha("CAS-0003-c", "k2", "c1",
                {"tours": 1, "blocs_etat": 0, "jetons_entree": 200, "jetons_sortie": 0},
                carre="sans-etat")

        releve = mesurer(self.harness)
        self.assertEqual(releve.tout.ha, 3)
        self.assertEqual(releve.tout.jetons, 1200)
        self.assertEqual(sorted(releve.par_kata), ["k1", "k2"])
        self.assertEqual(releve.par_kata["k1"].jetons, 1000)
        self.assertEqual(releve.par_kata["k1"].par_bloc, 500)
        self.assertEqual(releve.par_kata["k2"].blocs, 0)

    def test_le_carre_est_compte_a_cote_de_la_depense(self):
        """Le coût sans ce qu'il achète est un chiffre qu'on fait baisser en
        cessant de travailler."""
        self.ha("CAS-0001-a", "k1", "c1", {"tours": 1, "blocs_etat": 1,
                                           "jetons_entree": 10, "jetons_sortie": 1})
        self.ha("CAS-0002-b", "k1", "c1", {"tours": 1, "blocs_etat": 0,
                                           "jetons_entree": 10, "jetons_sortie": 1},
                carre="sans-etat")
        releve = mesurer(self.harness)
        self.assertEqual(releve.tout.conformes, 1)
        self.assertEqual(releve.tout.carres["sans-etat"], 1)

    def test_les_cibles_et_les_moteurs_se_comparent_aussi(self):
        """C'est ce que la SPECS §5.6 réclame : deux incarnations côte à côte."""
        self.ha("CAS-0001-a", "k1", "sobre", {"tours": 1, "blocs_etat": 0,
                                              "jetons_entree": 100, "jetons_sortie": 10})
        self.ha("CAS-0002-b", "k1", "instrumentee", {"tours": 1, "blocs_etat": 2,
                                                     "jetons_entree": 300, "jetons_sortie": 30})
        releve = mesurer(self.harness)
        self.assertEqual(releve.par_cible["sobre"].jetons, 110)
        self.assertEqual(releve.par_cible["instrumentee"].par_bloc, 165)
        self.assertEqual(list(releve.par_moteur), ["un/moteur"])

    def test_un_ha_sans_compteurs_est_compte_a_part(self):
        """Le taire ferait d'un corpus à moitié mesuré un corpus complet."""
        dossier = self.harness.corpus / "CAS-0009-muet"
        dossier.mkdir(parents=True)
        (dossier / "fiche.md").write_text("---\nkata: k1\n---\n\n# muet\n", encoding="utf-8")
        releve = mesurer(self.harness)
        self.assertEqual(releve.tout.ha, 0)
        self.assertEqual(releve.sans_scores, 1)

    def test_un_corpus_vide_ne_ment_pas(self):
        releve = mesurer(self.harness)
        self.assertEqual(releve.tout.ha, 0)
        self.assertEqual(releve.par_kata, {})


class Juges(Bac):
    """Les conformes se rapportent aux ha jugés, pas à tous."""

    def test_un_ha_sans_carre_ne_compte_pas_comme_un_echec(self):
        self.ha("CAS-0001-a", "k1", "c1", {"tours": 1, "blocs_etat": 1,
                                           "jetons_entree": 90, "jetons_sortie": 10})
        self.ha("CAS-0002-b", "k1", "c0", {"tours": 1, "blocs_etat": 0,
                                           "jetons_entree": 90, "jetons_sortie": 10},
                carre="")
        releve = mesurer(self.harness)
        self.assertEqual(releve.tout.ha, 2)
        self.assertEqual(releve.tout.juges, 1)
        self.assertEqual(releve.tout.conformes, 1)
        self.assertIn("1/1", rendre(releve))

    def test_sans_aucun_carre_le_rapport_ne_vaut_pas_zero(self):
        self.ha("CAS-0001-a", "k1", "c0", {"tours": 1, "blocs_etat": 0,
                                           "jetons_entree": 90, "jetons_sortie": 10},
                carre="")
        self.assertIn("0/—", rendre(mesurer(self.harness)))


class Doubles(Bac):
    """Un total qui compte deux fois la même conversation — NOTE-0019."""

    def setUp(self):
        super().setUp()
        for nom in ("reel", "essai"):
            (self.racine / "h" / "corpus" / nom).mkdir(parents=True)
        (self.racine / "h" / "harness.yaml").write_text(
            MINIMAL.replace(
                "corpus: corpus/",
                "corpus:\n  reel:\n    chemin: corpus/reel/\n"
                "  essai:\n    chemin: corpus/essai/\n",
            ),
            encoding="utf-8",
        )
        self.harness = charger(self.racine / "h")
        self.reel = self.harness.corpus_par_nom("reel").chemin
        self.essai = self.harness.corpus_par_nom("essai").chemin

    def poser(self, corpus: Path, nom: str, session: str) -> None:
        dossier = corpus / nom
        dossier.mkdir(parents=True)
        (dossier / "fiche.md").write_text(
            "---\nharness: h\nkata: k1\ncible: c1\nscores:\n  tours: 2\n"
            "  blocs_etat: 1\n  jetons_entree: 90\n  jetons_sortie: 10\n---\n\n"
            f"session `{session}`.\n",
            encoding="utf-8",
        )

    def test_la_part_comptee_deux_fois_est_dite_et_reste_dans_le_total(self):
        """Retrancher en silence rendrait un total que nul ne peut relire."""
        self.poser(self.reel, "CAS-0001-a", "s-1")
        self.poser(self.essai, "CAS-0009-a", "s-1")
        self.poser(self.essai, "CAS-0010-b", "s-2")

        releve = mesurer(self.harness, self.essai)
        self.assertEqual(releve.tout.ha, 2)
        self.assertEqual(releve.tout.jetons, 200)
        self.assertEqual(releve.doubles.ha, 1)
        self.assertEqual(releve.doubles.jetons, 100)
        self.assertIn("comptés deux fois", rendre(releve))

    def test_sans_double_rien_n_est_dit(self):
        self.poser(self.essai, "CAS-0001-a", "s-1")
        releve = mesurer(self.harness, self.essai)
        self.assertEqual(releve.doubles.ha, 0)
        self.assertNotIn("deux fois", rendre(releve))


class Rendu(Bac):
    def test_le_prix_d_une_observation_absente_se_dit(self):
        """« — » plutôt que zéro : il n'y a pas eu d'observation à payer."""
        self.ha("CAS-0001-a", "k1", "c1", {"tours": 1, "blocs_etat": 0,
                                           "jetons_entree": 100, "jetons_sortie": 10},
                carre="sans-etat")
        texte = rendre(mesurer(self.harness))
        self.assertIn("aucun bloc", texte)
        self.assertIn("1 sans-etat", texte)

    def test_le_releve_nomme_le_harness_et_son_corpus(self):
        self.ha("CAS-0001-a", "k1", "c1", {"tours": 1, "blocs_etat": 1,
                                           "jetons_entree": 100, "jetons_sortie": 10})
        texte = rendre(mesurer(self.harness))
        self.assertIn("h · corpus", texte)
        self.assertIn("par kata", texte)


class AuQG(Bac):
    """Le relevé se lit là où l'on modifie la forme — RFC-002 §6.3."""

    def setUp(self):
        super().setUp()
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.membre = self.comptes.creer_utilisateur("M", "m@exemple.test", MOT_DE_PASSE)
        self.dehors = self.comptes.creer_utilisateur("D", "d@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness(self.harness.id, self.membre.id)
        self.client = TestClient(creer(self.harness, self.racine, self.comptes))

    def cle(self, courriel: str) -> dict:
        reponse = self.client.post(
            "/session", json={"email": courriel, "mot_de_passe": MOT_DE_PASSE}
        )
        return {"Authorization": f"Bearer {reponse.json()['jeton']}"}

    def test_le_releve_donne_les_deux_niveaux(self):
        self.ha("CAS-0001-a", "k1", "c1", {"tours": 4, "blocs_etat": 2,
                                           "jetons_entree": 800, "jetons_sortie": 200})
        vu = self.client.get("/qg/usage", headers=self.cle("m@exemple.test"))
        self.assertEqual(vu.status_code, 200)
        corps = vu.json()
        self.assertEqual(corps["tout"]["jetons"], 1000)
        self.assertEqual(corps["tout"]["par_bloc"], 500)
        self.assertEqual(corps["tout"]["conformes"], 1)
        self.assertEqual(corps["par_kata"]["k1"]["par_tour"], 250)

    def test_une_observation_absente_se_dit_et_ne_vaut_pas_zero(self):
        """`null` plutôt que 0 : la page doit pouvoir écrire « — »."""
        self.ha("CAS-0002-a", "k1", "c1", {"tours": 2, "blocs_etat": 0,
                                           "jetons_entree": 900, "jetons_sortie": 100},
                carre="sans-etat")
        corps = self.client.get("/qg/usage", headers=self.cle("m@exemple.test")).json()
        self.assertIsNone(corps["tout"]["par_bloc"])
        self.assertEqual(corps["tout"]["carres"], {"sans-etat": 1})

    def test_un_non_membre_ne_lit_pas_la_depense(self):
        """Un agrégat ne révèle aucune pratique, mais il reste du harness."""
        refus = self.client.get("/qg/usage", headers=self.cle("d@exemple.test"))
        self.assertEqual(refus.status_code, 403)


if __name__ == "__main__":
    unittest.main()
