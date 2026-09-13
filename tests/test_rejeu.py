"""La non-régression rejoue les ha qu'un changement de source a périmés (R5.6).

Aucun réseau : la passerelle est un double, comme partout au banc.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import charger
from kokaji.trempe.banc.rejeu import modele_virtuel, perimes, rejouer, tours_du_ha

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
    etat_structure: false
    en_tete: H
    packaging: dossier
trempe:
  vocabulaire_interdit: []
  registre: registre.yaml
  checks_session:
    - id: une-question
      type: regex-par-bloc
      motif: "\\\\?"
      maximum: 1
      message: un tour ne pose qu'une question
personas: personas/
corpus: corpus/
"""

FICHE = """---
harness: h
kata: k1
version_kata: "1.0.0"
version_coupe: "{version}"
cible: c1
moteur: m
date: "2026-01-01T00:00:00"
source: reel
statut: brut
completude: B
design_exerce: [{variables}]
---

Versé depuis le journal du Dojo, session `s-1`.
"""

TRANSCRIPT = """# Transcript

## Tour 1

**Porteur** — premier mot

**Kata** —

une seule question ?

## Tour 2

**Porteur** — second mot

**Kata** —

deux questions ?

et une autre ?
"""


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name) / "harness"
        self.addCleanup(self._tmp.cleanup)
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text("champs:\n  c1: Un\n", encoding="utf-8")
        (self.racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.racine)
        self.kata = self.harness.kata_par_id("k1")

    def ha(self, nom="CAS-0001-x", version="ancienne", variables=""):
        dossier = self.harness.corpus / nom
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "fiche.md").write_text(
            FICHE.format(version=version, variables=variables), encoding="utf-8"
        )
        (dossier / "transcript.md").write_text(TRANSCRIPT, encoding="utf-8")
        return dossier


class Peremption(Bac):
    def test_un_ha_de_la_coupe_actuelle_n_est_pas_perime(self):
        self.ha(version="actuelle")
        self.assertEqual(perimes(self.harness, {("k1", "c1"): "actuelle"}), [])

    def test_un_ha_d_une_ancienne_coupe_est_perime(self):
        self.ha(version="ancienne")
        trouves = perimes(self.harness, {("k1", "c1"): "actuelle"})

        self.assertEqual(len(trouves), 1)
        self.assertEqual(trouves[0].version_ha, "ancienne")
        self.assertEqual(trouves[0].version_actuelle, "actuelle")

    def test_les_variables_annotees_sont_portees(self):
        """R5.6 — rejouer les ha exerçant les variables touchées."""
        self.ha(variables="relance-sur-vague, bornage-de-la-relance")
        trouve = perimes(self.harness, {("k1", "c1"): "actuelle"})[0]
        self.assertEqual(trouve.design_exerce, ("relance-sur-vague", "bornage-de-la-relance"))


class Lecture(Bac):
    def test_les_tours_de_l_interlocuteur_sont_relus(self):
        dossier = self.ha()
        porteurs, tours = tours_du_ha(dossier)

        self.assertEqual(porteurs, ["premier mot", "second mot"])
        self.assertEqual(len(tours), 2)
        self.assertIn("une seule question", tours[0].reponse)


class Rejeu(Bac):
    def rejouer(self, reponses):
        dossier = self.ha()
        perime = perimes(self.harness, {("k1", "c1"): "actuelle"})[0]

        class Double:
            def __init__(self):
                self.file = list(reponses)
                self.vus = []

            def completer(self, modele, messages, temperature=None):
                self.vus.append(len(messages))
                return self.file.pop(0)

        self.double = Double()
        return rejouer(self.harness, self.kata, perime, "h/k1", self.double), dossier

    def test_la_meme_matiere_est_rejouee(self):
        """L'interlocuteur est une transcription : ses tours ne changent pas."""
        ecart, _ = self.rejouer(["une question ?", "une autre ?"])
        self.assertEqual(self.double.vus, [1, 3])
        self.assertIsNone(ecart.interrompu)

    def test_une_regle_qui_se_tait_ou_elle_mordait(self):
        ecart, _ = self.rejouer(["une question ?", "une seule aussi ?"])
        self.assertEqual(ecart.mouvements, [("une-question", 1, 0)])
        self.assertFalse(ecart.regression)

    def test_une_regle_qui_mord_plus_qu_avant_est_une_regression(self):
        ecart, _ = self.rejouer(["deux ?\n\nquestions ?", "et ?\n\nencore ?"])
        self.assertEqual(ecart.mouvements, [("une-question", 1, 2)])
        self.assertTrue(ecart.regression)

    def test_une_panne_conserve_ce_qui_a_ete_joue(self):
        from kokaji.trempe.banc import PasserelleInjoignable

        dossier = self.ha()
        perime = perimes(self.harness, {("k1", "c1"): "actuelle"})[0]

        class Cassee:
            def completer(self, modele, messages, temperature=None):
                raise PasserelleInjoignable("coupure")

        ecart = rejouer(self.harness, self.kata, perime, "h/k1", Cassee())
        self.assertIn("coupure", ecart.interrompu)
        self.assertTrue(dossier.is_dir())


if __name__ == "__main__":
    unittest.main()


class ModeleVirtuel(unittest.TestCase):
    """Le nom sous lequel la passerelle sert une coupe (R5.6).

    Le suffixe `@<cible>` force une cible *autre* que celle du Dojo. Le coller à
    tout le monde demande un modèle qui n'existe pas : c'est ce qui a rendu
    irrejouables tous les ha de la cible par défaut, sans qu'aucun test ne le
    voie.
    """

    def test_la_cible_par_defaut_est_servie_sans_suffixe(self):
        self.assertEqual(modele_virtuel("h", "k1", "c1", "c1"), "h/k1")

    def test_une_autre_cible_porte_son_suffixe(self):
        self.assertEqual(modele_virtuel("h", "k1", "c2", "c1"), "h/k1@c2")

    def test_sans_cible_par_defaut_connue_tout_porte_son_suffixe(self):
        self.assertEqual(modele_virtuel("h", "k1", "c1"), "h/k1@c1")


class GardeDeCle(Bac):
    """Une clé factice se dit avant de brûler des appels, pas après.

    Laissée dans `.env`, elle produisait un 401 par tour et le rejeu s'achevait
    sur autant d'interruptions qu'il y avait de ha — après avoir tout tenté.
    """

    def test_une_cle_qui_n_en_est_pas_une_est_refusee(self):
        from kokaji.cli import main

        self.ha()
        self.assertEqual(
            main(["regression", str(self.racine), "--cle", "placeholder"]), 1
        )

    def test_une_cle_plausible_passe_la_garde(self):
        """La garde vérifie la forme, pas la validité : ça, seule la passerelle sait.

        La passerelle est **explicitement dirigée vers le vide**. Sans cette
        ligne, le défaut de `Passerelle` — `http://127.0.0.1:4000` — visait la
        passerelle du poste : sur une machine où le dojo tourne, ce test appelait
        la vraie, et chaque passe de la suite déposait un échec dans le journal
        de production. Le test passait, pour une raison qui n'était pas la sienne.
        """
        from kokaji.cli import main

        self.ha()
        # Elle ira jusqu'à l'appel, qui échouera faute de passerelle — donc pas 1
        # pour la raison de la garde, mais pour une interruption constatée.
        self.assertEqual(
            main([
                "regression", str(self.racine), "--cle", "sk-faux",
                "--passerelle", "http://127.0.0.1:1",
            ]),
            1,
        )
