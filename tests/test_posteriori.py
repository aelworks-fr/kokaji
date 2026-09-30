"""La trempe a posteriori et la semence d'un cas (RFC-020, lots B et C).

Harness purement structurel (§0). Le juge est un double injecté : ce qu'on
éprouve est la discipline autour de l'appel, pas le modèle.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_corpus import MANIFEST, _appel

from kokaji.corpus import verser
from kokaji.corpus.depot import DepotFichiers
from kokaji.corpus.rapporte import Declaration, decouper, rapporter
from kokaji.hds import charger
from kokaji.trempe.banc.jugement import JugeRefuse
from kokaji.trempe.banc.persona import charger as charger_persona
from kokaji.trempe.banc.posteriori import (
    CONTESTE,
    INDECIDABLE,
    INVARIANTS_ETEINTS,
    TrempeRefusee,
    rendre,
    tremper,
)
from kokaji.trempe.banc.semence import SemenceRefusee, semer_cas

CHECKS = """  checks_session:
    - { id: pas-de-jargon, type: interdit, motifs: ["synergie"] }
  grille_judge:
    - { id: clarte, question: "L'échange avance-t-il par questions claires ?", echelle: "1-5" }"""

TEXTE = """User: j'ai un problème à cadrer

Assistant: dis-m'en plus, en synergie

User: voilà le contexte

Assistant: voici ce que je comprends
"""


class Juge:
    """Un juge de papier : répond ce qu'on lui a mis dans la bouche."""

    def __init__(self, *reponses: str):
        self.reponses = list(reponses)
        self.recu: list[tuple[str, list]] = []

    def completer(self, modele: str, messages: list, temperature=None) -> str:
        self.recu.append((modele, messages))
        return self.reponses.pop(0) if self.reponses else "{}"


def verdict(valeur: str, detail: str = "vu") -> str:
    return f'```json\n{{ "verdict": "{valeur}", "detail": "{detail}" }}\n```'


def note(critere: str, valeur) -> str:
    return f'```json\n{{ "critere": "{critere}", "note": {valeur}, "motif": "vu" }}\n```'


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        self.racine = racine / "harness"
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text("champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8")
        (self.racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (self.racine / "harness.yaml").write_text(
            MANIFEST.replace("  checks_session: []", CHECKS), encoding="utf-8"
        )
        self.harness = charger(self.racine)
        self.journal = racine / "journal"
        self.journal.mkdir()

    def rapporter(self, texte=TEXTE, **declaration):
        return rapporter(
            self.harness, decouper(texte), Declaration(kata="k1", **declaration),
            praticien="u-1", texte_colle=texte, quand="2026-10-01T10:00:00+00:00",
        )

    def observe(self):
        (self.journal / "2026-01-01.jsonl").write_text(
            json.dumps(_appel("s-1", 1, "r1")) + "\n", encoding="utf-8"
        )
        return verser(self.harness, self.journal).ha[0]

    def jugements(self, ha) -> list[dict]:
        return DepotFichiers().jugements(ha.ref)


class Deterministe(Bac):
    """D20.3 §1 — les checks du harness tournent, les invariants sont éteints et dits éteints."""

    def test_les_checks_du_harness_mordent_sur_le_transcript_tel_quel(self):
        ha = self.rapporter()
        trempe = tremper(self.harness, ha.dossier, quand="2026-10-02T00:00:00+00:00")
        self.assertEqual(trempe.regles_en_faute, ("pas-de-jargon",))
        self.assertEqual(trempe.constats[0].tour, 1)

    def test_les_invariants_du_bloc_d_etat_sont_eteints_et_le_disent(self):
        ha = self.rapporter()
        trempe = tremper(self.harness, ha.dossier)
        self.assertIn("etat-bien-forme", trempe.eteints)
        self.assertEqual(trempe.eteints, INVARIANTS_ETEINTS)
        fait = self.jugements(ha)[-1]
        self.assertEqual(fait["type"], "trempe-posteriori")
        self.assertIn("aucun bloc d'état", fait["eteints"]["etat-bien-forme"])
        self.assertIn("éteints", rendre(trempe))
        self.assertIsNone(fait["conformite"])

    def test_sans_juge_rien_ne_touche_la_fiche(self):
        ha = self.rapporter()
        avant = (ha.dossier / "fiche.md").read_text(encoding="utf-8")
        tremper(self.harness, ha.dossier)
        self.assertEqual((ha.dossier / "fiche.md").read_text(encoding="utf-8"), avant)

    def test_un_ha_observe_n_est_pas_trempe_a_posteriori(self):
        ha = self.observe()
        with self.assertRaises(TrempeRefusee) as refus:
            tremper(self.harness, ha.dossier)
        self.assertIn("observe", str(refus.exception))


class Judge(Bac):
    """D20.3 §2 — la conformité au kata déclaré, à côté de la déclaration."""

    def test_sabotage_le_hors_sujet_est_conteste_a_cote_de_la_declaration_et_reste(self):
        """§7.3 — le juge conteste ; le verdict s'affiche à côté, n'écrase rien ; le ha reste."""
        ha = self.rapporter(kin="un sujet")
        juge = Juge(verdict("conteste", "l'échange découpe, il ne cadre pas"), note("clarte", 4))
        trempe = tremper(self.harness, ha.dossier, juge, juge="f/juge", quand="2026-10-02T00:00:00+00:00")
        self.assertEqual(trempe.conformite.verdict, CONTESTE)
        entete = DepotFichiers().entete(ha.ref)
        self.assertEqual(entete["conformite"]["verdict"], "conteste")
        self.assertEqual(entete["conformite"]["detail"], "l'échange découpe, il ne cadre pas")
        self.assertEqual(entete["conformite"]["juge"], "f/juge")
        self.assertEqual(entete["conformite"]["le"], "2026-10-02T00:00:00+00:00")
        # La déclaration est intacte, l'encre aussi, le ha est toujours là, brut.
        self.assertEqual(entete["declaration"]["kata"], "k1")
        self.assertEqual(entete["declaration"]["kin"], "un sujet")
        self.assertEqual(entete["provenance"], "rapporte")
        self.assertEqual(entete["statut"], "brut")
        self.assertTrue(ha.dossier.is_dir())
        # Et la grille du harness a suivi.
        self.assertEqual(trempe.scores[0]["critere"], "clarte")
        self.assertEqual(trempe.scores[0]["note"], 4)

    def test_la_consigne_montre_la_coupe_du_kata_et_la_matiere_sans_bloc(self):
        ha = self.rapporter()
        juge = Juge(verdict("conforme"), note("clarte", 3))
        tremper(self.harness, ha.dossier, juge, juge="f/juge")
        modele, messages = juge.recu[0]
        self.assertEqual(modele, "f/juge")
        self.assertIn("kata `k1`", messages[0]["content"])
        self.assertIn("voilà le contexte", messages[1]["content"])

    def test_le_juge_n_est_jamais_le_moteur_d_origine_connu(self):
        ha = self.rapporter(moteur_origine="f/origine")
        with self.assertRaises(JugeRefuse):
            tremper(self.harness, ha.dossier, Juge(), juge="f/origine")
        # Un moteur d'origine inconnu ne peut être confondu avec personne : le juge passe.
        autre = self.rapporter()
        trempe = tremper(self.harness, autre.dossier, Juge(verdict("conforme"), note("clarte", 3)), juge="f/juge")
        self.assertEqual(trempe.conformite.verdict, "conforme")

    def test_un_juge_qui_repond_mal_est_constate_indecidable(self):
        ha = self.rapporter()
        trempe = tremper(self.harness, ha.dossier, Juge("n'importe quoi", "{}"), juge="f/juge")
        self.assertEqual(trempe.conformite.verdict, INDECIDABLE)
        trempe = tremper(self.harness, ha.dossier, Juge(verdict("peut-etre"), "{}"), juge="f/juge")
        self.assertEqual(trempe.conformite.verdict, INDECIDABLE)

    def test_chaque_passage_s_ajoute_date_et_versionne(self):
        ha = self.rapporter()
        tremper(self.harness, ha.dossier, Juge(verdict("conteste"), note("clarte", 2)), juge="f/juge",
                quand="2026-10-02T00:00:00+00:00")
        tremper(self.harness, ha.dossier, Juge(verdict("conforme"), note("clarte", 4)), juge="f/juge",
                quand="2026-10-03T00:00:00+00:00")
        faits = [f for f in self.jugements(ha) if f.get("type") == "trempe-posteriori"]
        self.assertEqual([f["conformite"]["verdict"] for f in faits], ["conteste", "conforme"])
        self.assertEqual([f["le"] for f in faits], ["2026-10-02T00:00:00+00:00", "2026-10-03T00:00:00+00:00"])
        self.assertEqual(faits[0]["conformite"]["version_grille"], "conformite-1")
        self.assertEqual(DepotFichiers().entete(ha.ref)["conformite"]["verdict"], "conforme")


class Semence(Bac):
    """D20.4 — semer un cas pré-rempli, avec `seme_par:` ; §7.2."""

    def test_le_cas_seme_est_un_persona_lisible_qui_dit_d_ou_il_vient(self):
        ha = self.rapporter(kin="Refonte d'un portail", source_texte="un chat")
        cas = semer_cas(self.harness, ha.dossier, par="u-1")
        self.assertEqual(cas.id, "refonte-d-un-portail")
        self.assertEqual(cas.chemin, self.harness.personas / "refonte-d-un-portail.yaml")
        persona = charger_persona(cas.chemin)
        self.assertEqual(persona.seme_par, "CAS-0001")
        self.assertEqual(persona.nom, "Refonte d'un portail")
        self.assertIn("j'ai un problème à cadrer", persona.sujet)
        self.assertEqual(persona.deroule, ("j'ai un problème à cadrer", "voilà le contexte"))
        self.assertIn("À écrire", persona.posture)
        texte = cas.chemin.read_text(encoding="utf-8")
        self.assertIn("seme_par: CAS-0001", texte)
        self.assertIn("source_texte: un chat", texte)

    def test_sans_kin_le_cas_prend_le_nom_du_ha(self):
        ha = self.rapporter()
        cas = semer_cas(self.harness, ha.dossier)
        self.assertEqual(cas.id, "cas-0001")
        self.assertEqual(charger_persona(cas.chemin).nom, "Cas semé depuis CAS-0001")

    def test_semer_n_ecrase_pas_et_ne_seme_pas_depuis_un_ha_observe(self):
        ha = self.rapporter()
        semer_cas(self.harness, ha.dossier)
        with self.assertRaises(SemenceRefusee):
            semer_cas(self.harness, ha.dossier)
        with self.assertRaises(SemenceRefusee):
            semer_cas(self.harness, self.observe().dossier)

    def test_un_persona_d_avant_reste_lisible_sans_ces_champs(self):
        chemin = self.harness.personas / "ancien.yaml"
        chemin.write_text("id: ancien\nnom: A\nsujet: s\nposture: p\n", encoding="utf-8")
        persona = charger_persona(chemin)
        self.assertEqual(persona.seme_par, "")
        self.assertEqual(persona.deroule, ())


if __name__ == "__main__":
    unittest.main()
