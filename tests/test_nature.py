"""La justesse du diagnostic de nature — RFC-003 §4, §5.4 et §7, carnet #9.

Harness purement structurel (§0) : les natures y sont `n1`, `n2`, `n3`. Kokaji
n'en connaît aucune, et ces tests ne doivent pas en connaître davantage.

Aucun réseau : on mesure ce qu'une campagne a produit, on ne la joue pas.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import charger
from kokaji.trempe.banc.nature import couverture, mesurer, natures_emises, verdict

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
      - k1.c1: fait_etabli
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
  justesse:
    defaut: 0.75
personas: personas/
corpus: corpus/
"""


@dataclass
class Tour:
    rang: int
    porteur: str
    reponse: str


@dataclass
class Kin:
    id: str
    typologie: str = ""
    enonce_comme: str = ""

    @property
    def piege(self) -> bool:
        return bool(self.enonce_comme) and self.enonce_comme != self.typologie


def bloc(nature: str | None = None, **reste) -> str:
    etat = {"harness": "h", "kata": "k1", "champs": {}, **reste}
    if nature:
        etat["nature"] = {"valeur": nature, "confiance": "moyen", "revisee_le": "ouverture"}
    return "```json kokaji_state\n" + json.dumps({"kokaji_state": etat}) + "\n```"


def echange(*natures) -> list[Tour]:
    """Un tour par nature ; `None` pour un tour sans bloc."""
    return [Tour(rang, "dit", bloc(n)) for rang, n in enumerate(natures, 1)]


class Extraction(unittest.TestCase):
    def test_la_nature_se_lit_dans_le_bloc_d_etat(self):
        self.assertEqual(natures_emises(echange("n1", "n2")), [(1, "n1"), (2, "n2")])

    def test_un_tour_sans_nature_ne_compte_pas(self):
        self.assertEqual(natures_emises(echange(None, "n1")), [(2, "n1")])

    def test_un_bloc_illisible_n_interrompt_rien(self):
        """R7.2 — un bloc malformé est constaté, jamais bloquant."""
        tours = [Tour(1, "dit", "```json kokaji_state\n{ pas du json\n```"), *echange("n1")]
        self.assertEqual(natures_emises(tours), [(1, "n1")])

    def test_du_texte_hors_bloc_ne_devient_pas_une_nature(self):
        tours = [Tour(1, "dit", 'je dirais que "nature": "n2" ici'), *echange("n1")]
        self.assertEqual(natures_emises(tours), [(1, "n1")])


class Justesse(unittest.TestCase):
    def diagnostic(self, attendue, *natures, enonce=""):
        return mesurer(Kin("kin", attendue, enonce), "k1", echange(*natures))

    def test_c_est_la_derniere_nature_qui_compte(self):
        """La révisabilité est une vertu du RFC : se corriger, c'est bien travailler."""
        self.assertTrue(self.diagnostic("n2", "n1", "n2").juste)
        self.assertFalse(self.diagnostic("n1", "n1", "n2").juste)

    def test_un_kata_muet_n_est_pas_juste(self):
        muet = mesurer(Kin("kin", "n1"), "k1", echange(None, None))
        self.assertTrue(muet.muet)
        self.assertFalse(muet.juste)

    def test_le_tour_de_justesse_ignore_une_bonne_reponse_abandonnee(self):
        """Tomber juste puis changer d'avis, ce n'est pas avoir diagnostiqué."""
        self.assertEqual(self.diagnostic("n1", "n1", "n2", "n1").tour_de_justesse, 3)
        self.assertEqual(self.diagnostic("n1", "n1", "n1").tour_de_justesse, 1)

    def test_les_revisions_se_comptent(self):
        self.assertEqual(self.diagnostic("n3", "n1", "n2", "n3").revisions, 2)
        self.assertEqual(self.diagnostic("n1", "n1", "n1").revisions, 0)

    def test_un_kin_sans_typologie_sort_de_la_mesure(self):
        """Ne rien déclarer n'est pas déclarer un échec."""
        self.assertFalse(self.diagnostic("", "n1").juste)

    def test_le_piege_est_celui_dont_l_enonce_ment(self):
        self.assertTrue(self.diagnostic("n1", "n1", enonce="n2").piege)
        self.assertFalse(self.diagnostic("n1", "n1", enonce="n1").piege)


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name) / "harness"
        for sous in ("kata", "personas", "corpus"):
            (racine / sous).mkdir(parents=True)
        (racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (racine / "registre.yaml").write_text("champs:\n  c1: Un\n", encoding="utf-8")
        (racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(racine)

    def diagnostics(self, *cas):
        """(typologie, natures émises, énoncé_comme) → diagnostics."""
        return [
            mesurer(Kin(f"kin{rang}", attendue, enonce), "k1", echange(*emises))
            for rang, (attendue, emises, enonce) in enumerate(cas, 1)
        ]


class Seuil(Bac):
    def test_le_seuil_vient_du_harness(self):
        self.assertEqual(self.harness.trempe.seuil_justesse("k1"), 0.75)

    def test_un_kata_sans_seuil_propre_prend_celui_du_harness(self):
        self.assertEqual(self.harness.trempe.seuil_justesse("inconnu"), 0.75)

    def test_trois_sur_quatre_tient_le_seuil(self):
        rendu = verdict(self.harness, "k1", self.diagnostics(
            ("n1", ("n1",), ""), ("n2", ("n2",), ""), ("n3", ("n3",), ""), ("n1", ("n2",), ""),
        ))
        self.assertEqual(rendu.taux, 0.75)
        self.assertTrue(rendu.tenu)

    def test_deux_sur_quatre_ne_le_tient_pas(self):
        rendu = verdict(self.harness, "k1", self.diagnostics(
            ("n1", ("n1",), ""), ("n2", ("n2",), ""), ("n3", ("n1",), ""), ("n1", ("n2",), ""),
        ))
        self.assertFalse(rendu.tenu)

    def test_le_piege_rate_fait_tomber_le_verdict_malgre_le_taux(self):
        """« Dont impérativement le piège » n'est pas une pondération."""
        rendu = verdict(self.harness, "k1", self.diagnostics(
            ("n1", ("n1",), ""), ("n2", ("n2",), ""), ("n3", ("n3",), ""), ("n1", ("n2",), "n2"),
        ))
        self.assertEqual(rendu.taux, 0.75)
        self.assertEqual(rendu.pieges, 1)
        self.assertFalse(rendu.pieges_tenus)
        self.assertFalse(rendu.tenu)

    def test_un_kata_muet_pese_dans_le_denominateur(self):
        """Les sortir de la mesure flatterait le taux."""
        rendu = verdict(self.harness, "k1", self.diagnostics(
            ("n1", ("n1",), ""), ("n2", (None,), ""),
        ))
        self.assertEqual(rendu.mesures, 2)
        self.assertEqual(rendu.muets, 1)
        self.assertEqual(rendu.taux, 0.5)

    def test_aucune_mesure_n_est_un_vide_pas_un_echec(self):
        rendu = verdict(self.harness, "k1", [])
        self.assertIsNone(rendu.tenu)
        self.assertIsNone(rendu.taux)
        self.assertIn("aucune mesure", str(rendu))

    def test_sans_seuil_declare_le_seuil_vaut_zero(self):
        """Zéro n'est pas une indulgence : c'est l'aveu qu'aucun seuil n'a été posé."""
        manifest = MANIFEST.replace("  justesse:\n    defaut: 0.75\n", "")
        racine = Path(self._tmp.name) / "nu"
        for sous in ("kata", "personas", "corpus"):
            (racine / sous).mkdir(parents=True)
        (racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (racine / "registre.yaml").write_text("champs:\n  c1: Un\n", encoding="utf-8")
        (racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (racine / "harness.yaml").write_text(manifest, encoding="utf-8")

        self.assertEqual(charger(racine).trempe.seuil_justesse("k1"), 0.0)


class CouvertureDesNatures(unittest.TestCase):
    def test_une_nature_jamais_jouee_est_signalee(self):
        """Jamais jouée n'est pas réussie : c'est inconnue."""
        couv = couverture("k1", [Kin("a", "n1"), Kin("b", "n1")], ("n1", "n2", "n3"))
        self.assertEqual(couv.jouees, {"n1": 2})
        self.assertEqual(couv.manquantes, ("n2", "n3"))

    def test_une_couverture_complete_ne_signale_rien(self):
        couv = couverture("k1", [Kin("a", "n1"), Kin("b", "n2")], ("n1", "n2"))
        self.assertEqual(couv.manquantes, ())


if __name__ == "__main__":
    unittest.main()
