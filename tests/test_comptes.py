"""Le modèle d'autorat et ses invariants — RFC-004 §2 et §3.

Harness purement structurels (§0) : aucun nom de domaine ici.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.comptes import (
    ADMINISTRATION,
    ANONYME,
    COMPTE,
    CONTRIBUTEUR,
    ETRANGER,
    GESTES,
    GESTES_DE_SERVICE,
    PROPRIETAIRE,
    ROLES,
    AccesRefuse,
    Acl,
    AclInvalide,
    Comptes,
    IdentiteInconnue,
    exiger,
    exiger_au_service,
    peut,
    peut_au_service,
)

MOT_DE_PASSE = "un-mot-de-passe-assez-long"


class Invariants(unittest.TestCase):
    """§2.2 — « exactement un propriétaire, toujours »."""

    def test_une_acl_sans_proprietaire_est_impossible(self):
        with self.assertRaises(AclInvalide):
            Acl("h", "")

    def test_le_proprietaire_n_est_jamais_aussi_contributeur(self):
        with self.assertRaises(AclInvalide):
            Acl("h", "u1", ("u1",))

    def test_l_ajouter_comme_contributeur_ne_fait_rien(self):
        acl = Acl("h", "u1").avec("u1")
        self.assertEqual(acl.contributeurs, ())
        self.assertEqual(acl.role("u1"), PROPRIETAIRE)

    def test_retirer_le_proprietaire_est_refuse(self):
        with self.assertRaises(AclInvalide):
            Acl("h", "u1", ("u2",)).sans("u1")

    def test_ajouter_deux_fois_reste_idempotent(self):
        acl = Acl("h", "u1").avec("u2").avec("u2")
        self.assertEqual(acl.contributeurs, ("u2",))

    def test_les_roles_sont_ceux_du_rfc(self):
        acl = Acl("h", "u1", ("u2",))
        self.assertEqual(acl.role("u1"), PROPRIETAIRE)
        self.assertEqual(acl.role("u2"), CONTRIBUTEUR)
        self.assertEqual(acl.role("u3"), ETRANGER)


class Transfert(unittest.TestCase):
    """§2.2 — « geste explicite du propriétaire »."""

    def test_l_ancien_proprietaire_devient_contributeur(self):
        acl = Acl("h", "u1", ("u2",)).transferee_a("u2")
        self.assertEqual(acl.proprietaire, "u2")
        self.assertEqual(acl.contributeurs, ("u1",))

    def test_le_retrait_de_l_ancien_est_explicite(self):
        acl = Acl("h", "u1", ("u2",)).transferee_a("u2", garder_ancien=False)
        self.assertEqual(acl.contributeurs, ())

    def test_il_reste_toujours_un_et_un_seul_proprietaire(self):
        acl = Acl("h", "u1", ("u2", "u3")).transferee_a("u3")
        self.assertEqual(acl.proprietaire, "u3")
        self.assertNotIn("u3", acl.contributeurs)
        self.assertEqual(sorted(acl.contributeurs), ["u1", "u2"])


class Droits(unittest.TestCase):
    """§3 — la matrice, y compris ce qu'elle ouvre volontairement."""

    def test_le_contributeur_scelle_une_version(self):
        """Décision scellée : co-auteurs pleins, traçabilité plutôt que goulot."""
        self.assertTrue(peut("sceller", CONTRIBUTEUR))
        self.assertTrue(peut("editer", CONTRIBUTEUR))

    def test_les_trois_gestes_de_possession_restent_au_proprietaire(self):
        for geste in ("gerer_membres", "transferer", "supprimer"):
            self.assertTrue(peut(geste, PROPRIETAIRE), geste)
            self.assertFalse(peut(geste, CONTRIBUTEUR), geste)

    def test_un_etranger_ne_peut_rien(self):
        self.assertFalse(any(peut(g, ETRANGER) for g in ("lire", "editer", "forger", "sceller")))

    def test_un_geste_inconnu_est_refuse_par_defaut(self):
        """Ajouter un verbe sans l'inscrire au tableau le ferme, ne l'ouvre pas."""
        self.assertFalse(peut("facturer", PROPRIETAIRE))

    def test_exiger_leve_et_nomme_le_geste_sans_decrire_le_systeme(self):
        with self.assertRaises(AccesRefuse) as pris:
            exiger("gerer_membres", CONTRIBUTEUR, "h")
        self.assertIn("gerer_membres", str(pris.exception))
        self.assertNotIn("proprietaire", str(pris.exception))


class GestesDeService(unittest.TestCase):
    """RFC-006 §2 — `creer` est le premier geste sans objet.

    Toute la matrice du RFC-004 demande « quel est ton rôle *sur ce harness* ».
    Créer demande « as-tu le droit d'en faire un », ce qui ne se répond pas par
    un rôle puisqu'il n'y a pas encore de harness. Les deux tables ne se
    connaissent donc pas, et c'est ce qui empêche un geste d'emprunter le droit
    d'un autre.
    """

    def test_tout_compte_peut_creer(self):
        self.assertTrue(peut_au_service("creer", COMPTE))
        self.assertTrue(peut_au_service("creer", ADMINISTRATION))

    def test_un_anonyme_ne_peut_rien(self):
        for geste in GESTES_DE_SERVICE:
            with self.subTest(geste=geste):
                self.assertFalse(peut_au_service(geste, ANONYME))

    def test_administrer_ne_se_donne_pas_a_un_compte(self):
        self.assertFalse(peut_au_service("administrer", COMPTE))

    def test_un_role_de_harness_n_ouvre_aucun_geste_de_service(self):
        """Le sabotage central : être propriétaire n'autorise pas à créer."""
        for role in ROLES:
            with self.subTest(role=role):
                self.assertFalse(peut_au_service("creer", role))

    def test_une_qualite_n_ouvre_aucun_geste_de_harness(self):
        """Et l'inverse : être administrateur ne donne aucun droit sur une œuvre."""
        for geste in GESTES:
            with self.subTest(geste=geste):
                self.assertFalse(peut(geste, ADMINISTRATION))

    def test_un_geste_inconnu_est_refuse_par_defaut(self):
        """Comme `peut` : ajouter un verbe sans l'inscrire le ferme."""
        self.assertFalse(peut_au_service("supprimer_tout", ADMINISTRATION))

    def test_les_gestes_des_deux_tables_ne_se_recouvrent_pas(self):
        """Un même nom dans les deux tables rendrait le refus ambigu."""
        self.assertEqual(set(GESTES) & set(GESTES_DE_SERVICE), set())

    def test_exiger_nomme_le_geste_sans_decrire_le_systeme(self):
        with self.assertRaises(AccesRefuse) as capture:
            exiger_au_service("creer", ANONYME)
        self.assertEqual(str(capture.exception), "geste refusé : creer")


class Magasin(unittest.TestCase):
    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.un = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.deux = self.comptes.creer_utilisateur("Deux", "deux@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("h", self.un.id)

    def test_l_id_est_un_uuid_stable_independant_du_fournisseur(self):
        """§2.1 — prêt pour OAuth sans le coder."""
        self.assertEqual(len(self.un.id), 36)
        self.assertEqual(self.comptes.utilisateur(self.un.id).id, self.un.id)

    def test_un_email_ne_sert_qu_une_fois(self):
        with self.assertRaises(AclInvalide):
            self.comptes.creer_utilisateur("Bis", "UN@exemple.test", MOT_DE_PASSE)

    def test_le_mot_de_passe_n_est_jamais_stocke_en_clair(self):
        lignes = self.comptes._db.execute("SELECT empreinte FROM utilisateurs").fetchall()
        for ligne in lignes:
            self.assertNotIn(MOT_DE_PASSE, ligne["empreinte"])
            self.assertTrue(ligne["empreinte"].startswith("$argon2"))

    def test_un_mauvais_mot_de_passe_est_refuse(self):
        with self.assertRaises(IdentiteInconnue):
            self.comptes.ouvrir_session("un@exemple.test", "faux")

    def test_un_email_inconnu_donne_le_meme_refus(self):
        """Distinguer les deux dirait à un inconnu qui possède un compte ici."""
        with self.assertRaises(IdentiteInconnue) as absent:
            self.comptes.ouvrir_session("personne@exemple.test", MOT_DE_PASSE)
        with self.assertRaises(IdentiteInconnue) as faux:
            self.comptes.ouvrir_session("un@exemple.test", "faux")
        self.assertEqual(str(absent.exception), str(faux.exception))

    def test_une_session_fermee_ne_vaut_plus(self):
        jeton = self.comptes.ouvrir_session("un@exemple.test", MOT_DE_PASSE)
        self.assertEqual(self.comptes.session(jeton).id, self.un.id)
        self.comptes.fermer_session(jeton)
        with self.assertRaises(IdentiteInconnue):
            self.comptes.session(jeton)

    def test_deux_proprietaires_sont_inexprimables(self):
        """§8.3 — impossible par construction, pas refusé par un test."""
        with self.assertRaises(AclInvalide):
            self.comptes.enregistrer_harness("h", self.deux.id)

    def test_la_table_des_identites_externes_existe_et_reste_vide(self):
        """§2.1 — la place est tenue, rien n'y est écrit en v1."""
        compte = self.comptes._db.execute("SELECT COUNT(*) c FROM identites_externes").fetchone()
        self.assertEqual(compte["c"], 0)

    def test_le_profil_liste_les_harness_avec_leur_role(self):
        self.comptes.ajouter_contributeur("h", self.deux.id)
        self.comptes.enregistrer_harness("autre", self.deux.id)
        self.assertEqual(
            self.comptes.harness_de(self.deux.id),
            [("autre", "proprietaire"), ("h", "contributeur")],
        )

    def test_le_transfert_traverse_le_magasin(self):
        self.comptes.ajouter_contributeur("h", self.deux.id)
        acl = self.comptes.transferer("h", self.deux.id)
        self.assertEqual(acl.proprietaire, self.deux.id)
        self.assertEqual(self.comptes.role("h", self.un.id), CONTRIBUTEUR)

    def test_un_harness_sans_acl_ne_donne_aucun_role(self):
        self.assertEqual(self.comptes.role("jamais-enregistre", self.un.id), ETRANGER)


class Invitations(unittest.TestCase):
    """Une porte nominative, à usage unique et datée."""

    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.hote = self.comptes.creer_utilisateur(
            "Hôte", "hote@exemple.test", MOT_DE_PASSE, admin=True
        )

    def test_l_invitation_ne_cree_aucun_compte(self):
        """Un mot de passe qu'on envoie est un mot de passe partagé."""
        self.comptes.inviter("invite@exemple.test", par=self.hote.id)
        self.assertIsNone(self.comptes.par_email("invite@exemple.test"))

    def test_la_consommer_cree_le_compte_de_l_invite(self):
        jeton = self.comptes.inviter("invite@exemple.test", par=self.hote.id)
        invite = self.comptes.consommer(jeton, "Invité", "un-autre-mot-de-passe")

        self.assertEqual(invite.email, "invite@exemple.test")
        # Un invité n'hérite pas de l'administration de celui qui l'a invité.
        self.assertFalse(self.comptes.est_admin(invite.id))
        # Et son mot de passe est le sien : il ouvre une session avec.
        self.assertTrue(
            self.comptes.ouvrir_session("invite@exemple.test", "un-autre-mot-de-passe")
        )

    def test_un_jeton_ne_sert_qu_une_fois(self):
        jeton = self.comptes.inviter("invite@exemple.test", par=self.hote.id)
        self.comptes.consommer(jeton, "Invité", "un-autre-mot-de-passe")
        with self.assertRaises(IdentiteInconnue):
            self.comptes.consommer(jeton, "Bis", "encore-un-mot-de-passe")

    def test_une_invitation_perimee_ne_vaut_plus(self):
        from datetime import timedelta

        jeton = self.comptes.inviter(
            "invite@exemple.test", par=self.hote.id, duree=timedelta(seconds=-1)
        )
        with self.assertRaises(IdentiteInconnue):
            self.comptes.invitation(jeton)

    def test_revoquer_ferme_la_porte(self):
        jeton = self.comptes.inviter("invite@exemple.test", par=self.hote.id)
        self.comptes.revoquer(jeton)
        with self.assertRaises(IdentiteInconnue):
            self.comptes.invitation(jeton)

    def test_on_n_invite_pas_un_email_deja_pris(self):
        with self.assertRaises(AclInvalide):
            self.comptes.inviter("hote@exemple.test", par=self.hote.id)

    def test_un_jeton_inconnu_est_refuse_comme_un_perime(self):
        """Une porte fermée ne renseigne pas sur ce qu'il y a derrière."""
        with self.assertRaises(IdentiteInconnue):
            self.comptes.invitation("jeton-invente")

    def test_la_liste_dit_ce_qui_est_encore_vivant(self):
        vivant = self.comptes.inviter("un@exemple.test", par=self.hote.id)
        mort = self.comptes.inviter("deux@exemple.test", par=self.hote.id)
        self.comptes.revoquer(mort)
        etats = {i["email"]: i["vivante"] for i in self.comptes.invitations()}

        self.assertTrue(etats["un@exemple.test"])
        self.assertFalse(etats["deux@exemple.test"])
        self.assertTrue(vivant)


class Administration(unittest.TestCase):
    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)

    def test_un_compte_n_est_pas_admin_par_defaut(self):
        u = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.assertFalse(self.comptes.est_admin(u.id))

    def test_promouvoir_et_retirer_l_administration(self):
        u = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.comptes.promouvoir(u.id)
        self.assertTrue(self.comptes.est_admin(u.id))
        self.comptes.promouvoir(u.id, admin=False)
        self.assertFalse(self.comptes.est_admin(u.id))

    def test_la_liste_des_comptes_ne_sort_aucun_secret(self):
        self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        for compte in self.comptes.utilisateurs():
            self.assertEqual(set(compte), {"id", "nom", "email", "cree_le", "admin"})

    def test_changer_son_mot_de_passe(self):
        u = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.comptes.changer_mot_de_passe(u.id, "un-mot-de-passe-tout-neuf")

        with self.assertRaises(IdentiteInconnue):
            self.comptes.ouvrir_session("un@exemple.test", MOT_DE_PASSE)
        self.assertTrue(self.comptes.ouvrir_session("un@exemple.test", "un-mot-de-passe-tout-neuf"))

    def test_un_mot_de_passe_trop_court_est_refuse(self):
        u = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        with self.assertRaises(AclInvalide):
            self.comptes.changer_mot_de_passe(u.id, "court")


class Portail(unittest.TestCase):
    """Inscrire au portail — un fichier cassé enferme tout le monde dehors."""

    def setUp(self):
        import tempfile

        from kokaji.comptes import inscrire

        self.inscrire = inscrire
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.fichier = Path(self._tmp.name) / "users.yml"
        self.fichier.write_text(
            "users:\n  forgeron:\n    disabled: false\n    displayname: Forgeron\n"
            "    password: '$argon2id$v=19$m=65536,t=3,p=4$deja'\n"
            "    email: forgeron@exemple.test\n    groups: [admins]\n",
            encoding="utf-8",
        )

    def lire(self) -> dict:
        import yaml

        return yaml.safe_load(self.fichier.read_text(encoding="utf-8"))

    def test_l_email_est_l_identifiant(self):
        """Un seul mot à retenir, le même partout."""
        rendu = self.inscrire(
            self.fichier, email="Neuf@Exemple.test", nom="Neuf", mot_de_passe=MOT_DE_PASSE
        )
        self.assertEqual(rendu, "neuf@exemple.test")
        self.assertIn("neuf@exemple.test", self.lire()["users"])

    def test_le_mot_de_passe_est_hache_en_argon2(self):
        self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        entree = self.lire()["users"]["n@exemple.test"]

        self.assertTrue(entree["password"].startswith("$argon2"))
        self.assertNotIn(MOT_DE_PASSE, entree["password"])

    def test_l_existant_est_conserve(self):
        self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        self.assertIn("forgeron", self.lire()["users"])

    def test_on_n_ecrase_jamais_une_entree(self):
        """Inscrire quelqu'un de déjà présent serait réécrire son mot de passe."""
        from kokaji.comptes import PortailIndisponible

        self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        with self.assertRaises(PortailIndisponible):
            self.inscrire(self.fichier, email="N@exemple.test", nom="N", mot_de_passe="autre-chose")

    def test_un_fichier_absent_est_refuse_sans_le_creer(self):
        from kokaji.comptes import PortailIndisponible

        ailleurs = Path(self._tmp.name) / "nulle-part.yml"
        with self.assertRaises(PortailIndisponible):
            self.inscrire(ailleurs, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        self.assertFalse(ailleurs.exists())

    def test_un_fichier_illisible_ne_devient_pas_valide(self):
        from kokaji.comptes import PortailIndisponible

        self.fichier.write_text("users: [pas une section]\n", encoding="utf-8")
        with self.assertRaises(PortailIndisponible):
            self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        self.assertEqual(self.fichier.read_text(encoding="utf-8"), "users: [pas une section]\n")

    def test_l_en_tete_du_fichier_survit_a_une_inscription(self):
        """Ce fichier dit ce qu'il est ; l'inscrire ne doit pas l'effacer.

        `yaml.safe_dump` emportait ses commentaires à chaque inscription — même
        cause que le manifest de harness, trouvée le même jour, à la première
        inscription réelle. Un fichier d'infrastructure est une source lui aussi.
        """
        self.fichier.write_text(
            "# Les comptes du portail. Un fichier, pas une base.\n"
            + self.fichier.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        self.assertIn("# Les comptes du portail", self.fichier.read_text(encoding="utf-8"))

    def test_l_inscription_est_bien_ecrite(self):
        """Préserver ne doit pas vouloir dire ne rien écrire."""
        self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        texte = self.fichier.read_text(encoding="utf-8")
        self.assertIn("n@exemple.test", texte)
        self.assertIn("praticiens", texte)

    def test_aucun_brouillon_ne_reste_a_cote(self):
        self.inscrire(self.fichier, email="n@exemple.test", nom="N", mot_de_passe=MOT_DE_PASSE)
        self.assertEqual([f.name for f in Path(self._tmp.name).iterdir()], ["users.yml"])


class HarnessCourant(unittest.TestCase):
    """RFC-005 §2.2 — le harness que je pratique est une propriété de moi."""

    def setUp(self):
        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.un = self.comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
        self.deux = self.comptes.creer_utilisateur("Deux", "deux@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("h", self.un.id)

    def test_le_seul_harness_accessible_fait_defaut(self):
        """Un déploiement mono-harness n'oblige personne à choisir."""
        self.assertEqual(self.comptes.harness_courant(self.un.id), "h")

    def test_sans_choix_et_avec_plusieurs_harness_il_n_y_a_pas_de_defaut(self):
        self.comptes.enregistrer_harness("autre", self.un.id)
        self.assertIsNone(self.comptes.harness_courant(self.un.id))

    def test_choisir_puis_relire(self):
        self.comptes.enregistrer_harness("autre", self.un.id)
        self.assertEqual(self.comptes.choisir_harness(self.un.id, "autre"), "autre")
        self.assertEqual(self.comptes.harness_courant(self.un.id), "autre")

    def test_un_contributeur_peut_le_choisir(self):
        """Lire suffit — le harness courant n'est pas un geste de possession."""
        self.comptes.ajouter_contributeur("h", self.deux.id)
        self.assertEqual(self.comptes.choisir_harness(self.deux.id, "h"), "h")

    def test_un_etranger_ne_peut_pas_le_choisir(self):
        """Sinon une préférence deviendrait un contournement d'ACL."""
        with self.assertRaises(AccesRefuse):
            self.comptes.choisir_harness(self.deux.id, "h")
        self.assertIsNone(self.comptes.harness_courant(self.deux.id))

    def test_une_preference_devenue_caduque_se_lit_comme_absente(self):
        self.comptes.ajouter_contributeur("h", self.deux.id)
        self.comptes.choisir_harness(self.deux.id, "h")
        self.comptes.retirer_contributeur("h", self.deux.id)
        self.assertIsNone(self.comptes.harness_courant(self.deux.id))

    def test_effacer_le_choix_rend_au_defaut(self):
        self.comptes.enregistrer_harness("autre", self.un.id)
        self.comptes.choisir_harness(self.un.id, "autre")
        self.assertIsNone(self.comptes.choisir_harness(self.un.id, None))

    def test_un_utilisateur_inconnu_est_refuse(self):
        with self.assertRaises(AclInvalide):
            self.comptes.choisir_harness("personne", "h")


class Migration(unittest.TestCase):
    """Une base écrite avant le RFC-005 s'ouvre sans qu'on ait à la refaire."""

    def test_la_colonne_est_posee_sur_une_base_deja_ecrite(self):
        import sqlite3
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            chemin = Path(tmp) / "avant.sqlite3"
            ancienne = sqlite3.connect(chemin)
            ancienne.executescript(
                "CREATE TABLE utilisateurs ("
                "  id TEXT PRIMARY KEY, nom TEXT NOT NULL,"
                "  email TEXT NOT NULL UNIQUE COLLATE NOCASE, empreinte TEXT NOT NULL,"
                "  cree_le TEXT NOT NULL, admin INTEGER NOT NULL DEFAULT 0);"
            )
            ancienne.commit()
            ancienne.close()

            comptes = Comptes(chemin)
            self.addCleanup(comptes.fermer)
            qui = comptes.creer_utilisateur("Un", "un@exemple.test", MOT_DE_PASSE)
            comptes.enregistrer_harness("h", qui.id)
            self.assertEqual(comptes.harness_courant(qui.id), "h")


if __name__ == "__main__":
    unittest.main()
