"""Un harness, un dépôt — RFC-012, lot A : le dépôt local et son état.

Harness purement structurels (§0). git est appelé pour de vrai, sur des
dossiers jetables : c'est lui qu'on éprouve, pas une maquette.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_hds import MINIMAL, _ecrire_harness

from kokaji.depot import DepotIndisponible, est_depot, etat, initier


def _git(ou: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(ou), *args],
        capture_output=True, text=True, check=True,
    ).stdout.strip()


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name) / "h"
        _ecrire_harness(self.racine, MINIMAL)


class Initier(Bac):
    def test_un_dossier_devient_un_depot_avec_un_premier_commit(self):
        sha = initier(self.racine, "naissance : h")
        self.assertTrue(est_depot(self.racine))
        self.assertEqual(len(sha), 7)
        self.assertEqual(_git(self.racine, "log", "--format=%s"), "naissance : h")
        self.assertEqual(_git(self.racine, "status", "--porcelain"), "")

    def test_un_depot_ne_s_initie_pas_deux_fois(self):
        initier(self.racine, "naissance : h")
        with self.assertRaises(DepotIndisponible):
            initier(self.racine, "encore")

    def test_un_sous_dossier_d_un_depot_n_est_pas_un_depot(self):
        """`harness/atelier` dans le dépôt de l'instance : pas un dépôt à lui — D12.1."""
        initier(self.racine.parent, "le dépôt du dessus")
        self.assertFalse(est_depot(self.racine))
        # Et il peut le devenir : c'est le geste de la migration.
        initier(self.racine, "naissance : h")
        self.assertTrue(est_depot(self.racine))


class LEtat(Bac):
    def test_sans_depot_l_etat_le_dit(self):
        lu = etat(self.racine)
        self.assertFalse(lu.est_depot)
        self.assertEqual(lu.mot, "sans dépôt")

    def test_un_depot_propre_non_enregistre(self):
        initier(self.racine, "naissance : h")
        lu = etat(self.racine)
        self.assertTrue(lu.est_depot)
        self.assertTrue(lu.propre)
        self.assertEqual(lu.dernier_message, "naissance : h")
        self.assertTrue(lu.dernier_le.startswith("20"))
        self.assertEqual(lu.mot, "non enregistré")

    def test_des_modifications_non_scellees_se_disent(self):
        initier(self.racine, "naissance : h")
        (self.racine / "template.md").write_text("{{ role }} !", encoding="utf-8")
        self.assertEqual(etat(self.racine).mot, "modifications non scellées")

    def test_l_avance_se_compte_depuis_la_reference(self):
        sha0 = initier(self.racine, "naissance : h")
        self.assertEqual(etat(self.racine, sha0).mot, "à jour")
        (self.racine / "template.md").write_text("{{ role }} !", encoding="utf-8")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "scellement")
        lu = etat(self.racine, sha0)
        self.assertEqual(lu.avance, 1)
        self.assertEqual(lu.mot, "en avance de 1")

    def test_une_reference_inconnue_ne_se_devine_pas(self):
        """Le dépôt nu a avancé sans qu'on ait tiré : on ne dit pas « en retard de N »."""
        initier(self.racine, "naissance : h")
        lu = etat(self.racine, "0000000000000000000000000000000000000000")
        self.assertIsNone(lu.avance)
        self.assertFalse(lu.reference_connue)
        self.assertEqual(lu.mot, "non enregistré")



class LeDepotNu(Bac):
    """RFC-012 D12.2, D12.3 — enregistrer, pousser, tirer ; jamais de fusion."""

    def setUp(self):
        super().setUp()
        from kokaji.depot import initier

        initier(self.racine, "naissance : h")
        self.depots = Path(self._tmp.name) / "depots"
        self.depots.mkdir()

    def test_un_chemin_hors_du_dossier_des_depots_est_refuse(self):
        """Sabotage 2 : le service n'écrit ni ne clone n'importe où."""
        from kokaji.depot import DepotRefuse, chemin_admis

        self.assertEqual(chemin_admis("h.git", self.depots), self.depots / "h.git")
        with self.assertRaises(DepotRefuse):
            chemin_admis("../ailleurs/h.git", self.depots)
        with self.assertRaises(DepotRefuse):
            chemin_admis("/tmp/h.git", self.depots)
        with self.assertRaises(DepotRefuse):
            chemin_admis("h.git", None)

    def test_lier_cree_le_depot_nu_et_y_pousse_l_historique(self):
        from kokaji.depot import est_depot_nu, etat, lier, reference

        sha = lier(self.racine, self.depots / "h.git")
        self.assertTrue(est_depot_nu(self.depots / "h.git"))
        self.assertEqual(reference(self.depots / "h.git", "main"), sha)
        self.assertEqual(etat(self.racine, sha).mot, "à jour")

    def test_pousser_apres_un_commit_avance_le_depot_nu(self):
        from kokaji.depot import lier, pousser, reference

        lier(self.racine, self.depots / "h.git")
        (self.racine / "template.md").write_text("{{ role }} !", encoding="utf-8")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "scellement")
        sha = pousser(self.racine)
        self.assertEqual(reference(self.depots / "h.git", "main"), sha)

    def test_tirer_avec_des_modifications_non_scellees_refuse_et_ne_touche_rien(self):
        """Sabotage 3."""
        from kokaji.depot import DepotRefuse, lier, tirer

        lier(self.racine, self.depots / "h.git")
        (self.racine / "template.md").write_text("{{ role }} en cours", encoding="utf-8")
        with self.assertRaises(DepotRefuse) as vu:
            tirer(self.racine)
        self.assertIn("non scellées", str(vu.exception))
        self.assertEqual((self.racine / "template.md").read_text(encoding="utf-8"), "{{ role }} en cours")

    def _autre_clone(self):
        """Un second clone du même dépôt nu — un poste de travail, ailleurs."""
        from kokaji.depot import cloner

        autre = cloner(self.depots / "h.git", Path(self._tmp.name) / "poste")
        (autre / "registre.yaml").write_text("kata: {x: X}", encoding="utf-8")
        _git(autre, "add", "-A")
        _git(autre, "-c", "user.name=P", "-c", "user.email=p@e.test", "commit", "-q", "-m", "depuis le poste")
        _git(autre, "push", "-q", "origin", "HEAD:main")
        return autre

    def test_tirer_en_avance_rapide_prend_ce_qui_a_ete_pousse_d_ailleurs(self):
        from kokaji.depot import lier, tirer

        lier(self.racine, self.depots / "h.git")
        self._autre_clone()
        sha = tirer(self.racine)
        self.assertEqual((self.racine / "registre.yaml").read_text(encoding="utf-8"), "kata: {x: X}")
        self.assertEqual(_git(self.racine, "rev-parse", "--short", "HEAD"), sha)

    def test_une_branche_divergee_refuse_de_tirer_et_de_pousser_jamais_de_fusion(self):
        """Sabotage 4 : l'état dit divergé, rien n'est fusionné."""
        from kokaji.depot import DepotRefuse, lier, pousser, tirer

        lier(self.racine, self.depots / "h.git")
        self._autre_clone()
        (self.racine / "template.md").write_text("{{ role }} ici", encoding="utf-8")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "ici")
        with self.assertRaises(DepotRefuse) as t:
            tirer(self.racine)
        self.assertIn("divergé", str(t.exception))
        with self.assertRaises(DepotRefuse) as p:
            pousser(self.racine)
        self.assertIn("divergé", str(p.exception))
        self.assertEqual((self.racine / "template.md").read_text(encoding="utf-8"), "{{ role }} ici")

    def test_cloner_un_depot_nu_donne_un_dossier_lisible(self):
        from kokaji.depot import DepotRefuse, cloner, est_depot, lier
        from kokaji.hds import charger

        lier(self.racine, self.depots / "h.git")
        vers = cloner(self.depots / "h.git", Path(self._tmp.name) / "clone")
        self.assertTrue(est_depot(vers))
        self.assertEqual(charger(vers).id, "h")
        with self.assertRaises(DepotRefuse):
            cloner(self.depots / "absent.git", Path(self._tmp.name) / "rien")
        self.assertFalse((Path(self._tmp.name) / "rien").exists())

    def test_sans_reference_donnee_l_etat_lit_celle_du_clone(self):
        """La ligne de commande ne lit pas le magasin : « à jour » vient d'`origin`."""
        from kokaji.depot import etat, lier

        self.assertEqual(etat(self.racine).mot, "non enregistré")
        lier(self.racine, self.depots / "h.git")
        self.assertEqual(etat(self.racine).mot, "à jour")
        (self.racine / "template.md").write_text("{{ role }} !", encoding="utf-8")
        _git(self.racine, "add", "-A")
        _git(self.racine, "-c", "user.name=T", "-c", "user.email=t@e.test", "commit", "-q", "-m", "scellement")
        self.assertEqual(etat(self.racine).mot, "en avance de 1")

    def test_sans_depot_nu_pousser_et_tirer_le_disent(self):
        from kokaji.depot import DepotRefuse, pousser, tirer

        with self.assertRaises(DepotRefuse):
            pousser(self.racine)
        with self.assertRaises(DepotRefuse):
            tirer(self.racine)


class LaDonneeVivanteHorsDuDepot(Bac):
    """RFC-014 D14.5, lot 0 — un ha brut n'entre pas au dépôt ; promu, il y entre de force."""

    def test_un_harness_nait_avec_ses_ignores(self):
        from kokaji.depot import IGNORES_DU_HARNESS, initier

        initier(self.racine, "naissance : h")
        self.assertEqual((self.racine / ".gitignore").read_text(encoding="utf-8"), IGNORES_DU_HARNESS)
        self.assertIn(".gitignore", _git(self.racine, "ls-files"))

    def test_un_ha_brut_laisse_le_clone_propre_et_la_promotion_l_ajoute(self):
        """Sabotage 1 de la RFC-014 : une séance de plus, `git status` vide."""
        from kokaji.cli import main
        from kokaji.depot import initier

        initier(self.racine, "naissance : h")
        ha = self.racine / "corpus" / "CAS-0001-essai"
        ha.mkdir(parents=True)
        (ha / "fiche.md").write_text("---\nharness: h\nstatut: brut\n---\n", encoding="utf-8")
        (self.racine / "corpus" / ".ecartes.jsonl").write_text("{}\n", encoding="utf-8")
        self.assertEqual(_git(self.racine, "status", "--porcelain"), "")

        self.assertEqual(main(["promouvoir", str(self.racine), "CAS-0001-essai"]), 0)
        self.assertIn("statut: annote", (ha / "fiche.md").read_text(encoding="utf-8"))
        self.assertIn("corpus/CAS-0001-essai/fiche.md", _git(self.racine, "status", "--porcelain"))

    def test_un_ignore_existant_n_est_pas_ecrase(self):
        from kokaji.depot import initier

        (self.racine / ".gitignore").write_text("le mien\n", encoding="utf-8")
        initier(self.racine, "naissance : h")
        self.assertEqual((self.racine / ".gitignore").read_text(encoding="utf-8"), "le mien\n")


if __name__ == "__main__":
    unittest.main()
