"""Le versement du journal vers le corpus (SPECS §6).

Le journal de test est purement structurel : aucun nom de domaine (§0).
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.corpus import (
    deja_ailleurs,
    ecartees,
    ecarter,
    lire_journal,
    rafraichir_fiche,
    verser,
)
from kokaji.hds import charger

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
      - k1.c2: fait_etabli
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

IDENTITE = {
    "harness": "h", "kata": "k1", "version_kata": "0.1.0",
    "version_coupe": "abcdef123456", "cible": "c1", "date": "2026-01-01T00:00:00+00:00",
}


def _appel(session, tours, reponse, debut="2026-01-01T00:00:00"):
    messages = [{"role": "system", "content": "LA COUPE"}]
    for rang in range(tours):
        messages.append({"role": "user", "content": f"porteur {rang + 1}"})
        if rang < tours - 1:
            messages.append({"role": "assistant", "content": f"kata {rang + 1}"})
    return {
        "session": session, "identite": dict(IDENTITE), "messages": messages,
        "reponse": reponse, "debut": debut, "fin": debut,
        "moteur": "m", "fournisseur": "f",
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        racine = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        self.racine = racine / "harness"
        for sous in ("kata", "personas", "corpus"):
            (self.racine / sous).mkdir(parents=True)
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text("champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8")
        (self.racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n", encoding="utf-8"
        )
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.racine)

        self.journal = racine / "journal"
        self.journal.mkdir()

    def ecrire(self, appels, jour="2026-01-01"):
        (self.journal / f"{jour}.jsonl").write_text(
            "\n".join(json.dumps(a, ensure_ascii=False) for a in appels) + "\n",
            encoding="utf-8",
        )


class Rafraichir(Bac):
    """La capture ne possède pas toute la fiche — NOTE-0021.

    Elle la réécrivait entière depuis son gabarit à chaque passage. Ce qu'un
    autre geste y avait mis disparaissait sans que rien ne le montre : la
    fiche restait bien formée.
    """

    def fiche(self) -> Path:
        return next(self.harness.corpus.glob("CAS-*")) / "fiche.md"

    def premier_passage(self):
        self.ecrire([_appel("s-1", 1, "r1")])
        verser(self.harness, self.journal)
        return self.fiche()

    def second_passage(self):
        self.ecrire([_appel("s-1", 1, "r1"), _appel("s-1", 1, "r2")])
        return verser(self.harness, self.journal, rafraichir=True)

    def test_la_visibilite_reglee_par_le_praticien_survit(self):
        """RFC-004 §5 : verser un ha est le geste du praticien, pas de la veille."""
        fiche = self.premier_passage()
        fiche.write_text(
            fiche.read_text(encoding="utf-8").replace("visibilite: privee", "visibilite: versee"),
            encoding="utf-8",
        )
        self.second_passage()
        self.assertIn("visibilite: versee", fiche.read_text(encoding="utf-8"))

    def test_une_cle_ajoutee_apres_coup_survit(self):
        """La marque de ré-abstraction en est une — RFC-002 §7.2."""
        fiche = self.premier_passage()
        fiche.write_text(
            fiche.read_text(encoding="utf-8").replace(
                "statut: brut", "statut: brut\netat_reabstrait: true"
            ),
            encoding="utf-8",
        )
        self.second_passage()
        self.assertIn("etat_reabstrait: true", fiche.read_text(encoding="utf-8"))

    def test_le_corps_ajoute_survit(self):
        """La réserve qui dit qu'un état n'a pas été observé vit dans le corps."""
        fiche = self.premier_passage()
        fiche.write_text(
            fiche.read_text(encoding="utf-8") + "\n- **L'état n'a pas été observé.**\n",
            encoding="utf-8",
        )
        self.second_passage()
        self.assertIn("n'a pas été observé", fiche.read_text(encoding="utf-8"))

    def test_ce_que_la_capture_possede_est_bien_mis_a_jour(self):
        """Rien de tout cela ne doit figer les compteurs d'une conversation vivante."""
        fiche = self.premier_passage()
        self.assertIn("tours: 1", fiche.read_text(encoding="utf-8"))
        self.second_passage()
        self.assertIn("tours: 2", fiche.read_text(encoding="utf-8"))

    def test_une_fiche_illisible_se_remplace_et_ne_bloque_pas(self):
        """Perdre une annotation est un accident ; perdre la capture, une panne."""
        garde = rafraichir_fiche("pas de frontmatter du tout", "---\na: 1\n---\n\ncorps\n")
        self.assertIn("a: 1", garde)


class Fils(Bac):
    """Ce que la capture lit dans le premier tour humain — que chaque appel rejoue.

    Un appel d'interface du chat (titre, étiquettes, questions suivantes) n'est
    pas une pratique : il est marqué. Et deux sessions qui partagent le même
    premier tour sont le même fil, quel que soit le kata : même racine.
    """

    def _fiches(self) -> dict[str, str]:
        fiches = {}
        for dossier in self.harness.corpus.glob("CAS-*"):
            texte = (dossier / "fiche.md").read_text(encoding="utf-8")
            fiches[texte.split("session `")[1].split("`")[0]] = texte
        return fiches

    @staticmethod
    def _champ(fiche: str, cle: str) -> str | None:
        m = re.search(rf"(?m)^{cle}: ?(.*)$", fiche)
        return m.group(1).strip() if m else None

    def test_un_appel_d_interface_est_marque_une_pratique_non(self):
        a = _appel("s-1", 1, "un titre")
        a["messages"][1]["content"] = "### Task:\nGenerate a concise title summarizing the chat history."
        b = _appel("s-2", 1, "une réponse")
        b["messages"][1]["content"] = "J'ai un sujet arrivant autour du pilotage."
        self.ecrire([a, b])
        verser(self.harness, self.journal)
        fiches = self._fiches()
        self.assertEqual(self._champ(fiches["s-1"], "interface"), "true")
        self.assertEqual(self._champ(fiches["s-2"], "interface"), "false")

    def test_meme_premier_tour_meme_racine(self):
        a, b, c = _appel("s-1", 1, "r1"), _appel("s-2", 2, "r2"), _appel("s-3", 1, "r3")
        for appel in (a, b):
            appel["messages"][1]["content"] = "J'ai un  sujet arrivant\nautour du pilotage."
        c["messages"][1]["content"] = "Autre chose."
        self.ecrire([a, b, c])
        verser(self.harness, self.journal)
        fiches = self._fiches()
        racine = self._champ(fiches["s-1"], "racine")
        self.assertEqual(racine, self._champ(fiches["s-2"], "racine"))
        self.assertNotEqual(racine, self._champ(fiches["s-3"], "racine"))
        self.assertEqual(len(racine.strip('"')), 12)
        self.assertEqual(
            self._champ(fiches["s-1"], "amorce"), '"J\'ai un sujet arrivant autour du pilotage."'
        )

    def test_la_marque_se_pose_au_rafraichissement(self):
        """Les ha déjà là reçoivent la marque au passage suivant : c'est la capture qui la possède."""
        a = _appel("s-1", 1, "r1")
        a["messages"][1]["content"] = "### Task:\nGenerate 1-3 broad tags."
        self.ecrire([a])
        verser(self.harness, self.journal)
        fiche = next(self.harness.corpus.glob("CAS-*")) / "fiche.md"
        # Une fiche d'avant la marque : on l'efface, comme si elle n'avait jamais existé.
        texte = re.sub(r"(?m)^(interface|racine|amorce): .*\n", "", fiche.read_text(encoding="utf-8"))
        fiche.write_text(texte, encoding="utf-8")
        self.assertNotIn("interface:", fiche.read_text(encoding="utf-8"))
        verser(self.harness, self.journal, rafraichir=True)
        self.assertIn("interface: true", fiche.read_text(encoding="utf-8"))


class Raison(unittest.TestCase):
    """Le fichier des écartés est la seule trace qui restera de la décision."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.corpus = Path(self._tmp.name)

    def test_la_raison_donnee_est_celle_qui_est_ecrite(self):
        ecarter(self.corpus, "s-1", "double avec l'autre corpus", "2026-01-01T00:00:00")
        ligne = (self.corpus / ".ecartes.jsonl").read_text(encoding="utf-8")
        self.assertIn("double avec l'autre corpus", ligne)


class DeuxCorpus(Bac):
    """Une conversation n'a eu lieu qu'une fois — NOTE-0019.

    Deux corpus qui se recouvrent font de toute addition un compte faux, et
    rien sur le disque ne dit qu'un ha est le double d'un autre.
    """

    def setUp(self):
        super().setUp()
        for nom in ("reel", "essai"):
            (self.racine / "corpus" / nom).mkdir(parents=True)
        (self.racine / "harness.yaml").write_text(
            MANIFEST.replace(
                "corpus: corpus/",
                "corpus:\n"
                "  reel:\n"
                "    chemin: corpus/reel/\n"
                "    cles: [une-cle]\n"
                "  essai:\n"
                "    chemin: corpus/essai/\n",
            ),
            encoding="utf-8",
        )
        self.harness = charger(self.racine)
        self.reel = self.harness.corpus_par_nom("reel").chemin
        self.essai = self.harness.corpus_par_nom("essai").chemin

    def test_une_session_versee_ici_ne_l_est_plus_la(self):
        self.ecrire([_appel("s-1", 1, "r1")])
        verser(self.harness, self.journal, corpus=self.reel)

        ensuite = verser(self.harness, self.journal, corpus=self.essai)
        self.assertEqual(ensuite.ha, [])
        self.assertEqual(list(self.essai.glob("CAS-*")), [])

    def test_le_refus_est_dit_et_nomme_ou_elle_est(self):
        """Un saut silencieux se lirait « tout est à jour » : il ne l'est pas."""
        self.ecrire([_appel("s-1", 1, "r1")])
        premier = verser(self.harness, self.journal, corpus=self.reel)

        ensuite = verser(self.harness, self.journal, corpus=self.essai)
        self.assertEqual(ensuite.doubles, {"s-1": premier.ha[0].dossier})

    def test_un_double_deja_sur_le_disque_reste_rafraichi(self):
        """Figer une conversation vivante ajouterait une perte à une redite.

        L'état de départ est celui de l'Atelier : les deux copies existent
        déjà, parce que le partage par clés a été déclaré après coup.
        """
        self.ecrire([_appel("s-1", 1, "r1")])
        ici = verser(self.harness, self.journal, corpus=self.reel).ha[0]
        jumeau = self.essai / "CAS-0001-copie"
        jumeau.mkdir(parents=True)
        (jumeau / "fiche.md").write_text(
            "---\nstatut: brut\n---\n\nsession `s-1`.\n", encoding="utf-8"
        )

        self.ecrire([_appel("s-1", 1, "r1"), _appel("s-1", 1, "r2")])
        encore = verser(self.harness, self.journal, corpus=self.reel, rafraichir=True)
        self.assertEqual([h.tours for h in encore.ha], [2])
        self.assertEqual(encore.ha[0].dossier, ici.dossier)
        # Rafraîchi, et dit quand même : le double ne disparaît pas du rapport
        # parce qu'on a laissé passer l'écriture.
        self.assertEqual(encore.doubles, {"s-1": jumeau})

    def test_le_double_est_signale_mais_jamais_efface(self):
        """Effacer un ha est une décision humaine (R7.3) — pas une réparation."""
        self.ecrire([_appel("s-1", 1, "r1")])
        premier = verser(self.harness, self.journal, corpus=self.reel).ha[0]
        verser(self.harness, self.journal, corpus=self.essai)
        self.assertTrue((premier.dossier / "fiche.md").is_file())

    def test_un_corpus_ne_se_voit_pas_lui_meme_en_double(self):
        self.ecrire([_appel("s-1", 1, "r1")])
        verser(self.harness, self.journal, corpus=self.reel)
        self.assertEqual(deja_ailleurs(self.harness, self.reel), {})

    def test_sans_second_corpus_rien_ne_change(self):
        """Le harness à corpus unique ne paie pas ce contrôle."""
        self.ecrire([_appel("s-1", 1, "r1")])
        verser(self.harness, self.journal, corpus=self.reel)
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        seul = charger(self.racine)
        self.assertEqual(deja_ailleurs(seul, seul.corpus), {})


class Verser(Bac):
    def test_un_ha_par_session(self):
        self.ecrire([
            _appel("s-1", 1, "r1"), _appel("s-1", 2, "r2"),
            _appel("s-2", 1, "autre"),
        ])
        verses = verser(self.harness, self.journal).ha

        self.assertEqual([h.identifiant for h in verses], ["CAS-0001", "CAS-0002"])
        self.assertEqual(verses[0].tours, 2)
        for ha in verses:
            for fichier in ("fiche.md", "transcript.md", "sortie.md", "materiau/coupe.md"):
                self.assertTrue((ha.dossier / fichier).is_file(), fichier)

    def test_le_ha_nait_brut(self):
        """R7.3 — la capture n'est jamais conditionnelle, l'annotation est humaine."""
        self.ecrire([_appel("s-1", 1, "r1")])
        fiche = verser(self.harness, self.journal).ha[0].dossier / "fiche.md"
        texte = fiche.read_text(encoding="utf-8")

        self.assertIn("statut: brut", texte)
        self.assertIn("design_exerce: []", texte)
        self.assertIn("À renseigner", texte)

    def test_le_materiau_porte_la_coupe_injectee(self):
        self.ecrire([_appel("s-1", 1, "r1")])
        materiau = verser(self.harness, self.journal).ha[0].dossier / "materiau" / "coupe.md"
        self.assertEqual(materiau.read_text(encoding="utf-8"), "LA COUPE")

    def test_les_blocs_d_etat_sont_comptes(self):
        self.ecrire([_appel("s-1", 1, "```json kokaji_state\n{}\n```")])
        self.assertEqual(verser(self.harness, self.journal).ha[0].blocs, 1)

    def test_une_session_deja_versee_ne_l_est_pas_deux_fois(self):
        self.ecrire([_appel("s-1", 1, "r1")])
        verser(self.harness, self.journal)
        self.assertEqual(verser(self.harness, self.journal).ha, [])

    def test_on_peut_ne_verser_qu_une_session(self):
        self.ecrire([_appel("s-1", 1, "r1"), _appel("s-2", 1, "r2")])
        verses = verser(self.harness, self.journal, sessions=("s-2",)).ha
        self.assertEqual(len(verses), 1)
        self.assertEqual(verses[0].session, "s-2")

    def test_les_autres_harness_sont_ignores(self):
        etranger = _appel("s-x", 1, "r")
        etranger["identite"]["harness"] = "autre"
        self.ecrire([etranger])
        self.assertEqual(verser(self.harness, self.journal).ha, [])

    def test_une_session_ecartee_n_est_pas_versee(self):
        """Le journal ne perd rien : écarter un ha doit se déclarer, pas se supprimer."""
        self.ecrire([_appel("s-1", 1, "r1"), _appel("s-2", 1, "r2")])
        ecarter(self.harness.corpus, "s-1", "essai", "2026-01-01T00:00:00")

        verses = verser(self.harness, self.journal).ha
        self.assertEqual([h.session for h in verses], ["s-2"])

    def test_une_session_ne_se_declare_ecartee_qu_une_fois(self):
        ecarter(self.harness.corpus, "s-1", "premier", "2026-01-01T00:00:00")
        ecarter(self.harness.corpus, "s-1", "second", "2026-01-02T00:00:00")

        lignes = (self.harness.corpus / ".ecartes.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lignes), 1)
        self.assertIn("premier", lignes[0])
        self.assertEqual(ecartees(self.harness.corpus), {"s-1"})

    def test_une_ligne_illisible_ne_fait_pas_tomber_la_lecture(self):
        (self.journal / "2026-01-01.jsonl").write_text(
            json.dumps(_appel("s-1", 1, "r1")) + "\npas du json\n", encoding="utf-8"
        )
        self.assertEqual(len(lire_journal(self.journal)), 1)


if __name__ == "__main__":
    unittest.main()
