"""Le carnet de pratique capture sans classer.

Aucun nom de domaine ici (§0) : le carnet ne connaît que du texte.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.pratique import STATUTS, ajouter, brutes, lire


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.carnet = Path(self._tmp.name) / "PRATIQUE.md"

    def noter(self, texte: str, **contexte):
        return ajouter(texte, carnet=self.carnet, **contexte)


class Capture(Bac):
    def test_une_note_entre_toujours_en_brut(self):
        """Le statut n'est pas une question qu'on pose à la prise."""
        note = self.noter("quelque chose cloche")
        self.assertEqual(note.statut, "brut")
        self.assertIn(note.statut, STATUTS)

    def test_le_carnet_se_cree_a_la_premiere_note(self):
        self.assertFalse(self.carnet.is_file())
        self.noter("première")
        self.assertTrue(self.carnet.is_file())

    def test_le_contexte_est_facultatif_de_bout_en_bout(self):
        """Une note sans rattachement vaut mieux qu'une note non prise."""
        note = self.noter("juste une impression")
        self.assertEqual(note.contexte, "")
        self.assertEqual(lire(self.carnet)[0].texte, "juste une impression")

    def test_le_contexte_donne_est_conserve(self):
        self.noter("il redemande la même chose", kata="k@c", sujet="S", ha="CAS-0001")
        relue = lire(self.carnet)[0]
        for morceau in ("`k@c`", "sujet : S", "CAS-0001"):
            self.assertIn(morceau, relue.contexte)

    def test_une_note_vide_est_refusee(self):
        with self.assertRaises(ValueError):
            self.noter("   ")

    def test_les_identifiants_ne_se_reutilisent_pas(self):
        ids = [self.noter(f"note {rang}").id for rang in range(3)]
        self.assertEqual(ids, ["NOTE-0001", "NOTE-0002", "NOTE-0003"])

    def test_l_ordre_de_prise_est_conserve(self):
        for rang in range(3):
            self.noter(f"note {rang}")
        self.assertEqual([n.texte for n in lire(self.carnet)], ["note 0", "note 1", "note 2"])

    def test_une_note_sur_plusieurs_lignes_survit(self):
        self.noter("un constat\n\net ce qu'il implique")
        self.assertEqual(lire(self.carnet)[0].texte, "un constat\n\net ce qu'il implique")


class Tri(Bac):
    def test_le_tri_se_fait_a_la_main_dans_le_fichier(self):
        """Promouvoir, c'est éditer une ligne — aucune commande ne le fait."""
        self.noter("à creuser")
        texte = self.carnet.read_text(encoding="utf-8")
        self.carnet.write_text(
            texte.replace("**brut**", "**promu** — vers : docs/carnet.md #9"), encoding="utf-8"
        )

        relue = lire(self.carnet)[0]
        self.assertEqual(relue.statut, "promu")
        self.assertIn("vers : docs/carnet.md #9", relue.contexte)
        self.assertEqual(brutes(self.carnet), [])

    def test_les_brutes_sont_ce_qui_reste_a_relire(self):
        self.noter("une")
        self.noter("deux")
        self.carnet.write_text(
            self.carnet.read_text(encoding="utf-8").replace("**brut**", "**sans-suite**", 1),
            encoding="utf-8",
        )
        self.assertEqual([n.texte for n in brutes(self.carnet)], ["deux"])

    def test_un_statut_hors_liste_se_voit(self):
        """Un carnet mal édité se signale au lieu de se taire."""
        self.noter("une")
        self.carnet.write_text(
            self.carnet.read_text(encoding="utf-8").replace("**brut**", "**urgent**"),
            encoding="utf-8",
        )
        self.assertFalse(lire(self.carnet)[0].connu)


class Relecture(Bac):
    def test_un_carnet_absent_ne_leve_rien(self):
        self.assertEqual(lire(self.carnet), [])
        self.assertEqual(brutes(self.carnet), [])

    def test_la_date_est_celle_du_jour_de_prise(self):
        note = ajouter("une", carnet=self.carnet, quand=datetime(2026, 1, 2, tzinfo=UTC))
        self.assertEqual(note.date, "2026-01-02")
        self.assertEqual(lire(self.carnet)[0].date, "2026-01-02")


if __name__ == "__main__":
    unittest.main()
