"""Le judge sur grille — RFC-008 §7.

Harness purement structurels (§0). Le juge est un double injecté : ce qu'on
éprouve est la discipline autour de l'appel, pas le modèle.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.adoption import adopter_textes
from kokaji.trempe.banc.jugement import JugeRefuse, deja_juge, juger_grille

GRILLE = """\
  grille_judge:
  - { id: clarte, question: "L'échange avance-t-il par questions claires ?", echelle: "1-5" }
  - { id: sobriete, question: "Le kata s'en tient-il à ce qui a été dit ?", echelle: "1-5" }
"""


class Juge:
    """Un juge de papier : répond ce qu'on lui a mis dans la bouche."""

    def __init__(self, *reponses: str):
        self.reponses = list(reponses)
        self.recu: list[tuple[str, list]] = []

    def completer(self, modele: str, messages: list, temperature=None) -> str:
        self.recu.append((modele, messages))
        return self.reponses.pop(0) if self.reponses else "{}"


def note(critere: str, valeur) -> str:
    return f'```json\n{{ "critere": "{critere}", "note": {valeur}, "motif": "vu" }}\n```'


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        harness = adopter_textes(
            {"ouvrir": "Tu ouvres le sujet."},
            vers=self.racine, identifiant="h", nom="H",
        )
        manifest = harness.racine / "harness.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "  checks_session: []", "  checks_session: []\n" + GRILLE.rstrip()
            ),
            encoding="utf-8",
        )
        from kokaji.hds import charger

        self.harness = charger(harness.racine)
        self.dossier = self.harness.corpus / "CAS-0001-ouvrir-nue-abc123"
        self.dossier.mkdir(parents=True)
        (self.dossier / "fiche.md").write_text(
            "---\nharness: h\nkata: ouvrir\ncible: nue\nmoteur: f/pratiquant\n"
            'version_coupe: "abc123"\n---\n\n# CAS-0001\n',
            encoding="utf-8",
        )
        (self.dossier / "transcript.md").write_text(
            "## Tour 1\n\n**Porteur** — mon sujet\n\n**Kata** —\n\nune question\n"
            '\n```json kokaji_state\n{"secret": "déclaré, pas prouvé"}\n```\n',
            encoding="utf-8",
        )

    def jugements(self) -> list[dict]:
        return [
            json.loads(ligne)
            for ligne in (self.dossier / "jugements.jsonl")
            .read_text(encoding="utf-8").splitlines()
            if ligne.strip()
        ]


class LaGrille(Bac):
    def test_le_manifest_porte_la_grille_validee(self):
        grille = self.harness.trempe.grille_judge
        self.assertEqual([c.id for c in grille], ["clarte", "sobriete"])
        self.assertEqual(grille[0].bornes, (1, 5))

    def test_une_echelle_a_l_envers_refuse_le_harness(self):
        """Une grille fausse se refuse au chargement, pas en pleine campagne."""
        from kokaji.hds import ManifestInvalide, charger

        manifest = self.harness.racine / "harness.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace('echelle: "1-5"', 'echelle: "5-1"'),
            encoding="utf-8",
        )
        with self.assertRaises(ManifestInvalide) as refus:
            charger(self.harness.racine)
        self.assertIn("bornes croissantes", str(refus.exception))


class LeJugement(Bac):
    def test_chaque_critere_est_note_et_rattache_au_ha(self):
        juge = Juge(note("clarte", 4), note("sobriete", 2))
        fait = juger_grille(self.harness, self.dossier, juge, "f/juge")

        self.assertEqual([(s.critere, s.note) for s in fait.scores],
                         [("clarte", 4), ("sobriete", 2)])
        (ecrit,) = self.jugements()
        self.assertEqual(ecrit["juge"], "f/juge")
        self.assertEqual(ecrit["version_coupe"], "abc123")
        self.assertEqual(ecrit["kata"], "ouvrir")
        self.assertEqual(ecrit["cible"], "nue")
        self.assertEqual(ecrit["moteur_pratiquant"], "f/pratiquant")

    def test_une_question_a_la_fois(self):
        """Posées ensemble, elles s'entraînent vers une réponse uniforme."""
        juge = Juge(note("clarte", 3), note("sobriete", 3))
        juger_grille(self.harness, self.dossier, juge, "f/juge")
        self.assertEqual(len(juge.recu), 2)
        self.assertIn("questions claires", juge.recu[0][1][0]["content"])
        self.assertNotIn("s'en tient-il", juge.recu[0][1][0]["content"])

    def test_les_blocs_d_etat_sont_hors_de_la_matiere(self):
        """Ils disent ce que le kata déclare, pas ce qu'il fait."""
        juge = Juge(note("clarte", 3), note("sobriete", 3))
        juger_grille(self.harness, self.dossier, juge, "f/juge")
        matiere = juge.recu[0][1][1]["content"]
        self.assertNotIn("déclaré, pas prouvé", matiere)
        self.assertIn("une question", matiere)

    def test_le_juge_n_est_jamais_le_pratiquant(self):
        with self.assertRaises(JugeRefuse) as refus:
            juger_grille(self.harness, self.dossier, Juge(), "f/pratiquant")
        self.assertIn("confondus", str(refus.exception))
        self.assertFalse((self.dossier / "jugements.jsonl").is_file())

    def test_null_est_une_reponse_et_hors_echelle_n_en_est_pas_une(self):
        juge = Juge(
            '```json\n{ "critere": "clarte", "note": null, "motif": "trop court" }\n```',
            note("sobriete", 7),
        )
        fait = juger_grille(self.harness, self.dossier, juge, "f/juge")
        self.assertIsNone(fait.scores[0].note)
        self.assertEqual(fait.scores[0].motif, "trop court")
        # Un 7 sur 5 n'est pas une note haute : c'est un juge hors consigne.
        self.assertIsNone(fait.scores[1].note)
        self.assertIn("hors échelle", fait.scores[1].motif)

    def test_une_reponse_a_cote_ne_se_rattache_pas(self):
        """Une note du mauvais critère est pire qu'une absence de note."""
        juge = Juge(note("sobriete", 5), note("sobriete", 5))
        fait = juger_grille(self.harness, self.dossier, juge, "f/juge")
        self.assertIsNone(fait.scores[0].note)  # clarte : le juge a répondu à côté
        self.assertEqual(fait.scores[1].note, 5)

    def test_deux_jugements_s_ajoutent_sans_s_effacer(self):
        juger_grille(self.harness, self.dossier,
                     Juge(note("clarte", 3), note("sobriete", 3)), "f/juge")
        juger_grille(self.harness, self.dossier,
                     Juge(note("clarte", 5), note("sobriete", 1)), "f/autre-juge")
        self.assertEqual([j["juge"] for j in self.jugements()], ["f/juge", "f/autre-juge"])

    def test_deja_juge_ne_vaut_que_pour_le_meme_couple(self):
        juger_grille(self.harness, self.dossier,
                     Juge(note("clarte", 3), note("sobriete", 3)), "f/juge")
        self.assertTrue(deja_juge(self.dossier, "f/juge", "abc123"))
        self.assertFalse(deja_juge(self.dossier, "f/autre-juge", "abc123"))
        self.assertFalse(deja_juge(self.dossier, "f/juge", "def456"))

    def test_sans_grille_le_refus_est_nomme(self):
        from kokaji.hds import charger

        manifest = self.harness.racine / "harness.yaml"
        texte = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            texte[: texte.index("  grille_judge:")]
            + texte[texte.index("personas:") :],
            encoding="utf-8",
        )
        with self.assertRaises(JugeRefuse) as refus:
            juger_grille(charger(self.harness.racine), self.dossier, Juge(), "f/juge")
        self.assertIn("aucune grille", str(refus.exception))


if __name__ == "__main__":
    unittest.main()
