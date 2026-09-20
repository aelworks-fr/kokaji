"""La forge produit des coupes déterministes, spécialisées par cible (SPECS §4).

Comme pour le HDS, les harness de test sont purement structurels : aucun nom de
domaine n'entre ici (§0).

La trempe est débranchée : ces tests éprouvent l'assemblage, pas la vérification.
Le blocage de la forge par la trempe a ses propres tests.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.forge import ForgeImpossible, forger_harness
from kokaji.hds import charger

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
      - k1.c2: fait_etabli
  - id: k2
    nom: K2
    source: kata/k2.yaml
    livrable: L2
    amont: [k1]
    herite: [k1.c1]
    produit:
      - k2.c2: hypothese
    emet_options: true
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: k2, type: kata, nom: K2 }
  aretes:
    - { de: k1, vers: k2, label: suite }
template: template.md
cibles:
  - id: nue
    etat_structure: false
    en_tete: EN-TETE-NUE
    packaging: dossier
  - id: instrumentee
    etat_structure: true
    en_tete: EN-TETE-INSTRUMENTEE
    packaging: dossier
trempe:
  vocabulaire_interdit: []
  registre: registre.yaml
  checks_session: []
personas: personas/
corpus: corpus/
"""

TEMPLATE = """{{ en_tete }} — {{ kata_nom }}

{{ role }}

## Interdits
- socle
{{ interdits }}

## Questions

{{ questions }}

{{ heritage }}

## Livrable — {{ livrable_nom }}

{{ livrable_structure }}

{{ etat }}

## Passage

{{ passage }}
"""

KATA = """
version: 9.9.9
role: ROLE
interdits: [I1]
questions: [Q1, Q2]
livrable_structure: [S1]
passage: PASSAGE
"""


def _harness(racine: Path, *, template: str = TEMPLATE, kata: str = KATA,
             registre: str | None = None, manifest: str = MANIFEST):
    (racine / "kata").mkdir(parents=True, exist_ok=True)
    (racine / "personas").mkdir(exist_ok=True)
    (racine / "corpus").mkdir(exist_ok=True)
    (racine / "template.md").write_text(template, encoding="utf-8")
    (racine / "registre.yaml").write_text(
        registre
        if registre is not None
        else "champs:\n  c1: Description de c1\n  c2: Description de c2\n",
        encoding="utf-8",
    )
    for id_kata in ("k1", "k2"):
        (racine / "kata" / f"{id_kata}.yaml").write_text(kata, encoding="utf-8")
    (racine / "harness.yaml").write_text(manifest, encoding="utf-8")
    return charger(racine)


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name) / "harness"
        self.racine.mkdir()
        self.sortie = Path(self._tmp.name) / "dist"
        self.addCleanup(self._tmp.cleanup)

    def coupe(self, resultat, cible, kata):
        return next(c for c in resultat.coupes if c.cible == cible and c.kata == kata)


class Forge(Bac):
    def test_produit_une_coupe_par_kata_et_par_cible(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        self.assertEqual(len(resultat.coupes), 4)
        for cible in ("nue", "instrumentee"):
            for kata in ("k1", "k2"):
                self.assertTrue((self.sortie / "h" / cible / f"{kata}.md").is_file())
                self.assertTrue((self.sortie / "h" / cible / f"{kata}.json").is_file())

    def test_deux_forges_successives_donnent_les_memes_octets(self):
        """R4.1 — le déterminisme est ce qui rend un écart attribuable."""
        harness = _harness(self.racine)
        forger_harness(harness, sortie=self.sortie, trempe=False)
        premier = (self.sortie / "h" / "nue" / "k1.md").read_bytes()

        resultat = forger_harness(harness, sortie=self.sortie, trempe=False)
        self.assertEqual((self.sortie / "h" / "nue" / "k1.md").read_bytes(), premier)
        self.assertEqual(resultat.modifiees, ())

    def test_seule_la_cible_instrumentee_porte_le_bloc_d_etat(self):
        """R4.2 — les autres cibles n'en portent aucune trace."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        self.assertIn("kokaji_state", self.coupe(resultat, "instrumentee", "k1").texte)
        self.assertNotIn("kokaji_state", self.coupe(resultat, "nue", "k1").texte)
        self.assertNotIn("état", self.coupe(resultat, "nue", "k1").texte)

    def test_l_en_tete_vient_de_la_cible(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        self.assertTrue(self.coupe(resultat, "nue", "k1").texte.startswith("EN-TETE-NUE"))
        self.assertTrue(
            self.coupe(resultat, "instrumentee", "k1").texte.startswith("EN-TETE-INSTRUMENTEE")
        )

    def test_le_kata_sans_amont_n_a_pas_de_section_heritage(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        self.assertNotIn("reçois de l'amont", self.coupe(resultat, "nue", "k1").texte)
        self.assertIn("reçois de l'amont", self.coupe(resultat, "nue", "k2").texte)
        self.assertIn("Description de c1", self.coupe(resultat, "nue", "k2").texte)

    def test_le_bloc_d_etat_ferme_ses_listes(self):
        """Le gabarit ne montre que des marqueurs ; les valeurs sont énumérées à part.

        Une énumération dans le gabarit se lit comme un exemple à compléter : le
        modèle invente alors ses propres statuts.
        """
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        texte = self.coupe(resultat, "instrumentee", "k2").texte

        self.assertIn('"<statut_champ>"', texte)
        self.assertNotIn('"fait_etabli | hypothese', texte)
        self.assertIn("- `fait_etabli`", texte)
        self.assertIn("tu n'en ajoutes", texte)

    def test_le_bloc_d_etat_enumere_les_champs_du_kata(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        # k2 hérite de c1 et rend compte de c2 ; les deux sont dans le gabarit.
        texte = self.coupe(resultat, "instrumentee", "k2").texte
        self.assertIn('"c1": "<statut_champ>"', texte)
        self.assertIn('"c2": "<statut_champ>"', texte)
        self.assertNotIn('"<champ>"', texte)

    def test_le_bloc_d_etat_ignore_la_nature_si_le_kata_n_en_declare_aucune(self):
        """RFC-003 §5.2 — le HDS ne change pas : sans déclaration, pas de clé."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        texte = self.coupe(resultat, "instrumentee", "k1").texte

        self.assertNotIn('"nature"', texte)
        self.assertNotIn("<nature>", texte)

    def test_le_bloc_d_etat_porte_la_nature_declaree_par_le_kata(self):
        """Kokaji ferme la liste que le harness lui donne, et n'en sait rien d'autre."""
        kata = KATA + "natures: [n1, n2]\n"
        resultat = forger_harness(
            _harness(self.racine, kata=kata), sortie=self.sortie, trempe=False
        )
        texte = self.coupe(resultat, "instrumentee", "k1").texte

        self.assertIn('"nature": { "valeur": "<nature>"', texte)
        self.assertIn("- `n1`", texte)
        self.assertIn("- `n2`", texte)
        self.assertIn("dès ton premier bloc", texte)

    def test_la_nature_ne_sort_pas_sur_une_cible_sans_bloc(self):
        kata = KATA + "natures: [n1]\n"
        resultat = forger_harness(
            _harness(self.racine, kata=kata), sortie=self.sortie, trempe=False
        )
        self.assertNotIn("<nature>", self.coupe(resultat, "nue", "k1").texte)

    def test_une_liste_de_natures_mal_formee_est_refusee(self):
        kata = KATA + "natures: pas-une-liste\n"
        with self.assertRaises(ForgeImpossible):
            forger_harness(_harness(self.racine, kata=kata), sortie=self.sortie, trempe=False)

    def test_le_bloc_d_etat_nomme_l_etape_suivante(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        self.assertIn("il vaut l'étape suivante : `k2`", self.coupe(resultat, "instrumentee", "k1").texte)
        self.assertIn("l'étape suivante : aucune", self.coupe(resultat, "instrumentee", "k2").texte)

    def test_seul_le_kata_declare_emet_des_options(self):
        """RFC-001 — `emet_options` gouverne les deux sections facultatives."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        avec = self.coupe(resultat, "instrumentee", "k2").texte
        sans = self.coupe(resultat, "instrumentee", "k1").texte

        self.assertIn('"options"', avec)
        self.assertIn('"decision"', avec)
        self.assertNotIn('"options"', sans)
        self.assertNotIn('"decision"', sans)

    def test_les_options_ferment_leurs_listes_comme_le_reste(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        texte = self.coupe(resultat, "instrumentee", "k2").texte

        self.assertIn('"statut": "<statut_option>"', texte)
        self.assertNotIn("ouverte|engagee|ecartee", texte)
        self.assertIn("- `ecartee`", texte)
        self.assertIn("`k1`, `k2`", texte)  # les nœuds de la chaîne

    def test_la_coupe_porte_la_vigilance_contre_le_quota(self):
        """Le carnet #8 vit dans la coupe, pas seulement dans la documentation."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        texte = self.coupe(resultat, "instrumentee", "k2").texte
        self.assertIn("aucun quota", texte)

    def test_une_cible_sans_bloc_d_etat_n_a_pas_d_options(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        self.assertNotIn('"options"', self.coupe(resultat, "nue", "k2").texte)

    def test_les_declencheurs_du_bloc_sont_enumeres(self):
        """« À chaque point d'étape » se lisait comme une intention, pas une règle."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        texte = self.coupe(resultat, "instrumentee", "k1").texte

        self.assertIn("en tête de ta réponse", texte)
        self.assertIn("- tu rends le livrable ;", texte)
        self.assertIn("Hors de ces cas, tu n'émets rien.", texte)
        self.assertNotIn("À chaque point d'étape", texte)

    def test_un_kata_a_options_a_deux_declencheurs_de_plus(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        avec = self.coupe(resultat, "instrumentee", "k2").texte
        sans = self.coupe(resultat, "instrumentee", "k1").texte

        self.assertIn("une décision referme ou ouvre des possibles.", avec)
        self.assertNotIn("possibles", sans)

    def test_chaque_marqueur_dit_ce_qu_il_gouverne(self):
        """Les taxonomies se recouvrent : sans point d'application, elles se mélangent."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        texte = self.coupe(resultat, "instrumentee", "k1").texte

        self.assertIn("étanches", texte)
        self.assertIn("il gouverne les entrées de `champs`, et rien d'autre.", texte)
        self.assertIn("il gouverne la clé `statut` des entrées de `hypotheses`", texte)
        self.assertIn("il gouverne la clé `confiance` des entrées de `hypotheses`", texte)

    def test_l_estampille_identifie_la_coupe(self):
        """R4.3 — et la version de coupe distingue les cibles à kata égal."""
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False)
        nue = self.coupe(resultat, "nue", "k1").estampille
        instrumentee = self.coupe(resultat, "instrumentee", "k1").estampille
        self.assertEqual(nue.version_kata, "9.9.9")
        self.assertEqual(nue.harness, "h")
        self.assertNotEqual(nue.version_coupe, instrumentee.version_coupe)

    def test_le_releve_de_forge_diffe_la_coupe_precedente(self):
        harness = _harness(self.racine)
        forger_harness(harness, sortie=self.sortie, trempe=False)
        (self.racine / "kata" / "k1.yaml").write_text(
            KATA.replace("role: ROLE", "role: ROLE MODIFIE"), encoding="utf-8"
        )

        resultat = forger_harness(charger(self.racine), sortie=self.sortie, trempe=False)
        modifiees = {(c.cible, c.kata, c.etat) for c in resultat.modifiees}
        self.assertIn(("nue", "k1", "modifie"), modifiees)
        self.assertNotIn(("nue", "k2", "modifie"), modifiees)

        releve = (self.sortie / "h" / "CHANGEMENTS.md").read_text(encoding="utf-8")
        self.assertIn("+ROLE MODIFIE", releve)

    def test_ne_forge_que_la_cible_demandee(self):
        resultat = forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False, cibles=("nue",))
        self.assertEqual({c.cible for c in resultat.coupes}, {"nue"})
        self.assertFalse((self.sortie / "h" / "instrumentee").exists())


class LaCoupeOutil(Bac):
    """RFC-016 D16.2 — la coupe d'un kata d'action est un outil prêt à l'usage :
    son estampille empaquette capacités, effets et vérificateurs."""

    def _manifest_action(self) -> str:
        return MANIFEST.replace(
            """  - id: k1
    nom: K1
    source: kata/k1.yaml
    livrable: L1
    amont: []
    herite: []
    produit:
      - k1.c2: fait_etabli""",
            """  - id: k1
    nom: K1
    source: kata/k1.yaml
    livrable: L1
    amont: []
    herite: []
    produit:
      - k1.c2: fait_etabli
    raccourci: sonde
    perception: { entrees: [suite], retours: [rapport] }
    effets: { monde_lecture: [rapport] }
    capacites: [execution_shell]
    trempe:
      verificateurs:
        - { type: executable, check: "couvre la suite", source: rapport.xml }""",
        )

    def test_l_estampille_d_un_kata_d_action_porte_l_outil(self):
        import json

        forger_harness(_harness(self.racine, manifest=self._manifest_action()),
                       sortie=self.sortie, trempe=False)
        estampille = json.loads((self.sortie / "h" / "nue" / "k1.json").read_text(encoding="utf-8"))
        self.assertIn("outil", estampille)
        self.assertEqual(estampille["outil"]["capacites"], ["execution_shell"])
        self.assertEqual(estampille["outil"]["effets"]["monde_lecture"], ["rapport"])
        self.assertEqual(estampille["outil"]["verificateurs"][0]["source"], "rapport.xml")

    def test_un_kata_d_echange_n_a_pas_d_outil(self):
        import json

        forger_harness(_harness(self.racine, manifest=self._manifest_action()),
                       sortie=self.sortie, trempe=False)
        estampille = json.loads((self.sortie / "h" / "nue" / "k2.json").read_text(encoding="utf-8"))
        self.assertNotIn("outil", estampille)


class ForgeRefuse(Bac):
    def test_cible_inconnue(self):
        with self.assertRaises(ForgeImpossible) as capture:
            forger_harness(_harness(self.racine), sortie=self.sortie, trempe=False, cibles=("fantome",))
        self.assertIn("cible(s) inconnue(s) : fantome", str(capture.exception))

    def test_variable_du_template_sans_valeur(self):
        harness = _harness(self.racine, template=TEMPLATE + "\n{{ inventee }}\n")
        with self.assertRaises(ForgeImpossible) as capture:
            forger_harness(harness, sortie=self.sortie, trempe=False)
        self.assertIn("variable(s) du template sans valeur — inventee", str(capture.exception))

    def test_variable_obligatoire_vide(self):
        harness = _harness(self.racine, kata=KATA.replace("role: ROLE", "role: ''"))
        with self.assertRaises(ForgeImpossible) as capture:
            forger_harness(harness, sortie=self.sortie, trempe=False)
        self.assertIn("variable(s) vide(s) — role", str(capture.exception))

    def test_champ_herite_absent_du_registre(self):
        harness = _harness(self.racine, registre="champs: {}\n")
        with self.assertRaises(ForgeImpossible) as capture:
            forger_harness(harness, sortie=self.sortie, trempe=False)
        self.assertIn("absent du registre", str(capture.exception))

    def test_champ_produit_absent_du_registre(self):
        manifest = MANIFEST.replace("- k2.c2: hypothese", "- k2.inconnu: hypothese")
        with self.assertRaises(ForgeImpossible) as capture:
            forger_harness(_harness(self.racine, manifest=manifest), sortie=self.sortie, trempe=False)
        self.assertIn("champ absent du registre — 'k2.inconnu'", str(capture.exception))

    def test_la_cle_champs_de_la_source_est_refusee(self):
        """RFC-002 — `produit:` au manifest est la seule source de vérité."""
        harness = _harness(self.racine, kata=KATA.replace("role: ROLE", "champs: [c2]\nrole: ROLE"))
        with self.assertRaises(ForgeImpossible) as capture:
            forger_harness(harness, sortie=self.sortie, trempe=False)
        self.assertIn("remplacé par `produit:`", str(capture.exception))


if __name__ == "__main__":
    unittest.main()


class UnOrphelinDansUnHarnessNatif(Bac):
    """RFC-011 D11.2 — la forge choisit par kata : le texte, tel quel, plus l'estampille."""

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

    def mixte(self, texte: str):
        (self.racine / "kata").mkdir(exist_ok=True)
        (self.racine / "kata" / "venu.md").write_text(texte, encoding="utf-8")
        return _harness(self.racine, manifest=self.MIXTE)

    def test_le_texte_est_servi_tel_quel_et_les_natifs_se_forgent(self):
        h = self.mixte("Tu accompagnes une étape.\n")
        resultat = forger_harness(h, self.sortie, trempe=False)
        venu = self.coupe(resultat, "nue", "venu")
        self.assertTrue(venu.texte.startswith("Tu accompagnes une étape.\n"))
        self.assertIn("<!-- h/venu", venu.texte)
        self.assertEqual(venu.estampille.version_kata, "0.1.0")
        k1 = self.coupe(resultat, "nue", "k1")
        self.assertIn("EN-TETE-NUE — K1", k1.texte)

    def test_la_cible_instrumentee_le_sert_sans_bloc_d_etat(self):
        """RFC-011 D11.3 : sans contrat ni champs, rien ne s'invente — le QG l'affiche éteint."""
        resultat = forger_harness(self.mixte("Tu accompagnes.\n"), self.sortie, trempe=False)
        venu = self.coupe(resultat, "instrumentee", "venu")
        self.assertNotIn("kokaji_state", venu.texte)
        self.assertTrue(venu.texte.startswith("Tu accompagnes.\n"))
