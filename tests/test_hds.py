"""Le HDS refuse ce qui n'est pas un harness exploitable (SPECS §2 R2.1).

Les harness de test sont purement structurels : des identifiants sans domaine,
conformément au principe de découplage (§0). Le seul harness nommé que Kokaji
connaisse est l'Atelier, et il vit hors des tests.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import ManifestInvalide, charger, charger_tous

MINIMAL = """
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
  checks_session: []
personas: personas/
corpus: corpus/
"""


def _ecrire_harness(racine: Path, manifest: str = MINIMAL, *, kata=("k1",)) -> Path:
    (racine / "kata").mkdir(parents=True, exist_ok=True)
    (racine / "personas").mkdir(exist_ok=True)
    (racine / "corpus").mkdir(exist_ok=True)
    (racine / "template.md").write_text("{{ role }}", encoding="utf-8")
    (racine / "registre.yaml").write_text("kata: {}", encoding="utf-8")
    for id_kata in kata:
        (racine / "kata" / f"{id_kata}.yaml").write_text("role: r", encoding="utf-8")
    (racine / "harness.yaml").write_text(manifest, encoding="utf-8")
    return racine


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def fautes(self, manifest: str, **kw) -> list[str]:
        _ecrire_harness(self.racine, manifest, **kw)
        with self.assertRaises(ManifestInvalide) as capture:
            charger(self.racine)
        return [str(f) for f in capture.exception.fautes]

    def charger_ok(self, manifest: str, **kw):
        _ecrire_harness(self.racine, manifest, **kw)
        return charger(self.racine)


class ManifestValide(Bac):
    def test_charge_un_harness_minimal(self):
        _ecrire_harness(self.racine)
        h = charger(self.racine)
        self.assertEqual(h.id, "h")
        self.assertEqual(len(h.kata), 1)
        self.assertEqual(h.cible_par_id("c1").packaging, "dossier")

    def test_les_statuts_d_etat_ont_les_defauts_de_kokaji(self):
        _ecrire_harness(self.racine)
        h = charger(self.racine)
        self.assertIn("fait_etabli", h.etat.statuts_champ)
        self.assertIn("infirmee", h.etat.statuts_hypothese)

    def test_emet_options_vaut_faux_par_defaut(self):
        """RFC-001 — un kata qui ne déclare rien n'émet pas d'options."""
        _ecrire_harness(self.racine)
        self.assertFalse(charger(self.racine).kata_par_id("k1").emet_options)

    def test_emet_options_se_declare(self):
        manifest = MINIMAL.replace("    herite: []", "    herite: []\n    emet_options: true")
        _ecrire_harness(self.racine, manifest)
        self.assertTrue(charger(self.racine).kata_par_id("k1").emet_options)

    def test_un_corpus_simple_vaut_un_corpus_nomme_reel(self):
        """HDS v0.2 — la forme d'origine reste valide."""
        _ecrire_harness(self.racine)
        h = charger(self.racine)
        self.assertEqual([c.nom for c in h.corpus_nommes], ["reel"])
        self.assertEqual(h.corpus, h.corpus_nommes[0].chemin)

    def test_des_corpus_nommes_avec_leurs_cles(self):
        manifest = MINIMAL.replace(
            "corpus: corpus/",
            "corpus:\n  reel:\n    chemin: corpus/\n    cles: [chat]\n  essai: corpus/",
        )
        _ecrire_harness(self.racine, manifest)
        h = charger(self.racine)

        self.assertEqual([c.nom for c in h.corpus_nommes], ["reel", "essai"])
        self.assertEqual(h.corpus_par_nom("reel").cles, ("chat",))
        self.assertEqual(h.cles_des_autres("essai"), ("chat",))

    def test_l_id_prefixe_les_ressources(self):
        """R2.2 — deux harness chargés côte à côte ne se marchent pas dessus."""
        _ecrire_harness(self.racine)
        h = charger(self.racine)
        self.assertEqual(h.espace("k1"), "h/k1")


class ManifestRefuse(Bac):
    def test_manifest_absent(self):
        with self.assertRaises(ManifestInvalide) as capture:
            charger(self.racine)
        self.assertIn("manifest absent", str(capture.exception))

    def test_id_qui_n_est_pas_un_slug(self):
        self.assertIn(
            "harness.id : slug attendu (minuscules, tirets) : 'Pas Un Slug'",
            self.fautes(MINIMAL.replace("id: h\n", "id: Pas Un Slug\n")),
        )

    def test_kata_sans_source_sur_disque(self):
        manifest = MINIMAL.replace("kata/k1.yaml", "kata/absent.yaml")
        self.assertIn("kata[0].source : fichier absent : kata/absent.yaml", self.fautes(manifest))

    def test_amont_inconnu(self):
        manifest = MINIMAL.replace("amont: []", "amont: [fantome]")
        self.assertIn("kata[0].amont : kata inconnu : 'fantome'", self.fautes(manifest))

    def test_herite_sans_amont(self):
        manifest = MINIMAL.replace("herite: []", "herite: [autre.champ]")
        fautes = self.fautes(manifest)
        self.assertIn("kata[0].herite : hérite sans amont déclaré", fautes)

    def test_heritage_est_refuse_avec_son_nouveau_nom(self):
        """HDS v0.1 — le renommage se signale, il ne s'ignore pas."""
        manifest = MINIMAL.replace("herite: []", "heritage: []")
        self.assertIn(
            "kata[0].heritage : renommé `herite` en HDS v0.1 (RFC-002 §3)",
            self.fautes(manifest),
        )

    def test_herite_non_qualifie(self):
        manifest = MINIMAL.replace("herite: []", "herite: [besoin]")
        self.assertIn("kata[0].herite[0] : attendu : <kata>.<champ> — 'besoin'", self.fautes(manifest))

    def test_herite_d_un_kata_qui_n_est_pas_amont(self):
        manifest = MINIMAL.replace("amont: []", "amont: []").replace(
            "    herite: []", "    herite: [fantome.champ]")
        fautes = self.fautes(manifest)
        self.assertTrue(any("n'est pas un amont" in f for f in fautes), fautes)

    def test_produit_un_champ_qui_n_est_pas_le_sien(self):
        manifest = MINIMAL.replace("- k1.c1: fait_etabli", "- autre.c1: fait_etabli")
        fautes = self.fautes(manifest)
        self.assertTrue(any("ne produit que ses propres champs" in f for f in fautes), fautes)

    def test_produit_avec_un_statut_hors_taxonomie(self):
        manifest = MINIMAL.replace("- k1.c1: fait_etabli", "- k1.c1: presque")
        self.assertIn(
            "kata[0].produit[0] : statut hors `etat.statuts_champ` — 'presque'",
            self.fautes(manifest),
        )

    def test_l_ordre_de_D_est_celui_de_la_declaration(self):
        """RFC-002 §2 — `statuts_champ` étant surchargeable, il range ses statuts."""
        _ecrire_harness(self.racine)
        h = charger(self.racine)
        self.assertTrue(h.couvre("fait_etabli", "en_pause"))
        self.assertFalse(h.couvre("en_pause", "fait_etabli"))
        self.assertTrue(h.couvre("hypothese", "hypothese"))

    def test_heritage_circulaire(self):
        manifest = MINIMAL.replace(
            "  - id: k1\n    nom: K1\n    source: kata/k1.yaml\n    livrable: L1\n"
            "    amont: []\n    herite: []\n    produit:\n      - k1.c1: fait_etabli\n",
            "  - id: k1\n    nom: K1\n    source: kata/k1.yaml\n    livrable: L1\n"
            "    amont: [k2]\n    herite: []\n"
            "  - id: k2\n    nom: K2\n    source: kata/k2.yaml\n    livrable: L2\n"
            "    amont: [k1]\n    herite: []\n",
        ).replace(
            "    - { id: k1, type: kata, nom: K1 }",
            "    - { id: k1, type: kata, nom: K1 }\n    - { id: k2, type: kata, nom: K2 }",
        )
        fautes = self.fautes(manifest, kata=("k1", "k2"))
        self.assertTrue(
            any("héritage circulaire" in f for f in fautes), fautes
        )

    def test_kata_absent_de_la_chaine(self):
        manifest = MINIMAL.replace("    - { id: k1, type: kata, nom: K1 }", "    - { id: j, type: jalon, nom: J }")
        fautes = self.fautes(manifest)
        self.assertIn("chaine.noeuds : kata absent de la chaîne : 'k1'", fautes)

    def test_arete_vers_un_noeud_inconnu(self):
        manifest = MINIMAL.replace("  aretes: []", "  aretes:\n    - { de: k1, vers: nulle-part }")
        self.assertIn("chaine.aretes[0].vers : nœud inconnu : 'nulle-part'", self.fautes(manifest))

    def test_emet_options_qui_n_est_pas_un_booleen(self):
        manifest = MINIMAL.replace("    herite: []", "    herite: []\n    emet_options: peut-etre")
        self.assertIn("kata[0].emet_options : attendu : true ou false", self.fautes(manifest))

    def test_packaging_hors_du_standard(self):
        manifest = MINIMAL.replace("packaging: dossier", "packaging: tarball")
        self.assertIn("cibles[0].packaging : attendu : dossier | zip", self.fautes(manifest))

    def test_cibles_vides(self):
        manifest = MINIMAL.replace(
            "cibles:\n  - id: c1\n    etat_structure: false\n    en_tete: H\n    packaging: dossier\n",
            "cibles: []\n",
        )
        self.assertIn("cibles : attendu : une liste non vide", self.fautes(manifest))

    def test_chemin_qui_sort_du_harness(self):
        manifest = MINIMAL.replace("registre: registre.yaml", "registre: ../ailleurs.yaml")
        fautes = self.fautes(manifest)
        self.assertTrue(any("sort du harness" in f for f in fautes), fautes)

    def test_toutes_les_fautes_sont_rendues_ensemble(self):
        manifest = MINIMAL.replace("id: h\n", "id: Mauvais\n").replace(
            "packaging: dossier", "packaging: tarball"
        )
        self.assertGreaterEqual(len(self.fautes(manifest)), 2)


class LesCycles(Bac):
    """RFC-016 D16.4 — les boucles sont permises, mais déclarées avec un budget."""

    def _chaine(self, aretes: str, cycles: str = "") -> str:
        avec_k2 = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            "    produit:\n      - k1.c1: fait_etabli\n"
            "  - id: k2\n    nom: K2\n    source: kata/k2.yaml\n    livrable: L2\n"
            "    amont: []\n    herite: []\n    produit:\n      - k2.c2: fait_etabli",
        )
        return avec_k2.replace(
            """chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
  aretes: []""",
            "chaine:\n  noeuds:\n"
            "    - { id: k1, type: kata, nom: K1 }\n"
            "    - { id: k2, type: kata, nom: K2 }\n"
            f"  aretes:\n{aretes}" + (f"\n  cycles:\n{cycles}" if cycles else ""),
        )

    def test_une_chaine_sans_boucle_ne_demande_aucun_cycle(self):
        m = self._chaine("    - { de: k1, vers: k2 }")
        self.assertEqual(self.charger_ok(m, kata=("k1", "k2")).chaine.cycles, ())

    def test_une_boucle_non_declaree_est_refusee(self):
        m = self._chaine("    - { de: k1, vers: k2 }\n    - { de: k2, vers: k1 }")
        self.assertTrue(any("boucle non déclarée" in f for f in self.fautes(m, kata=("k1", "k2"))))

    def test_une_boucle_declaree_avec_budget_tient(self):
        m = self._chaine(
            "    - { de: k1, vers: k2 }\n    - { de: k2, vers: k1 }",
            "    - { noeuds: [k1, k2], budget: { passages: 3 } }",
        )
        chaine = self.charger_ok(m, kata=("k1", "k2")).chaine
        self.assertEqual(chaine.cycles[0].budget.passages, 3)
        self.assertTrue(chaine.cycles[0].budget.borne)

    def test_une_boucle_declaree_sans_budget_est_refusee(self):
        m = self._chaine(
            "    - { de: k1, vers: k2 }\n    - { de: k2, vers: k1 }",
            "    - { noeuds: [k1, k2] }",
        )
        self.assertTrue(any("budget absent" in f for f in self.fautes(m, kata=("k1", "k2"))))

    def test_un_budget_vide_ne_borne_rien(self):
        m = self._chaine(
            "    - { de: k1, vers: k2 }\n    - { de: k2, vers: k1 }",
            "    - { noeuds: [k1, k2], budget: {} }",
        )
        self.assertTrue(any("ne borne rien" in f for f in self.fautes(m, kata=("k1", "k2"))))

    def test_un_cycle_declare_qui_ne_boucle_pas_est_refuse(self):
        m = self._chaine(
            "    - { de: k1, vers: k2 }",
            "    - { noeuds: [k1, k2], budget: { passages: 2 } }",
        )
        self.assertTrue(any("ne forment pas une boucle" in f for f in self.fautes(m, kata=("k1", "k2"))))


class LeTriplet(Bac):
    """RFC-016 §2 — le triplet, et sa migration mécanique."""

    def charger(self, manifest: str, **kw):
        _ecrire_harness(self.racine, manifest, **kw)
        return charger(self.racine)

    def test_un_kata_sans_triplet_vaut_l_echange(self):
        """Migration mécanique : un manifeste d'avant la RFC-016 reste valide."""
        k = self.charger(MINIMAL).kata_par_id("k1")
        self.assertEqual(k.raccourci, "echange")
        self.assertFalse(k.agit_sur_le_monde)
        self.assertEqual(k.effets.monde_lecture, ())
        self.assertEqual(k.perception.entrees, ())
        self.assertEqual(k.intention, "")

    def test_une_sonde_ouvre_la_lecture_du_monde(self):
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    raccourci: sonde
    intention: établir si la suite passe
    perception:
      entrees: [suite]
      retours: [rapport]
    effets:
      monde_lecture: [rapport]
    trempe:
      verificateurs:
        - { type: executable, check: "couvre la suite", source: rapport.xml }""",
        )
        k = self.charger(manifest).kata_par_id("k1")
        self.assertEqual(k.raccourci, "sonde")
        self.assertEqual(k.effets.monde_lecture, ("rapport",))
        self.assertTrue(k.agit_sur_le_monde)
        self.assertEqual(k.intention, "établir si la suite passe")

    def test_le_raccourci_se_deduit_des_effets_s_il_est_tu(self):
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }
    trempe: { verificateurs: [ { type: executable, check: "compile", source: build.log } ] }""",
        )
        self.assertEqual(self.charger(manifest).kata_par_id("k1").raccourci, "production")

    def test_un_effet_du_monde_sans_verificateur_est_refuse(self):
        """Interdit n°1, D16.6 — un effet a un retour ET un vérificateur."""
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }""",
        )
        fautes = self.fautes(manifest)
        self.assertTrue(any("doit déclarer un vérificateur" in f for f in fautes), fautes)

    def test_un_verificateur_sans_source_est_refuse(self):
        """Interdit n°2 — pas de monde auto-rapporté."""
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }
    trempe: { verificateurs: [ { type: executable, check: "compile" } ] }""",
        )
        self.assertTrue(any("interdit n°2" in f for f in self.fautes(manifest)))

    def test_un_verificateur_de_type_inconnu_est_refuse(self):
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }
    trempe: { verificateurs: [ { type: vibe, check: "ok", source: x } ] }""",
        )
        self.assertTrue(any("type inconnu" in f for f in self.fautes(manifest)))

    def test_un_verificateur_qui_juge_le_resultat_tient(self):
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }
    trempe: { verificateurs: [ { type: executable, check: "compile", source: build.log } ] }""",
        )
        k = self.charger(manifest).kata_par_id("k1")
        self.assertEqual(k.verificateurs[0].source, "build.log")
        self.assertEqual(k.verificateurs[0].type, "executable")

    def test_un_effet_du_monde_sans_retour_est_refuse(self):
        """Interdit n°1 — pas d'action aveugle (sabotage 4)."""
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    effets: { monde_ecriture: [patch] }""",
        )
        fautes = self.fautes(manifest)
        self.assertTrue(any("action aveugle" in f for f in fautes), fautes)

    def test_un_raccourci_inconnu_est_refuse(self):
        manifest = MINIMAL.replace(
            "    source: kata/k1.yaml", "    source: kata/k1.yaml\n    raccourci: teleportation"
        )
        self.assertTrue(any("raccourci inconnu" in f for f in self.fautes(manifest)))

    def test_un_echange_qui_ecrit_le_monde_est_incoherent(self):
        manifest = MINIMAL.replace(
            """    produit:
      - k1.c1: fait_etabli""",
            """    produit:
      - k1.c1: fait_etabli
    raccourci: echange
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }""",
        )
        fautes = self.fautes(manifest)
        self.assertTrue(any("n'ouvre pas l'écriture" in f for f in fautes), fautes)


if __name__ == "__main__":
    unittest.main()


AVEC_AVAL = MINIMAL.replace(
    """chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
  aretes: []""",
    """  - id: k2
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
  aretes: []""",
)


class SeuilHerite(Bac):
    """Le seuil facultatif de `herite:` — RFC-002 §6.2, appliqué.

    Sans seuil déclaré, « le `produit` de l'amont couvre le `herite` de l'aval
    au sens de l'ordre des statuts » n'avait rien à comparer.
    """

    def charger_avec(self, manifest: str):
        _ecrire_harness(self.racine, manifest, kata=("k1", "k2"))
        return charger(self.racine)

    def test_un_heritage_nu_garde_son_sens(self):
        k2 = self.charger_avec(AVEC_AVAL).kata_par_id("k2")
        self.assertEqual(k2.herite, ("k1.c1",))
        self.assertEqual(k2.exigences, {})

    def test_le_seuil_est_lu_et_porte_par_le_kata(self):
        manifest = AVEC_AVAL.replace(
            "    herite: [k1.c1]", "    herite:\n      - k1.c1: fait_etabli"
        )
        k2 = self.charger_avec(manifest).kata_par_id("k2")

        self.assertEqual(k2.herite, ("k1.c1",))
        self.assertEqual(k2.exigences, {"k1.c1": "fait_etabli"})

    def test_un_seuil_hors_taxonomie_est_refuse(self):
        manifest = AVEC_AVAL.replace(
            "    herite: [k1.c1]", "    herite:\n      - k1.c1: inventé"
        )
        fautes = self.fautes(manifest, kata=("k1", "k2"))
        self.assertTrue(
            any("statut hors `etat.statuts_champ`" in f for f in fautes), fautes
        )


class PlusieursHarness(Bac):
    """RFC-005 §5 — un dossier qui *est* un harness, ou qui *en contient*."""

    def test_un_dossier_qui_est_un_harness_donne_ce_seul_harness(self):
        """La compatibilité qui évite de faire du multi-harness une migration."""
        _ecrire_harness(self.racine)
        self.assertEqual(list(charger_tous(self.racine)), ["h"])

    def test_un_dossier_qui_en_contient_les_donne_tous(self):
        _ecrire_harness(self.racine / "un")
        _ecrire_harness(self.racine / "deux", MINIMAL.replace("id: h\n", "id: h2\n"))
        charges = charger_tous(self.racine)
        self.assertEqual(sorted(charges), ["h", "h2"])
        self.assertEqual(charges["h2"].id, "h2")

    def test_un_sous_dossier_sans_manifest_est_ignore(self):
        """Un `.git`, un `corpus`, un brouillon — ce n'est pas une faute."""
        _ecrire_harness(self.racine / "un")
        (self.racine / "pas-un-harness").mkdir()
        self.assertEqual(list(charger_tous(self.racine)), ["h"])

    def test_deux_harness_de_meme_id_sont_refuses(self):
        """Le second masquerait le premier, et leurs corpus se mélangeraient."""
        _ecrire_harness(self.racine / "a")
        _ecrire_harness(self.racine / "b")
        with self.assertRaises(ManifestInvalide) as capture:
            charger_tous(self.racine)
        # Le refus nomme le dossier fautif et celui qui tenait déjà l'id : sans
        # les deux, on sait qu'il y a collision sans savoir où regarder.
        self.assertIn("b : id déjà porté par a : h", str(capture.exception))

    def test_un_dossier_sans_aucun_harness_est_refuse(self):
        with self.assertRaises(ManifestInvalide) as capture:
            charger_tous(self.racine)
        self.assertIn("aucun harness", str(capture.exception))

    def test_un_harness_invalide_ne_passe_pas_en_silence(self):
        """Charger plusieurs harness n'assouplit pas ce qu'est un harness."""
        _ecrire_harness(self.racine / "un")
        _ecrire_harness(self.racine / "deux", MINIMAL.replace("id: h\n", "id: H MAJUSCULE\n"))
        with self.assertRaises(ManifestInvalide):
            charger_tous(self.racine)


class UnKataOrphelinDansUnHarnessNatif(Bac):
    """RFC-011 D11.2 — une source `.md` est un texte servi tel quel."""

    ORPHELIN = MINIMAL.replace(
        "chaine:",
        """  - id: venu
    nom: Venu d'ailleurs
    source: kata/venu.md
    amont: []
    herite: []
    produit: []
    provenance: { source: manuel, checksum_import: abc, date_import: "2026-09-14" }
chaine:""",
    ).replace("  noeuds:\n", "  noeuds:\n    - { id: venu, type: kata, nom: Venu }\n")

    def ecrire(self, manifest: str):
        _ecrire_harness(self.racine, manifest)
        (self.racine / "kata" / "venu.md").write_text("Tu accompagnes.", encoding="utf-8")

    def test_il_se_charge_orphelin_avec_sa_provenance_et_son_nom_pour_livrable(self):
        self.ecrire(self.ORPHELIN)
        h = charger(self.racine)
        venu = h.kata_par_id("venu")
        self.assertTrue(venu.orphelin)
        self.assertFalse(h.kata_par_id("k1").orphelin)
        self.assertFalse(h.exogene)
        self.assertEqual(venu.livrable, "Venu d'ailleurs")
        self.assertEqual(dict(venu.provenance)["source"], "manuel")

    def test_sans_provenance_il_est_refuse(self):
        """Sabotage 3 : on ne sait pas d'où ça vient, on n'enregistre pas."""
        manifest = self.ORPHELIN.replace(
            '    provenance: { source: manuel, checksum_import: abc, date_import: "2026-09-14" }\n', ""
        )
        _ecrire_harness(self.racine, manifest)
        (self.racine / "kata" / "venu.md").write_text("Tu accompagnes.", encoding="utf-8")
        with self.assertRaises(ManifestInvalide) as capture:
            charger(self.racine)
        self.assertTrue(any("provenance" in str(f) for f in capture.exception.fautes))

    def test_un_texte_ne_tient_pas_de_contrat(self):
        """Sabotage 4."""
        self.ecrire(self.ORPHELIN.replace("    herite: []\n    produit: []\n    provenance",
                                          "    amont: [k1]\n    herite: [k1.c1]\n    produit: []\n    provenance"))
        with self.assertRaises(ManifestInvalide) as capture:
            charger(self.racine)
        self.assertTrue(any("ne tient pas de contrat" in str(f) for f in capture.exception.fautes),
                        [str(f) for f in capture.exception.fautes])

    def test_un_kata_natif_ne_declare_pas_de_provenance(self):
        manifest = MINIMAL.replace(
            "    livrable: L1\n",
            "    livrable: L1\n    provenance: { source: x, checksum_import: y, date_import: z }\n",
        )
        _ecrire_harness(self.racine, manifest)
        with self.assertRaises(ManifestInvalide) as capture:
            charger(self.racine)
        self.assertTrue(any("réservée à un kata orphelin" in str(f) for f in capture.exception.fautes))
