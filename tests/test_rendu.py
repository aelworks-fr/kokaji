"""Ce qu'un navigateur affiche vraiment — NOTE-0008.

Les mesures vivent dans `kokaji/rendu.py`, pas ici : elles ont deux appelants,
ce test et la vigie. Ce fichier sert la page pour de vrai et **exige que chaque
mesure tienne** ; la vigie reprend les mêmes en continu.

Il se saute proprement si aucun navigateur n'est disponible, et le dit — un
test qui manque doit s'entendre, pas disparaître.

    pip install playwright && playwright install chromium
    sudo playwright install-deps       # les bibliothèques système

`./dojo/verif/rendu.sh` est la variante en conteneur, pour un poste où l'on ne
veut — ou ne peut — rien installer.
"""

from __future__ import annotations

import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from test_hds import MINIMAL, _ecrire_harness

from kokaji.hds import charger
from kokaji.middleware.service import creer
from kokaji.rendu import navigateur_indisponible, regarder

MOTIF = navigateur_indisponible()


def _port_libre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@unittest.skipIf(MOTIF, f"aucun navigateur : {MOTIF}")
class Rendu(unittest.TestCase):
    """La page servie pour de vrai, et regardée par un navigateur."""

    @classmethod
    def setUpClass(cls):
        import uvicorn

        cls._tmp = tempfile.TemporaryDirectory()
        racine = Path(cls._tmp.name)
        _ecrire_harness(racine / "h", MINIMAL)
        (racine / "journal").mkdir()

        port = _port_libre()
        cls.url = f"http://127.0.0.1:{port}/"
        cls._serveur = uvicorn.Server(
            uvicorn.Config(
                creer(charger(racine / "h"), racine / "journal"),
                host="127.0.0.1",
                port=port,
                log_level="error",
            )
        )
        cls._fil = threading.Thread(target=cls._serveur.run, daemon=True)
        cls._fil.start()
        for _ in range(200):
            if cls._serveur.started:
                break
            threading.Event().wait(0.05)
        cls.verdicts = regarder(cls.url)

    @classmethod
    def tearDownClass(cls):
        cls._serveur.should_exit = True
        cls._fil.join(timeout=5)
        cls._tmp.cleanup()

    def test_chaque_mesure_tient(self):
        """Une mesure qui ne tient pas nomme ce qu'elle a vu, pas seulement qu'elle a vu."""
        for verdict in self.verdicts:
            with self.subTest(mesure=verdict.quoi):
                self.assertTrue(verdict.tient, f"{verdict.quoi} :\n{verdict.detail}")

    def test_les_mesures_couvrent_les_trois_largeurs_et_le_design(self):
        """Un jeu de mesures qui rétrécirait sans bruit ne protégerait plus rien."""
        quoi = [v.quoi for v in self.verdicts]
        self.assertTrue(any("360 px" in q for q in quoi), quoi)
        self.assertTrue(any("1280 px" in q for q in quoi), quoi)
        # L'ultra-large est venu après : le produit y tenait dans le tiers
        # gauche, et sous 1180 px le défaut n'existe pas. Une mesure ne voit
        # que les tailles qu'on lui donne.
        self.assertTrue(any("2560 px" in q for q in quoi), quoi)

    def test_chaque_module_est_regarde_sur_grand_ecran(self):
        """Le module d'accueil était centré depuis toujours : le mesurer seul
        serait passé au vert sans rien regarder — c'est « Découvrir » qui
        était collé au flanc."""
        quoi = [v.quoi for v in self.verdicts]
        for module in ("decouvrir", "profil", "vigie", "design"):
            self.assertIn(f"la colonne de {module} est centrée (2560 px)", quoi)
        # Centrer ne suffisait pas : il restait une colonne de bureau posée au
        # milieu d'un mur. La prose garde sa mesure, les surfaces tabulaires
        # s'élargissent — c'est celles-là qu'on vérifie.
        self.assertIn("le design profite de la place (2560 px)", quoi)
        # L'ultra-large est la troisième, ajoutée après coup : le produit tenait
        # dans le tiers gauche d'un 3440 px et aucune des deux autres ne pouvait
        # le voir — rien ne change sous 1180 px.
        self.assertTrue(any("2560 px" in q for q in quoi), quoi)
        self.assertTrue(any("centrée" in q for q in quoi), quoi)
        self.assertTrue(any("design" in q for q in quoi), quoi)
        self.assertGreaterEqual(len(self.verdicts), 10, quoi)

    def test_le_palier_de_l_audit_et_ses_deux_verdicts_sont_regardes(self):
        """K-01 et K-02 : le trou entre 800 et 1 024 px, le CTA dans l'écran,
        la modale devant tout — la vigie nourrie plutôt que contournée."""
        quoi = [v.quoi for v in self.verdicts]
        self.assertIn("la page tient dans l'écran (800 px)", quoi)
        for largeur in ("360", "800", "1280", "2560"):
            self.assertIn(f"le CTA principal est dans le viewport ({largeur} px)", quoi)
            self.assertIn(f"rien ne se superpose à une modale ouverte ({largeur} px)", quoi)

    def test_les_contrastes_et_les_tailles_sont_mesures(self):
        """K-14 : la vigie mesure ce que l'audit a mesuré à la main — partout, à chaque largeur."""
        quoi = [v.quoi for v in self.verdicts]
        for largeur in ("360", "800", "1280", "2560"):
            self.assertIn(f"les textes tiennent le contraste ({largeur} px)", quoi)
            self.assertIn(f"aucun texte sous 12 px ({largeur} px)", quoi)
        for module in ("decouvrir", "profil", "vigie", "design"):
            self.assertIn(f"les textes de {module} tiennent le contraste (360 px)", quoi)

    def test_chaque_axe_du_design_est_regarde(self):
        """Le module s'ouvre sur le premier axe : sans clic, les trois autres —
        dont les coupes, deux colonnes et un gabarit entier — resteraient
        invisibles à la mesure."""
        quoi = [v.quoi for v in self.verdicts]
        for axe in ("partition", "contrats", "trempe", "coupes"):
            self.assertIn(f"rien ne se chevauche dans l'axe {axe} (360 px)", quoi)
            self.assertIn(f"l'axe {axe} tient dans l'écran (360 px)", quoi)


class SansNavigateur(unittest.TestCase):
    def test_l_absence_de_navigateur_ne_tient_pas(self):
        """Ne pas pouvoir regarder n'est pas « rien à signaler » — NOTE-0003."""
        from kokaji import rendu

        original = rendu.navigateur_indisponible
        rendu.navigateur_indisponible = lambda: "pas de navigateur ici"
        self.addCleanup(setattr, rendu, "navigateur_indisponible", original)

        verdicts = rendu.regarder("http://127.0.0.1:1/")
        self.assertEqual(len(verdicts), 1)
        self.assertFalse(verdicts[0].tient)
        self.assertIn("aucun navigateur", verdicts[0].detail)


if __name__ == "__main__":
    unittest.main()
