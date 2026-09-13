"""Le lint de resserrage propose, il n'applique jamais (RFC-002 §6.4).

Harness purement structurel, aucun réseau.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import charger
from kokaji.trempe.banc.resserrage import fragment, observer, proposer

MANIFEST = """
harness:
  id: h
  nom: H
  version: 0.1.0
  langue: fr
  domaine: un domaine quelconque
kata:
  - id: k1
    nom: K1
    source: kata/k1.yaml
    livrable: L1
    amont: []
    herite: []
    produit:
      - k1.c1: hypothese
      - k1.c2: fait_etabli
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
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

FICHE = """---
harness: h
kata: k1
version_coupe: "v"
cible: c1
statut: brut
---

session `s`
"""


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name) / "harness"
        self.addCleanup(self._tmp.cleanup)
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text(
            "champs:\n  c1: Un\n  c2: Deux\n", encoding="utf-8"
        )
        (self.racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.racine)
        self.kata = self.harness.kata_par_id("k1")

    def ha(self, nom: str, *champs: dict):
        dossier = self.harness.corpus / nom
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "fiche.md").write_text(FICHE, encoding="utf-8")
        (dossier / "etats.jsonl").write_text(
            "".join(
                json.dumps({"horodatage": "2026-01-01", "etat": {"champs": c}}) + "\n"
                for c in champs
            ),
            encoding="utf-8",
        )

    def corpus(self, *etats: dict):
        for rang, etat in enumerate(etats, 1):
            self.ha(f"CAS-{rang:04d}-x", etat)
        return observer(self.harness, self.kata, self.harness.corpus)

    def proposition(self, champ: str, observations, minimum=3):
        obs = next(o for o in observations if o.champ == champ)
        return proposer(self.harness, obs, minimum)


class Observer(Bac):
    def test_seul_le_dernier_bloc_d_un_ha_compte(self):
        """C'est l'état final qui dit ce que le kata a livré."""
        self.ha("CAS-0001-x", {"c1": "en_pause"}, {"c1": "fait_etabli"})
        obs = observer(self.harness, self.kata, self.harness.corpus)
        self.assertEqual(next(o for o in obs if o.champ == "k1.c1").statuts, ("fait_etabli",))

    def test_un_champ_absent_n_est_pas_compte(self):
        obs = self.corpus({"c1": "fait_etabli"})
        self.assertEqual(next(o for o in obs if o.champ == "k1.c2").observes, 0)


class Proposer(Bac):
    def test_un_champ_durablement_plus_fort_est_proposable(self):
        obs = self.corpus(*[{"c1": "fait_etabli"}] * 3)
        proposition = self.proposition("k1.c1", obs)

        self.assertIsNotNone(proposition)
        self.assertEqual((proposition.declare, proposition.propose), ("hypothese", "fait_etabli"))

    def test_un_seul_ha_en_dessous_retient_la_promesse(self):
        """Une garantie est un minimum : le plus faible observé fait loi."""
        obs = self.corpus({"c1": "fait_etabli"}, {"c1": "fait_etabli"}, {"c1": "hypothese"})
        self.assertIsNone(self.proposition("k1.c1", obs))

    def test_en_deca_du_minimum_on_ne_conclut_rien(self):
        obs = self.corpus({"c1": "fait_etabli"}, {"c1": "fait_etabli"})
        self.assertIsNone(self.proposition("k1.c1", obs, minimum=3))

    def test_un_champ_livre_plus_faible_ne_donne_rien(self):
        """La sur-promesse est l'affaire du carré, pas du resserrage."""
        obs = self.corpus(*[{"c2": "hypothese"}] * 3)
        self.assertIsNone(self.proposition("k1.c2", obs))

    def test_un_statut_hors_taxonomie_ne_garantit_rien(self):
        obs = self.corpus(*[{"c1": "inventé"}] * 3)
        self.assertIsNone(self.proposition("k1.c1", obs))


class Fragment(Bac):
    def test_le_fragment_porte_tout_le_produit_et_marque_le_resserrage(self):
        obs = self.corpus(*[{"c1": "fait_etabli"}] * 3)
        propositions = [self.proposition("k1.c1", obs)]
        rendu = fragment(self.kata, propositions)

        self.assertIn("- k1.c1: fait_etabli   # resserré", rendu)
        self.assertIn("- k1.c2: fait_etabli", rendu)
        self.assertNotIn("k1.c2: fait_etabli   # resserré", rendu)


if __name__ == "__main__":
    unittest.main()
