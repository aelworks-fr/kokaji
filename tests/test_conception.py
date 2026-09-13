"""Concevoir un harness — proposer, juger, sceller.

Harness purement structurel (§0). Aucun réseau : la conception ne parle qu'aux
fichiers et à la trempe.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import ClassVar

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.conception import (
    JOURNAL,
    Proposition,
    ScellementRefuse,
    appliquer,
    juger,
    sceller,
    version_suivante,
)

MANIFEST = """
harness:
  id: h
  nom: H
  version: 1.2.3
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
  - id: k2
    nom: K2
    source: kata/k2.yaml
    livrable: L2
    amont: [k1]
    herite: [k1.c1]
    produit:
      - k2.c3: fait_etabli
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: k2, type: kata, nom: K2 }
  aretes:
    - { de: k1, vers: k2, label: suite }
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

SOURCE = "version: 1.0.0\nrole: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n"


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name) / "harness"
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}{{ etat }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text(
            "kata:\n  k1: K1\n  k2: K2\nlivrables: [L1, L2, L3]\n"
            "champs:\n  c1: Un\n  c2: Deux\n  c3: Trois\n  c4: Quatre\n",
            encoding="utf-8",
        )
        for id_kata in ("k1", "k2"):
            (self.racine / "kata" / f"{id_kata}.yaml").write_text(SOURCE, encoding="utf-8")
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")

    def manifest(self) -> dict:
        return yaml.safe_load((self.racine / "harness.yaml").read_text(encoding="utf-8"))

    def source(self, id_kata: str) -> dict:
        return yaml.safe_load((self.racine / "kata" / f"{id_kata}.yaml").read_text(encoding="utf-8"))


class Application(Bac):
    """Ce qu'une proposition fait au manifest — en mémoire, jamais sur disque."""

    def test_une_proposition_est_partielle_et_fusionne(self):
        """Remplacer effacerait ce que le formulaire n'a pas renvoyé."""
        apres = appliquer(self.manifest(), Proposition(kata=[{"id": "k2", "nom": "Nouveau nom"}]))
        k2 = next(k for k in apres["kata"] if k["id"] == "k2")

        self.assertEqual(k2["nom"], "Nouveau nom")
        self.assertEqual(k2["herite"], ["k1.c1"])  # non touché, donc conservé

    def test_un_kata_inconnu_est_ajoute(self):
        apres = appliquer(
            self.manifest(),
            Proposition(kata=[{"id": "k3", "nom": "K3", "amont": ["k2"], "herite": ["k2.c3"],
                               "produit": [{"k3.c4": "fait_etabli"}], "source": "kata/k3.yaml",
                               "livrable": "L3"}]),
        )
        self.assertEqual([k["id"] for k in apres["kata"]], ["k1", "k2", "k3"])

    def test_retirer_un_kata_emporte_ses_aretes_et_son_heritage(self):
        """Une chaîne qui pointe vers un absent est une chaîne fausse."""
        apres = appliquer(self.manifest(), Proposition(retirer=["k1"]))

        self.assertEqual([k["id"] for k in apres["kata"]], ["k2"])
        self.assertEqual(apres["kata"][0]["amont"], [])
        self.assertEqual(apres["kata"][0]["herite"], [])
        self.assertEqual(apres["chaine"]["aretes"], [])
        self.assertEqual([n["id"] for n in apres["chaine"]["noeuds"]], ["k2"])

    def test_le_manifest_sur_disque_n_est_pas_touche(self):
        appliquer(self.manifest(), Proposition(retirer=["k1"]))
        self.assertEqual(len(self.manifest()["kata"]), 2)


class Jugement(Bac):
    """Le verdict, c'est la trempe elle-même — pas un contrôle de formulaire."""

    def test_une_proposition_saine_tient(self):
        verdict = juger(self.racine, Proposition(kata=[{"id": "k2", "nom": "Autre"}]))
        self.assertTrue(verdict.tient, verdict.fautes + verdict.anomalies)
        self.assertFalse(verdict.touche_contrat)

    def test_exiger_plus_que_l_amont_ne_promet_est_refuse(self):
        """Le lint `ordre-des-statuts` garde la conception comme il garde la forge."""
        verdict = juger(
            self.racine, Proposition(kata=[{"id": "k2", "herite": [{"k1.c2": "fait_etabli"}]}])
        )
        self.assertFalse(verdict.tient)
        self.assertTrue(any("ordre-des-statuts" in a for a in verdict.anomalies), verdict.anomalies)

    def test_un_manifest_devenu_invalide_est_refuse(self):
        verdict = juger(self.racine, Proposition(kata=[{"id": "k2", "herite": ["k1.jamais"]}]))
        self.assertFalse(verdict.tient)

    def test_un_changement_de_f_diese_est_marque_comme_tel(self):
        verdict = juger(self.racine, Proposition(kata=[{"id": "k2", "herite": ["k1.c1", "k1.c2"]}]))
        self.assertTrue(verdict.touche_contrat)
        self.assertEqual(verdict.kata_touches, ("k2",))

    def test_retoucher_un_libelle_ne_touche_pas_le_contrat(self):
        verdict = juger(self.racine, Proposition(kata=[{"id": "k2", "nom": "Autre"}]))
        self.assertFalse(verdict.touche_contrat)

    def test_juger_n_ecrit_rien(self):
        avant = (self.racine / "harness.yaml").read_text(encoding="utf-8")
        juger(self.racine, Proposition(kata=[{"id": "k2", "nom": "Autre"}]))
        self.assertEqual((self.racine / "harness.yaml").read_text(encoding="utf-8"), avant)


class Versions(unittest.TestCase):
    def test_un_contrat_qui_bouge_donne_une_majeure(self):
        self.assertEqual(version_suivante("1.2.3", majeure=True), "2.0.0")

    def test_le_reste_donne_une_mineure(self):
        self.assertEqual(version_suivante("1.2.3", majeure=False), "1.3.0")

    def test_une_version_illisible_n_est_pas_devinee(self):
        with self.assertRaises(ScellementRefuse):
            version_suivante("v1", majeure=False)


class Scellement(Bac):
    def sceller(self, proposition, auteur="npelloux", motif="parce que"):
        return sceller(
            self.racine, proposition, auteur=auteur, motif=motif,
            quand=datetime(2026, 1, 2, tzinfo=UTC),
        )

    def test_sans_auteur_rien_n_est_scelle(self):
        """RFC-004 §3 — la traçabilité tient la responsabilité."""
        with self.assertRaises(ScellementRefuse):
            self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]), auteur="  ")
        self.assertEqual(self.manifest()["harness"]["version"], "1.2.3")

    def test_un_brouillon_qui_ne_tient_pas_n_ecrit_rien(self):
        with self.assertRaises(ScellementRefuse):
            self.sceller(Proposition(kata=[{"id": "k2", "herite": [{"k1.c2": "fait_etabli"}]}]))

        self.assertEqual(self.manifest()["harness"]["version"], "1.2.3")
        self.assertFalse((self.racine / JOURNAL).exists())

    def test_une_proposition_vide_arrete_la_version_courante(self):
        """RFC-006 — le geste qui manquait, et qu'un forgeron a cherché en vain.

        Sceller n'était que « sceller un changement » : on ne pouvait pas
        arrêter une définition qu'on n'avait pas modifiée, donc un harness qui
        vient de naître — copie exacte — ne pouvait jamais l'être.
        """
        avant = self.manifest()["harness"]["version"]
        trace = self.sceller(Proposition())

        self.assertEqual(trace.changements, ())
        self.assertEqual(trace.versions, {"h": avant})
        self.assertTrue((self.racine / JOURNAL).is_file())

    def test_un_arret_ne_fait_bouger_aucune_version(self):
        """En produire une nouvelle, identique, dirait qu'il y a eu un
        changement — alors que l'arrêt dit exactement l'inverse."""
        avant = self.manifest()["harness"]["version"]
        source_avant = self.source("k1")["version"]
        self.sceller(Proposition())

        self.assertEqual(self.manifest()["harness"]["version"], avant)
        self.assertEqual(self.source("k1")["version"], source_avant)

    def test_un_arret_exige_un_auteur_comme_tout_scellement(self):
        """Un scellement porte le nom de son auteur, changement ou non."""
        with self.assertRaises(ScellementRefuse):
            sceller(self.racine, Proposition(), auteur="  ")

    def test_deux_arrets_laissent_deux_traces(self):
        """Arrêter deux fois n'est pas une erreur : c'est deux relectures."""
        self.sceller(Proposition())
        self.sceller(Proposition())
        lignes = (self.racine / JOURNAL).read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lignes), 2)

    def test_un_contrat_qui_change_monte_le_kata_en_majeure(self):
        trace = self.sceller(Proposition(kata=[{"id": "k2", "herite": ["k1.c1", "k1.c2"]}]))

        self.assertEqual(self.source("k2")["version"], "2.0.0")
        self.assertEqual(self.manifest()["harness"]["version"], "2.0.0")
        self.assertEqual(trace.auteur, "npelloux")

    def test_une_retouche_reste_mineure(self):
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]))

        self.assertEqual(self.source("k2")["version"], "1.1.0")
        self.assertEqual(self.manifest()["harness"]["version"], "1.3.0")

    def test_la_source_d_un_kata_se_modifie_aussi(self):
        self.sceller(Proposition(source={"k1": {"role": "un autre rôle"}}))

        self.assertEqual(self.source("k1")["role"], "un autre rôle")
        self.assertEqual(self.source("k1")["version"], "1.1.0")

    def test_le_scellement_est_journalise_signe_et_date(self):
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]), motif="pour lire mieux")
        ligne = json.loads((self.racine / JOURNAL).read_text(encoding="utf-8").strip())

        self.assertEqual(ligne["auteur"], "npelloux")
        self.assertEqual(ligne["motif"], "pour lire mieux")
        self.assertTrue(ligne["le"].startswith("2026-01-02"))
        self.assertIn("k2", ligne["versions"])

    def test_deux_scellements_s_empilent(self):
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Un"}]))
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Deux"}]))
        lignes = (self.racine / JOURNAL).read_text(encoding="utf-8").strip().split("\n")

        self.assertEqual(len(lignes), 2)
        self.assertEqual(self.manifest()["harness"]["version"], "1.4.0")


class VocabulaireDeProposition(unittest.TestCase):
    def test_une_cle_hors_vocabulaire_est_refusee(self):
        """Une proposition parle le HDS, et rien d'autre."""
        with self.assertRaises(ValueError):
            Proposition.depuis({"kata": [], "couleur": "rouge"})

    def test_une_proposition_qui_n_est_pas_une_section(self):
        with self.assertRaises(TypeError):
            Proposition.depuis(["k1"])


if __name__ == "__main__":
    unittest.main()


class LeManifestEstUneSource(Scellement):
    """Sceller ne doit pas emporter les raisons écrites à côté des décisions.

    Le premier scellement réel de l'Atelier a réécrit son manifest par
    `yaml.safe_dump` : quarante lignes de commentaires perdues, l'ordre des clés
    avec, 155 lignes devenues 122. Rien ne l'avait montré parce qu'aucun
    scellement n'avait jamais eu lieu — le défaut attendait le premier usage.
    """

    def setUp(self):
        super().setUp()
        manifest = (self.racine / "harness.yaml").read_text(encoding="utf-8")
        (self.racine / "harness.yaml").write_text(
            "# une raison écrite en tête\n" + manifest.replace(
                "trempe:", "# pourquoi la trempe est ainsi\ntrempe:"
            ),
            encoding="utf-8",
        )

    def texte(self) -> str:
        return (self.racine / "harness.yaml").read_text(encoding="utf-8")

    def test_les_commentaires_survivent_au_scellement(self):
        self.sceller(Proposition(trempe={"vocabulaire_interdit": ["mot-qui-n-existe-nulle-part"]}))
        self.assertIn("# une raison écrite en tête", self.texte())
        self.assertIn("# pourquoi la trempe est ainsi", self.texte())

    def test_le_changement_est_bien_applique(self):
        """Préserver ne doit pas vouloir dire ne rien écrire."""
        self.sceller(Proposition(trempe={"vocabulaire_interdit": ["mot-qui-n-existe-nulle-part"]}))
        self.assertIn("mot-qui-n-existe-nulle-part", self.texte())
        self.assertEqual(
            self.manifest()["trempe"]["vocabulaire_interdit"],
            ["mot-qui-n-existe-nulle-part"],
        )

    def test_l_ordre_des_cles_est_conserve(self):
        avant = [l.split(":")[0] for l in self.texte().splitlines() if l and l[0].isalpha()]
        self.sceller(Proposition(trempe={"vocabulaire_interdit": ["mot-qui-n-existe-nulle-part"]}))
        apres = [l.split(":")[0] for l in self.texte().splitlines() if l and l[0].isalpha()]
        self.assertEqual(avant, apres)

    def test_une_section_intacte_n_est_pas_reecrite(self):
        """Remplacer une section inchangée emporterait ses commentaires sans
        rien changer d'autre."""
        (self.racine / "kata" / "k1.yaml").write_text(
            "# la raison de ce kata\n"
            + (self.racine / "kata" / "k1.yaml").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        self.sceller(Proposition(trempe={"vocabulaire_interdit": ["mot-qui-n-existe-nulle-part"]}))
        self.assertIn("# la raison de ce kata",
                      (self.racine / "kata" / "k1.yaml").read_text(encoding="utf-8"))


class ForgeApresScellement(Bac):
    """RFC-006 §4 amendé — sceller arrête, forger rend appelable.

    La forge **suit** le scellement, elle ne le conditionne pas : ce sont deux
    gestes, et les confondre avait produit une règle qui aurait coupé le chat.
    """

    def setUp(self):
        super().setUp()
        import os

        from fastapi.testclient import TestClient

        from kokaji.hds import charger
        from kokaji.middleware.service import creer

        self.sortie = Path(self._tmp.name) / "coupes"
        ancien = os.environ.get("KOKAJI_COUPES")
        os.environ["KOKAJI_COUPES"] = str(self.sortie)

        def rendre():
            if ancien is None:
                os.environ.pop("KOKAJI_COUPES", None)
            else:
                os.environ["KOKAJI_COUPES"] = ancien

        self.addCleanup(rendre)
        self.client = TestClient(creer(charger(self.racine), Path(self._tmp.name)))

    def sceller_page(self, proposition: dict) -> dict:
        return self.client.post(
            "/conception/scellement",
            json={"proposition": proposition, "auteur": "forgeron", "motif": "essai"},
        ).json()

    def test_arreter_une_version_forge_ses_coupes(self):
        """Un nouveau-né n'a rien à changer : l'arrêt doit suffire à le rendre appelable."""
        vu = self.sceller_page({})
        self.assertTrue(vu["coupes"]["forgees"], vu["coupes"])
        self.assertTrue(list(self.sortie.rglob("*.md")))

    def test_les_coupes_portent_la_version_scellee(self):
        """Forger l'objet gardé en mémoire les estampillerait de l'ancienne."""
        vu = self.sceller_page({"kata": [{"id": "k1", "livrable": "L3"}]})
        self.assertTrue(vu["coupes"]["forgees"], vu["coupes"])
        estampilles = list(self.sortie.rglob("k1.json"))
        self.assertTrue(estampilles)
        marque = json.loads(estampilles[0].read_text(encoding="utf-8"))
        self.assertEqual(marque.get("version_kata"), vu["versions"]["k1"])

    def test_sans_sortie_configuree_le_scellement_tient_quand_meme(self):
        """Une forge qui n'a pas lieu n'annule pas un scellement qui a eu lieu."""
        import os

        os.environ.pop("KOKAJI_COUPES", None)
        vu = self.sceller_page({})
        self.assertFalse(vu["coupes"]["forgees"])
        self.assertIn("aucune sortie", vu["coupes"]["motif"])
        self.assertEqual(vu["auteur"], "forgeron")


class SurfaceHttp(Bac):
    """La seule surface d'écriture sur une définition (module 3 du design)."""

    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient

        from kokaji.hds import charger
        from kokaji.middleware.service import creer

        self.client = TestClient(creer(charger(self.racine), Path(self._tmp.name)))

    def test_la_definition_sort_en_forme_editable(self):
        d = self.client.get("/conception").json()

        self.assertEqual(d["harness"]["version"], "1.2.3")
        self.assertEqual([k["id"] for k in d["kata"]], ["k1", "k2"])
        self.assertEqual(d["kata"][1]["herite"], [{"champ": "k1.c1", "minimum": ""}])
        self.assertIn("vocabulaire_interdit", d["trempe"])
        self.assertIsNone(d["harness"]["dernier_scellement"])

    def test_l_epreuve_n_ecrit_rien_et_rend_le_verdict(self):
        avant = (self.racine / "harness.yaml").read_text(encoding="utf-8")
        r = self.client.post("/conception/epreuve", json={"proposition": {
            "kata": [{"id": "k2", "herite": [{"k1.c2": "fait_etabli"}]}]}}).json()

        self.assertFalse(r["tient"])
        self.assertTrue(any("ordre-des-statuts" in a for a in r["anomalies"]))
        self.assertEqual((self.racine / "harness.yaml").read_text(encoding="utf-8"), avant)

    def test_l_epreuve_annonce_les_versions_avant_le_scellement(self):
        """Découvrir après coup qu'un kata est passé en majeure : jamais."""
        r = self.client.post("/conception/epreuve", json={"proposition": {
            "kata": [{"id": "k2", "herite": ["k1.c1", "k1.c2"]}]}}).json()

        self.assertTrue(r["tient"])
        self.assertTrue(r["touche_contrat"])
        self.assertEqual(r["versions"]["k2"], "2.0.0")

    def test_une_proposition_hors_vocabulaire_est_refusee(self):
        r = self.client.post("/conception/epreuve", json={"proposition": {"couleur": "rouge"}})
        self.assertEqual(r.status_code, 400)

    def test_sceller_ecrit_versionne_et_journalise(self):
        r = self.client.post("/conception/scellement", json={
            "proposition": {"kata": [{"id": "k2", "nom": "Autre"}]},
            "auteur": "npelloux", "motif": "pour lire mieux"})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["auteur"], "npelloux")
        self.assertEqual(self.manifest()["harness"]["version"], "1.3.0")
        self.assertTrue((self.racine / JOURNAL).is_file())

        relu = self.client.get("/conception").json()
        self.assertEqual(relu["harness"]["dernier_scellement"]["auteur"], "npelloux")

    def test_un_scellement_qui_ne_tient_pas_est_un_conflit(self):
        r = self.client.post("/conception/scellement", json={
            "proposition": {"kata": [{"id": "k2", "herite": [{"k1.c2": "fait_etabli"}]}]},
            "auteur": "npelloux"})

        self.assertEqual(r.status_code, 409)
        self.assertEqual(self.manifest()["harness"]["version"], "1.2.3")

    def test_sans_auteur_le_scellement_est_refuse(self):
        r = self.client.post("/conception/scellement", json={
            "proposition": {"kata": [{"id": "k2", "nom": "Autre"}]}, "auteur": "   "})
        self.assertEqual(r.status_code, 409)


class SurfaceGardee(Bac):
    """Éditer et sceller sont des droits — RFC-004 §3."""

    def setUp(self):
        super().setUp()
        from fastapi.testclient import TestClient

        from kokaji.comptes import Comptes
        from kokaji.hds import charger
        from kokaji.middleware.service import creer

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        mdp = "un-mot-de-passe-assez-long"
        self.co = self.comptes.creer_utilisateur("Co", "c@exemple.test", mdp)
        self.dehors = self.comptes.creer_utilisateur("Dehors", "d@exemple.test", mdp)
        self.comptes.enregistrer_harness("h", self.co.id)
        self.client = TestClient(creer(charger(self.racine), Path(self._tmp.name), self.comptes))
        self.mdp = mdp

    def cle(self, courriel: str) -> dict:
        jeton = self.client.post(
            "/session", json={"email": courriel, "mot_de_passe": self.mdp}
        ).json()["jeton"]
        return {"Authorization": f"Bearer {jeton}"}

    def test_un_non_membre_ne_lit_ni_n_eprouve_ni_ne_scelle(self):
        cle = self.cle("d@exemple.test")
        propose = {"proposition": {"kata": [{"id": "k2", "nom": "Autre"}]}}

        self.assertEqual(self.client.get("/conception", headers=cle).status_code, 403)
        self.assertEqual(
            self.client.post("/conception/epreuve", json=propose, headers=cle).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                "/conception/scellement", json={**propose, "auteur": "x"}, headers=cle
            ).status_code,
            403,
        )
        self.assertEqual(self.manifest()["harness"]["version"], "1.2.3")

    def test_sans_jeton_rien_ne_s_ouvre(self):
        self.assertEqual(self.client.get("/conception").status_code, 401)


class AjouterUnKata(Scellement):
    """Le geste manquait — RFC-006.

    Le manifest acceptait un kata neuf depuis toujours, mais rien ne suivait :
    ni sa source, ni sa place dans la chaîne, ni les noms qu'il fait entrer au
    registre. Le verdict accusait alors le kata au lieu de dire ce qui lui
    manquait.
    """

    NEUF: ClassVar[dict] = {
        "id": "k3",
        "nom": "K3",
        "livrable": "L3",
        "amont": ["k1"],
        "herite": [{"k1.c1": "fait_etabli"}],
        "produit": [{"k3.c9": "fait_etabli"}],
    }

    def test_un_kata_neuf_tient(self):
        verdict = juger(self.racine, Proposition(kata=[dict(self.NEUF)]))
        self.assertTrue(verdict.tient, [str(a) for a in verdict.fautes + verdict.anomalies])

    def test_il_entre_dans_la_chaine(self):
        """Un manifest qui déclare une étape que la topologie ignore est faux."""
        apres = appliquer(self.manifest(), Proposition(kata=[dict(self.NEUF)]))
        noeuds = {n["id"] for n in apres["chaine"]["noeuds"]}
        self.assertIn("k3", noeuds)
        self.assertTrue(
            any(a["de"] == "k1" and a["vers"] == "k3" for a in apres["chaine"]["aretes"])
        )

    def test_sa_source_est_semee(self):
        """Sans page à remplir, la forge s'arrête sur une variable sans valeur."""
        self.sceller(Proposition(kata=[dict(self.NEUF)]))
        source = self.racine / "kata" / "k3.yaml"
        self.assertTrue(source.is_file())
        self.assertIn("À écrire", source.read_text(encoding="utf-8"))

    def test_le_registre_suit(self):
        """Trois sections : le nom du kata, son livrable, et ce qu'il établit."""
        self.sceller(Proposition(kata=[dict(self.NEUF)]))
        import yaml as _yaml

        registre = _yaml.safe_load(
            (self.racine / "registre.yaml").read_text(encoding="utf-8")
        )
        self.assertIn("k3", registre["kata"])
        self.assertIn("L3", registre["livrables"])
        self.assertIn("c9", registre["champs"])

    def test_un_kata_existant_ne_refait_pas_sa_source(self):
        """Il n'arrive pas : il est retouché. Sa page reste la sienne."""
        self.sceller(Proposition(kata=[{"id": "k1", "livrable": "L2"}]))
        apres = (self.racine / "kata" / "k1.yaml").read_text(encoding="utf-8")
        self.assertNotIn("À écrire", apres)
        # Son contenu à lui survit ; seule sa version bouge, ce qui est le
        # propre d'un scellement.
        self.assertIn("role: r", apres)
