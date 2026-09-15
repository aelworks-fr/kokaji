"""L'instance s'exporte entière et s'importe — rien de captif (RFC-014, lot D).

Sabotage 4 : export puis import sur une base vide → même nombre de ha, mêmes
identités, même QG ; et l'export d'un ha est identique, octet pour octet, au
`CAS-XXXX/` que le régime fichiers écrivait. Tout ceci demande le Postgres
d'essai (`KOKAJI_BASE_URL_ESSAI`).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_corpus import MANIFEST, _appel

from kokaji.cli import main
from kokaji.comptes import Comptes
from kokaji.corpus.depot import DepotFichiers, RefHa
from kokaji.corpus.journal import lire_fichiers
from kokaji.hds import charger
from kokaji.qg import composer, sujets

URL_ESSAI = os.environ.get("KOKAJI_BASE_URL_ESSAI", "").strip()


def _octets(dossier: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(dossier)): p.read_bytes()
        for p in sorted(dossier.rglob("*"))
        if p.is_file()
    }


@unittest.skipUnless(URL_ESSAI, "KOKAJI_BASE_URL_ESSAI absent : pas de Postgres d'essai")
class Instance(unittest.TestCase):
    def setUp(self):
        from kokaji.corpus.base import DepotBase, JournalBase

        self.base, self.journal = DepotBase(URL_ESSAI), JournalBase(URL_ESSAI)
        Comptes(URL_ESSAI).fermer()  # pose les tables des comptes, que `vider` va toucher
        self.vider()
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.avant = os.environ.pop("KOKAJI_BASE_URL", None)

        # Une instance en régime fichiers : un harness, son corpus, son journal.
        self.harness_dir = self.racine / "harness" / "h"
        for sous in ("kata", "personas", "corpus"):
            (self.harness_dir / sous).mkdir(parents=True)
        (self.harness_dir / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.harness_dir / "registre.yaml").write_text("champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8")
        (self.harness_dir / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (self.harness_dir / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.harness_dir)
        self.journal_dir = self.racine / "journal"
        self.journal_dir.mkdir()
        appels = [_appel("s-1", 1, "r1"), _appel("s-2", 2, "r2", debut="2026-01-02T00:00:00")]
        for i, a in enumerate(appels):
            a.update({"id_appel": f"appel-{i}", "etat_apres": f"e{i}", "statut": "abouti"})
        (self.journal_dir / "2026-01-01.jsonl").write_text(
            "".join(json.dumps(a, ensure_ascii=False) + "\n" for a in appels), encoding="utf-8"
        )
        fichiers = DepotFichiers()
        for n, (sujet, quand) in enumerate((("S", "2026-01-01T10:00:00"), ("T", "2026-01-02T10:00:00")), 1):
            ref = fichiers.creer(self.harness.corpus, f"CAS-{n:04d}-k1-c1-abcdef")
            fichiers.ecrire_fiche(ref, f"---\nkata: k1\ncible: c1\nstatut: brut\ndate: {quand}\nscores:\n  tours: 1\n---\n\n# CAS-{n:04d}\n\nsession `s-{n}`\n")
            fichiers.ecrire_transcript(ref, f"## Tour 1\n\n**porteur** : p\n\n**kata** : r{n}\n")
            fichiers.ecrire_sortie(ref, f"# Dernière réponse — CAS-{n:04d}\n\nr{n}\n")
            fichiers.ecrire_materiau(ref, "coupe.md", "LA COUPE")
            fichiers.ecrire_etats(ref, [{"horodatage": quand, "etat": {"sujet": sujet, "kata": "k1", "champs": {"c1": "v"}}}])
            fichiers.ecrire_carre(ref, "# Carré de naturalité — tenu\n")
            fichiers.ajouter_jugement(ref, {"juge": "j", "version_coupe": "v1", "le": quand, "scores": [{"a": 1}]})
        fichiers.ecarter(self.harness.corpus, "s-9", "parasite", "2026-01-03T00:00:00")

    def tearDown(self):
        self.vider()
        self.base.fermer()
        self.journal.fermer()
        if self.avant is not None:
            os.environ["KOKAJI_BASE_URL"] = self.avant
        else:
            os.environ.pop("KOKAJI_BASE_URL", None)

    def vider(self):
        for table in ("ha", "ecart", "appel"):
            self.base._executer(f"DELETE FROM {table}")
        # Les comptes aussi : le Postgres d'essai est partagé avec la suite des comptes.
        for table in ("sessions", "harness_depot", "contributeurs", "identites_externes",
                      "invitations", "harness_acl", "utilisateurs"):
            self.base._executer(f"DELETE FROM {table}")

    def en_base(self):
        os.environ["KOKAJI_BASE_URL"] = URL_ESSAI

    def test_importer_une_instance_en_fichiers_puis_exporter_redonne_les_memes_octets(self):
        from kokaji.corpus.instance import exporter, importer

        bilan = importer(self.base, self.journal, self.racine / "harness", journal_fichiers=self.journal_dir)
        self.assertEqual((bilan.ha, bilan.ecartes, bilan.appels), (2, 1, 2))
        self.assertEqual(self.base.corpus_connus(), [(str(self.harness.corpus.resolve()), "h", "reel")])

        export = self.racine / "export"
        bilan = exporter(self.base, self.journal, export)
        self.assertEqual((bilan.ha, bilan.ecartes, bilan.appels), (2, 1, 2))
        self.assertEqual(bilan.corpus, ["h/reel"])

        # Octet pour octet : chaque CAS-XXXX/ et le journal.
        self.assertEqual(_octets(export / "ha" / "h" / "reel"), _octets(self.harness.corpus))
        self.assertEqual(lire_fichiers(export / "journal"), lire_fichiers(self.journal_dir))
        manifeste = json.loads((export / "manifeste.json").read_text(encoding="utf-8"))
        self.assertEqual(manifeste["corpus"], {"h/reel": str(self.harness.corpus.resolve())})

    def test_export_puis_import_sur_une_base_vide_redonne_le_meme_qg(self):
        from kokaji.corpus.instance import exporter, importer

        # Le QG en régime fichiers, sujet par sujet — la référence.
        attendu = {
            s: composer(self.harness, s, self.journal_dir).as_dict(self.harness)
            for s in sujets(self.harness, self.journal_dir)
        }
        self.assertEqual(sorted(attendu), ["S", "T"])

        importer(self.base, self.journal, self.racine / "harness", journal_fichiers=self.journal_dir)
        export = self.racine / "export"
        exporter(self.base, self.journal, export)
        self.vider()
        bilan = importer(self.base, self.journal, export)
        self.assertEqual(bilan.ha, 2)
        self.assertEqual(
            sorted(bilan.identifiants),
            sorted(f"{self.harness.corpus.resolve()}/CAS-{n:04d}-k1-c1-abcdef" for n in (1, 2)),
        )

        # Le QG en régime base, sans un seul fichier de ha ni de journal.
        for ref in DepotFichiers().tous(self.harness.corpus):
            DepotFichiers().supprimer(ref)
        self.en_base()
        obtenu = {
            s: composer(self.harness, s, self.racine / "journal-absent").as_dict(self.harness)
            for s in sujets(self.harness, self.racine / "journal-absent")
        }
        self.assertEqual(obtenu, attendu)

    def test_importer_vers_un_autre_dossier_de_harness_transpose_les_chemins(self):
        from kokaji.corpus.instance import exporter, importer

        importer(self.base, self.journal, self.racine / "harness")
        export = self.racine / "export"
        exporter(self.base, self.journal, export)
        self.vider()
        ailleurs = self.racine / "ailleurs"
        importer(self.base, self.journal, export, vers=ailleurs)
        self.assertEqual(
            self.base.corpus_connus(), [(str((ailleurs / "h" / "corpus").resolve()), "h", "reel")]
        )

    def test_promouvoir_en_regime_base_ecrit_le_ha_dans_le_clone_et_l_ajoute(self):
        from kokaji.corpus.instance import importer
        from kokaji.depot import initier

        importer(self.base, self.journal, self.racine / "harness")
        for ref in DepotFichiers().tous(self.harness.corpus):
            DepotFichiers().supprimer(ref)
        initier(self.harness_dir, "naissance")  # le clone, avec l'ignore des ha bruts (lot 0)
        self.assertEqual(DepotFichiers().tous(self.harness.corpus), [])

        self.en_base()
        code = main(["promouvoir", str(self.harness_dir), "CAS-0002"])
        self.assertEqual(code, 0)

        # Le ha est en base, annoté ; et sur le disque, dans le clone, suivi par git.
        ref = RefHa(self.harness.corpus, "CAS-0002-k1-c1-abcdef")
        self.assertEqual(self.base.entete(ref)["statut"], "annote")
        self.assertEqual(_octets(ref.chemin).keys(), {
            "fiche.md", "transcript.md", "sortie.md", "materiau/coupe.md",
            "etats.jsonl", "carre.md", "jugements.jsonl",
        })
        self.assertEqual(DepotFichiers().entete(ref)["statut"], "annote")
        suivis = subprocess.run(
            ["git", "-C", str(self.harness_dir), "ls-files", "--", "corpus"],
            capture_output=True, text=True, check=True,
        ).stdout
        self.assertIn("corpus/CAS-0002-k1-c1-abcdef/fiche.md", suivis)
        self.assertEqual(len([ref for ref in DepotFichiers().tous(self.harness.corpus)]), 1)

    def test_la_commande_instance_exporte_et_importe_comptes_compris(self):
        from kokaji.corpus.instance import importer

        # Les comptes de l'instance en fichiers : un SQLite, comme avant.
        sqlite = self.racine / "comptes.sqlite3"
        de = Comptes(sqlite)
        qui = de.creer_utilisateur("Un", "un@exemple.test", "un-mot-de-passe-assez-long", admin=True)
        de.enregistrer_harness("h", qui.id)
        de.fermer()

        importer(self.base, self.journal, self.racine / "harness", journal_fichiers=self.journal_dir)
        self.en_base()
        self.assertEqual(main(["instance", "importer", str(self.racine / "harness"), "--comptes", str(sqlite)]), 0)
        en_base = Comptes(URL_ESSAI)
        self.assertTrue(en_base.en_base)
        self.assertEqual(en_base.acl("h").proprietaire, qui.id)

        export = self.racine / "export-cli"
        self.assertEqual(main(["instance", "exporter", str(export)]), 0)
        self.assertTrue((export / "manifeste.json").is_file())
        self.assertTrue((export / "comptes.sqlite3").is_file())
        self.vider()
        self.assertEqual(main(["instance", "importer", str(export)]), 0)
        self.assertEqual(self.journal.compter(), 2)
        self.assertEqual(len(self.base.tous(self.harness.corpus)), 2)
        self.assertEqual(en_base.par_email("un@exemple.test").id, qui.id)
        self.assertEqual(en_base.acl("h").proprietaire, qui.id)
        en_base.fermer()

    def test_sans_base_la_commande_instance_refuse(self):
        self.assertEqual(main(["instance", "exporter", str(self.racine / "x")]), 1)


if __name__ == "__main__":
    unittest.main()
