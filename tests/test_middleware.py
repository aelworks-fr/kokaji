"""Le middleware capture, extrait l'état, et vérifie le carré (SPECS §7, RFC-002 §6.3).

Harness purement structurels, comme partout (§0). Aucun réseau : le journal est
un fichier, le middleware ne parle qu'à des fichiers.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import charger
from kokaji.middleware import carre_attendu, carre_du_ha, etats_du_ha, veiller

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
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: suite, type: externe, nom: Suite }
  aretes:
    - { de: k1, vers: suite, label: fin }
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


def bloc(champs: dict) -> str:
    return (
        "```json kokaji_state\n"
        + json.dumps({"kokaji_state": {"champs": champs, "pret_pour": None}})
        + "\n```"
    )


def bloc_action(champs: dict, actions: list) -> str:
    return (
        "```json kokaji_state\n"
        + json.dumps({"kokaji_state": {"champs": champs, "actions": actions, "pret_pour": None}})
        + "\n```"
    )


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        racine = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.racine = racine / "harness"
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text(
            "champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8"
        )
        (self.racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.racine)
        self.kata = self.harness.kata_par_id("k1")

        self.journal = racine / "journal"
        self.journal.mkdir()

    def appel(self, session, tours, reponse, fin="2026-01-01T10:00:00+00:00"):
        messages = [{"role": "system", "content": "LA COUPE"}]
        for rang in range(tours):
            messages.append({"role": "user", "content": f"porteur {rang + 1}"})
            if rang < tours - 1:
                messages.append({"role": "assistant", "content": f"kata {rang + 1}"})
        return {
            "session": session,
            "identite": {
                "harness": "h", "kata": "k1", "version_kata": "1.0.0",
                "version_coupe": "abc123", "cible": "c1", "date": fin,
            },
            "messages": messages, "reponse": reponse, "debut": fin, "fin": fin,
            "moteur": "m", "fournisseur": "f",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }

    def ecrire_journal(self, appels):
        (self.journal / "2026-01-01.jsonl").write_text(
            "\n".join(json.dumps(a, ensure_ascii=False) for a in appels) + "\n", encoding="utf-8"
        )

    def releves(self, *reponses):
        appels = [self.appel("s-1", i, r) for i, r in enumerate(reponses, 1)]
        return etats_du_ha(self.harness, self.kata, appels, ("c1", "c2"))


class Etat(Bac):
    def test_les_blocs_sont_horodates_et_rattaches(self):
        releves = self.releves(bloc({"c1": "fait_etabli"}))
        self.assertEqual(len(releves), 1)
        self.assertEqual(releves[0]["horodatage"], "2026-01-01T10:00:00+00:00")
        self.assertEqual(releves[0]["etat"]["champs"], {"c1": "fait_etabli"})

    def test_un_bloc_malforme_est_consigne_jamais_bloquant(self):
        """R7.2 — le middleware note la faute et poursuit."""
        releves = self.releves("```json kokaji_state\n{ pas du json\n```", bloc({"c1": "fait_etabli"}))
        self.assertEqual(len(releves), 2)
        self.assertEqual(releves[0]["fautes"][0]["regle"], "etat-bien-forme")
        self.assertEqual(releves[1]["fautes"], [])

    def test_un_statut_hors_taxonomie_est_consigne(self):
        releves = self.releves(bloc({"c1": "presque"}))
        self.assertIn("hors taxonomie", releves[0]["fautes"][0]["message"])


class CarreContinu(Bac):
    def test_conforme_quand_l_etat_final_livre_la_promesse(self):
        releves = self.releves(bloc({"c1": "fait_etabli", "c2": "hypothese"}))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "conforme")

    def test_sous_promettre_est_permis(self):
        """La pratique peut livrer plus fort que promis — c'est le slack."""
        releves = self.releves(bloc({"c1": "fait_etabli", "c2": "fait_etabli"}))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "conforme")

    def test_sur_promesse_quand_un_champ_est_trop_faible(self):
        releves = self.releves(bloc({"c1": "hypothese", "c2": "hypothese"}))
        carre = carre_du_ha(self.harness, self.kata, releves)

        self.assertEqual(carre.verdict, "sur-promesse")
        self.assertEqual(carre.manquants, (("c1", "fait_etabli", "hypothese"),))

    def test_sur_promesse_quand_un_champ_manque(self):
        releves = self.releves(bloc({"c1": "fait_etabli"}))
        carre = carre_du_ha(self.harness, self.kata, releves)

        self.assertEqual(carre.verdict, "sur-promesse")
        self.assertEqual(carre.manquants, (("c2", "hypothese", "absent"),))

    def test_seul_le_dernier_bloc_compte(self):
        """L'état final, pas les états intermédiaires."""
        releves = self.releves(
            bloc({"c1": "en_pause", "c2": "en_pause"}),
            bloc({"c1": "fait_etabli", "c2": "hypothese"}),
        )
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "conforme")

    def test_un_ha_sans_bloc_n_est_pas_evaluable(self):
        releves = self.releves("aucun bloc ici")
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "sans-etat")

    def test_un_statut_hors_taxonomie_ne_couvre_rien(self):
        """Un statut inventé est le plus faible de tous : il ne peut rien garantir."""
        releves = self.releves(bloc({"c1": "etabli", "c2": "etabli"}))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "sur-promesse")


class CarreDesActions(Bac):
    """RFC-016 amende RFC-002 : α couvre les actions — la trace est jugée."""

    def _honnete(self):
        return {"intention": "tester", "canal": "monde_lecture", "artefact": "rapport.json",
                "verdict": {"valeur": "tous_passes", "confiance": 1.0},
                "rapporte_par_l_agent": "tous_passes", "divergence": False}

    def _menteur(self):
        return {"intention": "tester", "canal": "monde_lecture", "artefact": "rapport.json",
                "verdict": {"valeur": "echecs", "confiance": 1.0},
                "rapporte_par_l_agent": "tous_passes", "divergence": True}

    def test_une_action_honnete_reste_conforme(self):
        releves = self.releves(bloc_action({"c1": "fait_etabli", "c2": "hypothese"}, [self._honnete()]))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "conforme")

    def test_une_action_qui_ment_est_une_sur_promesse_d_action(self):
        releves = self.releves(bloc_action({"c1": "fait_etabli", "c2": "hypothese"}, [self._menteur()]))
        carre = carre_du_ha(self.harness, self.kata, releves)
        self.assertEqual(carre.verdict, "action-sur-promesse")
        self.assertEqual(carre.manquants, (("rapport.json", "tous_passes", "echecs"),))

    def test_la_sur_promesse_de_champ_prime_sur_l_action(self):
        # champs trop faibles ET action menteuse : c'est le champ qui est nommé d'abord
        releves = self.releves(bloc_action({"c1": "hypothese", "c2": "hypothese"}, [self._menteur()]))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "sur-promesse")

    def test_un_ha_sans_action_est_jugé_comme_avant(self):
        releves = self.releves(bloc({"c1": "fait_etabli", "c2": "hypothese"}))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "conforme")


class HeritePremisse(Bac):
    def setUp(self):
        super().setUp()
        manifest = MANIFEST.replace("    amont: []\n    herite: []", "    amont: []\n    herite: []")
        (self.racine / "harness.yaml").write_text(manifest, encoding="utf-8")

    def test_un_kata_sans_amont_satisfait_la_premisse_par_vacuite(self):
        releves = self.releves(bloc({"c1": "fait_etabli", "c2": "hypothese"}))
        self.assertEqual(carre_du_ha(self.harness, self.kata, releves).verdict, "conforme")


class Veille(Bac):
    def test_une_session_close_devient_un_ha_avec_son_etat(self):
        """R7.3 — la capture n'attend aucun geste humain."""
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "fait_etabli", "c2": "hypothese"}))])
        veilles = veiller(
            self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00"
        ).veilles

        self.assertEqual(len(veilles), 1)
        self.assertEqual(veilles[0].carre, "conforme")
        dossier = self.harness.corpus / f"{veilles[0].ha}-k1-c1-abc123"
        self.assertTrue((dossier / "etats.jsonl").is_file())
        self.assertIn("conforme", (dossier / "carre.md").read_text(encoding="utf-8"))

    def test_une_session_vivante_entre_au_corpus_marquee_en_cours(self):
        """Le corpus suit la conversation ; il ne l'attend pas."""
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "fait_etabli"}))])
        veilles = veiller(
            self.harness, self.journal, repos=3600, maintenant="2026-01-01T10:01:00+00:00"
        ).veilles

        self.assertEqual(len(veilles), 1)
        self.assertTrue(veilles[0].en_cours)
        fiche = (veilles[0].ha and next(self.harness.corpus.glob("CAS-*")) / "fiche.md")
        texte = fiche.read_text(encoding="utf-8")
        self.assertIn("en_cours: true", texte)
        self.assertIn("completude: C", texte)

    def test_un_ha_brut_se_rafraichit_au_lieu_de_se_dupliquer(self):
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "fait_etabli"}))])
        veiller(self.harness, self.journal, repos=3600, maintenant="2026-01-01T10:01:00+00:00")

        # la conversation continue
        self.ecrire_journal([
            self.appel("s-1", 1, bloc({"c1": "fait_etabli"})),
            self.appel("s-1", 3, bloc({"c1": "fait_etabli", "c2": "hypothese"})),
        ])
        veilles = veiller(
            self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00"
        ).veilles

        self.assertEqual(len(list(self.harness.corpus.glob("CAS-*"))), 1)
        self.assertEqual(veilles[0].blocs, 2)
        self.assertFalse(veilles[0].en_cours)
        fiche = (next(self.harness.corpus.glob("CAS-*")) / "fiche.md").read_text(encoding="utf-8")
        self.assertIn("en_cours: false", fiche)

    def test_un_ha_annote_n_est_jamais_reecrit(self):
        """La promotion humaine prime sur la capture."""
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "fait_etabli"}))])
        veiller(self.harness, self.journal, repos=3600, maintenant="2026-01-01T10:01:00+00:00")

        dossier = next(self.harness.corpus.glob("CAS-*"))
        fiche = dossier / "fiche.md"
        fiche.write_text(
            fiche.read_text(encoding="utf-8").replace("statut: brut", "statut: annote")
            + "\n\nUne annotation humaine.\n",
            encoding="utf-8",
        )

        self.ecrire_journal([
            self.appel("s-1", 1, bloc({"c1": "fait_etabli"})),
            self.appel("s-1", 3, bloc({"c1": "fait_etabli", "c2": "hypothese"})),
        ])
        veiller(self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00")

        self.assertIn("Une annotation humaine.", fiche.read_text(encoding="utf-8"))
        self.assertIn("statut: annote", fiche.read_text(encoding="utf-8"))

    def test_la_sur_promesse_remonte_dans_la_veille(self):
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "hypothese"}))])
        veilles = veiller(
            self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00"
        ).veilles
        self.assertEqual(veilles[0].carre, "sur-promesse")


if __name__ == "__main__":
    unittest.main()


class CibleSansEtat(Bac):
    """Une cible qui ne demande aucun bloc ne reçoit pas de carré.

    Le verdict `sans-etat` reproche une absence. Sur une cible
    `etat_structure: false`, l'absence est conforme — et le corpus de
    l'Atelier portait 52 reproches de ce genre.
    """

    def setUp(self):
        super().setUp()
        (self.racine / "harness.yaml").write_text(
            MANIFEST.replace(
                "cibles:\n  - id: c1\n    etat_structure: true",
                "cibles:\n  - id: c0\n    etat_structure: false\n    en_tete: H\n"
                "    packaging: dossier\n  - id: c1\n    etat_structure: true",
            ),
            encoding="utf-8",
        )
        self.harness = charger(self.racine)

    def appel_sur_c0(self, session):
        appel = self.appel(session, 1, "une réponse sans aucun bloc")
        appel["identite"]["cible"] = "c0"
        return appel

    def test_la_cible_qui_ne_demande_rien_n_est_pas_jugee(self):
        self.assertFalse(carre_attendu(self.harness, "c0"))
        self.assertTrue(carre_attendu(self.harness, "c1"))

    def test_une_cible_inconnue_est_jugee_plutot_que_passee(self):
        """Se taire sur ce qu'on ne reconnaît pas rétablirait le silence ôté."""
        self.assertTrue(carre_attendu(self.harness, "jamais-declaree"))

    def test_aucun_carre_n_est_ecrit(self):
        self.ecrire_journal([self.appel_sur_c0("s-1")])
        passe = veiller(
            self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00"
        )
        dossier = next(self.harness.corpus.glob("CAS-*"))
        self.assertFalse((dossier / "carre.md").is_file())
        self.assertEqual(passe.veilles[0].carre, "")

    def test_un_carre_ecrit_avant_la_regle_est_retire(self):
        """Un fichier périmé se lit comme un fichier à jour."""
        self.ecrire_journal([self.appel_sur_c0("s-1")])
        veiller(self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00")
        dossier = next(self.harness.corpus.glob("CAS-*"))
        (dossier / "carre.md").write_text("# Carré de naturalité — sans-etat\n", encoding="utf-8")

        veiller(self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00")
        self.assertFalse((dossier / "carre.md").is_file())

    def test_le_verdict_d_une_re_abstraction_survit(self):
        """La ré-abstraction porte justement sur les cibles non instrumentées."""
        self.ecrire_journal([self.appel_sur_c0("s-1")])
        veiller(self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00")
        dossier = next(self.harness.corpus.glob("CAS-*"))
        # La marque telle que la ré-abstraction l'écrit, dans le carré lui-même.
        # La poser dans la fiche ne tiendrait pas : celle d'un ha `brut` est
        # réécrite à chaque passage de la veille.
        (dossier / "carre.md").write_text(
            "# Carré de naturalité — conforme\n\n"
            "> État **ré-abstrait** depuis le transcript, non émis en session.\n",
            encoding="utf-8",
        )

        veiller(self.harness, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00")
        self.assertIn("conforme", (dossier / "carre.md").read_text(encoding="utf-8"))


class VeilleEtDeuxCorpus(Bac):
    """La capture continue refuse un double, et le dit — NOTE-0019.

    C'est le chemin où un refus muet coûte le plus cher : la veille tourne
    sans personne devant, et un ha jamais écrit ne manque qu'au moment où on
    le cherche.
    """

    def setUp(self):
        super().setUp()
        for nom in ("reel", "essai"):
            (self.racine / "corpus" / nom).mkdir(parents=True)
        (self.racine / "harness.yaml").write_text(
            MANIFEST.replace(
                "corpus: corpus/",
                "corpus:\n  reel:\n    chemin: corpus/reel/\n"
                "  essai:\n    chemin: corpus/essai/\n",
            ),
            encoding="utf-8",
        )
        self.harness = charger(self.racine)
        self.reel = self.harness.corpus_par_nom("reel").chemin
        self.essai = self.harness.corpus_par_nom("essai").chemin

    def veille(self, corpus):
        return veiller(
            self.harness, self.journal, repos=60,
            maintenant="2026-01-01T11:00:00+00:00", corpus=corpus,
        )

    def test_la_session_n_entre_pas_dans_le_second_corpus(self):
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "fait_etabli", "c2": "hypothese"}))])
        self.assertEqual(len(self.veille(self.reel).veilles), 1)

        ensuite = self.veille(self.essai)
        self.assertEqual(ensuite.veilles, [])
        self.assertEqual(list(self.essai.glob("CAS-*")), [])

    def test_le_refus_est_rendu_et_nomme_ou_elle_est(self):
        self.ecrire_journal([self.appel("s-1", 1, bloc({"c1": "fait_etabli", "c2": "hypothese"}))])
        premier = self.veille(self.reel).veilles[0]

        ensuite = self.veille(self.essai)
        self.assertEqual(list(ensuite.doubles), ["s-1"])
        self.assertIn(premier.ha, ensuite.doubles["s-1"].name)


class VeilleSurPlusieursHarness(unittest.TestCase):
    """La veille itère, et un harness fautif n'emporte pas les autres — NOTE-0009."""

    def setUp(self):
        from types import SimpleNamespace

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.journal = self.racine / "journal"
        self.journal.mkdir()

        for identifiant in ("h", "h2"):
            dossier = self.racine / "harness" / identifiant
            for sous in ("kata", "personas", "corpus"):
                (dossier / sous).mkdir(parents=True)
            (dossier / "template.md").write_text("{{ role }}", encoding="utf-8")
            (dossier / "registre.yaml").write_text(
                "champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8"
            )
            (dossier / "kata" / "k1.yaml").write_text(
                "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
            )
            (dossier / "harness.yaml").write_text(
                MANIFEST.replace("id: h\n", f"id: {identifiant}\n"), encoding="utf-8"
            )

        self.args = SimpleNamespace(
            journal=self.journal, repos=0, source="reel", rattraper=False,
            corpus=None, cle_appelante=[],
        )

    def _appel(self, harness_id: str, session: str) -> dict:
        return {
            "session": session,
            "identite": {
                "harness": harness_id, "kata": "k1", "version_kata": "1.0.0",
                "version_coupe": "abc123", "cible": "c1",
                "date": "2026-01-01T10:00:00+00:00",
            },
            "messages": [{"role": "user", "content": "porteur"}],
            "reponse": bloc({"c1": "fait_etabli", "c2": "hypothese"}),
            "debut": "2026-01-01T10:00:00+00:00", "fin": "2026-01-01T10:00:00+00:00",
            "moteur": "m", "fournisseur": "f", "usage": {},
        }

    def _journal(self, appels):
        (self.journal / "2026-01-01.jsonl").write_text(
            "\n".join(json.dumps(a, ensure_ascii=False) for a in appels) + "\n", encoding="utf-8"
        )

    def _passe(self):
        """Le chemin exact de la veille : on charge ce qui tient, on veille dessus.

        Les harness refusés au chargement et ceux qui échouent en veille sont
        deux moments d'un même échec pour l'exploitant — la commande les
        rassemble, le test aussi.
        """
        from kokaji.cli import _une_passe
        from kokaji.hds import charger_valides

        harness, refuses = charger_valides(self.racine / "harness")
        veilles, echecs, _ = _une_passe(harness, self.args, "2026-01-01T11:00:00+00:00")
        return veilles, [*refuses, *echecs]

    def test_chaque_harness_capture_ses_propres_sessions(self):
        """Le journal est partagé ; chacun n'y prend que ses lignes."""
        self._journal([self._appel("h", "s-1"), self._appel("h2", "s-2")])
        veilles, echecs = self._passe()
        self.assertEqual(echecs, [])
        self.assertEqual(sorted(identifiant for identifiant, _ in veilles), ["h", "h2"])

    def test_un_harness_fautif_n_arrete_pas_les_autres(self):
        """La leçon de NOTE-0009 : le processus ne sort pas, il signale.

        Un corpus non déclaré sur `h2` doit coûter la capture de `h2`, et
        d'elle seule. Deux jours sans capture ont suivi la fois où un seul
        manifest refusé a fait sortir le processus.
        """
        self._journal([self._appel("h", "s-1"), self._appel("h2", "s-2")])
        self.args.corpus = "inexistant"
        veilles, echecs = self._passe()
        self.assertEqual([identifiant for identifiant, _ in echecs], ["h", "h2"])
        self.assertIn("corpus inconnu", echecs[0][1])
        self.assertEqual(veilles, [])

    def test_l_echec_est_rendu_et_nomme_son_harness(self):
        """Sans le nom, un exploitant sait qu'il y a une panne sans savoir où."""
        self._journal([self._appel("h", "s-1")])
        (self.racine / "harness" / "h2" / "registre.yaml").unlink()
        veilles, echecs = self._passe()
        self.assertEqual([identifiant for identifiant, _ in echecs], ["h2"])
        self.assertEqual([identifiant for identifiant, _ in veilles], ["h"])


class TaxonomiesVoisines(Bac):
    """NOTE-0005 — le modèle ne l'a pas inventée, il l'a prise à côté.

    « Hors taxonomie » ne dit pas d'où vient la valeur. Deux listes qui se
    recouvrent produisent cette confusion, et un refus anonyme la rend
    indiscernable d'une valeur en l'air. La nommer change le refus en
    diagnostic : corriger le modèle, ou séparer deux listes trop voisines.
    """

    NATURES = ("evident", "analysable", "emergent", "urgence", "indetermine")

    def fautes(self, champs: dict, natures=NATURES) -> list[str]:
        appels = [self.appel("s-1", 1, bloc(champs))]
        releves = etats_du_ha(self.harness, self.kata, appels, ("c1", "c2"), natures)
        return [f["message"] for f in releves[0]["fautes"]]

    def test_une_nature_prise_pour_un_statut_de_champ_est_nommee(self):
        """Le cas exact du carnet : `indetermine`, quatre fois au tour 1."""
        messages = self.fautes({"c1": "indetermine"})
        self.assertEqual(len(messages), 1)
        self.assertIn("valeur de `natures`", messages[0])

    def test_une_valeur_en_l_air_reste_un_refus_sans_diagnostic(self):
        """On ne nomme une voisine que s'il y en a une — inventer serait pire."""
        messages = self.fautes({"c1": "presque"})
        self.assertIn("hors taxonomie", messages[0])
        self.assertNotIn("valeur de", messages[0])

    def test_sans_natures_declarees_rien_n_est_invente(self):
        messages = self.fautes({"c1": "indetermine"}, natures=())
        self.assertNotIn("valeur de", messages[0])

    def test_un_statut_d_hypothese_pris_pour_un_statut_de_champ(self):
        """La confusion marche dans les deux sens, et les deux se disent."""
        messages = self.fautes({"c1": "validee"})
        self.assertIn("valeur de `statuts_hypothese`", messages[0])

    def test_un_statut_de_champ_pris_pour_un_statut_d_hypothese(self):
        appels = [
            self.appel(
                "s-1", 1,
                "```json kokaji_state\n"
                + json.dumps({"kokaji_state": {"champs": {}, "hypotheses": [
                    {"enonce": "e", "statut": "fait_etabli", "confiance": "moyenne"}
                ], "pret_pour": None}})
                + "\n```",
            )
        ]
        releves = etats_du_ha(self.harness, self.kata, appels, ("c1", "c2"), self.NATURES)
        messages = [f["message"] for f in releves[0]["fautes"]]
        self.assertTrue(
            any("valeur de `statuts_champ`" in m for m in messages), messages
        )
