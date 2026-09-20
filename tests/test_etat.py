"""Le bloc d'état : `actions[]` (RFC-016 D16.5).

Un kata qui touche le monde doit dire ce qu'il a fait, et son verdict est ce
qu'il **constate**, jamais ce qu'il affirme sans preuve.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.etat import fautes_de_bloc
from kokaji.hds import charger

MANIFEST = """
harness:
  id: h
  nom: H
  version: 0.1.0
  langue: fr
  domaine: un domaine quelconque
kata:
  - id: echange
    nom: Échange
    source: kata/echange.yaml
    livrable: L
    amont: []
    herite: []
    produit:
      - echange.c1: fait_etabli
  - id: tests
    nom: Tests
    source: kata/tests.yaml
    livrable: Rapport
    amont: []
    herite: []
    produit:
      - tests.verdict: fait_etabli
    raccourci: sonde
    perception: { entrees: [suite], retours: [execution] }
    effets: { monde_lecture: [execution] }
    capacites: [execution_shell]
    trempe:
      verificateurs:
        - { type: executable, check: "le rapport couvre la suite", source: rapport.xml }
chaine:
  noeuds:
    - { id: echange, type: kata, nom: Échange }
    - { id: tests, type: kata, nom: Tests }
  aretes: []
template: template.md
cibles:
  - id: c1
    etat_structure: true
    en_tete: H
    packaging: dossier
trempe:
  vocabulaire_interdit: []
  registre: registre.yaml
  checks_session: []
personas: personas/
corpus: corpus/
"""


ACTION = {
    "intention": "faire tourner la suite",
    "canal": "monde_lecture",
    "artefact": "rapport.xml",
    "verdict": {"valeur": "echecs", "detail": "2/148", "confiance": 0.98},
}


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name) / "h"
        for sous in ("kata", "personas", "corpus"):
            (racine / sous).mkdir(parents=True)
        (racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (racine / "registre.yaml").write_text(
            "champs:\n  c1: Un\n  verdict: Le verdict\n", encoding="utf-8"
        )
        for k in ("echange", "tests"):
            (racine / "kata" / f"{k}.yaml").write_text(
                "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
            )
        (racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(racine)

    def fautes(self, id_kata: str, etat: dict, **kw):
        kata = self.harness.kata_par_id(id_kata)
        champs = tuple(r for r, _ in kata.produit)
        return [r for r, _ in fautes_de_bloc(self.harness, kata, champs, etat, **kw)]

class Actions(Bac):
    ACTION = ACTION
    def test_un_kata_d_echange_sans_actions_ne_faute_pas(self):
        self.assertEqual(self.fautes("echange", {"champs": {"echange.c1": "fait_etabli"}}), [])

    def test_un_kata_qui_agit_doit_porter_des_actions(self):
        r = self.fautes("tests", {"champs": {"tests.verdict": "fait_etabli"}})
        self.assertIn("etat-actions-declarees", r)

    def test_un_kata_qui_agit_avec_ses_actions_tient(self):
        r = self.fautes("tests", {
            "champs": {"tests.verdict": "fait_etabli"}, "actions": [self.ACTION]
        })
        self.assertEqual(r, [])

    def test_un_echange_qui_porte_des_actions_faute(self):
        r = self.fautes("echange", {
            "champs": {"echange.c1": "fait_etabli"}, "actions": [self.ACTION]
        })
        self.assertIn("etat-actions-declarees", r)

    def test_une_action_sur_un_canal_non_declare_faute(self):
        action = {**self.ACTION, "canal": "monde_ecriture"}
        r = self.fautes("tests", {"champs": {"tests.verdict": "fait_etabli"}, "actions": [action]})
        self.assertIn("etat-actions-declarees", r)

    def test_un_verdict_sans_valeur_faute(self):
        action = {**self.ACTION, "verdict": {"detail": "x", "confiance": 0.5}}
        r = self.fautes("tests", {"champs": {"tests.verdict": "fait_etabli"}, "actions": [action]})
        self.assertIn("etat-actions-declarees", r)

    def test_une_confiance_hors_intervalle_faute(self):
        action = {**self.ACTION, "verdict": {"valeur": "ok", "confiance": 1.5}}
        r = self.fautes("tests", {"champs": {"tests.verdict": "fait_etabli"}, "actions": [action]})
        self.assertIn("etat-actions-declarees", r)

    def test_un_canal_declare_mais_jamais_exerce_faute(self):
        # le kata déclare monde_lecture mais l'action est absente de ce canal
        action = {**self.ACTION, "canal": "monde_lecture"}
        r = self.fautes("tests", {"champs": {"tests.verdict": "fait_etabli"}, "actions": [
            {**action, "intention": "autre", "verdict": {"valeur": "ok", "confiance": 0.9}},
        ]})
        self.assertEqual(r, [])  # le canal est exercé


if __name__ == "__main__":
    unittest.main()
