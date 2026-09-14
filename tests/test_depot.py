"""Un harness, un dépôt — RFC-012, lot A : le dépôt local et son état.

Harness purement structurels (§0). git est appelé pour de vrai, sur des
dossiers jetables : c'est lui qu'on éprouve, pas une maquette.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_hds import MINIMAL, _ecrire_harness

from kokaji.depot import DepotIndisponible, est_depot, etat, initier


def _git(ou: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(ou), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name) / "h"
        _ecrire_harness(self.racine, MINIMAL)


class Initier(Bac):
    def test_un_dossier_devient_un_depot_avec_un_premier_commit(self):
        sha = initier(self.racine, "naissance : h")
        self.assertTrue(est_depot(self.racine))
        self.assertEqual(len(sha), 7)
        self.assertEqual(_git(self.racine, "log", "--format=%s"), "naissance : h")
        self.assertEqual(_git(self.racine, "status", "--porcelain"), "")

    def test_un_depot_ne_s_initie_pas_deux_fois(self):
        initier(self.racine, "naissance : h")
        with self.assertRaises(DepotIndisponible):
            initier(self.racine, "encore")

    def test_un_sous_dossier_d_un_depot_n_est_pas_un_depot(self):
        """`harness/atelier` dans le dépôt de l'instance : pas un dépôt à lui — D12.1."""
        initier(self.racine.parent, "le dépôt du dessus")
        self.assertFalse(est_depot(self.racine))
        # Et il peut le devenir : c'est le geste de la migration.
        initier(self.racine, "naissance : h")
        self.assertTrue(est_depot(self.racine))


class LEtat(Bac):
    def test_sans_depot_l_etat_le_dit(self):
        lu = etat(self.racine)
        self.assertFalse(lu.est_depot)
        self.assertEqual(lu.mot, "sans dépôt")

    def test_un_depot_propre_non_enregistre(self):
        initier(self.racine, "naissance : h")
        lu = etat(self.racine)
        self.assertTrue(lu.est_depot)
        self.assertTrue(lu.propre)
        self.assertEqual(lu.dernier_message, "naissance : h")
        self.assertTrue(lu.dernier_le.startswith("20"))
        self.assertEqual(lu.mot, "non enregistré")

    def test_des_modifications_non_scellees_se_disent(self):
        initier(self.racine, "naissance : h")
        (self.racine / "template.md").write_text("{{ role }} !", encoding="utf-8")
        self.assertEqual(etat(self.racine).mot, "modifications non scellées")

    def test_l_avance_se_compte_depuis_la_reference(self):
        sha0 = initier(self.racine, "naissance : h")
        self.assertEqual(etat(self.racine, sha0).mot, "à jour")
        (self.racine / "template.md").write_text("{{ role }} !", encoding="utf-8")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "scellement")
        lu = etat(self.racine, sha0)
        self.assertEqual(lu.avance, 1)
        self.assertEqual(lu.mot, "en avance de 1")

    def test_une_reference_inconnue_ne_se_devine_pas(self):
        """Le dépôt nu a avancé sans qu'on ait tiré : on ne dit pas « en retard de N »."""
        initier(self.racine, "naissance : h")
        lu = etat(self.racine, "0000000000000000000000000000000000000000")
        self.assertIsNone(lu.avance)
        self.assertFalse(lu.reference_connue)
        self.assertEqual(lu.mot, "non enregistré")


if __name__ == "__main__":
    unittest.main()
