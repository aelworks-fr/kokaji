"""La vigie, et le verdict qui se périme — NOTE-0003, 0009, 0010, 0011.

Le test qui compte est celui de la péremption : c'est le seul qui attrape une
vigie morte, et une vigie morte ne dit rien du tout — ce qui se lit comme si
tout allait bien.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.vigie import Verdict, ecrire_verdicts, lire_verdicts, peremption, verifier_passerelle


class Peremption(unittest.TestCase):
    def releve(self, minutes: float, boucle: float = 60) -> dict:
        quand = datetime.now(UTC) - timedelta(minutes=minutes)
        return {"le": quand.isoformat(timespec="seconds"), "boucle": boucle, "verdicts": []}

    def test_un_verdict_frais_ne_se_perime_pas(self):
        self.assertEqual(peremption(self.releve(0.5)), "")

    def test_un_verdict_vieux_de_plus_de_trois_tours_est_perime(self):
        """La vigie ne tourne plus — et c'est ça, l'information."""
        self.assertIn("ne tourne plus", peremption(self.releve(5)))

    def test_l_absence_de_verdict_n_est_pas_un_calme(self):
        """Le cas des deux jours de veille morte : rien d'écrit, rien de faux."""
        self.assertIn("jamais rien écrit", peremption(None))

    def test_une_date_illisible_ne_passe_pas_pour_fraiche(self):
        self.assertIn("sans date lisible", peremption({"le": "hier", "boucle": 60}))

    def test_un_tour_unique_ne_se_perime_jamais(self):
        """Sans boucle déclarée, il n'y a pas de rythme à trahir."""
        self.assertEqual(peremption(self.releve(10_000, boucle=0)), "")


class Ecriture(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.chemin = Path(self._tmp.name) / "sous" / "verdicts.json"

    def test_le_verdict_se_relit(self):
        ecrire_verdicts(self.chemin, [Verdict("un check", True, "rien à signaler")], 30)
        releve = lire_verdicts(self.chemin)
        self.assertEqual(releve["boucle"], 30)
        self.assertEqual(releve["verdicts"][0]["quoi"], "un check")
        self.assertTrue(releve["verdicts"][0]["tient"])

    def test_aucun_brouillon_ne_reste_a_cote(self):
        """L'écriture est atomique : un fichier tronqué se lirait comme une panne."""
        ecrire_verdicts(self.chemin, [Verdict("un check", True)], 30)
        self.assertEqual([f.name for f in self.chemin.parent.iterdir()], ["verdicts.json"])

    def test_un_fichier_illisible_vaut_absence(self):
        self.chemin.parent.mkdir(parents=True)
        self.chemin.write_text("{ pas du json", encoding="utf-8")
        self.assertIsNone(lire_verdicts(self.chemin))

    def test_un_chemin_absent_vaut_absence(self):
        self.assertIsNone(lire_verdicts(None))
        self.assertIsNone(lire_verdicts(self.chemin))


class Passerelle(unittest.TestCase):
    """Ne pas pouvoir mesurer n'est pas mesurer que tout va bien."""

    def setUp(self):
        from test_hds import MINIMAL, _ecrire_harness

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        _ecrire_harness(racine, MINIMAL)
        from kokaji.hds import charger

        self.harness = {"h": charger(racine)}

    def test_une_passerelle_muette_ne_tient_pas(self):
        """La faute de NOTE-0003, refaite à l'envers : le silence n'est pas un succès."""
        from kokaji import passerelle

        def muette(*a, **k):
            raise passerelle.PasserelleInjoignable("connexion refusée")

        original = passerelle.autorisation_de_la_cle
        passerelle.autorisation_de_la_cle = muette
        self.addCleanup(setattr, passerelle, "autorisation_de_la_cle", original)

        verdict = verifier_passerelle(self.harness, "http://p", "m", "c")
        self.assertFalse(verdict.tient)
        self.assertIn("muette", verdict.detail)

    def test_un_ecart_ne_tient_pas_et_se_nomme(self):
        from kokaji import passerelle

        original = passerelle.autorisation_de_la_cle
        passerelle.autorisation_de_la_cle = lambda *a, **k: ("h/k1",)
        self.addCleanup(setattr, passerelle, "autorisation_de_la_cle", original)

        verdict = verifier_passerelle(self.harness, "http://p", "m", "c")
        self.assertFalse(verdict.tient)
        self.assertIn("h/k1@c1", verdict.detail)

    def test_sans_ecart_le_verdict_tient(self):
        from kokaji import passerelle

        original = passerelle.autorisation_de_la_cle
        passerelle.autorisation_de_la_cle = lambda *a, **k: ("h/k1", "h/k1@c1", "nu/x")
        self.addCleanup(setattr, passerelle, "autorisation_de_la_cle", original)

        verdict = verifier_passerelle(self.harness, "http://p", "m", "c", nus=("nu/x",))
        self.assertTrue(verdict.tient)


if __name__ == "__main__":
    unittest.main()
