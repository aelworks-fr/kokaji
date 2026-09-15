"""Le journal des appels — deux sources, une lecture (RFC-014, lot C).

Le fichier reste ce que le hook écrit sans base ; la base est ce qu'il écrit
avec ; `lire_journal` ne compte jamais un appel deux fois.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.corpus.journal import lire_fichiers, lire_journal

URL_ESSAI = os.environ.get("KOKAJI_BASE_URL_ESSAI", "").strip()
HOOK = Path(__file__).resolve().parents[1] / "dojo" / "litellm" / "hooks" / "journal_ha.py"


def _appel(numero: int, harness: str = "h", session: str = "s-1") -> dict:
    return {
        "statut": "abouti",
        "id_appel": f"appel-{numero}",
        "session": session,
        "etat_avant": None,
        "etat_apres": f"e{numero}",
        "debut": f"2026-09-15T10:00:{numero:02d}+00:00",
        "fin": f"2026-09-15T10:00:{numero:02d}+00:00",
        "moteur": "m",
        "fournisseur": None,
        "identite": {"harness": harness, "kata": "k1", "cible": "c", "cle": "chat"},
        "messages": [{"role": "user", "content": "é"}],
        "reponse": f"réponse {numero}",
        "usage": {"total_tokens": 3},
        "erreur": None,
    }


def _charger_le_hook():
    spec = importlib.util.spec_from_file_location("journal_ha", HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestFichiers(unittest.TestCase):
    def test_sans_dossier_rien_et_sans_base_les_fichiers_seuls(self):
        avant = os.environ.pop("KOKAJI_BASE_URL", None)
        try:
            self.assertEqual(lire_journal(None), [])
            self.assertEqual(lire_journal(Path("/nulle/part")), [])
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "2026-09-15.jsonl").write_text(
                    json.dumps(_appel(1)) + "\npas du json\n" + json.dumps(_appel(2, harness="autre")) + "\n",
                    encoding="utf-8",
                )
                self.assertEqual([l["id_appel"] for l in lire_fichiers(Path(tmp))], ["appel-1", "appel-2"])
                self.assertEqual([l["id_appel"] for l in lire_journal(Path(tmp), "h")], ["appel-1"])
        finally:
            if avant is not None:
                os.environ["KOKAJI_BASE_URL"] = avant

    def test_le_hook_ecrit_le_fichier_du_jour_sans_base(self):
        hook = _charger_le_hook()
        with tempfile.TemporaryDirectory() as tmp:
            ou = hook._ecrire(_appel(1), base=None, dossier=Path(tmp))
            self.assertEqual(ou, "fichier")
            self.assertEqual(len(list(Path(tmp).glob("*.jsonl"))), 1)
            self.assertEqual(lire_fichiers(Path(tmp))[0]["reponse"], "réponse 1")


@unittest.skipUnless(URL_ESSAI, "KOKAJI_BASE_URL_ESSAI absent : pas de Postgres d'essai")
class TestBase(unittest.TestCase):
    def setUp(self):
        from kokaji.corpus.base import JournalBase

        self.journal = JournalBase(URL_ESSAI)
        self.journal._executer("DELETE FROM appel WHERE id LIKE 'appel-%%'")
        self.avant = os.environ.get("KOKAJI_BASE_URL")
        os.environ["KOKAJI_BASE_URL"] = URL_ESSAI

    def tearDown(self):
        self.journal._executer("DELETE FROM appel WHERE id LIKE 'appel-%%'")
        self.journal.fermer()
        if self.avant is None:
            del os.environ["KOKAJI_BASE_URL"]
        else:
            os.environ["KOKAJI_BASE_URL"] = self.avant

    def test_le_hook_ecrit_en_base_et_la_lecture_demande_par_harness(self):
        hook = _charger_le_hook()
        base = hook._Base(URL_ESSAI)
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(hook._ecrire(_appel(1), base=base, dossier=Path(tmp)), "base")
            self.assertEqual(hook._ecrire(_appel(2, harness="autre"), base=base, dossier=Path(tmp)), "base")
            self.assertEqual(hook._ecrire(_appel(1), base=base, dossier=Path(tmp)), "base")  # rejoué : une fois
            self.assertEqual(list(Path(tmp).glob("*.jsonl")), [])  # rien en fichier
        base._connexion.close()

        self.assertEqual(self.journal.compter(), 2)
        self.assertEqual(self.journal.compter("h"), 1)
        lignes = self.journal.appels("h")
        self.assertEqual(lignes, [_appel(1)])  # la ligne entière, intacte, accents compris
        self.assertEqual([l["id_appel"] for l in lire_journal(None, "h")], ["appel-1"])
        self.assertEqual([l["id_appel"] for l in lire_journal(None)], ["appel-1", "appel-2"])

    def test_fichiers_et_base_se_lisent_ensemble_sans_compter_deux_fois(self):
        self.journal.ecrire(_appel(1))
        self.journal.ecrire(_appel(3))
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "2026-09-15.jsonl").write_text(
                json.dumps(_appel(1)) + "\n" + json.dumps(_appel(2)) + "\n", encoding="utf-8"
            )
            self.assertEqual(
                [l["id_appel"] for l in lire_journal(Path(tmp), "h")], ["appel-1", "appel-2", "appel-3"]
            )

    def test_une_base_tombee_ne_perd_pas_l_appel(self):
        hook = _charger_le_hook()
        muette = hook._Base("postgresql://kokaji:x@127.0.0.1:1/aucune?connect_timeout=1")
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertLogs("kokaji.journal_ha", level="WARNING"):
                self.assertEqual(hook._ecrire(_appel(9), base=muette, dossier=Path(tmp)), "fichier")
            self.assertEqual(hook._ecrire(_appel(10), base=muette, dossier=Path(tmp)), "fichier")
            self.assertEqual(len(lire_fichiers(Path(tmp))), 2)

    def test_la_veille_capture_un_ha_depuis_un_journal_qui_n_est_qu_en_base(self):
        from test_corpus import IDENTITE, Bac
        from test_corpus import _appel as appel_du_corpus

        from kokaji.middleware import veiller

        bac = Bac()
        bac.setUp()
        try:
            appel = appel_du_corpus("s-base", 1, "une réponse")
            appel.update({"id_appel": "appel-base-1", "etat_apres": "e1", "statut": "abouti"})
            self.assertEqual(appel["identite"]["harness"], IDENTITE["harness"])
            self.journal.ecrire(appel)
            # Le dossier du journal n'existe pas : tout vient de la base.
            passe = veiller(bac.harness, journal=bac.journal.parent / "absent", repos=0)
            self.assertEqual([ha.session for ha in passe.veilles], ["s-base"])
        finally:
            bac.doCleanups()

if __name__ == "__main__":
    unittest.main()
