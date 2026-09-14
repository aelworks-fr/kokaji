"""La trempe statique bloque la forge (SPECS §5, RFC-002 §6.2).

Harness purement structurels, comme partout ailleurs (§0).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.forge import TrempeEchouee, forger_harness
from kokaji.forge.coupe import charger_registre, forger
from kokaji.hds import charger
from kokaji.trempe.statique import verifier

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
  - id: k2
    nom: K2
    source: kata/k2.yaml
    livrable: L2
    amont: [k1]
    herite: [k1.c1]
    produit:
      - k2.c2: hypothese
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: k2, type: kata, nom: K2 }
    - { id: j1, type: jalon, nom: J1 }
  aretes:
    - { de: k1, vers: k2, label: suite }
    - { de: k2, vers: j1, label: fin }
template: template.md
cibles:
  - id: c1
    etat_structure: false
    en_tete: H
    packaging: dossier
trempe:
  vocabulaire_interdit: [mot banni]
  registre: registre.yaml
  checks_session: []
personas: personas/
corpus: corpus/
"""

REGISTRE = """
kata:
  k1: K1
  k2: K2
livrables: [L1, L2]
jalons:
  j1: J1
champs:
  c1: Un champ
  c2: Un autre
"""

TEMPLATE = "{{ en_tete }}\n\n{{ role }}\n\n{{ questions }}\n\n{{ livrable_structure }}\n\n{{ passage }}\n"
KATA = "version: 1.0.0\nrole: ROLE\nquestions: [Q1]\nlivrable_structure: [S1]\npassage: PASSAGE\n"


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name) / "harness"
        self.sortie = Path(self._tmp.name) / "dist"
        self.addCleanup(self._tmp.cleanup)
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        self.ecrire()

    def ecrire(self, *, manifest=MANIFEST, registre=REGISTRE, template=TEMPLATE, kata=KATA):
        (self.racine / "template.md").write_text(template, encoding="utf-8")
        (self.racine / "registre.yaml").write_text(registre, encoding="utf-8")
        for id_kata in ("k1", "k2"):
            (self.racine / "kata" / f"{id_kata}.yaml").write_text(kata, encoding="utf-8")
        (self.racine / "harness.yaml").write_text(manifest, encoding="utf-8")

    def anomalies(self, **kw):
        self.ecrire(**kw)
        harness = charger(self.racine)
        registre = charger_registre(harness.trempe.registre)
        template = harness.template.read_text(encoding="utf-8")
        coupes = [
            forger(harness, k, c, template, registre)
            for c in harness.cibles
            for k in harness.kata
        ]
        return verifier(harness, coupes, registre)

    def regles(self, **kw):
        return {a.regle for a in self.anomalies(**kw)}


class HarnessSain(Bac):
    def test_aucune_anomalie(self):
        self.assertEqual(self.anomalies(), ())

    def test_un_tableau_json_n_est_pas_un_crochet_de_gabarit(self):
        """Le premier faux positif rencontré : `["OPT-2"]` dans un bloc de code."""
        template = TEMPLATE + '\n```json\n{ "ferme": ["OPT-2"] }\n```\n'
        self.assertEqual(self.anomalies(template=template), ())


class Coupes(Bac):
    def test_variable_non_resolue(self):
        """Un `{{ … }}` venu d'une valeur passe la forge — pas la trempe."""
        kata = KATA.replace("role: ROLE", "role: ROLE {{ reste }}")
        self.assertIn("marqueur-residuel", self.regles(kata=kata))

    def test_crochet_de_gabarit(self):
        self.assertIn("marqueur-residuel", self.regles(template=TEMPLATE + "\n[nom du kata]\n"))

    def test_lien_markdown_n_est_pas_un_crochet(self):
        self.assertEqual(self.anomalies(template=TEMPLATE + "\n[un lien](https://x)\n"), ())

    def test_marque_de_chantier(self):
        self.assertIn("marqueur-residuel", self.regles(template=TEMPLATE + "\nTODO: finir\n"))

    def test_vocabulaire_interdit_du_harness(self):
        anomalies = self.anomalies(template=TEMPLATE + "\nUn Mot Banni ici.\n")
        self.assertIn("vocabulaire-interdit", {a.regle for a in anomalies})
        self.assertIn("mot banni", anomalies[0].message)

    def test_decompte_faux(self):
        template = TEMPLATE + "\nTrois points :\n- un\n- deux\n"
        anomalies = [a for a in self.anomalies(template=template) if a.regle == "decompte"]
        self.assertTrue(anomalies)
        self.assertIn("2 listé", anomalies[0].message)

    def test_decompte_juste(self):
        template = TEMPLATE + "\nDeux points :\n- un\n- deux\n"
        self.assertEqual(self.anomalies(template=template), ())


class Contrat(Bac):
    def test_produit_vide(self):
        manifest = MANIFEST.replace("    produit:\n      - k2.c2: hypothese", "    produit: []")
        self.assertIn("contrat-complet", self.regles(manifest=manifest))

    def test_amont_sans_herite(self):
        manifest = MANIFEST.replace("    herite: [k1.c1]", "    herite: []")
        anomalies = [a for a in self.anomalies(manifest=manifest) if a.regle == "contrat-complet"]
        self.assertIn("à moitié écrit", anomalies[0].message)

    def test_typage_de_chaine_rompu(self):
        """L'aval hérite d'un champ que l'amont ne garantit pas."""
        manifest = MANIFEST.replace("herite: [k1.c1]", "herite: [k1.c2]")
        anomalies = [a for a in self.anomalies(manifest=manifest) if a.regle == "typage-chaine"]
        self.assertIn("n'est pas dans le `produit` de 'k1'", anomalies[0].message)

    def test_l_aval_exige_plus_que_l_amont_ne_promet(self):
        """RFC-002 §6.2 — « couvre au sens de l'ordre des statuts », enfin vérifié.

        `k1` ne garantit `c1` qu'en `hypothese` ; `k2` le veut établi. Rien à
        l'exécution ne dirait cette faute : le carré de `k1` serait conforme,
        celui de `k2` aussi, et la chaîne fausse.
        """
        manifest = MANIFEST.replace("      - k1.c1: fait_etabli", "      - k1.c1: hypothese")
        manifest = manifest.replace(
            "    herite: [k1.c1]", "    herite:\n      - k1.c1: fait_etabli"
        )
        anomalies = [a for a in self.anomalies(manifest=manifest) if a.regle == "ordre-des-statuts"]

        self.assertEqual(len(anomalies), 1)
        self.assertIn("au moins en `fait_etabli`", anomalies[0].message)
        self.assertIn("ne garantit que `hypothese`", anomalies[0].message)

    def test_un_seuil_que_l_amont_depasse_ne_dit_rien(self):
        """Sur-tenir n'est pas une faute : le régime prudence l'autorise."""
        manifest = MANIFEST.replace(
            "    herite: [k1.c1]", "    herite:\n      - k1.c1: hypothese"
        )
        self.assertNotIn("ordre-des-statuts", self.regles(manifest=manifest))

    def test_un_heritage_nu_n_exige_aucun_seuil(self):
        """L'écriture d'avant garde exactement le sens qu'elle avait."""
        manifest = MANIFEST.replace("      - k1.c1: fait_etabli", "      - k1.c1: en_pause")
        self.assertNotIn("ordre-des-statuts", self.regles(manifest=manifest))

    def test_contrebande(self):
        """RFC-002 §6.2 — la source de k1 cite `c2`, qu'elle n'hérite ni ne produit."""
        anomalies = self.anomalies(kata=KATA.replace("role: ROLE", "role: on parle de c2 ici"))
        self.assertIn("contrebande", {a.regle for a in anomalies})


class Registre(Bac):
    def test_kata_absent_du_registre(self):
        self.assertIn("registre-canonique", self.regles(registre=REGISTRE.replace("  k2: K2\n", "")))

    def test_livrable_absent_du_registre(self):
        self.assertIn("registre-canonique", self.regles(registre=REGISTRE.replace("[L1, L2]", "[L1]")))

    def test_jalon_absent_du_registre(self):
        self.assertIn("registre-canonique", self.regles(registre=REGISTRE.replace("  j1: J1\n", "")))


class BlocageDeLaForge(Bac):
    def test_une_anomalie_empeche_toute_ecriture(self):
        """`dist/` ne reçoit jamais une coupe fautive."""
        self.ecrire(template=TEMPLATE + "\nTODO\n")
        with self.assertRaises(TrempeEchouee):
            forger_harness(charger(self.racine), sortie=self.sortie)
        self.assertFalse(self.sortie.exists())

    def test_on_peut_forger_sans_trempe(self):
        self.ecrire(template=TEMPLATE + "\nTODO\n")
        resultat = forger_harness(charger(self.racine), sortie=self.sortie, trempe=False)
        self.assertEqual(len(resultat.coupes), 2)


if __name__ == "__main__":
    unittest.main()


class UnOrphelinEstUneCoupe(Bac):
    """RFC-011 D11.2 — le texte se trempe comme une coupe ; le registre ne le concerne pas."""

    MIXTE = MANIFEST.replace(
        "chaine:",
        """  - id: venu
    nom: Venu
    source: kata/venu.md
    amont: []
    herite: []
    produit: []
    provenance: { source: manuel, checksum_import: abc, date_import: "2026-09-14" }
chaine:""",
    ).replace("  noeuds:\n", "  noeuds:\n    - { id: venu, type: kata, nom: Venu }\n")

    def texte(self, contenu: str):
        (self.racine / "kata" / "venu.md").write_text(contenu, encoding="utf-8")

    def test_hors_du_registre_il_ne_fait_pas_d_anomalie(self):
        self.texte("Tu accompagnes une étape.\n")
        self.assertEqual(self.regles(manifest=self.MIXTE), set())

    def test_un_marqueur_de_gabarit_dans_le_texte_est_refuse(self):
        """Sabotage 1 du RFC-011."""
        self.texte("Tu accompagnes [À COMPLÉTER] — TBD.\n")
        self.assertIn("marqueur-residuel", self.regles(manifest=self.MIXTE))

    def test_le_vocabulaire_interdit_du_harness_s_applique_au_texte(self):
        """Sabotage 2."""
        self.texte("Tu emploies un mot banni.\n")
        self.assertIn("vocabulaire-interdit", self.regles(manifest=self.MIXTE))
