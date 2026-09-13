"""Kokaji se trempe lui-même (SPECS §10, R10.2).

Les dépôts de test sont créés à la volée, avec leurs propres interdits : aucun
terme réel n'entre ici — ce serait exactement ce que la règle interdit.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.trempe.depot import charger_interdits, trempe_du_depot

CONFIG = """
interdits:
  - terme-proscrit
  - Autre Terme
exemptions:
  - .trempe-kokaji.yaml
  - exempte/*
commits: 5
"""


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "essai@exemple.test")
        self.git("config", "user.name", "essai")
        self.ecrire(".trempe-kokaji.yaml", CONFIG)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.racine), *args], check=True, capture_output=True)

    def ecrire(self, chemin, contenu):
        fichier = self.racine / chemin
        fichier.parent.mkdir(parents=True, exist_ok=True)
        fichier.write_text(contenu, encoding="utf-8")

    def commiter(self, message="un commit"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)


class Fichiers(Bac):
    def test_un_depot_propre_ne_dit_rien(self):
        self.ecrire("code.py", "# rien à signaler\n")
        self.commiter()
        self.assertEqual(trempe_du_depot(self.racine), ())

    def test_un_terme_interdit_est_situe(self):
        self.ecrire("code.py", "ligne une\nvoici un terme-proscrit ici\n")
        self.commiter()
        trouvailles = trempe_du_depot(self.racine)

        self.assertEqual(len(trouvailles), 1)
        self.assertEqual(trouvailles[0].ou, "code.py")
        self.assertEqual(trouvailles[0].ligne, 2)

    def test_la_recherche_ignore_la_casse(self):
        self.ecrire("code.py", "AUTRE terme\n")
        self.commiter()
        self.assertEqual(len(trempe_du_depot(self.racine)), 1)

    def test_un_fichier_exempte_est_passe(self):
        self.ecrire("exempte/note.md", "terme-proscrit\n")
        self.commiter()
        self.assertEqual(trempe_du_depot(self.racine), ())

    def test_un_fichier_non_suivi_n_est_pas_lu(self):
        """Ce qui n'est pas versionné ne quitte pas la machine."""
        self.ecrire("code.py", "propre\n")
        self.commiter()
        self.ecrire("brouillon.md", "terme-proscrit\n")
        self.assertEqual(trempe_du_depot(self.racine), ())

    def test_un_binaire_ne_fait_pas_tomber_la_trempe(self):
        (self.racine / "image.bin").write_bytes(b"\x00\x01\x02\xff")
        self.commiter()
        self.assertEqual(trempe_du_depot(self.racine), ())


class Commits(Bac):
    def test_un_message_de_commit_est_relu(self):
        """R10.1 couvre aussi les commits."""
        self.ecrire("code.py", "propre\n")
        self.commiter("ajoute un terme-proscrit au passage")
        trouvailles = trempe_du_depot(self.racine)

        self.assertEqual(len(trouvailles), 1)
        self.assertTrue(trouvailles[0].ou.startswith("commit "))
        self.assertIsNone(trouvailles[0].ligne)


class Configuration(Bac):
    def test_la_liste_locale_complete_la_publique(self):
        self.ecrire(".trempe-kokaji.local.yaml", "interdits: [secret-local]\n")
        interdits = charger_interdits(self.racine)

        self.assertIn("terme-proscrit", interdits.termes)
        self.assertIn("secret-local", interdits.termes)

    def test_sans_liste_rien_n_est_cherche(self):
        (self.racine / ".trempe-kokaji.yaml").unlink()
        self.ecrire("code.py", "terme-proscrit\n")
        self.commiter()
        self.assertEqual(trempe_du_depot(self.racine), ())


if __name__ == "__main__":
    unittest.main()
