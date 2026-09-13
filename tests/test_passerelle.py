"""L'autorisation de la passerelle, dérivée de la forge — NOTE-0002, NOTE-0010.

Harness purement structurels (§0). Aucun réseau : l'appel HTTP est injecté.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_hds import MINIMAL, _ecrire_harness

from kokaji.hds import charger
from kokaji.passerelle import (
    PasserelleInjoignable,
    autorisation_de_la_cle,
    ecart_d_autorisation,
    modeles_virtuels,
    publier_autorisation,
)


class Declares(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name)
        manifest = MINIMAL.replace(
            "cibles:\n  - id: c1",
            "cibles:\n  - id: c2\n    etat_structure: false\n    en_tete: H\n"
            "    packaging: dossier\n  - id: c1",
        )
        _ecrire_harness(racine, manifest)
        self.harness = charger(racine)

    def test_la_forme_nue_et_chaque_cible(self):
        """Une autorisation qui n'aurait que la forme nue refuserait le banc."""
        self.assertEqual(
            modeles_virtuels(self.harness), ("h/k1", "h/k1@c2", "h/k1@c1")
        )

    def test_sans_les_cibles_il_ne_reste_que_la_forme_nue(self):
        self.assertEqual(modeles_virtuels(self.harness, cibles=False), ("h/k1",))


class Ecarts(unittest.TestCase):
    def test_aucun_ecart_est_faux(self):
        """`if ecart:` doit se lire comme « il y a un décrochage »."""
        self.assertFalse(ecart_d_autorisation(("a", "b"), ("b", "a")))

    def test_un_modele_forge_mais_non_autorise(self):
        """La panne des trois fois : la coupe existe, la clé la refuse."""
        ecart = ecart_d_autorisation(("a", "b"), ("a",))
        self.assertEqual(ecart.manquants, ("b",))
        self.assertIn("forgé mais non autorisé : b", ecart.rendre())

    def test_un_modele_autorise_mais_plus_forge(self):
        """Une porte ouverte sur une coupe qui n'existe plus, que nul ne voit."""
        ecart = ecart_d_autorisation(("a",), ("a", "vieux"))
        self.assertEqual(ecart.surnumeraires, ("vieux",))
        self.assertIn("autorisé mais plus forgé : vieux", ecart.rendre())


class Passerelle(unittest.TestCase):
    """L'appel est injecté : le module se teste sans passerelle qui tourne."""

    def test_l_autorisation_se_lit(self):
        def appeler(url, admin, corps=None):
            self.assertIn("/key/info", url)
            return {"info": {"models": ["h/k1"]}}

        self.assertEqual(autorisation_de_la_cle("http://p", "m", "c", appeler), ("h/k1",))

    def test_une_cle_sans_liste_n_autorise_rien_de_connu(self):
        vu = autorisation_de_la_cle("http://p", "m", "c", lambda *a, **k: {"info": {}})
        self.assertEqual(vu, ())

    def test_publier_remplace_et_n_ajoute_pas(self):
        """Ajouter laisserait vivre les autorisations d'un kata retiré."""
        vus = {}

        def appeler(url, admin, corps=None):
            vus.update({"url": url, "corps": corps})
            return {}

        publier_autorisation("http://p/", "m", "c", ("h/k1", "h/k2"), appeler)
        self.assertEqual(vus["url"], "http://p/key/update")
        self.assertEqual(vus["corps"], {"key": "c", "models": ["h/k1", "h/k2"]})

    def test_une_passerelle_muette_se_dit(self):
        def appeler(url, admin, corps=None):
            raise PasserelleInjoignable("connexion refusée")

        with self.assertRaises(PasserelleInjoignable):
            autorisation_de_la_cle("http://p", "m", "c", appeler)


class LaConfigSeule(unittest.TestCase):
    """Au premier démarrage, la passerelle n'existe pas encore : `--config` sans
    `--url` écrit la liste et s'arrête, sans rien appeler. Le clone étranger
    (RFC-009 §7) a trouvé le contraire : un défaut sur `--url` rendait cette
    branche inatteignable, et le README échouait à sa cinquième ligne."""

    def test_config_sans_url_ecrit_et_n_appelle_personne(self):
        from kokaji.cli import main

        with tempfile.TemporaryDirectory() as tmp:
            racine = Path(tmp)
            _ecrire_harness(racine / "h", MINIMAL)
            moteurs = racine / "moteurs.yaml"
            moteurs.write_text("defaut:\n  model: m/x\n  api_key: os.environ/X\n", encoding="utf-8")
            config = racine / "config.yaml"
            config.write_text("litellm_settings: {}\n", encoding="utf-8")

            code = main([
                "passerelle", str(racine / "h"),
                "--config", str(config), "--moteurs", str(moteurs),
            ])

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()


class Configuration(unittest.TestCase):
    """La `model_list` engendrée — l'autre moitié de NOTE-0002."""

    def setUp(self):
        from kokaji.hds import charger

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        _ecrire_harness(self.racine / "h", MINIMAL)
        self.harness = {"h": charger(self.racine / "h")}
        self.moteurs = {"defaut": {"model": "un/moteur", "api_key": "os.environ/CLE"}}

    def test_chaque_modele_virtuel_a_son_entree(self):
        from kokaji.passerelle import entrees_de_la_passerelle

        entrees = entrees_de_la_passerelle(self.harness, self.moteurs, ("nu/x",))
        self.assertEqual(
            [e["model_name"] for e in entrees], ["h/k1", "h/k1@c1", "nu/x"]
        )
        self.assertEqual(entrees[0]["litellm_params"]["model"], "un/moteur")

    def test_un_moteur_par_modele_l_emporte(self):
        """Ce qui permet d'exposer deux incarnations et de les comparer (§5.6)."""
        from kokaji.passerelle import entrees_de_la_passerelle

        moteurs = dict(self.moteurs, par_modele={"h/k1@c1": {"model": "un/autre"}})
        entrees = entrees_de_la_passerelle(self.harness, moteurs)
        par_nom = {e["model_name"]: e["litellm_params"]["model"] for e in entrees}
        self.assertEqual(par_nom["h/k1"], "un/moteur")
        self.assertEqual(par_nom["h/k1@c1"], "un/autre")

    def test_la_pose_ne_touche_que_sa_part(self):
        """On engendre une part, pas un fichier : le reste est écrit à la main."""
        from kokaji.passerelle import (
            entrees_de_la_passerelle,
            modeles_de_la_configuration,
            poser_model_list,
            rendre_model_list,
        )

        config = self.racine / "config.yaml"
        config.write_text(
            "# un commentaire d'humain\nmodel_list:\n  - model_name: vieux\n"
            "    litellm_params: {model: x}\n\ngeneral_settings:\n  master_key: secret\n",
            encoding="utf-8",
        )
        entrees = entrees_de_la_passerelle(self.harness, self.moteurs)
        poser_model_list(config, rendre_model_list(entrees))

        texte = config.read_text(encoding="utf-8")
        self.assertIn("# un commentaire d'humain", texte)
        self.assertIn("master_key: secret", texte)
        self.assertNotIn("vieux", texte)
        self.assertEqual(modeles_de_la_configuration(config), ("h/k1", "h/k1@c1"))

    def test_reposer_deux_fois_ne_double_rien(self):
        """Sans marques, chaque passage empilerait un bloc de plus."""
        from kokaji.passerelle import (
            entrees_de_la_passerelle,
            modeles_de_la_configuration,
            poser_model_list,
            rendre_model_list,
        )

        config = self.racine / "config.yaml"
        config.write_text("general_settings:\n  master_key: secret\n", encoding="utf-8")
        bloc = rendre_model_list(entrees_de_la_passerelle(self.harness, self.moteurs))
        poser_model_list(config, bloc)
        une_fois = config.read_text(encoding="utf-8")
        poser_model_list(config, bloc)
        self.assertEqual(modeles_de_la_configuration(config), ("h/k1", "h/k1@c1"))
        self.assertIn("master_key: secret", config.read_text(encoding="utf-8"))
        # Au caractère près : la version d'avant ne comparait que les modèles,
        # et laissait passer une ligne vide ajoutée à chaque pose. Le fichier
        # grossissait sans que rien ne casse — donc sans que rien ne le dise.
        self.assertEqual(config.read_text(encoding="utf-8"), une_fois)


class PublierLesModeles(unittest.TestCase):
    """NOTE-0016 — forger ne suffit pas : la passerelle doit aussi router."""

    SERVIS: ClassVar[dict] = {"data": [{"model_name": "h/k1"}, {"model_name": "nu/x"}]}

    def faux(self, vus: list):
        def appeler(url, admin, corps=None):
            vus.append((url, corps))
            return self.SERVIS if url.endswith("/model/info") else {}

        return appeler

    def test_n_ajoute_que_ce_qui_manque(self):
        """Republier un modèle existant en créerait un double, et deux entrées
        du même nom rendraient le routage indécidable."""
        from kokaji.passerelle import publier_modeles

        vus = []
        ajoutes = publier_modeles(
            "http://p", "m",
            [{"model_name": "h/k1", "litellm_params": {"model": "x"}},
             {"model_name": "h/k2", "litellm_params": {"model": "x"}}],
            self.faux(vus),
        )
        self.assertEqual(ajoutes, ("h/k2",))
        self.assertEqual([u for u, _ in vus if u.endswith("/model/new")],
                         ["http://p/model/new"])

    def test_l_etat_lu_est_celui_du_moment(self):
        """`/model/info` dit l'état réel ; `config.yaml` ne dirait que celui du
        démarrage, et l'on republierait à chaque fois ce qui existe déjà."""
        from kokaji.passerelle import modeles_servis

        vus = []
        self.assertEqual(modeles_servis("http://p", "m", self.faux(vus)), ("h/k1", "nu/x"))
        self.assertTrue(vus[0][0].endswith("/model/info"))

    def test_rien_a_ajouter_n_appelle_rien(self):
        from kokaji.passerelle import publier_modeles

        vus = []
        ajoutes = publier_modeles(
            "http://p", "m", [{"model_name": "h/k1", "litellm_params": {}}], self.faux(vus)
        )
        self.assertEqual(ajoutes, ())
        self.assertEqual([u for u, _ in vus if u.endswith("/model/new")], [])
