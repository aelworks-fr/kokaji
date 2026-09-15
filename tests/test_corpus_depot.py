"""Le dépôt de ha — l'interface du corpus (RFC-014, lots A et B).

Ce que tout consommateur attend d'un dépôt, éprouvé sur les deux : celui des
fichiers, toujours ; celui de la base quand `KOKAJI_BASE_URL_ESSAI` désigne
un Postgres d'essai (la CI en pose un). Même contrat, même jeu de tests.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.corpus.depot import (
    DepotDeHa,
    DepotFichiers,
    RefHa,
    depot_pour,
    identifiant_de,
    ref_de,
    transferer,
)

URL_ESSAI = os.environ.get("KOKAJI_BASE_URL_ESSAI", "").strip()
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


class TestChoixDuDepot(unittest.TestCase):
    def test_sans_base_declaree_le_depot_est_celui_des_fichiers(self):
        avant = os.environ.pop("KOKAJI_BASE_URL", None)
        try:
            self.assertIsInstance(depot_pour(), DepotFichiers)
            self.assertIsInstance(depot_pour(), DepotDeHa)
        finally:
            if avant is not None:
                os.environ["KOKAJI_BASE_URL"] = avant

    @unittest.skipUnless(URL_ESSAI, "KOKAJI_BASE_URL_ESSAI absent : pas de Postgres d'essai")
    def test_une_base_declaree_donne_le_depot_base(self):
        from kokaji.corpus.base import DepotBase

        avant = os.environ.get("KOKAJI_BASE_URL")
        os.environ["KOKAJI_BASE_URL"] = URL_ESSAI
        try:
            self.assertIsInstance(depot_pour(), DepotBase)
            self.assertIs(depot_pour(), depot_pour())  # une connexion, pas une par appel
        finally:
            if avant is None:
                del os.environ["KOKAJI_BASE_URL"]
            else:
                os.environ["KOKAJI_BASE_URL"] = avant


class ContratDuDepot:
    """Le contrat, sans dire où les pièces vivent. Chaque dépôt l'hérite."""

    depot: DepotDeHa

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.corpus = Path(self.tmp.name) / "corpus"

    def tearDown(self):
        for ref in self.depot.tous(self.corpus):
            self.depot.supprimer(ref)
        self.tmp.cleanup()

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
        self.assertIsNone(self.depot.trouver(self.corpus, "CAS-0004"))
        self.assertEqual(self.depot.numero_suivant(self.corpus), 4)
        self.depot.creer(self.corpus, "CAS-0003-titre")  # deux fois : idempotent
        self.assertEqual(len(self.depot.tous(self.corpus)), 1)
        self.depot.supprimer(ref)
        self.assertFalse(self.depot.existe(ref))
        self.assertEqual(self.depot.tous(self.corpus), [])

    def test_deux_corpus_ne_se_voient_pas(self):
        autre = Path(self.tmp.name) / "autre"
        self.depot.creer(self.corpus, "CAS-0001-a")
        self.depot.creer(autre, "CAS-0001-b")
        self.depot.ecarter(autre, "s-x", "ailleurs", "2026-09-15T00:00:00")
        try:
            self.assertEqual([r.nom for r in self.depot.tous(self.corpus)], ["CAS-0001-a"])
            self.assertEqual([r.nom for r in self.depot.tous(autre)], ["CAS-0001-b"])
            self.assertEqual(self.depot.ecartes(self.corpus), [])
        finally:
            for ref in self.depot.tous(autre):
                self.depot.supprimer(ref)

    def test_les_pieces_manquantes_se_lisent_vides_jamais_en_erreur(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.assertIsNone(self.depot.fiche(ref))
        self.assertEqual(self.depot.entete(ref), {})
        self.assertIsNone(self.depot.transcript(ref))
        self.assertIsNone(self.depot.sortie(ref))
        self.assertIsNone(self.depot.materiau(ref, "coupe.md"))
        self.assertEqual(self.depot.materiaux(ref), [])
        self.assertEqual(self.depot.etats(ref), [])
        self.assertFalse(self.depot.a_des_etats(ref))
        self.assertIsNone(self.depot.carre(ref))
        self.assertEqual(self.depot.jugements(ref), [])

    def test_chaque_piece_s_ecrit_et_se_relit_telle_quelle(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, FICHE)
        self.depot.ecrire_transcript(ref, "## Tour 1\n")
        self.depot.ecrire_sortie(ref, "# Dernière réponse\n")
        self.depot.ecrire_materiau(ref, "coupe.md", "la coupe")
        self.depot.ecrire_materiau(ref, "coupe.md", "la coupe, réécrite")
        self.depot.ecrire_etats(ref, [{"etat": {"sujet": "s"}}, {"etat": {"__illisible__": 1}}])
        self.depot.ecrire_carre(ref, "# Carré de naturalité — tenu\n")
        self.depot.ajouter_jugement(ref, {"juge": "j", "version_coupe": "v1"})
        self.depot.ajouter_jugement(ref, {"juge": "j", "version_coupe": "v2"})

        self.assertEqual(self.depot.fiche(ref), FICHE)
        self.assertEqual(self.depot.entete(ref), {"kata": "k1", "cible": "c", "statut": "brut"})
        self.assertEqual(self.depot.transcript(ref), "## Tour 1\n")
        self.assertEqual(self.depot.sortie(ref), "# Dernière réponse\n")
        self.assertEqual(self.depot.materiau(ref, "coupe.md"), "la coupe, réécrite")
        self.assertEqual(self.depot.materiaux(ref), ["coupe.md"])
        self.assertEqual(
            self.depot.etats(ref), [{"etat": {"sujet": "s"}}, {"etat": {"__illisible__": 1}}]
        )
        self.assertTrue(self.depot.a_des_etats(ref))
        self.assertEqual(self.depot.carre(ref), "# Carré de naturalité — tenu\n")
        self.assertEqual([j["version_coupe"] for j in self.depot.jugements(ref)], ["v1", "v2"])

        self.depot.ecrire_etats(ref, [])  # réécrire vide : écrit, mais vide
        self.assertEqual(self.depot.etats(ref), [])
        self.assertTrue(self.depot.a_des_etats(ref))

        self.depot.retirer_carre(ref)
        self.assertIsNone(self.depot.carre(ref))
        self.depot.retirer_carre(ref)  # deux fois : rien ne casse

    def test_une_fiche_reecrite_remplace_la_precedente(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, FICHE)
        self.depot.ecrire_fiche(ref, FICHE.replace("statut: brut", "statut: annote"))
        self.assertEqual(self.depot.entete(ref)["statut"], "annote")

    def test_une_fiche_sans_entete_ou_mal_formee_donne_un_entete_vide(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, "# Sans frontmatter\n")
        self.assertEqual(self.depot.entete(ref), {})
        self.depot.ecrire_fiche(ref, "---\n- une liste\n---\n")
        self.assertEqual(self.depot.entete(ref), {})

    def test_supprimer_un_ha_emporte_ses_pieces(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, FICHE)
        self.depot.ecrire_etats(ref, [{"etat": {}}])
        self.depot.ajouter_jugement(ref, {"juge": "j"})
        self.depot.supprimer(ref)
        self.assertIsNone(self.depot.fiche(ref))
        self.assertEqual(self.depot.etats(ref), [])
        self.assertEqual(self.depot.jugements(ref), [])

    def test_les_ecartes_se_declarent_au_corpus_et_se_relisent_dans_l_ordre(self):
        self.depot.ecarter(self.corpus, "s-1", "parasite", "2026-09-15T00:00:00")
        self.depot.ecarter(self.corpus, "s-2", "nommément", "2026-09-15T00:00:01")
        self.assertEqual(
            self.depot.ecartes(self.corpus),
            [
                {"session": "s-1", "raison": "parasite", "le": "2026-09-15T00:00:00"},
                {"session": "s-2", "raison": "nommément", "le": "2026-09-15T00:00:01"},
            ],
        )


class TestDepotFichiers(ContratDuDepot, unittest.TestCase):
    depot = DepotFichiers()

    def test_le_format_d_echange_reste_le_dossier_lisible_sans_kokaji(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, FICHE)
        self.depot.ecrire_transcript(ref, "t")
        self.depot.ecrire_sortie(ref, "s")
        self.depot.ecrire_materiau(ref, "coupe.md", "c")
        self.depot.ecrire_etats(ref, [{"a": 1}])
        self.depot.ecrire_carre(ref, "k")
        self.depot.ajouter_jugement(ref, {"j": 1})
        self.depot.ecarter(self.corpus, "s", "r", "q")
        for piece in ("fiche.md", "transcript.md", "sortie.md", "materiau/coupe.md",
                      "etats.jsonl", "carre.md", "jugements.jsonl"):
            self.assertTrue((ref.chemin / piece).is_file(), piece)
        self.assertTrue((self.corpus / DepotFichiers.ECARTES).is_file())

    def test_une_ligne_illisible_du_jsonl_est_sautee_pas_fatale(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        (ref.chemin / "etats.jsonl").write_text('{"a": 1}\npas du json\n\n{"b": 2}\n', encoding="utf-8")
        self.assertEqual(self.depot.etats(ref), [{"a": 1}, {"b": 2}])

    def test_seuls_les_dossiers_cas_comptent(self):
        self.corpus.mkdir(parents=True)
        (self.corpus / "CAS-0001-vrai").mkdir()
        (self.corpus / "CAS-0002-fichier").write_text("", encoding="utf-8")
        (self.corpus / "autre").mkdir()
        self.assertEqual([r.nom for r in self.depot.tous(self.corpus)], ["CAS-0001-vrai"])


@unittest.skipUnless(URL_ESSAI, "KOKAJI_BASE_URL_ESSAI absent : pas de Postgres d'essai")
class TestDepotBase(ContratDuDepot, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from kokaji.corpus.base import DepotBase

        cls.depot = DepotBase(URL_ESSAI)

    @classmethod
    def tearDownClass(cls):
        cls.depot.fermer()

    def test_les_colonnes_sont_tirees_de_la_fiche_pour_requeter(self):
        ref = self.depot.creer(self.corpus, "CAS-0001-x")
        self.depot.ecrire_fiche(ref, FICHE.replace("statut: brut", "statut: brut\nscores:\n  tours: 3"))
        ligne = self.depot._lire_une(
            "SELECT id, kata, cible, statut, scores FROM ha WHERE corpus = %s AND nom = %s",
            str(self.corpus.resolve()), "CAS-0001-x",
        )
        self.assertEqual(ligne, ("CAS-0001", "k1", "c", "brut", {"tours": 3}))

    def test_le_harness_et_le_nom_du_corpus_se_lisent_dans_le_chemin(self):
        corpus = Path(self.tmp.name) / "atelier" / "corpus" / "principal"
        ref = self.depot.creer(corpus, "CAS-0001-x")
        try:
            ligne = self.depot._lire_une(
                "SELECT harness, corpus_nom FROM ha WHERE corpus = %s", str(corpus.resolve())
            )
            self.assertEqual(ligne, ("atelier", "principal"))
        finally:
            self.depot.supprimer(ref)

    def test_une_base_injoignable_se_dit_et_ne_rend_rien_de_perime(self):
        from kokaji.corpus.base import BaseInjoignable, DepotBase

        muet = DepotBase("postgresql://kokaji:x@127.0.0.1:1/aucune?connect_timeout=1")
        with self.assertRaises(BaseInjoignable):
            muet.tous(self.corpus)

    def test_un_ha_va_et_vient_entre_fichiers_et_base_octet_pour_octet(self):
        """D14.8, sabotage 4 : l'export est identique au dossier que les fichiers écrivaient."""
        fichiers = DepotFichiers()
        origine = Path(self.tmp.name) / "origine"
        ref = fichiers.creer(origine, "CAS-0007-aller-retour")
        fichiers.ecrire_fiche(ref, FICHE)
        fichiers.ecrire_transcript(ref, "## Tour 1\n\nbonjour\n")
        fichiers.ecrire_sortie(ref, "# Dernière réponse — CAS-0007\n\nau revoir\n")
        fichiers.ecrire_materiau(ref, "coupe.md", "la coupe injectée")
        fichiers.ecrire_materiau(ref, "tours.json", "[]")
        fichiers.ecrire_etats(ref, [{"horodatage": "2026-09-15T00:00:00", "etat": {"sujet": "s", "champs": {"a": 1}}}])
        fichiers.ecrire_carre(ref, "# Carré de naturalité — tenu\n\ndétail\n")
        fichiers.ajouter_jugement(ref, {"juge": "j", "version_coupe": "v1", "le": "2026-09-15T00:00:00", "scores": [1, 2]})

        en_base = transferer(ref, fichiers, self.depot)
        self.assertEqual(en_base.corpus, origine)
        retour = Path(self.tmp.name) / "retour"
        revenu = transferer(en_base, self.depot, fichiers, corpus=retour)
        self.assertEqual(revenu.corpus, retour)

        self.assertEqual(
            sorted(p.relative_to(ref.chemin) for p in ref.chemin.rglob("*") if p.is_file()),
            sorted(p.relative_to(revenu.chemin) for p in revenu.chemin.rglob("*") if p.is_file()),
        )
        for piece in ref.chemin.rglob("*"):
            if piece.is_file():
                self.assertEqual(
                    piece.read_bytes(), (revenu.chemin / piece.relative_to(ref.chemin)).read_bytes(),
                    str(piece.relative_to(ref.chemin)),
                )
        self.depot.supprimer(en_base)
        shutil.rmtree(origine)


if __name__ == "__main__":
    unittest.main()
