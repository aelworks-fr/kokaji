"""La pratique rapportée — importer une conversation jouée ailleurs (RFC-020, lot A).

Le harness de test est purement structurel : aucun nom de domaine (§0).
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_corpus import MANIFEST, _appel

from kokaji.corpus import verser
from kokaji.corpus.depot import DepotFichiers, ref_de, transferer
from kokaji.corpus.provenance import OBSERVE, RAPPORTE, ProvenanceInalterable, provenance_de
from kokaji.corpus.rapporte import Declaration, HorsFrontiere, decouper, fondre, rapporter
from kokaji.corpus.visibilite import regler_visibilite
from kokaji.hds import charger
from kokaji.qg import conversation
from kokaji.trempe.banc.rejeu import tours_du_ha

# Un second kata, qui agit sur le monde — pour le sabotage de la frontière (§2).
MANIFEST_AVEC_ACTION = MANIFEST.replace(
    """chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }""",
    """  - id: k2
    nom: K2
    source: kata/k2.yaml
    livrable: L2
    amont: [k1]
    herite: []
    produit:
      - k2.c2: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }
    capacites: [execution_shell]
    trempe: { verificateurs: [ { type: executable, check: "compile", source: build.log } ] }
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: k2, type: kata, nom: K2 }""",
).replace("  aretes: []", "  aretes:\n    - { de: k1, vers: k2 }")

TEXTE = """User: j'ai un problème à cadrer
avec deux lignes

Assistant: dis-m'en plus

User: voilà le contexte

Assistant: voici ce que je comprends
"""


class Bac(unittest.TestCase):
    manifest = MANIFEST

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        self.racine = racine / "harness"
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text("champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8")
        for kata in ("k1", "k2"):
            (self.racine / "kata" / f"{kata}.yaml").write_text(
                "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
            )
        (self.racine / "harness.yaml").write_text(self.manifest, encoding="utf-8")
        self.harness = charger(self.racine)
        self.journal = racine / "journal"
        self.journal.mkdir()

    def rapporter(self, texte=TEXTE, **declaration):
        return rapporter(
            self.harness, decouper(texte), Declaration(kata="k1", **declaration),
            praticien="u-1", texte_colle=texte, quand="2026-10-01T10:00:00+00:00",
        )


class Decouper(unittest.TestCase):
    """D20.1 — un découpage proposé, jamais imposé."""

    def test_les_etiquettes_des_outils_de_chat_font_les_tours(self):
        tours = decouper(TEXTE)
        self.assertEqual([t["role"] for t in tours], ["humain", "kata", "humain", "kata"])
        self.assertEqual(tours[0]["texte"], "j'ai un problème à cadrer\navec deux lignes")
        self.assertEqual(tours[-1]["texte"], "voici ce que je comprends")

    def test_les_etiquettes_decorees_et_seules_sur_leur_ligne_comptent(self):
        tours = decouper("**Vous**\nbonjour\n\n### ChatGPT a dit :\nsalut\n> Moi : ok")
        self.assertEqual([(t["role"], t["texte"]) for t in tours],
                         [("humain", "bonjour"), ("kata", "salut"), ("humain", "ok")])

    def test_sans_etiquette_les_paragraphes_alternent(self):
        tours = decouper("premier\n\ndeuxième\n---\ntroisième")
        self.assertEqual([(t["role"], t["texte"]) for t in tours],
                         [("humain", "premier"), ("kata", "deuxième"), ("humain", "troisième")])

    def test_un_mot_suivi_de_deux_points_n_est_pas_une_etiquette(self):
        tours = decouper("Note: ceci reste du texte\n\nsuite")
        self.assertEqual(tours[0]["texte"], "Note: ceci reste du texte")

    def test_deux_tours_du_meme_role_se_fondent_et_les_vides_tombent(self):
        tours = fondre([
            {"role": "humain", "texte": "a"}, {"role": "humain", "texte": "b"},
            {"role": "kata", "texte": "  "}, {"role": "kata", "texte": "c"},
        ])
        self.assertEqual(tours, [{"role": "humain", "texte": "a\n\nb"}, {"role": "kata", "texte": "c"}])


class Nominal(Bac):
    """§7.1 — coller, déclarer, retrouver immédiatement au corpus à l'encre `rapporte`."""

    def test_le_ha_nait_brut_a_l_encre_rapporte_avec_sa_declaration(self):
        ha = self.rapporter(kin="un sujet", moteur_origine="m/x", date_origine="2026-08-12",
                            source_texte="un chat généraliste", decoupage_corrige=True)
        self.assertEqual(ha.identifiant, "CAS-0001")
        self.assertTrue(ha.dossier.name.endswith("-k1-rapporte"))
        entete = DepotFichiers().entete(ha.ref)
        self.assertEqual(entete["provenance"], RAPPORTE)
        self.assertEqual(entete["statut"], "brut")
        self.assertEqual(entete["completude"], "B")
        self.assertEqual(entete["kata"], "k1")
        self.assertEqual(entete["praticien"], "u-1")
        self.assertEqual(entete["visibilite"], "privee")
        self.assertEqual(entete["source"], "reel")
        self.assertEqual(entete["moteur"], "m/x")
        self.assertEqual(entete["date"], "2026-08-12")
        self.assertEqual(entete["scores"]["tours"], 2)
        declaration = entete["declaration"]
        self.assertEqual(declaration["kata"], "k1")
        self.assertEqual(declaration["kin"], "un sujet")
        self.assertEqual(declaration["source_texte"], "un chat généraliste")
        self.assertTrue(declaration["decoupage_corrige"])
        self.assertEqual(declaration["rapporte_par"], "u-1")
        fiche = (ha.dossier / "fiche.md").read_text(encoding="utf-8")
        self.assertIn("Pratique rapportée", fiche)
        self.assertNotIn("session `", fiche)  # la veille ne le prendra jamais pour un des siens

    def test_ce_qu_on_ne_sait_pas_se_dit_inconnu_ou_vide_jamais_devine(self):
        entete = DepotFichiers().entete(self.rapporter().ref)
        self.assertEqual(entete["moteur"], "inconnu")
        self.assertEqual(entete["declaration"]["moteur_origine"], "inconnu")
        self.assertEqual(entete["version_coupe"], "")
        self.assertEqual(entete["cible"], "")
        self.assertEqual(entete["date"], "2026-10-01T10:00:00+00:00")
        self.assertFalse(entete["declaration"]["decoupage_corrige"])

    def test_le_transcript_se_lit_par_les_lecteurs_du_middleware(self):
        ha = self.rapporter()
        porteurs, tours = tours_du_ha(ha.dossier)
        self.assertEqual(porteurs, ["j'ai un problème à cadrer\navec deux lignes", "voilà le contexte"])
        self.assertEqual([t.reponse for t in tours], ["dis-m'en plus", "voici ce que je comprends"])
        vue = conversation(self.harness, None, ha.dossier.name)
        self.assertEqual([t["role"] for t in vue["tours"]], ["humain", "kata", "humain", "kata"])

    def test_la_sortie_est_la_derniere_reponse_et_le_texte_colle_reste_en_materiau(self):
        ha = self.rapporter()
        self.assertIn("voici ce que je comprends", (ha.dossier / "sortie.md").read_text(encoding="utf-8"))
        self.assertEqual((ha.dossier / "materiau" / "texte-colle.md").read_text(encoding="utf-8"), TEXTE)
        self.assertIn('"kata": "k1"', (ha.dossier / "materiau" / "declaration.json").read_text(encoding="utf-8"))

    def test_un_kata_qui_parle_d_abord_et_un_porteur_sans_reponse_tiennent(self):
        tours = [{"role": "kata", "texte": "bonjour, que puis-je ?"},
                 {"role": "humain", "texte": "ceci"}, {"role": "kata", "texte": "cela"},
                 {"role": "humain", "texte": "et enfin"}]
        ha = rapporter(self.harness, tours, Declaration(kata="k1"), praticien="u-1")
        porteurs, echange = tours_du_ha(ha.dossier)
        self.assertEqual(porteurs, ["", "ceci", "et enfin"])
        self.assertEqual([t.reponse for t in echange], ["bonjour, que puis-je ?", "cela", ""])

    def test_les_numeros_suivent_ceux_de_la_capture(self):
        (self.journal / "2026-01-01.jsonl").write_text(
            __import__("json").dumps(_appel("s-1", 1, "r1")) + "\n", encoding="utf-8"
        )
        verser(self.harness, self.journal)
        self.assertEqual(self.rapporter().identifiant, "CAS-0002")

    def test_un_ha_capture_nait_observe(self):
        (self.journal / "2026-01-01.jsonl").write_text(
            __import__("json").dumps(_appel("s-1", 1, "r1")) + "\n", encoding="utf-8"
        )
        ha = verser(self.harness, self.journal).ha[0]
        self.assertEqual(DepotFichiers().entete(ref_de(ha.dossier))["provenance"], OBSERVE)

    def test_la_veille_ne_touche_jamais_un_ha_rapporte(self):
        """Il n'est pas versé depuis le journal : aucun passage ne le rafraîchit."""
        ha = self.rapporter()
        avant = (ha.dossier / "fiche.md").read_text(encoding="utf-8")
        verser(self.harness, self.journal, rafraichir=True)
        self.assertEqual((ha.dossier / "fiche.md").read_text(encoding="utf-8"), avant)
        self.assertEqual(len(list(self.harness.corpus.glob("CAS-*"))), 1)


class Refus(Bac):
    """Ce qui n'entre pas — et n'écrit rien."""

    manifest = MANIFEST_AVEC_ACTION

    def test_sabotage_l_action_rapportee_est_refusee_en_citant_la_frontiere(self):
        """§7.4 — un déroulé rattaché à un kata à effets monde ne s'importe pas."""
        tours = decouper("User: déploie\n\nAssistant: j'ai déployé, ça marche")
        with self.assertRaises(HorsFrontiere) as refus:
            rapporter(self.harness, tours, Declaration(kata="k2"), praticien="u-1")
        self.assertIn("RFC-020 §2", str(refus.exception))
        self.assertIn("monde_ecriture", str(refus.exception))
        self.assertEqual(list(self.harness.corpus.glob("CAS-*")), [])

    def test_un_kata_d_echange_du_meme_harness_passe(self):
        self.assertEqual(self.rapporter().kata, "k1")

    def test_un_kata_inconnu_des_tours_vides_ou_un_role_inconnu_sont_refuses(self):
        with self.assertRaises(ValueError):
            rapporter(self.harness, decouper(TEXTE), Declaration(kata="k9"))
        with self.assertRaises(ValueError):
            rapporter(self.harness, [], Declaration(kata="k1"))
        with self.assertRaises(ValueError):
            rapporter(self.harness, [{"role": "juge", "texte": "x"}], Declaration(kata="k1"))
        self.assertEqual(list(self.harness.corpus.glob("CAS-*")), [])


class EncreIndelebile(Bac):
    """§7.6 — tenter de passer un ha `rapporte` en `observe`, par tous les gestes."""

    def test_par_edition_de_la_fiche(self):
        ha = self.rapporter()
        fiche = (ha.dossier / "fiche.md").read_text(encoding="utf-8")
        with self.assertRaises(ProvenanceInalterable):
            DepotFichiers().ecrire_fiche(ha.ref, fiche.replace("provenance: rapporte", "provenance: observe"))
        with self.assertRaises(ProvenanceInalterable):
            DepotFichiers().ecrire_fiche(ha.ref, fiche.replace("provenance: rapporte\n", ""))
        self.assertEqual(provenance_de(DepotFichiers().entete(ha.ref)), RAPPORTE)

    def test_les_gestes_legitimes_gardent_l_encre(self):
        """Régler la visibilité, annoter : la fiche se réécrit, l'encre reste."""
        ha = self.rapporter()
        regler_visibilite(ha.dossier, "verse", par="u-1")
        entete = DepotFichiers().entete(ha.ref)
        self.assertEqual(entete["visibilite"], "verse")
        self.assertEqual(entete["provenance"], RAPPORTE)
        fiche = (ha.dossier / "fiche.md").read_text(encoding="utf-8")
        DepotFichiers().ecrire_fiche(ha.ref, fiche.replace("statut: brut", "statut: annote"))
        self.assertEqual(DepotFichiers().entete(ha.ref)["provenance"], RAPPORTE)

    def test_par_export_puis_reimport_d_une_fiche_maquillee(self):
        """Un export édité à la main, réimporté sur le ha qui existe : refusé."""
        ha = self.rapporter()
        export = Path(self._tmp.name) / "export"
        copie = transferer(ha.ref, DepotFichiers(), DepotFichiers(), corpus=export)
        fiche = copie.chemin / "fiche.md"
        fiche.write_text(
            fiche.read_text(encoding="utf-8").replace("provenance: rapporte", "provenance: observe"),
            encoding="utf-8",
        )
        with self.assertRaises(ProvenanceInalterable):
            transferer(copie, DepotFichiers(), DepotFichiers(), corpus=self.harness.corpus)
        self.assertEqual(DepotFichiers().entete(ha.ref)["provenance"], RAPPORTE)

    def test_un_ha_muet_se_lit_observe(self):
        self.assertEqual(provenance_de({}), OBSERVE)
        self.assertEqual(provenance_de({"provenance": "n'importe quoi"}), OBSERVE)


if __name__ == "__main__":
    unittest.main()
