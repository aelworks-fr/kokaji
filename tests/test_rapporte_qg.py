"""La pratique rapportée par la surface HTTP (RFC-020, lot E).

Traverse les routes, parce que c'est là que l'encre et les droits se tiennent
ou se perdent. Harness purement structurel (§0) ; le juge est absent : on
éprouve l'étage déterministe et les refus, pas le modèle.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from test_isolation import MANIFEST, MOT_DE_PASSE

from kokaji.comptes import Comptes
from kokaji.hds import charger
from kokaji.middleware.service import creer

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
      - k2.c1: fait_etabli
    perception: { retours: [patch] }
    effets: { monde_ecriture: [patch] }
    capacites: [execution_shell]
    trempe: { verificateurs: [ { type: executable, check: "compile", source: build.log } ] }
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: k2, type: kata, nom: K2 }""",
).replace("  aretes: []", "  aretes:\n    - { de: k1, vers: k2 }").replace(
    "  checks_session: []", '  checks_session:\n    - { id: pas-de-jargon, type: interdit, motifs: ["synergie"] }'
)

TEXTE = "User: j'ai un problème à cadrer\n\nAssistant: dis-m'en plus, en synergie\n\nUser: voilà\n\nAssistant: bien\n"


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        racine = Path(self._tmp.name) / "harness"
        for sous in ("kata", "personas", "corpus"):
            (racine / sous).mkdir(parents=True)
        (racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (racine / "registre.yaml").write_text("champs:\n  c1: Un\n", encoding="utf-8")
        for kata in ("k1", "k2"):
            (racine / "kata" / f"{kata}.yaml").write_text(
                "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
            )
        (racine / "harness.yaml").write_text(MANIFEST_AVEC_ACTION, encoding="utf-8")
        self.harness = charger(racine)

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.patron = self.comptes.creer_utilisateur("Patron", "p@exemple.test", MOT_DE_PASSE)
        self.co = self.comptes.creer_utilisateur("Co", "c@exemple.test", MOT_DE_PASSE)
        self.comptes.enregistrer_harness("h", self.patron.id)
        self.comptes.ajouter_contributeur("h", self.co.id)
        self.client = TestClient(creer(self.harness, Path(self._tmp.name), self.comptes))

    def cle(self, qui) -> dict:
        courriel = {self.patron.id: "p", self.co.id: "c"}[qui.id]
        reponse = self.client.post(
            "/session", json={"email": f"{courriel}@exemple.test", "mot_de_passe": MOT_DE_PASSE}
        )
        return {"Authorization": f"Bearer {reponse.json()['jeton']}"}

    def rapporter(self, qui, **corps):
        tours = self.client.post("/qg/rapporte/decoupage", json={"texte": TEXTE}, headers=self.cle(qui)).json()["tours"]
        return self.client.post(
            "/qg/rapporte", json={"kata": "k1", "tours": tours, "texte": TEXTE, **corps}, headers=self.cle(qui)
        )


class Nominal(Bac):
    """§7.1 — coller, corriger, déclarer ; la retrouver immédiatement à l'encre `rapporte`."""

    def test_decouper_puis_rapporter_puis_la_retrouver(self):
        tours = self.client.post("/qg/rapporte/decoupage", json={"texte": TEXTE}, headers=self.cle(self.co)).json()["tours"]
        self.assertEqual([t["role"] for t in tours], ["humain", "kata", "humain", "kata"])

        fait = self.rapporter(self.co, kin="un sujet", source_texte="un chat", decoupage_corrige=True)
        self.assertEqual(fait.status_code, 200, fait.text)
        self.assertEqual(fait.json()["identifiant"], "CAS-0001")

        # Immédiatement dans la liste, à son encre, pour la personne qui a rapporté.
        liste = self.client.get("/qg/conversations", headers=self.cle(self.co)).json()
        self.assertEqual(len(liste), 1)
        self.assertEqual(liste[0]["provenance"], "rapporte")
        self.assertEqual(liste[0]["declaration"]["kin"], "un sujet")
        self.assertTrue(liste[0]["declaration"]["decoupage_corrige"])
        self.assertIsNone(liste[0]["conformite"])
        ha = self.client.get("/ha", headers=self.cle(self.co)).json()
        self.assertEqual(ha[0]["provenance"], "rapporte")
        self.assertEqual(ha[0]["statut"], "brut")

    def test_le_ha_est_celui_de_la_personne_qui_rapporte(self):
        """RFC-004 §5 — le propriétaire ne voit pas la pratique d'autrui, même rapportée."""
        self.rapporter(self.co)
        self.assertEqual(self.client.get("/qg/conversations", headers=self.cle(self.patron)).json(), [])
        self.assertEqual(self.client.get("/ha", headers=self.cle(self.patron)).json(), [])

    def test_un_texte_vide_ne_se_decoupe_pas(self):
        r = self.client.post("/qg/rapporte/decoupage", json={"texte": "  "}, headers=self.cle(self.co))
        self.assertEqual(r.status_code, 400)

    def test_sans_compte_rien_ne_se_rapporte(self):
        r = self.client.post("/qg/rapporte", json={"kata": "k1", "tours": []})
        self.assertEqual(r.status_code, 401)


class Refus(Bac):
    def test_sabotage_l_action_rapportee_est_refusee_en_citant_la_frontiere(self):
        """§7.4 — un kata à effets monde : 422, la frontière citée, rien d'écrit."""
        r = self.rapporter(self.co, kata="k2")
        self.assertEqual(r.status_code, 422, r.text)
        self.assertIn("RFC-020 §2", r.json()["detail"])
        self.assertEqual(self.client.get("/ha", headers=self.cle(self.co)).json(), [])

    def test_un_kata_inconnu_ou_des_tours_vides_font_400(self):
        self.assertEqual(self.rapporter(self.co, kata="k9").status_code, 400)
        r = self.client.post("/qg/rapporte", json={"kata": "k1", "tours": []}, headers=self.cle(self.co))
        self.assertEqual(r.status_code, 400)


class TremperEtSemer(Bac):
    def test_tremper_sans_juge_attache_les_constats_et_dit_les_eteints(self):
        id_ha = self.rapporter(self.co).json()["id"]
        r = self.client.post("/qg/conversation/tremper", json={"id": id_ha}, headers=self.cle(self.co))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual([c["regle"] for c in r.json()["constats"]], ["pas-de-jargon"])
        self.assertIn("etat-bien-forme", r.json()["eteints"])
        self.assertIsNone(r.json()["conformite"])

    def test_semer_ecrit_un_kin_avec_seme_par_et_n_ecrase_pas(self):
        id_ha = self.rapporter(self.co, kin="Refonte du portail").json()["id"]
        r = self.client.post("/qg/conversation/semer", json={"id": id_ha}, headers=self.cle(self.co))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["seme_par"], "CAS-0001")
        fichier = self.harness.personas / r.json()["fichier"]
        self.assertIn("seme_par: CAS-0001", fichier.read_text(encoding="utf-8"))
        encore = self.client.post("/qg/conversation/semer", json={"id": id_ha}, headers=self.cle(self.co))
        self.assertEqual(encore.status_code, 409)

    def test_un_ha_illisible_est_inconnu_pour_tremper_et_semer(self):
        """Dire « il existe, mais pas pour toi » renseignerait sur la pratique d'autrui."""
        id_ha = self.rapporter(self.co).json()["id"]
        for route in ("/qg/conversation/tremper", "/qg/conversation/semer"):
            r = self.client.post(route, json={"id": id_ha}, headers=self.cle(self.patron))
            self.assertEqual(r.status_code, 404, route)


if __name__ == "__main__":
    unittest.main()
