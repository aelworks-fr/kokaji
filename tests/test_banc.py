"""Le banc joue un persona et lit ce qui s'est passé (SPECS §5).

La passerelle est remplacée par un double : le banc doit être éprouvable sans
moteur, sinon on ne peut pas éprouver le banc lui-même.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.hds import charger
from kokaji.trempe.banc import Tour, evaluer, jouer, rapport
from kokaji.trempe.banc.checks import RegleInconnue, blocs_etat, checks_du_harness
from kokaji.trempe.banc.persona import PersonaInvalide, charger_tous
from kokaji.trempe.banc.persona import charger as charger_persona

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
    emet_options: true
chaine:
  noeuds:
    - { id: k1, type: kata, nom: K1 }
    - { id: suite, type: externe, nom: Suite }
  aretes:
    - { de: k1, vers: suite, label: fin }
template: template.md
cibles:
  - id: c1
    etat_structure: true
    en_tete: H
    packaging: dossier
trempe:
  vocabulaire_interdit: []
  registre: registre.yaml
  checks_session:
    - id: une-question
      type: regex-par-bloc
      motif: "\\\\?"
      maximum: 1
      message: un tour ne pose qu'une question
    - id: pas-de-verdict
      type: interdit
      motifs: ["tu devrais"]
      message: le kata ne prescrit pas
personas: personas/
corpus: corpus/
"""

PERSONA = """
id: p1
nom: P1
sujet: Un sujet quelconque.
posture: Tu réponds brièvement.
pieges:
  - Tu réponds à côté une fois sur deux.
design_exerce: [d1]
tours_max: 3
"""

ETAT_BON = """```json kokaji_state
{ "kokaji_state": { "champs": { "c2": "fait_etabli" },
  "hypotheses": [ { "id": "1", "libelle": "l", "statut": "en_cours", "confiance": "faible" } ],
  "pret_pour": "suite" } }
```"""

ETAT_MAUVAIS = """```json kokaji_state
{ "kokaji_state": { "champs": { "c2": "etabli", "invente": "fait_etabli" },
  "hypotheses": [ { "id": "1", "libelle": "l", "statut": "peut-etre", "confiance": "sur" } ],
  "pret_pour": "ailleurs" } }
```"""


class DoubleP:
    """Une passerelle qui répond selon un script, sans réseau."""

    def __init__(self, porteur, atelier):
        self.porteur, self.reponse = list(porteur), list(atelier)
        self.appels = []

    def completer(self, modele, messages, temperature=None):
        self.appels.append((modele, len(messages), temperature))
        file = self.porteur if modele == "nu" else self.reponse
        return file.pop(0) if file else "…"


class Bac(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.racine = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        (self.racine / "kata").mkdir()
        (self.racine / "personas").mkdir()
        (self.racine / "corpus").mkdir()
        (self.racine / "template.md").write_text("{{ role }}", encoding="utf-8")
        (self.racine / "registre.yaml").write_text("champs:\n  c1: Un champ\n  c2: Un autre\n", encoding="utf-8")
        (self.racine / "kata" / "k1.yaml").write_text(
            "role: r\nquestions: [q]\nlivrable_structure: [s]\npassage: p\n",
            encoding="utf-8",
        )
        (self.racine / "personas" / "p1.yaml").write_text(PERSONA, encoding="utf-8")
        (self.racine / "harness.yaml").write_text(MANIFEST, encoding="utf-8")
        self.harness = charger(self.racine)
        self.kata = self.harness.kata_par_id("k1")
        self.persona = charger_persona(self.racine / "personas" / "p1.yaml")


class Persona(Bac):
    def test_la_consigne_porte_le_sujet_et_les_pieges(self):
        consigne = self.persona.consigne
        self.assertIn("Un sujet quelconque.", consigne)
        self.assertIn("Tu réponds à côté une fois sur deux.", consigne)
        self.assertIn("Tu es l'utilisateur", consigne)

    def test_refuse_un_persona_incomplet(self):
        (self.racine / "personas" / "casse.yaml").write_text("id: x\n", encoding="utf-8")
        with self.assertRaises(PersonaInvalide) as capture:
            charger_tous(self.racine / "personas")
        self.assertIn("champ(s) absent(s)", str(capture.exception))


class Jouer(Bac):
    def test_deroule_la_session_jusqu_au_plafond_du_persona(self):
        double = DoubleP(["p1", "p2", "p3", "p4"], ["a1", "a2", "a3", "a4"])
        tours, interrompu = jouer(self.persona, "h/k1", "nu", double)

        self.assertIsNone(interrompu)
        self.assertEqual(len(tours), 3)  # tours_max du persona
        self.assertEqual([t.porteur for t in tours], ["p1", "p2", "p3"])
        self.assertEqual([t.reponse for t in tours], ["a1", "a2", "a3"])

    def test_chacun_ne_voit_que_son_propre_echange(self):
        """Le persona ignore la coupe ; le kata ignore la consigne du persona."""
        double = DoubleP(["p1", "p2"], ["a1", "a2"])
        jouer(self.persona, "h/k1", "nu", double, tours_max=2)

        vers_kata = [n for modele, n, _ in double.appels if modele == "h/k1"]
        vers_persona = [n for modele, n, _ in double.appels if modele == "nu"]
        self.assertEqual(vers_kata, [1, 3])  # user, (user+assistant)+user
        self.assertEqual(vers_persona, [2, 4])  # la consigne système en plus

    def test_la_temperature_est_transmise(self):
        double = DoubleP(["p"], ["a"])
        jouer(self.persona, "h/k1", "nu", double, tours_max=1, temperature=0.0)
        self.assertEqual({t for _, _, t in double.appels}, {0.0})

    def test_une_panne_interrompt_sans_perdre_les_tours_joues(self):
        class Cassee(DoubleP):
            def completer(self, modele, messages, temperature=None):
                if len(self.appels) >= 3:
                    from kokaji.trempe.banc import PasserelleInjoignable

                    raise PasserelleInjoignable("coupure")
                return super().completer(modele, messages, temperature)

        tours, interrompu = jouer(self.persona, "h/k1", "nu", Cassee(["p1", "p2"], ["a1"]))
        self.assertEqual(len(tours), 1)
        self.assertIn("coupure", interrompu)


class MaximumZero(unittest.TestCase):
    """Zéro est une valeur, pas une absence — trouvé par le scénario de bout en bout.

    `regle.get("maximum") or 1` transformait un maximum de zéro en un : une
    règle qui dit « aucune occurrence » devenait « au plus une », en silence.
    Le harness croyait interdire, et n'interdisait rien.
    """

    def tour(self, texte: str):
        from kokaji.trempe.banc import Tour

        return [Tour(rang=1, porteur="p", reponse=texte)]

    def test_par_tour_avec_maximum_zero_refuse_la_premiere(self):
        from kokaji.trempe.banc.checks import _regex_par_tour

        regle = {"id": "aucune", "motif": r"^- ", "maximum": 0, "message": "aucune puce"}
        self.assertEqual(len(_regex_par_tour(regle, self.tour("- une puce"))), 1)

    def test_par_bloc_avec_maximum_zero_refuse_le_premier(self):
        from kokaji.trempe.banc.checks import _regex_par_bloc

        regle = {"id": "aucune", "motif": r"\?", "maximum": 0, "message": "aucune question"}
        self.assertEqual(len(_regex_par_bloc(regle, self.tour("Une question ?"))), 1)

    def test_un_maximum_absent_vaut_toujours_un(self):
        """Le défaut historique ne bouge pas : seule l'absence le déclenche."""
        from kokaji.trempe.banc.checks import _regex_par_tour

        regle = {"id": "au-plus-une", "motif": r"^- ", "message": "au plus une"}
        self.assertEqual(len(_regex_par_tour(regle, self.tour("- une puce"))), 0)
        self.assertEqual(len(_regex_par_tour(regle, self.tour("- une\n- deux"))), 1)


class Evaluer(Bac):
    def evaluer(self, *reponses):
        tours = tuple(Tour(rang=i, porteur="p", reponse=r) for i, r in enumerate(reponses, 1))
        return evaluer(self.harness, self.kata, tours)

    def test_session_sans_faute(self):
        self.assertEqual(self.evaluer("Une seule question ?", ETAT_BON), ())

    def test_deux_questions_dans_deux_paragraphes(self):
        constats = self.evaluer("Première question ?\n\nEt une seconde ?")
        self.assertEqual([c.regle for c in constats], ["une-question"])
        self.assertIn("compté : 2", constats[0].message)

    def test_une_question_qui_propose_ses_options_reste_une_question(self):
        self.assertEqual(self.evaluer("Quel manque ?\n- ceci ?\n- cela ?"), ())

    def test_une_question_citee_n_en_fait_pas_une_de_plus(self):
        """Le défaut du compte par symbole : « tu demandes X ? » comptait double."""
        self.assertEqual(
            self.evaluer("Tu me demandes combien de temps ? Une heure ? Deux ?"), ()
        )

    def test_un_bloc_de_code_ne_questionne_pas(self):
        self.assertEqual(self.evaluer("Une question ?\n\n```\nque fait ceci ?\n```"), ())

    def test_check_du_harness_interdit(self):
        constats = self.evaluer("À mon avis tu devrais commencer par là.")
        self.assertEqual([c.regle for c in constats], ["pas-de-verdict"])

    def test_invariants_sur_le_bloc_d_etat(self):
        regles = {c.regle for c in self.evaluer(ETAT_MAUVAIS)}
        self.assertEqual(
            regles, {"etat-champs-declares", "etat-statuts-declares", "etat-passage-declare"}
        )

    def test_bloc_illisible(self):
        constats = self.evaluer("```json kokaji_state\n{ pas du json\n```")
        self.assertIn("illisible", constats[0].message)

    def test_un_type_de_regle_inconnu_est_refuse(self):
        with self.assertRaises(RegleInconnue):
            checks_du_harness(
                type(self.harness)(
                    **{
                        **self.harness.__dict__,
                        "trempe": type(self.harness.trempe)(
                            vocabulaire_interdit=(),
                            registre=self.harness.trempe.registre,
                            checks_session=({"id": "x", "type": "inventé"},),
                        ),
                    }
                ),
                [Tour(1, "p", "a")],
            )


class Options(Bac):
    """RFC-001 — ce que Kokaji impose aux options déclarées."""

    def evaluer(self, *reponses):
        tours = tuple(Tour(rang=i, porteur="p", reponse=r) for i, r in enumerate(reponses, 1))
        return evaluer(self.harness, self.kata, tours)

    def bloc(self, corps):
        return "```json kokaji_state\n{ \"kokaji_state\": " + corps + " }\n```"

    def test_options_et_decision_conformes(self):
        bon = self.bloc(
            '{ "champs": {}, "options": [ { "id": "OPT-1", "libelle": "une piste",'
            ' "noeud": "k1", "statut": "ouverte" } ],'
            ' "decision": { "libelle": "on tranche", "ferme": ["OPT-1"], "ouvre": [] },'
            ' "pret_pour": null }'
        )
        self.assertEqual(self.evaluer(bon), ())

    def test_statut_d_option_hors_taxonomie(self):
        mauvais = self.bloc(
            '{ "champs": {}, "options": [ { "id": "OPT-1", "libelle": "l",'
            ' "noeud": "k1", "statut": "en-suspens" } ], "pret_pour": null }'
        )
        constats = self.evaluer(mauvais)
        self.assertTrue(any("statut d'option hors taxonomie" in c.message for c in constats))

    def test_option_sans_libelle(self):
        """La parade contre Goodhart : une option sans substance est une faute."""
        mauvais = self.bloc(
            '{ "champs": {}, "options": [ { "id": "OPT-1", "libelle": "  ",'
            ' "noeud": "k1", "statut": "ouverte" } ], "pret_pour": null }'
        )
        self.assertTrue(any("sans libellé" in c.message for c in self.evaluer(mauvais)))

    def test_option_hors_chaine(self):
        mauvais = self.bloc(
            '{ "champs": {}, "options": [ { "id": "OPT-1", "libelle": "l",'
            ' "noeud": "ailleurs", "statut": "ouverte" } ], "pret_pour": null }'
        )
        self.assertTrue(any("hors chaîne" in c.message for c in self.evaluer(mauvais)))

    def test_decision_citant_une_option_jamais_declaree(self):
        mauvais = self.bloc(
            '{ "champs": {}, "decision": { "libelle": "on tranche",'
            ' "ferme": ["OPT-9"], "ouvre": [] }, "pret_pour": null }'
        )
        constats = self.evaluer(mauvais)
        self.assertTrue(any("jamais déclarée" in c.message for c in constats))

    def test_une_decision_peut_citer_une_option_d_un_tour_anterieur(self):
        ouverture = self.bloc(
            '{ "champs": {}, "options": [ { "id": "OPT-1", "libelle": "l",'
            ' "noeud": "k1", "statut": "ouverte" } ], "pret_pour": null }'
        )
        coupe = self.bloc(
            '{ "champs": {}, "decision": { "libelle": "on tranche",'
            ' "ferme": ["OPT-1"], "ouvre": [] }, "pret_pour": null }'
        )
        self.assertEqual(self.evaluer(ouverture, coupe), ())


class Juge(Bac):
    """R5.5 — Kokaji fournit le mécanisme, le harness fournit la grille."""

    def setUp(self):
        super().setUp()
        (self.racine / "registre.yaml").write_text(
            "champs:\n  c1: Un champ\n  c2: Un autre\n"
            "design_exerce:\n  d1: La forme tient-elle d1 ?\n  d2: Et d2 ?\n",
            encoding="utf-8",
        )
        self.harness = charger(self.racine)
        self.tours = [
            Tour(1, "p", "un extrait qui existe vraiment"),
            Tour(2, "p", "autre chose de citable ici"),
        ]

    def juger(self, reponses, **kw):
        """`reponses` : une réponse, ou une par variable — le juge est appelé
        une fois par question."""
        from kokaji.trempe.banc import juger

        file = list(reponses) if isinstance(reponses, list) else None

        class Double:
            def completer(self, modele, messages, temperature=None):
                Double.consigne = messages[0]["content"]
                Double.transcript = messages[1]["content"]
                return file.pop(0) if file else reponses

        return juger(self.harness, self.tours, Double(), "juge/x", **kw)

    def bloc(self, entree):
        import json as j
        return "```json\n" + j.dumps(entree) + "\n```"

    def test_la_grille_vient_du_registre(self):
        from kokaji.trempe.banc import grille

        self.assertEqual(set(grille(self.harness)), {"d1", "d2"})

    def test_un_verdict_par_variable(self):
        verdicts = self.juger([
            self.bloc({"variable": "d1", "verdict": "tenue", "tour": 1,
                       "citation": "un extrait qui existe vraiment", "motif": "m"}),
            self.bloc({"variable": "d2", "verdict": "non-tenue", "tour": 2,
                       "citation": "autre chose de citable ici", "motif": "m"}),
        ])
        self.assertEqual([v.variable for v in verdicts], ["d1", "d2"])
        self.assertEqual([v.verdict for v in verdicts], ["tenue", "non-tenue"])
        self.assertEqual(verdicts[0].tour, 1)

    def test_une_citation_introuvable_invalide_le_verdict(self):
        """Une preuve qu'on ne retrouve pas dans l'échange n'est pas une preuve."""
        verdicts = self.juger(self.bloc({
            "variable": "d1", "verdict": "non-tenue", "tour": 1,
            "citation": "une phrase que le kata n'a jamais dite", "motif": "m",
        }), variables=("d1",))
        self.assertEqual(verdicts[0].verdict, "illisible")
        self.assertIn("introuvable", verdicts[0].motif)

    def test_un_bloc_d_etat_n_est_pas_citable(self):
        """Un bloc dit ce que le kata déclare, pas ce qu'il fait."""
        from kokaji.trempe.banc import juger

        class Double:
            transcript = ""
            def completer(self, modele, messages, temperature=None):
                Double.transcript = messages[1]["content"]
                return "{}"

        tours = [Tour(1, "p", "de la prose\n```json kokaji_state\n{\"champs\": {}}\n```")]
        juger(self.harness, tours, Double(), "juge/x", variables=("d1",))
        self.assertIn("de la prose", Double.transcript)
        self.assertNotIn("kokaji_state", Double.transcript)

    def test_la_consigne_cherche_le_manquement(self):
        """Une consigne neutre obtient une approbation uniforme."""
        self.juger(self.bloc({"variable": "d1", "verdict": "tenue", "tour": 1,
                              "citation": "un extrait qui existe vraiment", "motif": "m"}),
                   variables=("d1",))
        from kokaji.trempe.banc.juge import _consigne

        consigne = _consigne("d1", "La forme tient-elle d1 ?")
        self.assertIn("manquement", consigne)
        self.assertIn("échoue", consigne)

    def test_un_manquement_sans_citation_est_rejete(self):
        """Une accusation sans preuve n'est pas une accusation."""
        verdicts = self.juger(self.bloc(
            {"variable": "d1", "verdict": "non-tenue", "tour": 1, "citation": "  ", "motif": "m"}
        ), variables=("d1",))
        self.assertEqual(verdicts[0].verdict, "illisible")
        self.assertIn("sans citation", verdicts[0].motif)

    def test_un_acquittement_ne_demande_pas_de_citation(self):
        """On ne cite pas la preuve d'une absence."""
        verdicts = self.juger(self.bloc(
            {"variable": "d1", "verdict": "tenue", "citation": "", "motif": "cherché, rien trouvé"}
        ), variables=("d1",))
        self.assertEqual(verdicts[0].verdict, "tenue")

    def test_indecidable_ne_demande_pas_de_citation(self):
        """Se taire est une réponse pleine."""
        verdicts = self.juger(self.bloc([
            {"variable": "d1", "verdict": "indecidable", "citation": "", "motif": "pas éprouvé"},
        ][0]))
        self.assertEqual(verdicts[0].verdict, "indecidable")

    def test_un_verdict_hors_grille_est_constate(self):
        verdicts = self.juger(self.bloc([
            {"variable": "d1", "verdict": "excellent", "tour": 1, "citation": "x", "motif": "m"},
        ][0]))
        self.assertEqual(verdicts[0].verdict, "illisible")
        self.assertIn("hors grille", verdicts[0].motif)

    def test_une_variable_oubliee_est_constatee(self):
        verdicts = self.juger(self.bloc({"variable": "autre", "verdict": "tenue", "tour": 1,
                                         "citation": "x", "motif": "m"}), variables=("d1",))
        self.assertEqual(verdicts[0].variable, "d1")
        self.assertEqual(verdicts[0].verdict, "illisible")

    def test_un_juge_qui_repond_n_importe_quoi_ne_fait_pas_tomber_l_evaluation(self):
        verdicts = self.juger("je ne sais pas répondre en JSON")
        self.assertEqual({v.verdict for v in verdicts}, {"illisible"})
        self.assertEqual(len(verdicts), 2)

    def test_on_peut_ne_juger_qu_une_variable(self):
        verdicts = self.juger(
            self.bloc({"variable": "d2", "verdict": "tenue", "tour": 1,
                       "citation": "autre chose de citable ici", "motif": "m"}),
            variables=("d2",),
        )
        self.assertEqual([v.variable for v in verdicts], ["d2"])

    def test_une_variable_hors_registre_est_refusee(self):
        with self.assertRaises(ValueError) as capture:
            self.juger("{}", variables=("inventee",))
        self.assertIn("hors du registre", str(capture.exception))

    def test_le_juge_ne_voit_jamais_la_coupe(self):
        """Il lit l'échange et la question, pas la doctrine qu'il devrait valider."""
        from kokaji.trempe.banc.juge import _consigne

        consigne = _consigne("d1", "La forme tient-elle d1 ?")
        self.assertIn("La forme tient-elle d1 ?", consigne)
        self.assertNotIn("{{", consigne)


class Lecture(Bac):
    def test_les_blocs_sont_extraits(self):
        self.assertEqual(len(blocs_etat(f"texte {ETAT_BON} texte {ETAT_BON}")), 2)

    def test_le_rapport_aligne_les_sessions(self):
        from kokaji.trempe.banc import Resultat

        sortie = rapport(
            [
                Resultat("h", "k1", "p1", "m-a", (Tour(1, "p", ETAT_BON),), ()),
                Resultat("h", "k1", "p1", "m-b", (Tour(1, "p", "q ?\n\nq ?"),),
                         evaluer(self.harness, self.kata, (Tour(1, "p", "q ?\n\nq ?"),))),
            ]
        )
        self.assertIn("m-a", sortie)
        self.assertIn("une-question", sortie)
        self.assertIn("persona", sortie.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
