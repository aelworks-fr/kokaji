"""Faire naître un harness par copie — RFC-006 §3 et §7.

Harness purement structurels (§0), sauf l'épreuve de naissance qui part de
l'Atelier : l'invariant du §7.5 ne veut rien dire sur une fixture minimale, il
ne se prouve que sur une œuvre complète.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml
from test_hds import MINIMAL, _ecrire_harness

from kokaji.hds import charger, charger_valides
from kokaji.naissance import VERSION_INITIALE, NaissanceRefusee, copier, naitre


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        # Une version distincte de `VERSION_INITIALE` : sinon l'assertion du
        # repart-de-zéro passerait sans rien prouver.
        _ecrire_harness(self.racine / "source", MINIMAL.replace("version: 0.1.0", "version: 2.4.0"))
        self.source = charger(self.racine / "source")
        self.vers = self.racine / "harness"
        self.vers.mkdir()


class Copie(Bac):
    def test_la_copie_porte_son_identite_neuve(self):
        dossier = copier(self.source, self.vers, "neuf", "Un harness neuf")
        copie = charger(dossier)
        self.assertEqual(copie.id, "neuf")
        self.assertEqual(copie.nom, "Un harness neuf")

    def test_la_copie_repart_de_la_premiere_version(self):
        """Une copie est une œuvre neuve, pas la suite de l'originale.

        Garder la version de la source lui ferait revendiquer une lignée de
        scellements qu'elle n'a pas.
        """
        copie = charger(copier(self.source, self.vers, "neuf", "Neuf"))
        self.assertEqual(copie.version, VERSION_INITIALE)
        self.assertNotEqual(copie.version, self.source.version)

    def test_la_definition_suit(self):
        dossier = copier(self.source, self.vers, "neuf", "Neuf")
        self.assertTrue((dossier / "template.md").is_file())
        self.assertTrue((dossier / "registre.yaml").is_file())
        self.assertTrue((dossier / "kata" / "k1.yaml").is_file())
        self.assertEqual(
            [k.id for k in charger(dossier).kata], [k.id for k in self.source.kata]
        )

    def test_le_dossier_porte_le_nom_de_l_id(self):
        """C'est ainsi que `charger_valides` la retrouvera."""
        copier(self.source, self.vers, "neuf", "Neuf")
        charges, refuses = charger_valides(self.vers)
        self.assertEqual(refuses, [])
        self.assertEqual(sorted(charges), ["neuf"])

    def test_l_ordre_du_manifest_est_conserve(self):
        """On relit le fichier plutôt que de recomposer l'objet chargé.

        Le manifest porte ce que le modèle en mémoire ne garde pas — l'ordre des
        clés, les défauts laissés implicites. Le recomposer les inventerait.
        """
        dossier = copier(self.source, self.vers, "neuf", "Neuf")
        avant = list(yaml.safe_load(MINIMAL))
        apres = list(yaml.safe_load((dossier / "harness.yaml").read_text(encoding="utf-8")))
        self.assertEqual(avant, apres)


class LaPratiqueNeSuitPas(Bac):
    """L'invariant du §3.1 — sans lui, copier contournerait tout le RFC-004."""

    def test_le_corpus_de_la_copie_est_vide(self):
        (self.source.corpus / "CAS-0001-un-ha").mkdir(parents=True)
        (self.source.corpus / "CAS-0001-un-ha" / "fiche.md").write_text("x", encoding="utf-8")

        copie = charger(copier(self.source, self.vers, "neuf", "Neuf"))
        self.assertTrue(copie.corpus.is_dir())
        self.assertEqual(list(copie.corpus.glob("CAS-*")), [])

    def test_chaque_corpus_declare_existe_et_est_vide(self):
        """Les chemins viennent du manifest : les deviner ferait naître une
        copie dont les corpus pointent sur des dossiers absents."""
        manifest = MINIMAL.replace(
            "corpus: corpus/",
            "corpus:\n  reel:\n    chemin: corpus/reel/\n  essai: corpus/essai/",
        )
        _ecrire_harness(self.racine / "deux", manifest)
        for nom in ("reel", "essai"):
            dossier = self.racine / "deux" / "corpus" / nom
            dossier.mkdir(parents=True)
            (dossier / "CAS-0001-x").mkdir()
        source = charger(self.racine / "deux")

        copie = charger(copier(source, self.vers, "neuf", "Neuf"))
        self.assertEqual([c.nom for c in copie.corpus_nommes], ["reel", "essai"])
        for corpus in copie.corpus_nommes:
            self.assertTrue(corpus.chemin.is_dir(), corpus.nom)
            self.assertEqual(list(corpus.chemin.iterdir()), [], corpus.nom)


class LaLigneeNeSuitPas(Bac):
    """La lignée appartient à qui l'a faite, comme la pratique — §7.1.

    Le journal des scellements dit qui a arrêté cette définition, quand et
    pourquoi. Une copie qui l'emporterait naîtrait en revendiquant des versions
    signées par quelqu'un qui ne l'a jamais vue — et l'épreuve du §7 l'a trouvée
    « déjà scellée » à sa naissance.
    """

    def test_le_journal_des_scellements_ne_se_copie_pas(self):
        from kokaji.conception import JOURNAL
        from kokaji.naissance import scelle

        (self.source.racine / JOURNAL).write_text(
            '{"auteur": "Quelqu un", "motif": "x", "le": "2026-01-01", '
            '"versions": {}, "changements": []}\n',
            encoding="utf-8",
        )
        copie = charger(copier(self.source, self.vers, "neuf", "Neuf"))
        self.assertFalse((copie.racine / JOURNAL).exists())
        self.assertFalse(scelle(copie), "un nouveau-né est un brouillon")


class Refus(Bac):
    def test_un_id_deja_pris_est_refuse(self):
        copier(self.source, self.vers, "neuf", "Neuf")
        with self.assertRaises(NaissanceRefusee) as capture:
            copier(self.source, self.vers, "neuf", "Encore")
        self.assertIn("porte déjà ce nom", str(capture.exception))

    def test_un_id_ou_un_nom_vide_est_refuse(self):
        for identifiant, nom in (("", "Neuf"), ("neuf", "  ")):
            with self.subTest(id=identifiant, nom=nom), self.assertRaises(NaissanceRefusee):
                copier(self.source, self.vers, identifiant, nom)

    def test_un_refus_n_ecrit_rien(self):
        """Un dossier à moitié né se lirait comme un harness cassé."""
        with self.assertRaises(NaissanceRefusee):
            copier(self.source, self.vers, "", "Neuf")
        self.assertEqual(list(self.vers.iterdir()), [])

    def test_une_copie_qui_ne_tient_pas_est_retiree(self):
        """Mieux vaut aucune naissance qu'une naissance à réparer."""
        with self.assertRaises(NaissanceRefusee):
            naitre(self.source, self.vers, "Pas Un Slug", "Neuf")
        self.assertEqual(list(self.vers.iterdir()), [])


class InvariantDeNaissance(unittest.TestCase):
    """§7.5 — ce qui naît valide, forge et trempe sans retouche.

    L'épreuve part de l'Atelier : sur une fixture minimale elle ne prouverait
    rien, puisque c'est la richesse de la source qui met la copie en danger.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.vers = Path(self._tmp.name)
        # Le produit loge l'Atelier à sa racine (RFC-009) ; une instance, sous harness/.
        racine = Path(__file__).resolve().parents[1]
        self.reponse = next(
            c for c in (racine / "atelier", racine / "harness" / "atelier") if c.is_dir()
        )

    def test_la_copie_de_l_exemple_valide_forge_et_trempe(self):
        from kokaji.forge import forger_harness

        copie = naitre(charger(self.reponse), self.vers, "essai-neuf", "Essai neuf")
        self.assertEqual(copie.id, "essai-neuf")
        self.assertEqual(len(copie.kata), 3)

        resultat = forger_harness(copie, sortie=self.vers / "dist", trempe=True)
        self.assertEqual(len(resultat.coupes), 6)

    def test_la_copie_de_l_exemple_n_emporte_aucun_ha(self):
        copie = naitre(charger(self.reponse), self.vers, "essai-neuf", "Essai neuf")
        for corpus in copie.corpus_nommes:
            self.assertEqual(list(corpus.chemin.glob("CAS-*")), [], corpus.nom)


if __name__ == "__main__":
    unittest.main()


class Semer(unittest.TestCase):
    """Partir de rien — RFC-006 §3, amendé le 16 août.

    Copier donne une forme qui marche ; semer donne une page presque blanche.
    On copie quand une méthode voisine existe, on sème quand la sienne ne
    ressemble à rien de ce qu'on a déjà.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.vers = Path(self._tmp.name)

    def test_la_semence_vaut_se_forge_et_se_trempe(self):
        """L'invariant du §7.5 vaut pour elle aussi : un squelette qu'il faudrait
        réparer avant de s'en servir ne serait pas une semence."""
        from kokaji.forge import forger_harness
        from kokaji.naissance import semer

        ne = semer(self.vers, "neuf", "Un harness neuf")
        self.assertEqual(ne.id, "neuf")
        self.assertEqual(ne.nom, "Un harness neuf")
        resultat = forger_harness(ne, sortie=self.vers / "dist", trempe=True)
        self.assertEqual(len(resultat.coupes), 1)

    def test_elle_ne_porte_aucun_domaine(self):
        """SPECS §0 — Kokaji ne connaît que la structure des harness.

        Ce n'est pas un second harness d'exemple : elle ne décrit aucun métier.
        """
        from kokaji.naissance import SEMENCE

        manifest = (SEMENCE / "harness.yaml").read_text(encoding="utf-8")
        self.assertIn("À décrire", manifest)
        self.assertNotIn("atelier", manifest.lower())

    def test_son_corpus_est_vide_et_existe(self):
        from kokaji.naissance import semer

        ne = semer(self.vers, "neuf", "Neuf")
        self.assertTrue(ne.corpus.is_dir())
        self.assertEqual(list(ne.corpus.glob("CAS-*")), [])

    def test_elle_nait_brouillon(self):
        from kokaji.naissance import scelle, semer

        self.assertFalse(scelle(semer(self.vers, "neuf", "Neuf")))

    def test_deux_semis_sous_le_meme_id_sont_refuses(self):
        from kokaji.naissance import NaissanceRefusee, semer

        semer(self.vers, "neuf", "Neuf")
        with self.assertRaises(NaissanceRefusee):
            semer(self.vers, "neuf", "Encore")


class UnHarnessNaitDepot(unittest.TestCase):
    """RFC-012 D12.1 — un harness qui naît est aussitôt un dépôt git."""

    def test_la_copie_est_un_depot_avec_un_premier_commit(self):
        import subprocess

        from test_hds import MINIMAL, _ecrire_harness

        from kokaji.depot import est_depot
        from kokaji.hds import charger
        from kokaji.naissance import naitre

        with tempfile.TemporaryDirectory() as tmp:
            source = _ecrire_harness(Path(tmp) / "source", MINIMAL)
            ne = naitre(charger(source), Path(tmp) / "harness", "neuf", "Le neuf")
            self.assertTrue(est_depot(ne.racine))
            journal = subprocess.run(
                ["git", "-C", str(ne.racine), "log", "--format=%s"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            self.assertEqual(journal, "naissance : neuf — « Le neuf »")
            # La source, elle, n'est pas devenue un dépôt.
            self.assertFalse(est_depot(source))
