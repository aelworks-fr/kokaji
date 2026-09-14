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

    def test_un_gabarit_qui_tient_est_un_changement_nomme(self):
        v = juger(self.racine, Proposition(template="Doctrine.\n{{ role }}{{ etat }}"))
        self.assertTrue(v.tient, v)
        self.assertEqual([c.ou for c in v.changements], ["template"])
        self.assertFalse(v.touche_contrat)

    def test_un_gabarit_identique_ne_change_rien(self):
        v = juger(self.racine, Proposition(template="{{ role }}{{ etat }}"))
        self.assertTrue(v.tient)
        self.assertEqual(v.changements, ())

    def test_un_gabarit_qui_cite_une_variable_inconnue_est_refuse(self):
        """Sabotage 1 du RFC-010 : la forge nomme la variable, rien n'est écrit."""
        v = juger(self.racine, Proposition(template="{{ role }}{{ inconnue }}"))
        self.assertFalse(v.tient)
        self.assertTrue(any("inconnue" in f for f in v.fautes), v.fautes)
        self.assertEqual((self.racine / "template.md").read_text(encoding="utf-8"), "{{ role }}{{ etat }}")

    def test_un_densho_qui_vide_une_variable_obligatoire_est_refuse(self):
        """Sabotage 2 : `questions` vidé — variable obligatoire vide."""
        (self.racine / "template.md").write_text("{{ role }}{{ questions }}{{ etat }}", encoding="utf-8")
        v = juger(self.racine, Proposition(source={"k1": {"questions": []}}))
        self.assertFalse(v.tient)
        self.assertTrue(any("questions" in f for f in v.fautes), v.fautes)

    def test_un_mot_interdit_dans_le_gabarit_est_refuse_par_la_trempe(self):
        """Sabotage 3 : le vocabulaire interdit du harness s'applique au gabarit."""
        v = juger(
            self.racine,
            Proposition(
                template="tabou {{ role }}{{ etat }}",
                trempe={"vocabulaire_interdit": ["tabou"]},
            ),
        )
        self.assertFalse(v.tient)
        self.assertTrue(any("tabou" in a for a in v.anomalies), v.anomalies)

    def test_juger_n_ecrit_rien(self):
        avant = (self.racine / "harness.yaml").read_text(encoding="utf-8")
        juger(self.racine, Proposition(kata=[{"id": "k2", "nom": "Autre"}]))
        self.assertEqual((self.racine / "harness.yaml").read_text(encoding="utf-8"), avant)


class Rendu(Bac):
    """La coupe qu'on voit avant de sceller — RFC-010 D10.3."""

    def test_la_coupe_rendue_est_celle_que_la_forge_ecrit(self):
        from kokaji.conception import rendre_coupe
        from kokaji.forge import forger_harness
        from kokaji.hds import charger

        sortie = Path(self._tmp.name) / "dist"
        forger_harness(charger(self.racine), sortie)
        ecrite = (sortie / "h" / "c1" / "k1.md").read_text(encoding="utf-8")

        rendue = rendre_coupe(self.racine, "k1", "c1")
        self.assertEqual(rendue.texte, ecrite)
        self.assertEqual(rendue.estampille.cible, "c1")

    def test_un_brouillon_se_voit_dans_la_coupe_sans_etre_ecrit(self):
        """Sabotage 4 : après le rendu, `kata/` et `template.md` sont intacts."""
        from kokaji.conception import rendre_coupe

        avant = {f.name: f.read_text(encoding="utf-8") for f in self.racine.rglob("*") if f.is_file()}
        rendue = rendre_coupe(
            self.racine, "k1", "c1",
            Proposition(template="Doctrine.\n{{ role }}{{ etat }}", source={"k1": {"role": "neuf"}}),
        )
        self.assertIn("Doctrine.", rendue.texte)
        self.assertIn("neuf", rendue.texte)
        apres = {f.name: f.read_text(encoding="utf-8") for f in self.racine.rglob("*") if f.is_file()}
        self.assertEqual(apres, avant)
        self.assertFalse((Path(self._tmp.name) / "dist").exists())

    def test_un_kata_ou_une_cible_inconnus_sont_nommes(self):
        from kokaji.conception import CoupeIntrouvable, rendre_coupe

        with self.assertRaises(CoupeIntrouvable):
            rendre_coupe(self.racine, "k9", "c1")
        with self.assertRaises(CoupeIntrouvable):
            rendre_coupe(self.racine, "k1", "c9")

    def test_un_gabarit_impossible_a_forger_le_dit(self):
        from kokaji.conception import rendre_coupe
        from kokaji.forge import ForgeImpossible

        with self.assertRaises(ForgeImpossible):
            rendre_coupe(self.racine, "k1", "c1", Proposition(template="{{ inconnue }}"))


class Versions(unittest.TestCase):
    def test_un_contrat_qui_bouge_donne_une_majeure(self):
        self.assertEqual(version_suivante("1.2.3", majeure=True), "2.0.0")

    def test_le_reste_donne_une_mineure(self):
        self.assertEqual(version_suivante("1.2.3", majeure=False), "1.3.0")

    def test_une_version_illisible_n_est_pas_devinee(self):
        with self.assertRaises(ScellementRefuse):
            version_suivante("v1", majeure=False)


class Scellement(Bac):
    def sceller(self, proposition, auteur="forgeron", motif="parce que"):
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
        self.assertEqual(trace.auteur, "forgeron")

    def test_une_retouche_reste_mineure(self):
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]))

        self.assertEqual(self.source("k2")["version"], "1.1.0")
        self.assertEqual(self.manifest()["harness"]["version"], "1.3.0")

    def test_le_gabarit_s_ecrit_au_scellement_et_monte_le_harness_en_mineure(self):
        self.sceller(Proposition(template="Doctrine.\n{{ role }}{{ etat }}"))

        self.assertEqual(
            (self.racine / "template.md").read_text(encoding="utf-8"), "Doctrine.\n{{ role }}{{ etat }}"
        )
        self.assertEqual(self.manifest()["harness"]["version"], "1.3.0")
        # Aucun kata n'a bougé : leurs versions non plus.
        self.assertEqual(self.source("k1")["version"], "1.0.0")

    def test_un_gabarit_qui_ne_tient_pas_n_ecrit_rien(self):
        with self.assertRaises(ScellementRefuse):
            self.sceller(Proposition(template="{{ inconnue }}"))
        self.assertEqual((self.racine / "template.md").read_text(encoding="utf-8"), "{{ role }}{{ etat }}")
        self.assertEqual(self.manifest()["harness"]["version"], "1.2.3")

    def test_la_source_d_un_kata_se_modifie_aussi(self):
        self.sceller(Proposition(source={"k1": {"role": "un autre rôle"}}))

        self.assertEqual(self.source("k1")["role"], "un autre rôle")
        self.assertEqual(self.source("k1")["version"], "1.1.0")

    def test_le_scellement_est_journalise_signe_et_date(self):
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]), motif="pour lire mieux")
        ligne = json.loads((self.racine / JOURNAL).read_text(encoding="utf-8").strip())

        self.assertEqual(ligne["auteur"], "forgeron")
        self.assertEqual(ligne["motif"], "pour lire mieux")
        self.assertTrue(ligne["le"].startswith("2026-01-02"))
        self.assertIn("k2", ligne["versions"])

    def test_deux_scellements_s_empilent(self):
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Un"}]))
        self.sceller(Proposition(kata=[{"id": "k2", "nom": "Deux"}]))
        lignes = (self.racine / JOURNAL).read_text(encoding="utf-8").strip().split("\n")

        self.assertEqual(len(lignes), 2)
        self.assertEqual(self.manifest()["harness"]["version"], "1.4.0")


class LeScellementCommite(Scellement):
    """Un scellement est un commit — dans le dépôt qui contient le harness (D9.1)."""

    def git(self, depot: Path, *args: str) -> str:
        import subprocess

        return subprocess.run(
            ["git", "-c", "safe.directory=*", "-C", str(depot), *args],
            capture_output=True, text=True, check=True,
        ).stdout.strip()

    def depot(self, ou: Path) -> Path:
        self.git(ou, "init", "-q")
        self.git(ou, "config", "user.email", "t@exemple.test")
        self.git(ou, "config", "user.name", "T")
        self.git(ou, "add", "-A")
        self.git(ou, "commit", "-q", "-m", "avant")
        return ou

    def test_hors_de_tout_depot_le_scellement_tient_et_le_dit(self):
        trace = self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]))
        self.assertEqual(trace.commit, "")
        self.assertIn("aucun dépôt git", trace.commit_motif)
        self.assertEqual(self.manifest()["harness"]["version"], "1.3.0")

    def test_le_harness_qui_est_un_depot_se_commite_signe_et_motive(self):
        self.depot(self.racine)
        trace = self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]), motif="pour lire mieux")

        self.assertTrue(trace.commit, trace.commit_motif)
        self.assertEqual(trace.commit_motif, "")
        self.assertEqual(self.git(self.racine, "status", "--porcelain"), "")
        message = self.git(self.racine, "log", "-1", "--format=%B")
        self.assertTrue(message.startswith("scellement : h — "), message)
        self.assertIn("h v1.3.0", message)
        self.assertIn("pour lire mieux", message)
        self.assertIn("Scellé par forgeron", message)
        self.assertEqual(self.git(self.racine, "log", "-1", "--format=%an"), "forgeron")

    def test_dans_un_depot_plus_large_seul_le_harness_part(self):
        """Le dépôt de l'instance porte d'autres choses : elles ne partent pas sous ce nom."""
        parent = self.racine.parent
        self.depot(parent)
        (parent / "autre.txt").write_text("en cours", encoding="utf-8")

        trace = self.sceller(Proposition(kata=[{"id": "k2", "nom": "Autre"}]))

        self.assertTrue(trace.commit, trace.commit_motif)
        self.assertEqual(self.git(parent, "status", "--porcelain"), "?? autre.txt")
        commites = self.git(parent, "show", "--stat", "--format=", "HEAD")
        self.assertIn("harness/harness.yaml", commites)
        self.assertNotIn("autre.txt", commites)

    def test_un_arret_commite_sa_trace(self):
        """Un arrêt n'écrit que le journal des scellements : c'est ce qui se commite."""
        self.depot(self.racine)
        trace = self.sceller(Proposition())
        self.assertTrue(trace.commit, trace.commit_motif)
        self.assertIn(JOURNAL, self.git(self.racine, "show", "--stat", "--format=", "HEAD"))

    def test_un_scellement_qui_ne_tient_pas_ne_commite_rien(self):
        self.depot(self.racine)
        avant = self.git(self.racine, "rev-parse", "HEAD")
        with self.assertRaises(ScellementRefuse):
            self.sceller(Proposition(template="{{ inconnue }}"))
        self.assertEqual(self.git(self.racine, "rev-parse", "HEAD"), avant)
        self.assertEqual(self.git(self.racine, "status", "--porcelain"), "")


class VocabulaireDeProposition(unittest.TestCase):
    def test_le_gabarit_est_un_texte(self):
        with self.assertRaises(TypeError):
            Proposition.depuis({"template": {"texte": "x"}})
        self.assertEqual(Proposition.depuis({"template": "x"}).template, "x")
        self.assertFalse(Proposition.depuis({"template": "x"}).vide)

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

    def test_la_definition_expose_le_gabarit_les_cibles_et_les_densho(self):
        d = self.client.get("/conception").json()

        self.assertEqual(d["template"]["chemin"], "template.md")
        self.assertEqual(d["template"]["texte"], "{{ role }}{{ etat }}")
        self.assertEqual(d["template"]["variables"], ["role", "etat"])
        self.assertEqual([c["id"] for c in d["cibles"]], ["c1"])
        self.assertEqual(d["kata"][0]["source"]["role"], "r")
        self.assertEqual(d["kata"][0]["source"]["questions"], ["q"])

    def test_l_epreuve_accepte_le_gabarit_et_annonce_la_version_du_harness(self):
        v = self.client.post(
            "/conception/epreuve",
            json={"proposition": {"template": "Doctrine.\n{{ role }}{{ etat }}"}},
        ).json()
        self.assertTrue(v["tient"], v)
        self.assertEqual([c["ou"] for c in v["changements"]], ["template"])
        self.assertEqual(v["versions"], {"h": "1.3.0"})

    def test_la_vigie_se_lit_depuis_la_page(self):
        """RFC-013, remarque 2 : la vigie est l'état du produit, pas un secret."""
        d = self.client.get("/vigie").json()
        self.assertIn("verdicts", d)
        self.assertIn("tient", d)

    def test_l_etat_du_depot_se_lit(self):
        """RFC-012 lot A : sans dépôt, la surface le dit ; avec, elle le décrit."""
        d = self.client.get("/depot").json()
        self.assertEqual(d["etat"], "sans dépôt")
        self.assertFalse(d["est_depot"])
        self.assertIsNone(d["enregistrement"])

        from kokaji.depot import initier

        initier(self.racine, "naissance : h")
        d = self.client.get("/depot").json()
        self.assertEqual(d["etat"], "non enregistré")
        self.assertEqual(d["dernier_commit"]["message"], "naissance : h")
        self.assertTrue(d["propre"])

    def test_sans_magasin_l_enregistrement_ne_se_fait_pas(self):
        r = self.client.put("/depot", json={"chemin": "h.git"})
        self.assertEqual(r.status_code, 404)

    def test_la_coupe_se_rend_par_la_surface_sans_rien_ecrire(self):
        avant = (self.racine / "template.md").read_text(encoding="utf-8")
        r = self.client.post("/conception/coupe", json={
            "kata": "k1", "cible": "c1",
            "proposition": {"template": "Doctrine.\n{{ role }}{{ etat }}"}})

        self.assertEqual(r.status_code, 200, r.text)
        self.assertIn("Doctrine.", r.json()["texte"])
        self.assertEqual(r.json()["estampille"]["kata"], "k1")
        self.assertEqual((self.racine / "template.md").read_text(encoding="utf-8"), avant)

    def test_une_coupe_introuvable_ou_impossible_se_dit(self):
        self.assertEqual(
            self.client.post("/conception/coupe", json={"kata": "k9", "cible": "c1"}).status_code, 404
        )
        r = self.client.post("/conception/coupe", json={
            "kata": "k1", "cible": "c1", "proposition": {"template": "{{ inconnue }}"}})
        self.assertEqual(r.status_code, 422)
        self.assertIn("inconnue", r.json()["detail"])

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
            "auteur": "forgeron", "motif": "pour lire mieux"})

        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["auteur"], "forgeron")
        self.assertEqual(self.manifest()["harness"]["version"], "1.3.0")
        self.assertTrue((self.racine / JOURNAL).is_file())

        relu = self.client.get("/conception").json()
        self.assertEqual(relu["harness"]["dernier_scellement"]["auteur"], "forgeron")

    def test_un_scellement_qui_ne_tient_pas_est_un_conflit(self):
        r = self.client.post("/conception/scellement", json={
            "proposition": {"kata": [{"id": "k2", "herite": [{"k1.c2": "fait_etabli"}]}]},
            "auteur": "forgeron"})

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

    def test_le_depot_nu_s_enregistre_se_pousse_et_se_tire_par_la_surface(self):
        """RFC-012 lot B — le nominal, et les sabotages 2 et 5 sur la surface."""
        import os
        from unittest.mock import patch

        from kokaji.depot import est_depot_nu, initier

        initier(self.racine, "naissance : h")
        depots = Path(self._tmp.name) / "depots"
        depots.mkdir()
        proprietaire = self.cle("c@exemple.test")
        with patch.dict(os.environ, {"KOKAJI_DEPOTS": str(depots)}):
            # Sabotage 2 : hors du dossier des dépôts, refus nommé, aucune ligne.
            hors = self.client.put("/depot", json={"chemin": "/tmp/ailleurs.git"}, headers=proprietaire)
            self.assertEqual(hors.status_code, 409, hors.text)
            self.assertIsNone(self.comptes.depot("h"))

            r = self.client.put("/depot", json={"chemin": "h.git"}, headers=proprietaire)
            self.assertEqual(r.status_code, 200, r.text)
            self.assertTrue(est_depot_nu(depots / "h.git"))
            self.assertEqual(self.comptes.depot("h").chemin, str(depots / "h.git"))
            self.assertEqual(self.comptes.depot("h").commit_reference, r.json()["commit_reference"])

            lu = self.client.get("/depot", headers=proprietaire).json()
            self.assertEqual(lu["etat"], "à jour")
            self.assertEqual(lu["enregistrement"]["chemin"], str(depots / "h.git"))

            # Un scellement commite et pousse (pousser_au_scellement, vrai par défaut).
            scelle = self.client.post("/conception/scellement", json={
                "proposition": {"kata": [{"id": "k2", "nom": "Autre"}]}, "auteur": "Co"},
                headers=proprietaire).json()
            self.assertTrue(scelle["commit"], scelle)
            self.assertEqual(scelle["pousse"], scelle["commit"], scelle)
            self.assertEqual(self.comptes.depot("h").commit_reference, scelle["commit"])

            # Rien à pousser, rien à tirer : ça se dit, en 200.
            self.assertEqual(self.client.post("/depot/pousser", headers=proprietaire).status_code, 200)
            self.assertEqual(self.client.post("/depot/tirer", headers=proprietaire).status_code, 200)

            # Sabotage 5 : un non-membre ne pousse pas ; un contributeur n'enregistre pas.
            dehors = self.cle("d@exemple.test")
            self.assertEqual(self.client.post("/depot/pousser", headers=dehors).status_code, 403)
            self.comptes.ajouter_contributeur("h", self.dehors.id)
            self.assertEqual(self.client.put("/depot", json={"chemin": "x.git"}, headers=dehors).status_code, 403)
            self.assertEqual(self.client.delete("/depot", headers=dehors).status_code, 403)
            self.assertEqual(self.client.post("/depot/pousser", headers=dehors).status_code, 200)

            # Désenregistrer efface la ligne, le clone et le dépôt nu restent.
            self.assertTrue(self.client.delete("/depot", headers=proprietaire).json()["desenregistre"])
            self.assertIsNone(self.comptes.depot("h"))
            self.assertTrue(est_depot_nu(depots / "h.git"))

    def test_un_non_membre_ne_lit_ni_n_eprouve_ni_ne_scelle(self):
        cle = self.cle("d@exemple.test")
        propose = {"proposition": {"kata": [{"id": "k2", "nom": "Autre"}]}}

        self.assertEqual(self.client.get("/conception", headers=cle).status_code, 403)
        self.assertEqual(self.client.get("/depot", headers=cle).status_code, 403)
        # La vigie, elle, se lit par tout compte connecté — mais pas sans session.
        self.assertEqual(self.client.get("/vigie", headers=cle).status_code, 200)
        self.assertEqual(self.client.get("/vigie").status_code, 401)
        # Sabotage 5 du RFC-010 : la coupe se refuse comme le reste.
        self.assertEqual(
            self.client.post(
                "/conception/coupe", json={"kata": "k1", "cible": "c1"}, headers=cle
            ).status_code,
            403,
        )
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
