"""Les sabotages du RFC-004 §8 — SPECS R12.3 et R12.4.

Ce ne sont pas des tests de fonctions : ils traversent la surface HTTP, parce
que c'est là que l'isolation se tient ou se perd. Un droit vérifié dans une
fonction pure ne prouve rien sur une route qui aurait oublié de l'appeler.

R12.3 dit la règle : **un droit qu'aucun sabotage n'attaque n'est pas tenu pour
acquis**. Chaque refus du §3 a donc ici une tentative, et exige un refus net.

Harness purement structurel (§0) : aucun nom de domaine.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from kokaji.comptes import Comptes
from kokaji.hds import charger
from kokaji.middleware.service import creer

MOT_DE_PASSE = "un-mot-de-passe-assez-long"

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
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
  aretes: []
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

FICHE = """---
harness: h
kata: k1
version_kata: "0.1.0"
version_coupe: "abc"
cible: c1
moteur: fournisseur/moteur
date: "2026-01-01T10:00:00+00:00"
praticien: {praticien}
visibilite: {visibilite}
source: reel
statut: brut
---

# {identifiant} — k1 c1

Versé depuis le journal du Dojo, session `s-{identifiant}`.
"""


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name) / "harness"
        for sous in ("kata", "personas", "corpus"):
            (racine / sous).mkdir(parents=True)
        (racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (racine / "registre.yaml").write_text("champs:\n  c1: Un\n", encoding="utf-8")
        (racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(racine)

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.patron = self.comptes.creer_utilisateur("Patron", "p@exemple.test", MOT_DE_PASSE)
        self.co = self.comptes.creer_utilisateur("Co", "c@exemple.test", MOT_DE_PASSE)
        self.dehors = self.comptes.creer_utilisateur("Dehors", "d@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("h", self.patron.id)
        self.comptes.ajouter_contributeur("h", self.co.id)

        self.client = TestClient(creer(self.harness, Path(self._tmp.name), self.comptes))

    def ha(self, identifiant: str, praticien: str, visibilite: str = "privee") -> Path:
        dossier = self.harness.corpus / f"{identifiant}-k1-c1-abc"
        dossier.mkdir(parents=True, exist_ok=True)
        (dossier / "fiche.md").write_text(
            FICHE.format(praticien=praticien, visibilite=visibilite, identifiant=identifiant),
            encoding="utf-8",
        )
        (dossier / "transcript.md").write_text("**Porteur** — un tour\n", encoding="utf-8")
        return dossier

    def cle(self, qui) -> dict:
        courriel = {self.patron.id: "p", self.co.id: "c", self.dehors.id: "d"}[qui.id]
        reponse = self.client.post(
            "/session", json={"email": f"{courriel}@exemple.test", "mot_de_passe": MOT_DE_PASSE}
        )
        return {"Authorization": f"Bearer {reponse.json()['jeton']}"}


class MembresNommes(Bac):
    """Un co-auteur se lit à son nom — l'identifiant reste ce qu'on envoie."""

    def test_la_liste_nomme_les_membres(self):
        vu = self.client.get("/membres", headers=self.cle(self.patron)).json()
        self.assertEqual(vu["proprietaire"]["nom"], "Patron")
        self.assertEqual(vu["proprietaire"]["email"], "p@exemple.test")
        self.assertEqual([c["nom"] for c in vu["contributeurs"]], ["Co"])
        self.assertEqual(vu["contributeurs"][0]["id"], self.co.id)

    def test_ajouter_rend_la_liste_nommee(self):
        vu = self.client.post(
            "/membres", json={"email": "d@exemple.test"}, headers=self.cle(self.patron)
        )
        self.assertEqual(vu.status_code, 200)
        self.assertEqual(
            sorted(c["nom"] for c in vu.json()["contributeurs"]), ["Co", "Dehors"]
        )

    def test_retirer_rend_la_liste_nommee(self):
        self.comptes.ajouter_contributeur("h", self.dehors.id)
        vu = self.client.delete(f"/membres/{self.dehors.id}", headers=self.cle(self.patron))
        self.assertEqual(vu.status_code, 200)
        self.assertEqual([c["nom"] for c in vu.json()["contributeurs"]], ["Co"])

    # Pas de test du repli « compte inconnu » : le magasin refuse d'ajouter un
    # contributeur qui n'existe pas (`AclInvalide: contributeur inconnu`), et
    # rien n'efface un compte. Le repli reste comme garde bon marché, mais il
    # est aujourd'hui inatteignable — l'éprouver demanderait de forcer l'état
    # par une porte dérobée, ce qui ne prouverait rien du service.

    def test_les_candidats_excluent_ceux_qui_sont_deja_la(self):
        vu = self.client.get("/membres/candidats", headers=self.cle(self.patron)).json()
        self.assertEqual([c["nom"] for c in vu["candidats"]], ["Dehors"])

    def test_un_co_auteur_ne_liste_pas_les_comptes_du_service(self):
        """Qui n'a pas le droit d'ajouter n'a pas à savoir qui existe."""
        for qui in (self.co, self.dehors):
            refus = self.client.get("/membres/candidats", headers=self.cle(qui))
            self.assertEqual(refus.status_code, 403)

    def test_la_liste_ne_dit_rien_d_autre_que_de_quoi_designer(self):
        """Nom, adresse, identifiant — et rien de la pratique (R12.4)."""
        vu = self.client.get("/membres/candidats", headers=self.cle(self.patron)).json()
        self.assertEqual(set(vu["candidats"][0]), {"id", "nom", "email"})

    def test_la_definition_porte_les_memes_noms(self):
        """La page lit `/conception` : les deux sources doivent concorder."""
        vu = self.client.get("/definition", headers=self.cle(self.co))
        membres = self.client.get("/conception", headers=self.cle(self.co)).json()["membres"]
        self.assertEqual(vu.status_code, 200)
        self.assertEqual(membres["proprietaire"]["nom"], "Patron")
        self.assertEqual([c["nom"] for c in membres["contributeurs"]], ["Co"])


class Nominal(Bac):
    """§8.1 — le parcours qui doit marcher."""

    def test_le_contributeur_lit_la_definition(self):
        reponse = self.client.get("/definition", headers=self.cle(self.co))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(reponse.json()["harness"], "h")

    def test_son_ha_est_prive_a_la_naissance(self):
        self.ha("CAS-0001", self.co.id)
        vu = self.client.get("/ha", headers=self.cle(self.co)).json()
        self.assertEqual(len(vu), 1)
        self.assertEqual(vu[0]["visibilite"], "privee")

    def test_verse_il_devient_visible_du_proprietaire(self):
        self.ha("CAS-0001", self.co.id)
        verse = self.client.post(
            "/ha/CAS-0001/visibilite", json={"valeur": "verse"}, headers=self.cle(self.co)
        )
        self.assertEqual(verse.status_code, 200)

        lu = self.client.get("/ha/CAS-0001", headers=self.cle(self.patron))
        self.assertEqual(lu.status_code, 200)

    def test_le_versement_est_revocable(self):
        self.ha("CAS-0001", self.co.id, "verse")
        self.client.post(
            "/ha/CAS-0001/visibilite", json={"valeur": "privee"}, headers=self.cle(self.co)
        )
        repris = self.client.get("/ha/CAS-0001", headers=self.cle(self.patron))
        self.assertEqual(repris.status_code, 403)

    def test_le_profil_donne_ma_liste_et_mon_role(self):
        profil = self.client.get("/profil", headers=self.cle(self.co)).json()
        self.assertEqual(profil["harness"], [{"harness": "h", "role": "contributeur"}])


class Sabotages(Bac):
    """§8.2 — chacun doit produire un refus net."""

    def test_1_le_contributeur_ne_gere_pas_les_membres(self):
        refus = self.client.post(
            "/membres", json={"email": "d@exemple.test"}, headers=self.cle(self.co)
        )
        self.assertEqual(refus.status_code, 403)
        self.assertEqual(self.comptes.role("h", self.dehors.id), "etranger")

    def test_1bis_le_contributeur_ne_transfere_pas(self):
        refus = self.client.post(
            "/transfert", json={"vers": self.co.id}, headers=self.cle(self.co)
        )
        self.assertEqual(refus.status_code, 403)
        self.assertEqual(self.comptes.acl("h").proprietaire, self.patron.id)

    def test_2_un_non_membre_ne_lit_pas_la_definition(self):
        for route in ("/definition", "/chaine", "/ha", "/qg/sujets", "/qg/conversations"):
            refus = self.client.get(route, headers=self.cle(self.dehors))
            self.assertEqual(refus.status_code, 403, route)

    def test_3_le_proprietaire_ne_lit_pas_un_ha_non_verse(self):
        """Le sabotage le plus important : l'autorat ne donne pas la pratique."""
        self.ha("CAS-0001", self.co.id)
        cle = self.cle(self.patron)

        for route in ("/ha/CAS-0001", "/ha/CAS-0001/transcript", "/ha/CAS-0001/etat"):
            refus = self.client.get(route, headers=cle)
            self.assertEqual(refus.status_code, 403, route)

    def test_3bis_un_ha_non_verse_ne_figure_meme_pas_a_la_liste(self):
        """Compter les silences renseignerait déjà sur la pratique d'autrui."""
        self.ha("CAS-0001", self.co.id)
        self.assertEqual(self.client.get("/ha", headers=self.cle(self.patron)).json(), [])

    def test_3ter_seul_le_praticien_regle_la_visibilite(self):
        self.ha("CAS-0001", self.co.id)
        refus = self.client.post(
            "/ha/CAS-0001/visibilite", json={"valeur": "verse"}, headers=self.cle(self.patron)
        )
        self.assertEqual(refus.status_code, 403)

    def test_un_ha_d_avant_le_rfc_reste_ferme(self):
        """Sans praticien inscrit, personne n'hérite du ha : pas de fuite rétroactive."""
        self.ha("CAS-0002", "")
        for qui in (self.patron, self.co):
            self.assertEqual(self.client.get("/ha/CAS-0002", headers=self.cle(qui)).status_code, 403)

    def test_sans_jeton_rien_ne_s_ouvre(self):
        self.assertEqual(self.client.get("/ha").status_code, 401)
        self.assertEqual(self.client.get("/definition").status_code, 401)

    def test_un_jeton_invente_ne_vaut_rien(self):
        faux = {"Authorization": "Bearer jeton-invente-de-toutes-pieces"}
        self.assertEqual(self.client.get("/ha", headers=faux).status_code, 401)


class AdminDExploitation(Bac):
    """L'administration ne donne pas la pratique — R12.4 vaut pour elle aussi."""

    def setUp(self):
        super().setUp()
        self.comptes.promouvoir(self.patron.id)

    def test_l_admin_lit_les_comptes_et_les_invitations(self):
        d = self.client.get("/admin/donnees", headers=self.cle(self.patron)).json()
        self.assertEqual(len(d["comptes"]), 3)
        # L'autorat se lit harness par harness : l'administration voit le
        # service entier, pas un harness qu'on lui aurait choisi.
        self.assertEqual(d["harness"][0]["autorat"]["proprietaire"], self.patron.id)

    def test_un_non_admin_ne_voit_pas_la_page_de_donnees(self):
        for qui in (self.co, self.dehors):
            self.assertEqual(
                self.client.get("/admin/donnees", headers=self.cle(qui)).status_code, 403
            )

    def test_l_admin_ne_lit_pas_un_ha_non_verse(self):
        """Le sabotage n°3, refait contre le compte qui administre tout le reste.

        C'est la ligne qui décide de ce que vaut la phrase du RFC : qui dirait
        « je ne sais pas » en sachant son patron lecteur ?
        """
        self.ha("CAS-0001", self.co.id)
        cle = self.cle(self.patron)

        for route in ("/ha/CAS-0001", "/ha/CAS-0001/transcript", "/ha/CAS-0001/etat"):
            self.assertEqual(self.client.get(route, headers=cle).status_code, 403, route)
        self.assertEqual(self.client.get("/ha", headers=cle).json(), [])

    def test_l_admin_ne_regle_pas_la_visibilite_d_autrui(self):
        self.ha("CAS-0001", self.co.id)
        refus = self.client.post(
            "/ha/CAS-0001/visibilite", json={"valeur": "verse"}, headers=self.cle(self.patron)
        )
        self.assertEqual(refus.status_code, 403)


class Invitation(Bac):
    """Ce qui s'envoie est une porte, pas une clé."""

    def setUp(self):
        super().setUp()
        self.comptes.promouvoir(self.patron.id)

    def ouvrir(self, email="neuf@exemple.test"):
        return self.client.post(
            "/admin/invitations", json={"email": email}, headers=self.cle(self.patron)
        )

    def test_l_admin_ouvre_une_invitation_et_recoit_un_lien(self):
        r = self.ouvrir()
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["chemin"].startswith("/invitation/"))

    def test_un_contributeur_n_invite_pas(self):
        refus = self.client.post(
            "/admin/invitations", json={"email": "x@exemple.test"}, headers=self.cle(self.co)
        )
        self.assertEqual(refus.status_code, 403)

    def test_l_invite_cree_son_compte_sans_jeton_ni_session(self):
        """La page d'invitation est ouverte : sans elle, l'invité ne peut pas entrer."""
        jeton = self.ouvrir().json()["jeton"]

        etat = self.client.get(f"/invitation/{jeton}/etat")
        self.assertEqual(etat.json()["email"], "neuf@exemple.test")

        cree = self.client.post(
            f"/invitation/{jeton}",
            json={"nom": "Neuf", "mot_de_passe": "un-mot-de-passe-a-moi"},
        )
        self.assertEqual(cree.status_code, 200)
        self.assertIsNotNone(self.comptes.par_email("neuf@exemple.test"))

    def test_le_lien_ne_sert_qu_une_fois(self):
        jeton = self.ouvrir().json()["jeton"]
        self.client.post(f"/invitation/{jeton}",
                         json={"nom": "Neuf", "mot_de_passe": "un-mot-de-passe-a-moi"})
        second = self.client.post(f"/invitation/{jeton}",
                                  json={"nom": "Bis", "mot_de_passe": "encore-un-mot-de-passe"})
        self.assertEqual(second.status_code, 404)

    def test_un_invite_n_herite_d_aucun_droit(self):
        jeton = self.ouvrir().json()["jeton"]
        self.client.post(f"/invitation/{jeton}",
                         json={"nom": "Neuf", "mot_de_passe": "un-mot-de-passe-a-moi"})
        neuf = self.comptes.par_email("neuf@exemple.test")

        self.assertFalse(self.comptes.est_admin(neuf.id))
        self.assertEqual(self.comptes.role("h", neuf.id), "etranger")

    def test_une_invitation_revoquee_ne_vaut_plus(self):
        jeton = self.ouvrir().json()["jeton"]
        self.client.delete(f"/admin/invitations/{jeton}", headers=self.cle(self.patron))
        self.assertEqual(self.client.get(f"/invitation/{jeton}/etat").status_code, 404)

    def test_chacun_change_son_propre_mot_de_passe(self):
        r = self.client.post("/moi/mot-de-passe", json={"nouveau": "un-mot-de-passe-tout-neuf"},
                             headers=self.cle(self.co))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(self.comptes.ouvrir_session("c@exemple.test", "un-mot-de-passe-tout-neuf"))


class Invariants(Bac):
    """§8.3 — impossible par construction."""

    def test_retirer_le_proprietaire_est_un_conflit_pas_un_droit(self):
        refus = self.client.delete(f"/membres/{self.patron.id}", headers=self.cle(self.patron))
        self.assertEqual(refus.status_code, 409)
        self.assertEqual(self.comptes.acl("h").proprietaire, self.patron.id)

    def test_le_transfert_garde_un_seul_proprietaire(self):
        self.client.post("/transfert", json={"vers": self.co.id}, headers=self.cle(self.patron))
        acl = self.comptes.acl("h")
        self.assertEqual(acl.proprietaire, self.co.id)
        self.assertNotIn(self.co.id, acl.contributeurs)
        self.assertIn(self.patron.id, acl.contributeurs)

    def test_la_sante_reste_ouverte(self):
        """Savoir que le service répond ne dit rien de ce qu'il contient."""
        reponse = self.client.get("/sante")
        self.assertEqual(reponse.status_code, 200)
        self.assertTrue(reponse.json()["partage"])


class SansMagasin(Bac):
    """Le mode mono-utilisateur reste ce qu'il était : personne à isoler."""

    def setUp(self):
        super().setUp()
        self.client = TestClient(creer(self.harness, Path(self._tmp.name)))

    def test_tout_est_lisible_sans_authentification(self):
        self.ha("CAS-0001", "")
        self.assertEqual(self.client.get("/ha").status_code, 200)
        self.assertEqual(len(self.client.get("/ha").json()), 1)

    def test_les_routes_d_autorat_n_existent_pas(self):
        """Les déclarer sans magasin donnerait des portes qui répondent 500."""
        self.assertEqual(self.client.get("/profil").status_code, 404)
        self.assertEqual(self.client.post("/membres", json={"email": "x@y.zz"}).status_code, 404)


if __name__ == "__main__":
    unittest.main()


class EnteteDIdentite(Bac):
    """Un portail devant le service — la confiance est déclarée, jamais supposée."""

    def client_avec(self, entete: str = "Remote-Email"):
        from kokaji.middleware.service import creer

        return TestClient(
            creer(self.harness, Path(self._tmp.name), self.comptes, entete_identite=entete)
        )

    def test_sans_reglage_l_entete_est_ignore(self):
        """Par défaut, un en-tête ne vaut rien : personne ne se déclare soi-même."""
        refus = self.client.get("/definition", headers={"Remote-Email": "p@exemple.test"})
        self.assertEqual(refus.status_code, 401)

    def test_avec_reglage_le_portail_identifie(self):
        client = self.client_avec()
        r = client.get("/definition", headers={"Remote-Email": "c@exemple.test"})
        self.assertEqual(r.status_code, 200)

    def test_un_email_inconnu_du_magasin_est_refuse_sans_etre_cree(self):
        """Un compte se crée par invitation, jamais par une entête."""
        client = self.client_avec()
        refus = client.get("/definition", headers={"Remote-Email": "jamais-vu@exemple.test"})

        self.assertEqual(refus.status_code, 403)
        self.assertIsNone(self.comptes.par_email("jamais-vu@exemple.test"))

    def test_l_entete_ne_contourne_pas_l_isolation_de_la_pratique(self):
        """Se faire annoncer par le portail ne donne pas la pratique d'autrui."""
        self.ha("CAS-0001", self.co.id)
        client = self.client_avec()
        self.assertEqual(
            client.get("/ha/CAS-0001", headers={"Remote-Email": "p@exemple.test"}).status_code, 403
        )
