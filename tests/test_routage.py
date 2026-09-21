"""Le routage mécanique de la chaîne — RFC-016 D16.3.

Le dojo évalue des conditions, il ne juge pas ; sans condition qui tranche, la
main revient à l'humain — jamais de branche devinée.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.routage import (
    ConditionInvalide,
    evaluer_condition,
    parser_condition,
    projeter,
    router,
)


def etat_verdict(valeur: str) -> dict:
    return {"actions": [{"verdict": {"valeur": valeur, "confiance": 0.9}}]}


class Evaluer(unittest.TestCase):
    def test_une_condition_vide_passe_toujours(self):
        self.assertTrue(evaluer_condition("", {}))
        self.assertTrue(evaluer_condition("   ", {"quoi": "que ce soit"}))

    def test_le_verdict_de_la_derniere_action_se_lit(self):
        self.assertTrue(evaluer_condition("verdict == 'tous_passes'", etat_verdict("tous_passes")))
        self.assertFalse(evaluer_condition("verdict == 'tous_passes'", etat_verdict("echecs")))

    def test_l_alias_resultat_pointe_la_racine(self):
        self.assertTrue(evaluer_condition("resultat.verdict == 'echecs'", etat_verdict("echecs")))

    def test_un_chemin_dans_les_champs(self):
        etat = {"champs": {"cadrage.pret": "fait_etabli"}}
        self.assertTrue(evaluer_condition("champs.cadrage.pret == 'fait_etabli'", etat))

    def test_la_nature_calculee(self):
        self.assertTrue(evaluer_condition("nature == 'urgence'", {"nature": {"valeur": "urgence"}}))

    def test_and_et_or(self):
        etat = etat_verdict("echecs")
        etat["champs"] = {"k.n": 3}
        self.assertTrue(evaluer_condition("verdict == 'echecs' and champs.k.n > 2", etat))
        self.assertFalse(evaluer_condition("verdict == 'echecs' and champs.k.n > 5", etat))
        self.assertTrue(evaluer_condition("verdict == 'tous_passes' or champs.k.n > 2", etat))

    def test_un_ordre_sur_un_absent_est_faux_pas_une_erreur(self):
        self.assertFalse(evaluer_condition("champs.absent > 3", {}))

    def test_les_nombres_se_comparent(self):
        self.assertTrue(evaluer_condition("champs.n >= 3", {"champs": {"n": 3}}))
        self.assertFalse(evaluer_condition("champs.n < 3", {"champs": {"n": 3}}))

    def test_une_condition_illisible_leve(self):
        for mauvaise in ("verdict", "verdict tous_passes", "verdict === 'x'", "a == 1 et b == 2"):
            with self.assertRaises(ConditionInvalide):
                parser_condition(mauvaise)

    def test_la_projection_n_ecrase_pas_un_champ_verdict_reel(self):
        # si l'état porte déjà `verdict`, la dernière action le surcharge (calculé prime)
        vue = projeter({"verdict": "brut", "actions": [{"verdict": {"valeur": "calcule"}}]})
        self.assertEqual(vue["verdict"], "calcule")


@dataclass
class _Arete:
    de: str
    vers: str
    condition: str = ""


@dataclass
class _Chaine:
    aretes: tuple


@dataclass
class _Harness:
    chaine: _Chaine


class Router(unittest.TestCase):
    def harness(self, *aretes):
        return _Harness(chaine=_Chaine(aretes=tuple(_Arete(*a) for a in aretes)))

    def test_une_seule_condition_qui_tranche(self):
        h = self.harness(
            ("tests", "deploiement", "verdict == 'tous_passes'"),
            ("tests", "correction", "verdict == 'echecs'"),
        )
        self.assertEqual(router(h, "tests", etat_verdict("tous_passes")).vers, "deploiement")
        self.assertEqual(router(h, "tests", etat_verdict("echecs")).vers, "correction")

    def test_aucune_condition_ne_tranche_rend_la_main(self):
        h = self.harness(
            ("tests", "deploiement", "verdict == 'tous_passes'"),
            ("tests", "correction", "verdict == 'echecs'"),
        )
        r = router(h, "tests", etat_verdict("partiel"))
        self.assertIsNone(r.vers)
        self.assertIn("aucune condition", r.checkpoint)
        self.assertEqual(set(r.candidats), {"deploiement", "correction"})

    def test_plusieurs_conditions_tranchent_est_ambigu(self):
        h = self.harness(
            ("k", "a", "verdict == 'x'"),
            ("k", "b", "verdict == 'x'"),
        )
        r = router(h, "k", etat_verdict("x"))
        self.assertIsNone(r.vers)
        self.assertIn("ambigu", r.checkpoint)

    def test_une_arete_sans_condition_passe(self):
        h = self.harness(("k", "suite", ""))
        self.assertEqual(router(h, "k", {}).vers, "suite")

    def test_une_fin_de_chaine_rend_la_main(self):
        h = self.harness(("autre", "x", ""))
        r = router(h, "k", {})
        self.assertIsNone(r.vers)
        self.assertIn("fin de chaîne", r.checkpoint)


if __name__ == "__main__":
    unittest.main()
