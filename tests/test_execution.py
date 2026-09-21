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

from kokaji.execution import (
    CapaciteRefusee,
    Executeur,
    ExecuteurBoite,
    ExecuteurInerte,
    ExecutionEnRetard,
    executeur_pour,
)
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


class Boite(unittest.TestCase):
    """RFC-017 D17.8 — la boîte aux lettres : job déposé, résultat attendu."""

    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.boite = Path(self._tmp.name)

    def _faux_bac(self, resultat: dict, delai: float = 5.0):
        """Un bac à sable de test : prend le premier job prêt, écrit un résultat."""
        import json
        import threading
        import time

        def surveiller():
            fin = time.monotonic() + delai
            while time.monotonic() < fin:
                for pret in self.boite.glob("*/pret"):
                    job = pret.parent
                    if not (job / "resultat.json").is_file():
                        (job / "resultat.json").write_text(json.dumps(resultat), encoding="utf-8")
                        return
                time.sleep(0.02)

        t = threading.Thread(target=surveiller, daemon=True)
        t.start()
        return t

    def test_un_job_depose_et_un_resultat_lu(self):
        self._faux_bac({"actions": [{"intention": "x"}], "verdict": {"valeur": "ok"}})
        ex = ExecuteurBoite(self.boite, accordees=("execution_shell",), delai=5, intervalle=0.02)
        r = ex.executer({"capacites": ["execution_shell"]}, {"entree": 1})
        self.assertEqual(r.verdict, {"valeur": "ok"})
        self.assertEqual(len(r.actions), 1)
        self.assertFalse(r.inerte)

    def test_une_capacite_non_accordee_refuse_avant_depot(self):
        ex = ExecuteurBoite(self.boite, accordees=("lecture",), delai=1, intervalle=0.02)
        with self.assertRaises(CapaciteRefusee):
            ex.executer({"capacites": ["execution_shell"]}, {})
        # rien n'a été déposé : le run refuse de partir
        self.assertEqual(list(self.boite.glob("*/job.json")), [])

    def test_un_resultat_en_retard_remonte_en_urgence(self):
        ex = ExecuteurBoite(self.boite, accordees=("execution_shell",), delai=0.3, intervalle=0.05)
        with self.assertRaises(ExecutionEnRetard):
            ex.executer({"capacites": ["execution_shell"]}, {})

    def test_sans_boite_l_executeur_est_inerte(self):
        import os

        avant = os.environ.pop("KOKAJI_BOITE_EXECUTION", None)
        try:
            self.assertIsInstance(executeur_pour(), ExecuteurInerte)
        finally:
            if avant is not None:
                os.environ["KOKAJI_BOITE_EXECUTION"] = avant

    def test_une_boite_declaree_donne_l_executeur_boite(self):
        import os

        avant = dict(os.environ)
        os.environ["KOKAJI_BOITE_EXECUTION"] = str(self.boite)
        os.environ["KOKAJI_CAPACITES_ACCORDEES"] = "execution_shell, lecture_depot"
        try:
            ex = executeur_pour()
            self.assertIsInstance(ex, ExecuteurBoite)
            self.assertEqual(ex.accordees, {"execution_shell", "lecture_depot"})
        finally:
            os.environ.clear()
            os.environ.update(avant)


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
