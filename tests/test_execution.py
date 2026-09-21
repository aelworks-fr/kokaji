"""L'exécuteur inerte et le budget au runtime — RFC-016 D16.3/D16.4.

Rien ne s'exécute : le défaut est inerte, et le budget se décompte sur des
compteurs. Tout le runtime s'éprouve sans toucher le monde.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.execution import Executeur, ExecuteurInerte, executeur_pour
from kokaji.routage import Parcours, pas


class Inerte(unittest.TestCase):
    def test_le_defaut_est_inerte(self):
        ex = executeur_pour()
        self.assertIsInstance(ex, ExecuteurInerte)
        self.assertIsInstance(ex, Executeur)

    def test_l_inerte_n_execute_rien_et_le_dit(self):
        r = executeur_pour().executer({"capacites": ["execution_shell"]}, {"entree": 1})
        self.assertTrue(r.inerte)
        self.assertEqual(r.actions, ())
        self.assertIn("inerte", r.note)

    def test_un_moteur_inconnu_reste_inerte(self):
        self.assertIsInstance(executeur_pour("un-agent-quelconque"), ExecuteurInerte)


@dataclass
class _Arete:
    de: str
    vers: str
    condition: str = ""


@dataclass
class _Budget:
    passages: int | None = None


@dataclass
class _Cycle:
    noeuds: tuple
    budget: _Budget


@dataclass
class _Chaine:
    aretes: tuple
    cycles: tuple = ()


@dataclass
class _Harness:
    chaine: _Chaine


def _verdict(v: str) -> dict:
    return {"actions": [{"verdict": {"valeur": v, "confiance": 0.9}}]}


class Budget(unittest.TestCase):
    def harness(self):
        return _Harness(_Chaine(
            aretes=(
                _Arete("tests", "deploiement", "verdict == 'tous_passes'"),
                _Arete("tests", "correction", "verdict == 'echecs'"),
                _Arete("correction", "tests"),
            ),
            cycles=(_Cycle(noeuds=("tests", "correction"), budget=_Budget(passages=3)),),
        ))

    def test_un_pas_hors_cycle_ne_decompte_rien(self):
        etape = pas(self.harness(), "tests", _verdict("tous_passes"), Parcours())
        self.assertEqual(etape.routage.vers, "deploiement")
        self.assertFalse(etape.urgence)

    def test_le_cycle_se_decompte_et_sort_en_urgence(self):
        h, p = self.harness(), Parcours()
        # correction → tests, trois fois permises, la quatrième sort en urgence
        for i in range(3):
            etape = pas(h, "correction", {}, p)
            self.assertEqual(etape.routage.vers, "tests", f"passage {i + 1}")
            self.assertFalse(etape.urgence)
        etape = pas(h, "correction", {}, p)
        self.assertTrue(etape.urgence)
        self.assertIsNone(etape.routage.vers)
        self.assertIn("budget de cycle épuisé", etape.routage.checkpoint)
        self.assertIn("main rendue", etape.conduite)

    def test_sans_budget_de_passages_ne_sort_jamais(self):
        h = _Harness(_Chaine(
            aretes=(_Arete("a", "b"), _Arete("b", "a")),
            cycles=(_Cycle(noeuds=("a", "b"), budget=_Budget(passages=None)),),
        ))
        p = Parcours()
        for _ in range(10):
            self.assertFalse(pas(h, "a", {}, p).urgence)

    def test_un_pas_qui_ne_tranche_pas_reste_un_checkpoint(self):
        etape = pas(self.harness(), "tests", _verdict("partiel"), Parcours())
        self.assertIsNone(etape.routage.vers)
        self.assertFalse(etape.urgence)


if __name__ == "__main__":
    unittest.main()
