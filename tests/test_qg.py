"""Le QG lit et n'évalue pas (SPECS §8, RFC-001 R8.4, carnet #8).

Harness purement structurels (§0). Aucun réseau : le QG lit des fichiers.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import charger
from kokaji.qg import composer, rendre_texte, sujets

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
      - k1.c2: hypothese
    emet_options: true
  - id: k2
    nom: K2
    source: kata/k2.yaml
    livrable: L2
    amont: [k1]
    herite: [k1.c1]
    produit:
      - k2.c3: fait_etabli
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


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name) / "harness"
        self.addCleanup(self._tmp.cleanup)
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text(
            "champs:\n  c1: Un\n  c2: Deux\n  c3: Trois\n", encoding="utf-8"
        )
        for id_kata in ("k1", "k2"):
            (self.racine / "kata" / f"{id_kata}.yaml").write_text(
                "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
            )
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.racine)

    def ha(self, nom: str, releves: list[dict]):
        dossier = self.harness.corpus / nom
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "etats.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in releves), encoding="utf-8"
        )

    @staticmethod
    def releve(horodatage: str, **etat) -> dict:
        return {"horodatage": horodatage, "etat": etat}


class Chaine(Bac):
    def test_la_topologie_vient_du_manifest(self):
        """R8.1 — le QG ne connaît aucune chaîne en dur."""
        self.ha("CAS-0001-x", [self.releve("2026-01-01T10:00:00", sujet="S", kata="k1", champs={})])
        vue = composer(self.harness, "S")

        self.assertEqual([n.id for n in vue.noeuds], ["k1", "k2", "j1"])
        self.assertEqual(vue.aretes[0]["de"], "k1")

    def test_les_sujets_viennent_des_blocs(self):
        self.ha("CAS-0001-x", [
            self.releve("2026-01-01T10:00:00", sujet="Un sujet", kata="k1", champs={}),
            self.releve("2026-01-01T11:00:00", sujet="Un autre", kata="k1", champs={}),
        ])
        self.assertEqual(sujets(self.harness), ["Un autre", "Un sujet"])


class Chaleur(Bac):
    """La formule du handoff : ce qui est acquis sur ce qui est connu."""

    def noeud(self, champs: dict, hypotheses=None, noeud: str = "k1"):
        self.ha("CAS-0001-x", [
            self.releve("2026-01-01T10:00:00", sujet="S", kata=noeud,
                        champs=champs, hypotheses=hypotheses or [])
        ])
        vue = composer(self.harness, "S")
        return next(n for n in vue.noeuds if n.id == noeud)

    def chaleur(self, champs: dict, hypotheses=None, noeud: str = "k1"):
        return self.noeud(champs, hypotheses, noeud).chaleur(self.harness)

    def test_graduee_jamais_binaire(self):
        self.assertEqual(self.chaleur({"c1": "fait_etabli", "c2": "fait_etabli"}), 1.0)
        self.assertEqual(self.chaleur({"c1": "fait_etabli", "c2": "hypothese"}), 0.5)
        self.assertEqual(self.chaleur({"c1": "en_pause", "c2": "en_pause"}), 0.0)

    def test_un_noeud_jamais_pratique_ne_rend_pas_zero(self):
        """Ne pas savoir n'est pas un savoir nul : le nœud se tait."""
        self.ha("CAS-0001-x", [
            self.releve("2026-01-01T10:00:00", sujet="S", kata="k1", champs={"c1": "fait_etabli"})
        ])
        vue = composer(self.harness, "S")
        jamais = next(n for n in vue.noeuds if n.id == "k2")

        self.assertFalse(jamais.pratique)
        self.assertIsNone(jamais.chaleur(self.harness))

    def test_seuls_les_champs_connus_comptent(self):
        """Un champ dont rien n'est dit ne pèse pas dans le dénominateur."""
        self.assertEqual(self.chaleur({"c1": "fait_etabli"}), 1.0)

    def test_une_hypothese_validee_rechauffe(self):
        froid = self.chaleur({"c1": "fait_etabli"}, [{"statut": "en_cours"}])
        chaud = self.chaleur({"c1": "fait_etabli"}, [{"statut": "validee"}])
        self.assertEqual(froid, 0.5)
        self.assertEqual(chaud, 1.0)

    def test_une_hypothese_infirmee_ne_refroidit_jamais(self):
        """Une trempe ratée est une information, pas une régression."""
        seule = self.chaleur({"c1": "fait_etabli"})
        avec = self.chaleur({"c1": "fait_etabli"}, [{"statut": "infirmee"}])
        self.assertEqual(avec, seule)

    def test_une_hypothese_en_pause_sort_des_deux_termes(self):
        seule = self.chaleur({"c1": "fait_etabli"})
        avec = self.chaleur({"c1": "fait_etabli"}, [{"statut": "en_pause"}])
        self.assertEqual(avec, seule)

    def test_un_statut_inconnu_ne_colore_pas(self):
        self.assertEqual(self.chaleur({"c1": "inventé", "c2": "inventé"}), 0.0)


class Possibles(Bac):
    def poser(self, *releves):
        self.ha("CAS-0001-x", list(releves))
        return composer(self.harness, "S")

    def test_les_options_vivantes_se_comptent_par_noeud(self):
        """R8.4 — un badge numérique par nœud."""
        vue = self.poser(
            self.releve(
                "2026-01-01T10:00:00", sujet="S", kata="k1", champs={},
                options=[
                    {"id": "OPT-1", "libelle": "une piste", "noeud": "k1", "statut": "ouverte"},
                    {"id": "OPT-2", "libelle": "une autre", "noeud": "k1", "statut": "ecartee"},
                ],
            )
        )
        k1 = next(n for n in vue.noeuds if n.id == "k1")
        self.assertEqual(len(k1.options_vivantes), 1)
        self.assertEqual(len(vue.options_vivantes), 1)

    def test_l_age_se_compte_depuis_la_naissance_de_l_option(self):
        """« La dormance n'est pas un statut : c'est un âge. »"""
        naissance = {"id": "OPT-1", "libelle": "l", "noeud": "k1", "statut": "ouverte"}
        vue = self.poser(
            self.releve("2026-01-01T00:00:00", sujet="S", kata="k1", champs={}, options=[naissance]),
            self.releve("2026-01-03T00:00:00", sujet="S", kata="k1", champs={}, options=[naissance]),
        )
        self.assertEqual(vue.options_vivantes[0].age_jours, 2.0)

    def test_l_age_median_est_rendu(self):
        vue = self.poser(
            self.releve("2026-01-01T00:00:00", sujet="S", kata="k1", champs={}, options=[
                {"id": "OPT-1", "libelle": "a", "noeud": "k1", "statut": "ouverte"}]),
            self.releve("2026-01-02T00:00:00", sujet="S", kata="k1", champs={}, options=[
                {"id": "OPT-1", "libelle": "a", "noeud": "k1", "statut": "ouverte"},
                {"id": "OPT-2", "libelle": "b", "noeud": "k1", "statut": "ouverte"}]),
        )
        self.assertEqual(vue.age_median(), 0.5)

    def test_une_option_engagee_n_est_plus_vivante(self):
        vue = self.poser(
            self.releve("2026-01-01T00:00:00", sujet="S", kata="k1", champs={}, options=[
                {"id": "OPT-1", "libelle": "a", "noeud": "k1", "statut": "ouverte"}]),
            self.releve("2026-01-02T00:00:00", sujet="S", kata="k1", champs={}, options=[
                {"id": "OPT-1", "libelle": "a", "noeud": "k1", "statut": "engagee"}]),
        )
        self.assertEqual(vue.options_vivantes, [])

    def test_le_delta_d_une_decision_est_rendu(self):
        vue = self.poser(
            self.releve(
                "2026-01-01T00:00:00", sujet="S", kata="k1", champs={},
                decision={"libelle": "on tranche", "ferme": ["OPT-1"], "ouvre": ["OPT-2", "OPT-3"]},
            )
        )
        self.assertEqual(len(vue.decisions), 1)
        self.assertEqual(vue.decisions[0]["ferme"], ["OPT-1"])
        self.assertEqual(vue.decisions[0]["ouvre"], ["OPT-2", "OPT-3"])

    def test_une_decision_sans_libelle_n_est_pas_une_decision(self):
        vue = self.poser(
            self.releve("2026-01-01T00:00:00", sujet="S", kata="k1", champs={},
                        decision={"libelle": "", "ferme": [], "ouvre": []})
        )
        self.assertEqual(vue.decisions, [])


class LectureSeule(Bac):
    def test_aucun_score_composite_n_est_rendu(self):
        """Carnet #8 — le QG rend des comptes, des listes et des âges. Rien d'autre."""
        self.ha("CAS-0001-x", [self.releve("2026-01-01T10:00:00", sujet="S", kata="k1", champs={})])
        rendu = composer(self.harness, "S").as_dict(self.harness)

        interdits = {"score", "indice", "fecondite", "sante", "note", "seuil", "cible"}
        self.assertEqual(interdits & set(json.dumps(rendu).lower().split('"')), set())

    def test_un_bloc_illisible_ne_colore_rien(self):
        self.ha("CAS-0001-x", [{"horodatage": "2026-01-01T10:00:00", "etat": {"__illisible__": "…"}}])
        self.assertEqual(sujets(self.harness), [])

    def test_le_rendu_texte_porte_la_meme_vue(self):
        self.ha("CAS-0001-x", [
            self.releve("2026-01-01T10:00:00", sujet="S", kata="k1",
                        champs={"c1": "fait_etabli", "c2": "hypothese"},
                        options=[{"id": "OPT-1", "libelle": "une piste", "noeud": "k1",
                                  "statut": "ouverte"}])
        ])
        texte = rendre_texte(self.harness, composer(self.harness, "S"))

        self.assertIn("sujet : S", texte)
        self.assertIn("possibles vivants : 1", texte)
        self.assertIn("une piste", texte)


if __name__ == "__main__":
    unittest.main()


class Profil(Bac):
    """Le module Profil du design (RFC-004 §4) — ses données, pas sa forme."""

    def test_les_activites_viennent_des_blocs_et_de_rien_d_autre(self):
        from kokaji.qg import activites

        self.ha("CAS-0001-x", [
            self.releve("2026-01-01T10:00:00", sujet="S", kata="k1", champs={}),
            self.releve("2026-01-02T10:00:00", sujet="S", kata="k1", champs={}),
        ])
        (self.harness.corpus / "CAS-0001-x" / "fiche.md").write_text(
            '---\nkata: k1\ndate: "2026-01-02T10:00:00+00:00"\n---\n', encoding="utf-8"
        )
        trouve = activites(self.harness)

        self.assertEqual(len(trouve), 1)
        self.assertEqual(trouve[0]["sujet"], "S")
        self.assertEqual(trouve[0]["sessions"], 1)
        self.assertEqual(trouve[0]["harness"], "H")

    def test_un_ha_sans_sujet_ne_fabrique_aucune_activite(self):
        """Un sujet n'existe que si un bloc l'a nommé."""
        from kokaji.qg import activites

        self.ha("CAS-0001-x", [{"horodatage": "2026-01-01T10:00:00", "etat": {"__illisible__": "…"}}])
        (self.harness.corpus / "CAS-0001-x" / "fiche.md").write_text(
            '---\nkata: k1\n---\n', encoding="utf-8"
        )
        self.assertEqual(activites(self.harness), [])

    def test_la_composition_compte_les_types_de_la_chaine(self):
        from kokaji.qg import composition

        self.assertEqual(composition(self.harness), "1 jalon, 2 kata")


class LeNomDUnNoeud(Bac):
    """RFC-013, K-06 — une seule source de nom d'affichage : celle du kata."""

    def test_un_kata_prend_le_nom_de_son_densho_et_un_jalon_garde_le_sien(self):
        from kokaji.hds import charger
        from kokaji.qg import composer

        manifest = (self.racine / "harness.yaml").read_text(encoding="utf-8")
        (self.racine / "harness.yaml").write_text(
            manifest.replace("{ id: k1, type: kata, nom: K1 }", "{ id: k1, type: kata, nom: Ancien nom }"),
            encoding="utf-8",
        )
        vue = composer(charger(self.racine), "S")
        noms = {n.id: n.nom for n in vue.noeuds}
        self.assertEqual(noms["k1"], "K1")
        self.assertEqual(noms["j1"], "J1")


class UnNoeudSansContrat(Bac):
    """RFC-011 D11.3, sabotage 5 — le carré d'un kata en texte est éteint, les autres vivants."""

    def test_le_kata_en_texte_est_sans_contrat_et_les_autres_non(self):
        from kokaji.hds import charger
        from kokaji.qg import composer

        manifest = (self.racine / "harness.yaml").read_text(encoding="utf-8")
        manifest = manifest.replace(
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
        (self.racine / "harness.yaml").write_text(manifest, encoding="utf-8")
        (self.racine / "kata" / "venu.md").write_text("Tu accompagnes.\n", encoding="utf-8")
        vue = composer(charger(self.racine), "S")
        sans = {n.id: n.sans_contrat for n in vue.noeuds}
        self.assertTrue(sans["venu"])
        self.assertFalse(sans["k1"])
        self.assertFalse(sans["k2"])
