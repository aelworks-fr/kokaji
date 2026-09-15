"""Le dépôt de ha — l'interface du corpus (RFC-014, lot A).

Ce que tout consommateur attend d'un dépôt, éprouvé sur celui des fichiers :
le même jeu de tests servira au dépôt de la base, au lot B.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.corpus.depot import DepotDeHa, DepotFichiers, RefHa, depot_pour, identifiant_de, ref_de

FICHE = "---\nkata: k1\ncible: c\nstatut: brut\n---\n\n# CAS-0001\n\nsession `s-1`\n"


class TestReference(unittest.TestCase):
    def test_l_identifiant_se_lit_dans_le_nom(self):
        self.assertEqual(identifiant_de("CAS-0012-idee-sobre-34c46a"), "CAS-0012")
        self.assertEqual(identifiant_de("autre-chose"), "autre-chose")

    def test_une_reference_se_resout_en_chemin_et_reste_un_chemin_pour_la_transition(self):
        ref = RefHa(Path("/c"), "CAS-0001-x")
        self.assertEqual(ref.identifiant, "CAS-0001")
        self.assertEqual(ref.chemin, Path("/c/CAS-0001-x"))
        self.assertEqual(Path(ref), Path("/c/CAS-0001-x"))
        self.assertEqual(ref / "fiche.md", Path("/c/CAS-0001-x/fiche.md"))
        self.assertEqual(ref_de(Path("/c/CAS-0001-x")), ref)
        self.assertIs(ref_de(ref), ref)


class TestDepotFichiers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus"
        self.depot = DepotFichiers()

    def tearDown(self):
        self.tmp.cleanup()

    def test_le_depot_par_defaut_est_celui_des_fichiers(self):
        self.assertIsInstance(depot_pour(), DepotFichiers)
        self.assertIsInstance(depot_pour(), DepotDeHa)

    def test_un_corpus_vide_n_a_rien_et_numerote_depuis_un(self):
        self.assertEqual(self.depot.tous(self.corpus), [])
        self.assertEqual(self.depot.numero_suivant(self.corpus), 1)
        self.assertIsNone(self.depot.trouver(self.corpus, "CAS-0001"))
        self.assertEqual(self.depot.ecartes(self.corpus), [])

    def test_creer_puis_retrouver_par_identifiant(self):
        ref = self.depot.creer(self.corpus, "CAS-0003-titre")
        self.assertTrue(self.depot.existe(ref))
        self.assertEqual(self.depot.tous(self.corpus), [ref])
        self.assertEqual(self.depot.trouver(self.corpus, "CAS-0003"), ref)
        self.assertEqual(self.depot.numero_suivant(self.corpus), 4)
        self.depot.supprimer(ref)
        self.assertFalse(self.depot.existe(ref))
        self.assertEqual(self.depot.tous(self.corpus), [])

    def test_les_pieces_manquantes_se_lisent_vides_jamais_en_erreur(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.assertIsNone(self.depot.fiche(ref))
        self.assertEqual(self.depot.entete(ref), {})
        self.assertIsNone(self.depot.transcript(ref))
        self.assertIsNone(self.depot.sortie(ref))
        self.assertIsNone(self.depot.materiau(ref, "coupe.md"))
        self.assertEqual(self.depot.etats(ref), [])
        self.assertFalse(self.depot.a_des_etats(ref))
        self.assertIsNone(self.depot.carre(ref))
        self.assertEqual(self.depot.jugements(ref), [])

    def test_chaque_piece_s_ecrit_a_sa_place_sur_le_disque(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, FICHE)
        self.depot.ecrire_transcript(ref, "## Tour 1\n")
        self.depot.ecrire_sortie(ref, "# Dernière réponse\n")
        self.depot.ecrire_materiau(ref, "coupe.md", "la coupe")
        self.depot.ecrire_etats(ref, [{"etat": {"sujet": "s"}}, {"etat": {"__illisible__": 1}}])
        self.depot.ecrire_carre(ref, "# Carré de naturalité — tenu\n")
        self.depot.ajouter_jugement(ref, {"juge": "j", "version_coupe": "v1"})
        self.depot.ajouter_jugement(ref, {"juge": "j", "version_coupe": "v2"})

        # Le format d'échange (D9.1) reste celui des dossiers : lisible sans Kokaji.
        for piece in ("fiche.md", "transcript.md", "sortie.md", "materiau/coupe.md",
                      "etats.jsonl", "carre.md", "jugements.jsonl"):
            self.assertTrue((ref.chemin / piece).is_file(), piece)

        self.assertEqual(self.depot.entete(ref), {"kata": "k1", "cible": "c", "statut": "brut"})
        self.assertEqual(self.depot.materiau(ref, "coupe.md"), "la coupe")
        self.assertEqual(len(self.depot.etats(ref)), 2)
        self.assertTrue(self.depot.a_des_etats(ref))
        self.assertEqual(self.depot.carre(ref), "# Carré de naturalité — tenu\n")
        self.assertEqual([j["version_coupe"] for j in self.depot.jugements(ref)], ["v1", "v2"])

        self.depot.retirer_carre(ref)
        self.assertIsNone(self.depot.carre(ref))
        self.depot.retirer_carre(ref)  # deux fois : rien ne casse

    def test_une_fiche_sans_entete_ou_mal_formee_donne_un_entete_vide(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, "# Sans frontmatter\n")
        self.assertEqual(self.depot.entete(ref), {})
        self.depot.ecrire_fiche(ref, "---\n- une liste\n---\n")
        self.assertEqual(self.depot.entete(ref), {})

    def test_une_ligne_illisible_du_jsonl_est_sautee_pas_fatale(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        (ref.chemin / "etats.jsonl").write_text('{"a": 1}\npas du json\n\n{"b": 2}\n', encoding="utf-8")
        self.assertEqual(self.depot.etats(ref), [{"a": 1}, {"b": 2}])

    def test_les_ecartes_se_declarent_au_corpus_et_se_relisent(self):
        self.depot.ecarter(self.corpus, "s-1", "parasite", "2026-09-15T00:00:00")
        self.depot.ecarter(self.corpus, "s-2", "nommément", "2026-09-15T00:00:00")
        self.assertEqual([e["session"] for e in self.depot.ecartes(self.corpus)], ["s-1", "s-2"])
        self.assertTrue((self.corpus / DepotFichiers.ECARTES).is_file())

    def test_seuls_les_dossiers_cas_comptent(self):
        self.corpus.mkdir(parents=True)
        (self.corpus / "CAS-0001-vrai").mkdir()
        (self.corpus / "CAS-0002-fichier").write_text("", encoding="utf-8")
        (self.corpus / "autre").mkdir()
        self.assertEqual([r.nom for r in self.depot.tous(self.corpus)], ["CAS-0001-vrai"])


if __name__ == "__main__":
    unittest.main()
