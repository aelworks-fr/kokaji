"""L'adoption d'un harness exogène — RFC-008 N0.

Harness purement structurels (§0) : les prompts sont des textes neutres.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.adoption import AdoptionRefusee, adopter_etape, importer
from kokaji.forge import forger_harness
from kokaji.passerelle import modeles_virtuels


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.textes = self.racine / "textes"
        self.textes.mkdir()

    def prompt(self, nom: str, texte: str = "Tu accompagnes une étape.") -> Path:
        chemin = self.textes / nom
        chemin.write_text(texte, encoding="utf-8")
        return chemin

    def adopter(self, *chemins: Path, **options):
        return importer(
            list(chemins),
            vers=self.racine / "harness",
            identifiant=options.pop("identifiant", "adopte"),
            nom=options.pop("nom", "Un harness adopté"),
            **options,
        )


class Adoption(Bac):
    def test_chaque_prompt_devient_un_kata_dans_l_ordre_donne(self):
        harness = self.adopter(self.prompt("ouvrir.md"), self.prompt("conclure.md"))
        self.assertTrue(harness.exogene)
        self.assertEqual([k.id for k in harness.kata], ["ouvrir", "conclure"])
        self.assertEqual([c.id for c in harness.cibles], ["nue"])
        self.assertFalse(harness.cibles[0].etat_structure)

    def test_la_provenance_est_estampillee_et_stable(self):
        """Le même import redonne le même checksum, quel que soit l'ordre."""
        a, b = self.prompt("ouvrir.md"), self.prompt("conclure.md")
        un = dict(self.adopter(a, b).provenance)
        deux = dict(
            importer([b, a], vers=self.racine / "h2", identifiant="h2", nom="H2").provenance
        )
        self.assertEqual(un["checksum_import"], deux["checksum_import"])
        self.assertTrue(un["date_import"])
        self.assertEqual(un["source"], "manuel")

    def test_la_forge_est_passe_plat(self):
        """Le texte importé sort tel quel — c'est la promesse du §5."""
        harness = self.adopter(self.prompt("ouvrir.md", "Le texte, exactement lui."))
        forger_harness(harness, sortie=self.racine / "dist")
        coupe = (self.racine / "dist" / "adopte" / "nue" / "ouvrir.md").read_text(
            encoding="utf-8"
        )
        self.assertTrue(coupe.startswith("Le texte, exactement lui.\n"))
        self.assertIn("adopte/ouvrir", coupe)  # l'estampille, seule addition

    def test_les_modeles_virtuels_sont_ceux_de_tout_harness(self):
        """« Tout ce qui sait servir un kata sait servir un import » (§4)."""
        harness = self.adopter(self.prompt("ouvrir.md"))
        self.assertEqual(
            modeles_virtuels(harness), ("adopte/ouvrir", "adopte/ouvrir@nue")
        )


class Refus(Bac):
    """§9 — erreur explicite, et rien d'enregistré."""

    def test_un_fichier_absent_refuse_tout(self):
        present = self.prompt("ouvrir.md")
        with self.assertRaises(AdoptionRefusee) as refus:
            self.adopter(present, self.textes / "absent.md")
        self.assertIn("absent", str(refus.exception))
        self.assertFalse((self.racine / "harness").exists())

    def test_un_dossier_deja_pris_refuse_sans_toucher(self):
        self.adopter(self.prompt("ouvrir.md"))
        temoin = (self.racine / "harness" / "adopte" / "harness.yaml").read_text(
            encoding="utf-8"
        )
        with self.assertRaises(AdoptionRefusee):
            self.adopter(self.prompt("autre.md"))
        self.assertEqual(
            (self.racine / "harness" / "adopte" / "harness.yaml").read_text(
                encoding="utf-8"
            ),
            temoin,
        )

    def test_un_prompt_vide_refuse_tout(self):
        with self.assertRaises(AdoptionRefusee):
            self.adopter(self.prompt("vide.md", "  \n"))
        self.assertFalse((self.racine / "harness").exists())


class LeManifestDit(Bac):
    """Ce que le chargeur exige d'un exogène, et refuse d'un ordinaire."""

    def test_un_exogene_sans_provenance_est_refuse(self):
        """Sans elle, « exogène » ne serait qu'un mot."""
        from kokaji.hds import ManifestInvalide, charger

        harness = self.adopter(self.prompt("ouvrir.md"))
        manifest = harness.racine / "harness.yaml"
        texte = manifest.read_text(encoding="utf-8")
        debut = texte.index("  provenance:")
        fin = texte.index("kata:")
        manifest.write_text(texte[:debut] + texte[fin:], encoding="utf-8")
        with self.assertRaises(ManifestInvalide) as refus:
            charger(harness.racine)
        self.assertIn("provenance", str(refus.exception))

    def test_un_harness_ordinaire_ne_porte_pas_de_provenance(self):
        from kokaji.hds import ManifestInvalide, charger

        harness = self.adopter(self.prompt("ouvrir.md"))
        manifest = harness.racine / "harness.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace("  exogene: true\n", ""),
            encoding="utf-8",
        )
        with self.assertRaises(ManifestInvalide) as refus:
            charger(harness.racine)
        self.assertIn("réservée aux harness", str(refus.exception))


class UneEtapeDePlus(Bac):
    """Le harness adopté grandit d'un texte — après le premier import."""

    def test_l_etape_entre_et_la_chaine_la_porte(self):
        harness = self.adopter(self.prompt("ouvrir.md"))
        grandi = adopter_etape(harness.racine, "relire", "Tu relis ce qui est acquis.")
        self.assertEqual([k.id for k in grandi.kata], ["ouvrir", "relire"])
        self.assertIn("relire", [n.id for n in grandi.chaine.noeuds])
        self.assertEqual(
            (harness.racine / "prompts" / "relire.md").read_text(encoding="utf-8"),
            "Tu relis ce qui est acquis.",
        )

    def test_les_commentaires_du_manifest_survivent(self):
        """La leçon du premier scellement réel, tenue ici aussi."""
        harness = self.adopter(self.prompt("ouvrir.md"))
        adopter_etape(harness.racine, "relire", "Un texte.")
        manifest = (harness.racine / "harness.yaml").read_text(encoding="utf-8")
        self.assertIn("# Harness adopté — RFC-008 N0", manifest)
        self.assertIn("La provenance, non", manifest.replace("la provenance, non", "La provenance, non"))

    def test_un_harness_natif_est_refuse_vers_le_bon_geste(self):
        from kokaji.naissance import semer

        semer(self.racine / "natif", "natif", "Un natif")
        with self.assertRaises(AdoptionRefusee) as refus:
            adopter_etape(self.racine / "natif" / "natif", "relire", "Un texte.")
        self.assertIn("module design", str(refus.exception))

    def test_un_nom_deja_pris_est_refuse_sans_rien_toucher(self):
        harness = self.adopter(self.prompt("ouvrir.md"))
        avant = (harness.racine / "harness.yaml").read_text(encoding="utf-8")
        with self.assertRaises(AdoptionRefusee):
            adopter_etape(harness.racine, "ouvrir", "Un doublon.")
        self.assertEqual(
            (harness.racine / "harness.yaml").read_text(encoding="utf-8"), avant
        )

    def test_un_echec_apres_ecriture_remet_tout_a_l_octet_pres(self):
        """Le refus tardif est le seul qui teste le retour arrière : le doublon,
        lui, est refusé avant toute écriture."""
        from unittest.mock import patch

        from kokaji import adoption

        harness = self.adopter(self.prompt("ouvrir.md"))
        avant = (harness.racine / "harness.yaml").read_text(encoding="utf-8")
        vrai = adoption.charger
        with patch.object(
            adoption, "charger",
            side_effect=[vrai(harness.racine), RuntimeError("la copie ne tient pas")],
        ), self.assertRaises(AdoptionRefusee):
            adopter_etape(harness.racine, "relire", "Un texte.")
        self.assertEqual(
            (harness.racine / "harness.yaml").read_text(encoding="utf-8"), avant
        )
        self.assertFalse((harness.racine / "prompts" / "relire.md").exists())


class LesContratsArrivent(Bac):
    """N3 commence : l'écran contrats scelle des adjonctions sur un adopté.

    Trouvé en jouant le geste de bout en bout : l'épreuve appliquait la trempe
    statique de plein citoyen, et le scellement écrivait des sources de forge
    que l'adopté n'a pas — chacun refusait ou cassait le pas vers N3.
    """

    def grandi(self):
        harness = self.adopter(self.prompt("ouvrir.md"))
        from kokaji.adoption import adopter_etape

        return adopter_etape(harness.racine, "relire", "Tu relis.")

    PROPOSITION: ClassVar[dict] = {"kata": [
        {"id": "ouvrir", "produit": [{"ouvrir.sujet": "en_pause"}]},
        {"id": "relire", "amont": ["ouvrir"], "herite": ["ouvrir.sujet"]},
    ]}

    def test_l_epreuve_ne_juge_pas_l_adopte_en_plein_citoyen(self):
        from kokaji.conception import Proposition, juger

        verdict = juger(self.grandi().racine, Proposition.depuis(self.PROPOSITION))
        self.assertEqual(verdict.fautes, ())
        self.assertEqual(verdict.anomalies, ())

    def test_ni_gabarit_ni_densho_ne_s_ecrivent_sur_un_adopte(self):
        """Sabotage 6 du RFC-010 : le texte d'un adopté se lit, ne s'édite pas par cet axe."""
        from kokaji.conception import Proposition, juger

        racine = self.grandi().racine
        # L'adoption engendre un gabarit neutre : il doit rester tel quel.
        gabarit_avant = (racine / "template.md").read_text(encoding="utf-8")
        for proposition in (
            Proposition(template="Une doctrine"),
            Proposition(source={"ouvrir": {"role": "x"}}),
        ):
            verdict = juger(racine, proposition)
            self.assertFalse(verdict.tient)
            self.assertIn("harness adopté", verdict.fautes[0])
        self.assertEqual((racine / "template.md").read_text(encoding="utf-8"), gabarit_avant)

    def test_le_scellement_ecrit_le_contrat_sans_inventer_de_source(self):
        from kokaji.conception import Proposition, sceller
        from kokaji.hds import charger

        harness = self.grandi()
        sceller(harness.racine, Proposition.depuis(self.PROPOSITION),
                auteur="essai", motif="adjonctions")
        relu = charger(harness.racine)
        self.assertEqual(list(relu.kata[1].herite), ["ouvrir.sujet"])
        self.assertEqual(relu.kata[0].produit, (("ouvrir.sujet", "en_pause"),))
        # Pas de page de forge inventée : le geste de N4, pas du scellement.
        self.assertFalse((harness.racine / "kata").exists())
        # Le registre suit, et les commentaires du manifest survivent.
        self.assertIn("ouvrir", (harness.racine / "registre.yaml").read_text(encoding="utf-8"))
        self.assertIn("# Harness adopté",
                      (harness.racine / "harness.yaml").read_text(encoding="utf-8"))


N2 = """
etat:
  champs:
  - sujet
  - decision
"""

CIBLE_INSTRUMENTEE = """\
  - id: instrumentee
    etat_structure: true
    en_tete: Un harness adopté
    packaging: dossier
"""


class Instrumentation(Bac):
    """N2 — la coupe instrumentée par enrichissement (RFC-008 §6)."""

    def vers_n2(self, harness):
        """Le geste de l'importeur : déclarer les champs, ouvrir la cible."""
        manifest = harness.racine / "harness.yaml"
        texte = manifest.read_text(encoding="utf-8")
        texte = texte.replace("personas: personas/", N2.strip() + "\npersonas: personas/")
        texte = texte.replace("trempe:", CIBLE_INSTRUMENTEE + "trempe:")
        manifest.write_text(texte, encoding="utf-8")
        from kokaji.hds import charger

        return charger(harness.racine)

    def test_le_texte_s_enrichit_sans_se_reecrire(self):
        harness = self.vers_n2(
            self.adopter(self.prompt("ouvrir.md", "Le texte importé, intact."))
        )
        forger_harness(harness, sortie=self.racine / "dist")

        nue = (self.racine / "dist" / "adopte" / "nue" / "ouvrir.md").read_text(
            encoding="utf-8"
        )
        armee = (
            self.racine / "dist" / "adopte" / "instrumentee" / "ouvrir.md"
        ).read_text(encoding="utf-8")
        # La nue ne bouge pas : c'est elle qui permet de mesurer l'effet de
        # l'instrumentation elle-même (A/B nue vs instrumentée, §6).
        self.assertNotIn("kokaji_state", nue)
        self.assertTrue(armee.startswith("Le texte importé, intact."))
        self.assertIn("kokaji_state", armee)
        self.assertIn('"sujet"', armee)
        self.assertIn('"decision"', armee)

    def test_sans_vocabulaire_le_refus_est_nomme(self):
        """§9 — jamais de champs inventés."""
        from kokaji.forge import ForgeImpossible

        harness = self.adopter(self.prompt("ouvrir.md"))
        manifest = harness.racine / "harness.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "trempe:", CIBLE_INSTRUMENTEE + "trempe:"
            ),
            encoding="utf-8",
        )
        from kokaji.hds import charger

        with self.assertRaises(ForgeImpossible) as refus:
            forger_harness(charger(harness.racine), sortie=self.racine / "dist")
        self.assertIn("etat.champs", str(refus.exception))

    def test_les_champs_du_manifest_sont_refuses_hors_exogene(self):
        from kokaji.hds import ManifestInvalide, charger

        harness = self.adopter(self.prompt("ouvrir.md"))
        manifest = harness.racine / "harness.yaml"
        texte = manifest.read_text(encoding="utf-8")
        texte = texte.replace("  exogene: true\n", "")
        debut, fin = texte.index("  provenance:"), texte.index("kata:")
        texte = texte[:debut] + texte[fin:]
        texte = texte.replace("personas: personas/", N2.strip() + "\npersonas: personas/")
        manifest.write_text(texte, encoding="utf-8")
        with self.assertRaises(ManifestInvalide) as refus:
            charger(harness.racine)
        self.assertIn("réservé aux harness exogènes", str(refus.exception))

    def test_un_contrat_declare_referme_l_exception(self):
        """RFC-008 §4 : les deux sources ne coexistent jamais."""
        from kokaji.hds import ManifestInvalide, charger

        harness = self.vers_n2(self.adopter(self.prompt("ouvrir.md")))
        manifest = harness.racine / "harness.yaml"
        manifest.write_text(
            manifest.read_text(encoding="utf-8").replace(
                "    produit: []",
                "    produit:\n    - ouvrir.sujet: fait_etabli",
            ),
            encoding="utf-8",
        )
        with self.assertRaises(ManifestInvalide) as refus:
            charger(harness.racine)
        self.assertIn("cette clé se retire", str(refus.exception))

    def test_le_carre_reste_eteint_sur_l_instrumentee_sans_contrat(self):
        """§8 — le sabotage d'honnêteté : aucun vert n'apparaît avant N3."""
        from kokaji.middleware import carre_attendu

        harness = self.vers_n2(self.adopter(self.prompt("ouvrir.md")))
        self.assertFalse(carre_attendu(harness, "instrumentee", harness.kata[0]))


if __name__ == "__main__":
    unittest.main()
