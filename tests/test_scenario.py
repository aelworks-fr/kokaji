"""Deux scénarios d'usage, de bout en bout — RFC-006 et SPECS §7.

Les autres fichiers éprouvent des pièces. Celui-ci suit **ce qu'une personne
fait**, dans l'ordre où elle le fait, et ne s'arrête qu'au bout : semer un
harness, lui ajouter une étape, déclarer ses données et ses règles de trempe,
le forger, le pratiquer sur les quatre natures de sujet, puis l'archiver.

Ce qu'un tel scénario attrape et qu'un test de pièce ne peut pas : les
enchaînements. La journée du 16 août a montré que presque tous les défauts se
révélaient au **premier usage réel** d'un geste, jamais à la lecture — un
scénario est la façon la moins coûteuse de provoquer ce premier usage.

Aucun réseau : la pratique est écrite au journal comme le Dojo l'écrirait, et
c'est la vraie veille qui la capture.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml

from kokaji.comptes import Comptes
from kokaji.conception import Proposition, juger, sceller
from kokaji.forge import forger_harness
from kokaji.hds import charger
from kokaji.middleware import veiller
from kokaji.naissance import scelle, semer

SECRET_DU_CHAT = "un-secret-partage"


def jeton_du_chat(email: str) -> str:
    """Le JWT signé que le chat transmet — RFC-005 §3.3."""
    import base64
    import hashlib
    import hmac
    import time

    def b64(donnees: dict) -> str:
        brut = json.dumps(donnees, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(brut).decode().rstrip("=")

    entete, charge = b64({"alg": "HS256", "typ": "JWT"}), b64(
        {"email": email, "exp": int(time.time()) + 300}
    )
    signature = hmac.new(
        SECRET_DU_CHAT.encode(), f"{entete}.{charge}".encode(), hashlib.sha256
    ).digest()
    return f"{entete}.{charge}.{base64.urlsafe_b64encode(signature).decode().rstrip('=')}"


NATURES = {
    "evident": "simple",
    "analysable": "compliqué",
    "emergent": "complexe",
    "urgence": "chaotique",
}


def bloc(champs: dict, nature: str | None = None, hypotheses=(), options=()) -> str:
    """Un bloc d'état, tel qu'un kata l'émet au fil de la conversation."""
    etat: dict = {"champs": champs, "pret_pour": None}
    if nature:
        etat["nature"] = {"valeur": nature, "confiance": "moyen"}
    if hypotheses:
        etat["hypotheses"] = list(hypotheses)
    if options:
        etat["options"] = list(options)
    return "```json kokaji_state\n" + json.dumps({"kokaji_state": etat}) + "\n```"


class DeLaSemenceALaPratique(unittest.TestCase):
    """Scénario 1 — tout ce qu'il faut faire avant d'avoir observé quoi que ce soit."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.journal = self.racine / "journal"
        self.journal.mkdir()

    def manifest(self, harness) -> dict:
        return yaml.safe_load((harness.racine / "harness.yaml").read_text(encoding="utf-8"))

    def sceller(self, harness, proposition, motif: str):
        return sceller(harness.racine, proposition, auteur="scénario", motif=motif)

    def journaliser(self, harness_id: str, kata: str, session: str, reponses: list[str]):
        """Écrit une conversation au journal, comme la passerelle le ferait."""
        lignes = []
        for rang, reponse in enumerate(reponses, 1):
            lignes.append(json.dumps({
                "statut": "abouti",
                "id_appel": f"{session}-{rang}",
                "session": session,
                "debut": f"2026-03-0{rang} 10:00:00+00:00",
                "fin": f"2026-03-0{rang} 10:00:0{rang}+00:00",
                "moteur": "un-moteur",
                "fournisseur": "un-fournisseur",
                "identite": {
                    "harness": harness_id, "kata": kata, "version_kata": "0.1.0",
                    "version_coupe": "abcdef", "cible": "sobre",
                    "date": f"2026-03-0{rang} 10:00:00+00:00",
                },
                "messages": [{"role": "user", "content": f"porteur {rang}"}],
                "reponse": reponse,
                "usage": {},
            }, ensure_ascii=False))
        (self.journal / "2026-03-01.jsonl").write_text("\n".join(lignes) + "\n", encoding="utf-8")

    def test_le_scenario_entier(self):
        # --- 1. semer -------------------------------------------------------
        with self.subTest("semer"):
            harness = semer(self.racine / "harness", "essai", "Harness d'essai")
            self.assertEqual([k.id for k in harness.kata], ["premiere-etape"])
            self.assertFalse(scelle(harness), "un harness neuf est un brouillon")

        # --- 2. ajouter une étape -------------------------------------------
        with self.subTest("ajouter une étape"):
            ajout = Proposition(kata=[{
                "id": "verdict", "nom": "Rendre un verdict", "livrable": "Un verdict",
                "amont": ["premiere-etape"],
                "herite": [{"premiere-etape.sujet": "fait_etabli"}],
                "produit": [{"verdict.decision": "fait_etabli"}],
            }])
            self.assertTrue(juger(harness.racine, ajout).tient)
            self.sceller(harness, ajout, "une étape de plus")
            harness = charger(harness.racine)
            self.assertEqual([k.id for k in harness.kata], ["premiere-etape", "verdict"])

        with self.subTest("la chaîne, la source et le registre ont suivi"):
            noeuds = {n.id for n in harness.chaine.noeuds}
            self.assertIn("verdict", noeuds)
            self.assertTrue((harness.racine / "kata" / "verdict.yaml").is_file())
            registre = yaml.safe_load(
                (harness.racine / "registre.yaml").read_text(encoding="utf-8")
            )
            self.assertIn("verdict", registre["kata"])
            self.assertIn("Un verdict", registre["livrables"])
            self.assertIn("decision", registre["champs"])

        # --- 3. les trois types de trempe de session ------------------------
        with self.subTest("configurer la trempe"):
            regles = Proposition(trempe={
                "vocabulaire_interdit": ["mot-proscrit"],
                "checks_session": [
                    {"id": "une-question", "type": "regex-par-bloc", "motif": r"\?",
                     "maximum": 1, "message": "un tour ne pose qu'une question"},
                    {"id": "pas-de-liste", "type": "regex-par-tour", "motif": r"^- ",
                     "maximum": 0, "message": "pas de liste à puces"},
                    {"id": "pas-de-prescription", "type": "interdit",
                     "motifs": ["tu devrais"], "message": "on fait préciser, on ne prescrit pas"},
                ],
            })
            self.assertTrue(juger(harness.racine, regles).tient)
            self.sceller(harness, regles, "les règles de conduite")
            harness = charger(harness.racine)
            self.assertEqual(
                [c["type"] for c in harness.trempe.checks_session],
                ["regex-par-bloc", "regex-par-tour", "interdit"],
            )

        # --- 4. forger ------------------------------------------------------
        with self.subTest("forger et tremper"):
            resultat = forger_harness(harness, sortie=self.racine / "coupes", trempe=True)
            self.assertEqual(len(resultat.coupes), 2, "une coupe par kata")

        # --- 5. pratiquer sur les quatre natures ----------------------------
        for nature in NATURES:
            with self.subTest(f"pratiquer un sujet {nature}"):
                session = f"s-{nature}"
                self.journaliser(harness.id, "premiere-etape", session, [
                    bloc({"sujet": "en_chantier"}, nature=nature),
                    bloc(
                        {"sujet": "fait_etabli"}, nature=nature,
                        hypotheses=[{"enonce": f"sujet {nature}", "statut": "validee",
                                     "confiance": "moyen"}],
                    ),
                ])
                veilles = veiller(harness, self.journal, repos=0, maintenant="2026-03-09T10:00:00+00:00").veilles
                rendu = {v.session: v for v in veilles}
                self.assertIn(session, rendu, f"le ha du sujet {nature} est capturé")
                self.assertEqual(rendu[session].carre, "conforme", f"carré du sujet {nature}")
                self.assertEqual(rendu[session].fautes, 0, f"état du sujet {nature}")

        # --- 6. la trempe attrape ce qu'elle doit attraper -------------------
        with self.subTest("les règles de session refusent"):
            from kokaji.trempe.banc import Tour
            from kokaji.trempe.banc.checks import checks_du_harness

            # Deux questions dans **deux paragraphes** : la règle compte les
            # blocs, pas les points d'interrogation — une question qui propose
            # ses options en ligne reste une question.
            tours = [Tour(
                rang=1, porteur="p",
                reponse="Une question ?\n\nUne autre ?\n\n- une puce\n\ntu devrais partir",
            )]
            attrapes = {c.regle for c in checks_du_harness(harness, tours)}
            self.assertEqual(
                attrapes, {"une-question", "pas-de-liste", "pas-de-prescription"}
            )


class Archiver(unittest.TestCase):
    """Scénario 2 — retirer un harness du service sans rien détruire."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.harness = semer(self.racine / "harness", "essai", "Harness d'essai")

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.qui = self.comptes.creer_utilisateur(
            "Un", "un@exemple.test", "un-mot-de-passe-assez-long"
        )
        self.comptes.enregistrer_harness("essai", self.qui.id)

    def test_archiver_puis_defaire(self):
        with self.subTest("il sert avant"):
            self.assertIsNone(self.comptes.archive_le("essai"))
            self.assertEqual(self.comptes.harness_courant(self.qui.id), "essai")

        with self.subTest("archiver le date"):
            le = self.comptes.archiver("essai")
            self.assertEqual(self.comptes.archive_le("essai"), le)

        with self.subTest("rien n'est détruit"):
            self.assertTrue(self.harness.racine.is_dir())
            self.assertTrue((self.harness.racine / "harness.yaml").is_file())
            for corpus in self.harness.corpus_nommes:
                self.assertTrue(corpus.chemin.is_dir())

        with self.subTest("et l'archivage se défait"):
            self.comptes.desarchiver("essai")
            self.assertIsNone(self.comptes.archive_le("essai"))


if __name__ == "__main__":
    unittest.main()


class PasserelleDePapier:
    """Une passerelle qui répond et **note ce qu'on lui a demandé**.

    Un double en mémoire ne suffirait pas ici : ce qu'on veut éprouver est
    précisément que le service *appelle* la passerelle au bon moment, avec le
    bon corps. On monte donc un vrai serveur HTTP, sur un port libre — le
    scénario traverse la même plomberie qu'en service, et rien ne sort de la
    machine.
    """

    def __init__(self):
        import http.server
        import threading

        self.recu: list[tuple[str, dict | None]] = []
        self.modeles: list[str] = []
        self.autorises: list[str] = []
        papier = self

        class Poignee(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _corps(self):
                taille = int(self.headers.get("content-length") or 0)
                return json.loads(self.rfile.read(taille) or b"{}") if taille else None

            def _rendre(self, charge):
                brut = json.dumps(charge).encode()
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.send_header("content-length", str(len(brut)))
                self.end_headers()
                self.wfile.write(brut)

            def do_GET(self):
                papier.recu.append((self.path.split("?")[0], None))
                if self.path.startswith("/model/info"):
                    return self._rendre({"data": [{"model_name": n} for n in papier.modeles]})
                return self._rendre({"info": {"models": papier.autorises}})

            def do_POST(self):
                corps = self._corps()
                papier.recu.append((self.path, corps))
                if self.path == "/model/new":
                    papier.modeles.append(corps["model_name"])
                elif self.path == "/key/update":
                    papier.autorises = list(corps.get("models") or [])
                elif self.path.endswith("/chat/completions"):
                    dit = getattr(papier, "prochaine", "dit")
                    if hasattr(papier, "journaliser"):
                        papier.journaliser(corps)
                    return self._rendre(
                        {"choices": [{"message": {"role": "assistant", "content": dit}}]}
                    )
                return self._rendre({})

        self.serveur = http.server.HTTPServer(("127.0.0.1", 0), Poignee)
        self.base = f"http://127.0.0.1:{self.serveur.server_port}"
        threading.Thread(target=self.serveur.serve_forever, daemon=True).start()

    def fermer(self):
        self.serveur.shutdown()

    def appels(self, chemin: str) -> list:
        return [corps for url, corps in self.recu if url == chemin]


class PasserelleQuiJournalise(PasserelleDePapier):
    """La passerelle de papier, qui inscrit aussi ce qu'elle sert au journal.

    Elle tient la part des crochets du Dojo qui compte pour la veille : lire
    `<harness>/<kata>` dans le nom du modèle, et poser cette identité sur la
    ligne. Sans elle, le journal existerait sans que rien ne s'y rattache.
    """

    def __init__(self, journal: Path):
        self.journal = journal
        self.prochaine = "dit"
        super().__init__()

    def repondra(self, texte: str) -> None:
        self.prochaine = texte

    def journaliser(self, corps: dict) -> None:
        reference, _, cible = str(corps.get("model") or "").partition("@")
        harness, _, kata = reference.partition("/")
        rang = len(self.recu)
        ligne = {
            "statut": "abouti",
            "id_appel": f"appel-{rang}",
            "session": "s-du-chat",
            "debut": f"2026-04-01 10:00:0{rang}+00:00",
            "fin": f"2026-04-01 10:00:0{rang}+00:00",
            "moteur": "un/moteur",
            "fournisseur": "un-fournisseur",
            "identite": {
                "harness": harness, "kata": kata, "version_kata": "0.1.0",
                "version_coupe": "abcdef", "cible": cible or "sobre",
                "date": "2026-04-01 10:00:00+00:00",
            },
            "messages": corps.get("messages") or [],
            "reponse": self.prochaine,
            "usage": {},
        }
        with (self.journal / "conversation.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")


class DeLaDefinitionAuChat(unittest.TestCase):
    """Scénario 3 — ce qui se passe entre un scellement et une conversation.

    Le §7.1 du RFC-006 promet qu'après scellement « le chat offre ses kata ».
    Ce scénario le tient de bout en bout : la définition est scellée, ses coupes
    forgées, ses modèles déclarés à la passerelle, son autorisation publiée — et
    la complétion passe.
    """

    def setUp(self):
        import os

        from fastapi.testclient import TestClient

        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous
        from kokaji.middleware.chat import Passerelle

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        (self.racine / "journal").mkdir()

        semer(self.racine / "harness", "essai", "Harness d'essai")
        semer(self.racine / "harness", "voisin", "Harness voisin")

        self.papier = PasserelleDePapier()
        self.addCleanup(self.papier.fermer)

        (self.racine / "moteurs.yaml").write_text(
            "defaut:\n  model: un/moteur\n  api_key: os.environ/CLE\npar_modele: {}\n",
            encoding="utf-8",
        )
        reglages = {
            "KOKAJI_PASSERELLE_URL": self.papier.base,
            "LITELLM_MASTER_KEY": "maitre",
            "KOKAJI_PASSERELLE_CLE": "sk-appelante",
            "KOKAJI_MOTEURS": str(self.racine / "moteurs.yaml"),
            "KOKAJI_COUPES": str(self.racine / "coupes"),
            "KOKAJI_HARNESS": str(self.racine / "harness"),
            "KOKAJI_MODELES_NUS": "nu/persona",
        }
        for cle, valeur in reglages.items():
            ancien = os.environ.get(cle)
            os.environ[cle] = valeur
            self.addCleanup(
                lambda c=cle, a=ancien: os.environ.__setitem__(c, a)
                if a is not None
                else os.environ.pop(c, None)
            )

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.qui = self.comptes.creer_utilisateur(
            "Un", "un@exemple.test", "un-mot-de-passe-assez-long"
        )
        self.comptes.enregistrer_harness("essai", self.qui.id)
        self.comptes.enregistrer_harness("voisin", self.qui.id)
        self.comptes.choisir_harness(self.qui.id, "essai")

        charges, _ = charger_valides(self.racine / "harness")
        self.client = TestClient(creer_tous(
            charges, self.racine / "journal", self.comptes,
            secret_chat=SECRET_DU_CHAT,
            passerelle=Passerelle(self.papier.base, "sk-appelante", frozenset({"nu/persona"})),
        ))

    def signe(self, email: str = "un@exemple.test") -> dict:
        return {"X-OpenWebUI-User-Jwt": jeton_du_chat(email)}

    def test_le_scenario_entier(self):
        with self.subTest("le chat n'offre que les kata du harness courant"):
            vu = self.client.get("/v1/models", headers=self.signe()).json()
            self.assertEqual([m["id"] for m in vu["data"]], ["essai/premiere-etape"])
            self.assertEqual(vu["data"][0]["name"], "Première étape")

        with self.subTest("sans identité signée, rien n'est servi"):
            self.assertEqual(self.client.get("/v1/models").status_code, 401)

        with self.subTest("le kata du voisin est refusé au relais"):
            refus = self.client.post(
                "/v1/chat/completions",
                json={"model": "voisin/premiere-etape", "messages": []},
                headers=self.signe(),
            )
            self.assertEqual(refus.status_code, 403)

        with self.subTest("sceller forge et publie"):
            trace = self.client.post(
                "/conception/scellement",
                json={"proposition": {}, "auteur": "scénario", "motif": "arrêt"},
                headers=self.signe(),
            ).json()
            self.assertTrue(trace["coupes"]["forgees"], trace["coupes"])
            self.assertTrue(trace["passerelle"]["publie"], trace["passerelle"])

        with self.subTest("la passerelle sait router les kata scellés"):
            declares = {c["model_name"] for c in self.papier.appels("/model/new")}
            self.assertEqual(
                declares, {"essai/premiere-etape", "essai/premiere-etape@sobre"}
            )
            self.assertEqual(
                self.papier.appels("/model/new")[0]["litellm_params"]["model"], "un/moteur"
            )

        with self.subTest("et sait qui a le droit de les appeler"):
            autorises = self.papier.appels("/key/update")[-1]["models"]
            self.assertIn("essai/premiere-etape", autorises)
            self.assertIn("voisin/premiere-etape", autorises)
            self.assertIn("nu/persona", autorises, "les modèles nus restent autorisés")

        with self.subTest("la complétion passe jusqu'au moteur"):
            rendu = self.client.post(
                "/v1/chat/completions",
                json={"model": "essai/premiere-etape", "messages": [{"role": "user", "content": "x"}]},
                headers=self.signe(),
            )
            self.assertEqual(rendu.status_code, 200, rendu.text)
            self.assertEqual(rendu.json()["choices"][0]["message"]["content"], "dit")

        with self.subTest("un harness archivé n'offre plus rien"):
            self.comptes.archiver("essai")
            vu = self.client.get("/v1/models", headers=self.signe()).json()
            self.assertEqual(vu["data"], [])


class DuChatAuCarre(unittest.TestCase):
    """Scénario 4 — la boucle entière, d'un appel du chat à un ha observé.

    Les trois premiers scénarios s'arrêtent chacun à une frontière : l'un écrit
    le journal à la main, l'autre s'arrête à la complétion. Celui-ci les relie —
    une conversation part du chat, traverse Kokaji, atteint la passerelle,
    revient, et **la veille la ramasse**. C'est le seul qui dise que la chaîne
    tient d'un bout à l'autre.

    La passerelle de papier joue ici le rôle des deux crochets du Dojo : lire
    `<harness>/<kata>` dans le nom du modèle, et inscrire l'appel au journal
    avec son identité de ha. C'est une **redite assumée** de
    `dojo/litellm/hooks/` — ces crochets vivent dans la passerelle, pas dans
    Kokaji, et rien ici ne peut les importer. Ce que le scénario éprouve n'est
    donc pas leur code, mais le **contrat** qu'ils tiennent : sans `identite`
    sur la ligne, la veille ne ramasse rien.
    """

    def setUp(self):
        import os

        from fastapi.testclient import TestClient

        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous
        from kokaji.middleware.chat import Passerelle

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.journal = self.racine / "journal"
        self.journal.mkdir()

        self.harness = semer(self.racine / "harness", "essai", "Harness d'essai")
        self.papier = PasserelleQuiJournalise(self.journal)
        self.addCleanup(self.papier.fermer)

        for cle in ("KOKAJI_PASSERELLE_URL", "KOKAJI_MOTEURS", "KOKAJI_COUPES"):
            ancien = os.environ.pop(cle, None)
            self.addCleanup(
                lambda c=cle, a=ancien: os.environ.__setitem__(c, a) if a is not None else None
            )

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        qui = self.comptes.creer_utilisateur(
            "Un", "un@exemple.test", "un-mot-de-passe-assez-long"
        )
        self.comptes.enregistrer_harness("essai", qui.id)

        charges, _ = charger_valides(self.racine / "harness")
        self.client = TestClient(creer_tous(
            charges, self.journal, self.comptes,
            secret_chat=SECRET_DU_CHAT,
            passerelle=Passerelle(self.papier.base, "sk-appelante"),
        ))

    def parler(self, contenu: str):
        return self.client.post(
            "/v1/chat/completions",
            json={"model": "essai/premiere-etape",
                  "messages": [{"role": "user", "content": contenu}]},
            headers={"X-OpenWebUI-User-Jwt": jeton_du_chat("un@exemple.test")},
        )

    def test_la_boucle_entiere(self):
        with self.subTest("le chat offre le kata"):
            vu = self.client.get(
                "/v1/models",
                headers={"X-OpenWebUI-User-Jwt": jeton_du_chat("un@exemple.test")},
            ).json()
            self.assertEqual([m["id"] for m in vu["data"]], ["essai/premiere-etape"])

        with self.subTest("deux tours de conversation"):
            self.papier.repondra(bloc({"sujet": "en_chantier"}, nature="analysable"))
            self.assertEqual(self.parler("de quoi s'agit-il").status_code, 200)
            self.papier.repondra(bloc({"sujet": "fait_etabli"}, nature="analysable"))
            self.assertEqual(self.parler("voilà").status_code, 200)

        with self.subTest("le journal porte l'identité de ha"):
            lignes = [
                json.loads(l)
                for l in (self.journal / "conversation.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if l.strip()
            ]
            self.assertEqual(len(lignes), 2)
            self.assertEqual(lignes[0]["identite"]["harness"], "essai")
            self.assertEqual(lignes[0]["identite"]["kata"], "premiere-etape")

        with self.subTest("la veille ramasse, et le carré se prononce"):
            veilles = veiller(
                self.harness, self.journal, repos=0,
                maintenant="2030-01-01T00:00:00+00:00",
            ).veilles
            self.assertEqual(len(veilles), 1, "une conversation, un ha")
            self.assertEqual(veilles[0].carre, "conforme")
            self.assertEqual(veilles[0].blocs, 2, "les deux tours ont laissé leur état")
            self.assertEqual(veilles[0].fautes, 0)

        with self.subTest("et le ha est au corpus, lisible"):
            dossiers = sorted(self.harness.corpus.glob("CAS-*"))
            self.assertEqual(len(dossiers), 1)
            fiche = (dossiers[0] / "fiche.md").read_text(encoding="utf-8")
            self.assertIn("essai", fiche)
            self.assertIn("premiere-etape", fiche)
            self.assertTrue((dossiers[0] / "carre.md").is_file())


class LaReabstractionSurvitALaVeille(unittest.TestCase):
    """Scénario 5 — ré-abstraire un ha, puis laisser la veille repasser.

    La ré-abstraction reconstruit l'état d'un ha capturé sur une cible qui ne
    demande aucun bloc, et **marque** son résultat : ce n'est pas une
    observation, c'est une lecture (RFC-002 §7.2). Toute la valeur du geste
    tient dans cette marque.

    Or la veille repasse toutes les trente secondes sur les ha `brut`. Le
    scénario pose donc la seule question qui compte : ce que la ré-abstraction
    a écrit est-il encore là au tour suivant ? Un test de pièce ne peut pas la
    poser — il faut les deux gestes, dans l'ordre, sur le même ha.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.journal = self.racine / "journal"
        self.journal.mkdir()

        semer(self.racine / "harness", "essai", "Harness d'essai")
        # La cible de la semence est instrumentée : on la désinstrumente, car
        # c'est exactement le cas que la ré-abstraction existe pour rattraper.
        manifeste = self.racine / "harness" / "essai" / "harness.yaml"
        manifeste.write_text(
            manifeste.read_text(encoding="utf-8").replace(
                "etat_structure: true", "etat_structure: false"
            ),
            encoding="utf-8",
        )
        self.charge = charger(self.racine / "harness" / "essai")
        self.papier = PasserelleDePapier()
        self.addCleanup(self.papier.fermer)

    def pratiquer(self, session: str, reponse: str):
        """Deux tours écrits au journal comme le Dojo les écrirait."""
        ligne = {
            "session": session,
            "identite": {
                "harness": "essai", "kata": "premiere-etape", "version_kata": "0.1.0",
                "version_coupe": "abc123", "cible": "sobre",
                "date": "2026-01-01T10:00:00+00:00",
            },
            "messages": [
                {"role": "system", "content": "LA COUPE"},
                {"role": "user", "content": "mon sujet"},
            ],
            "reponse": reponse,
            "debut": "2026-01-01T10:00:00+00:00", "fin": "2026-01-01T10:00:00+00:00",
            "moteur": "m", "fournisseur": "f",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        (self.journal / "2026-01-01.jsonl").write_text(
            json.dumps(ligne, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def veille(self):
        return veiller(
            self.charge, self.journal, repos=60, maintenant="2026-01-01T11:00:00+00:00"
        )

    def test_la_marque_et_l_etat_relu_survivent_au_tour_suivant(self):
        from kokaji.middleware.reabstraction import reabstraire
        from kokaji.trempe.banc.client import Passerelle

        with self.subTest("la veille capture un ha sans état, et ne le juge pas"):
            self.pratiquer("s-1", "une réponse, aucun bloc — la cible n'en demande pas")
            passe = self.veille()
            self.assertEqual(passe.veilles[0].carre, "")
            dossier = next(self.charge.corpus.glob("CAS-*"))
            self.assertFalse((dossier / "carre.md").is_file())

        with self.subTest("ré-abstraire reconstruit l'état et le marque"):
            self.papier.prochaine = bloc({"sujet": "en_chantier"})
            fait = reabstraire(
                self.charge, dossier,
                Passerelle(self.papier.base, "sk-essai"), "un/moteur",
            )
            self.assertEqual(fait.blocs, 1)
            releves = (dossier / "etats.jsonl").read_text(encoding="utf-8")
            self.assertIn('"reabstrait": true', releves)
            self.assertIn("ré-abstrait", (dossier / "carre.md").read_text(encoding="utf-8"))
            fiche = (dossier / "fiche.md").read_text(encoding="utf-8")
            self.assertIn("etat_reabstrait: true", fiche)
            self.assertIn("n'a pas été observé", fiche)

        with self.subTest("la veille repasse — et ne défait rien"):
            self.veille()
            fiche = (dossier / "fiche.md").read_text(encoding="utf-8")
            self.assertIn("etat_reabstrait: true", fiche)
            self.assertIn("n'a pas été observé", fiche)
            self.assertIn("ré-abstrait", (dossier / "carre.md").read_text(encoding="utf-8"))
            self.assertIn(
                '"reabstrait": true', (dossier / "etats.jsonl").read_text(encoding="utf-8")
            )

        with self.subTest("une observation, elle, l'emporte sur la lecture"):
            # Si le kata se met vraiment à émettre, ce qu'il émet gagne : une
            # lecture n'a jamais à tenir tête à une observation.
            self.pratiquer("s-1", "voici l'état\n\n" + bloc({"sujet": "fait_etabli"}))
            self.veille()
            releves = (dossier / "etats.jsonl").read_text(encoding="utf-8")
            self.assertNotIn('"reabstrait": true', releves)
            self.assertIn("fait_etabli", releves)


class InviterDepuisLaPage(unittest.TestCase):
    """Scénario 6 — ouvrir le service à quelqu'un, par l'interface.

    Le geste existait en ligne de commande et par une route ; ce que personne
    n'avait fait, c'est le parcours entier depuis la page : l'administrateur
    y arrive, ouvre une invitation, obtient un lien, l'invité s'en sert. Le
    scénario le fait, parce que la semaine a montré qu'un geste jamais joué
    en entier cache toujours une marche.
    """

    def setUp(self):
        from fastapi.testclient import TestClient

        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        (self.racine / "journal").mkdir()
        semer(self.racine / "harness", "essai", "Harness d'essai")

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.patron = self.comptes.creer_utilisateur(
            "Patron", "patron@exemple.test", "un-mot-de-passe-assez-long"
        )
        self.comptes.enregistrer_harness("essai", self.patron.id)
        self.comptes.promouvoir(self.patron.id)

        charges, _ = charger_valides(self.racine / "harness")
        self.client = TestClient(
            creer_tous(charges, self.racine / "journal", self.comptes)
        )

    def cle(self, email: str) -> dict:
        jeton = self.client.post(
            "/session", json={"email": email, "mot_de_passe": "un-mot-de-passe-assez-long"}
        ).json()["jeton"]
        return {"Authorization": f"Bearer {jeton}"}

    def test_de_la_page_au_compte_de_l_invite(self):
        patron = self.cle("patron@exemple.test")

        with self.subTest("le QG mène à l'administration"):
            self.assertTrue(self.client.get("/harness", headers=patron).json()["administration"])

        with self.subTest("la page ouvre une invitation et rend le lien"):
            ouverte = self.client.post(
                "/admin/invitations", json={"email": "invite@exemple.test"}, headers=patron
            )
            self.assertEqual(ouverte.status_code, 200)
            chemin = ouverte.json()["chemin"]
            self.assertTrue(chemin.startswith("/invitation/"))

        with self.subTest("elle figure aussitôt parmi les invitations vivantes"):
            vues = self.client.get("/admin/donnees", headers=patron).json()["invitations"]
            self.assertEqual([i["email"] for i in vues if i["vivante"]], ["invite@exemple.test"])

        with self.subTest("l'invité s'en sert et obtient un compte"):
            jeton = chemin.rsplit("/", 1)[1]
            self.assertTrue(self.client.get(f"/invitation/{jeton}/etat").json()["email"])
            fait = self.client.post(
                f"/invitation/{jeton}",
                json={"nom": "Invitée", "mot_de_passe": "un-autre-mot-de-passe-long"},
            )
            self.assertEqual(fait.status_code, 200)

        with self.subTest("le lien ne resservira pas"):
            self.assertEqual(self.client.post(
                f"/invitation/{jeton}",
                json={"nom": "Encore", "mot_de_passe": "un-troisieme-mot-de-passe"},
            ).status_code, 404)

        with self.subTest("elle entre, et ne voit aucun harness qui n'est pas le sien"):
            sien = self.client.post(
                "/session",
                json={"email": "invite@exemple.test",
                      "mot_de_passe": "un-autre-mot-de-passe-long"},
            )
            self.assertEqual(sien.status_code, 200)
            offre = self.client.get(
                "/harness", headers={"Authorization": f"Bearer {sien.json()['jeton']}"}
            ).json()
            self.assertEqual(offre["harness"], [])
            self.assertFalse(offre["administration"])


class AjouterUnCoAuteur(unittest.TestCase):
    """Scénario 7 — ouvrir son harness à quelqu'un, depuis le module design.

    Le geste existait par une route ; personne ne l'avait joué depuis l'écran,
    ni vérifié que ce que l'écran reçoit permet de **nommer** les membres. La
    page affichait des UUID.
    """

    def setUp(self):
        from fastapi.testclient import TestClient

        from kokaji.hds import charger_valides
        from kokaji.middleware.aiguilleur import creer_tous

        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        (self.racine / "journal").mkdir()
        semer(self.racine / "harness", "essai", "Harness d'essai")

        self.comptes = Comptes()
        self.addCleanup(self.comptes.fermer)
        self.patron = self.comptes.creer_utilisateur(
            "Patronne", "patronne@exemple.test", "un-mot-de-passe-assez-long"
        )
        self.autre = self.comptes.creer_utilisateur(
            "Compagnon", "compagnon@exemple.test", "un-mot-de-passe-assez-long"
        )
        self.comptes.enregistrer_harness("essai", self.patron.id)

        charges, _ = charger_valides(self.racine / "harness")
        self.client = TestClient(creer_tous(charges, self.racine / "journal", self.comptes))

    def cle(self, email: str) -> dict:
        jeton = self.client.post(
            "/session", json={"email": email, "mot_de_passe": "un-mot-de-passe-assez-long"}
        ).json()["jeton"]
        return {"Authorization": f"Bearer {jeton}"}

    def test_de_l_ecran_au_co_auteur(self):
        patronne = self.cle("patronne@exemple.test")
        compagnon = self.cle("compagnon@exemple.test")

        with self.subTest("l'écran sait qui possède, sans ouvrir le module Profil"):
            offre = self.client.get("/harness", headers=patronne).json()
            self.assertEqual(
                [h["role"] for h in offre["harness"] if h["id"] == "essai"], ["proprietaire"]
            )

        with self.subTest("il nomme les membres au lieu de les numéroter"):
            vu = self.client.get("/conception", headers=patronne).json()["membres"]
            self.assertEqual(vu["proprietaire"]["nom"], "Patronne")
            self.assertEqual(vu["proprietaire"]["email"], "patronne@exemple.test")
            self.assertEqual(vu["contributeurs"], [])

        with self.subTest("le compagnon ne voit pas encore le harness"):
            self.assertEqual(self.client.get("/conception", headers=compagnon).status_code, 403)

        with self.subTest("la patronne l'ajoute par son adresse"):
            fait = self.client.post(
                "/membres", json={"email": "compagnon@exemple.test"}, headers=patronne
            )
            self.assertEqual(fait.status_code, 200)
            self.assertEqual([c["nom"] for c in fait.json()["contributeurs"]], ["Compagnon"])

        with self.subTest("il entre, et lit la définition"):
            self.assertEqual(self.client.get("/conception", headers=compagnon).status_code, 200)

        with self.subTest("une adresse inconnue est refusée avec son motif"):
            refus = self.client.post(
                "/membres", json={"email": "personne@exemple.test"}, headers=patronne
            )
            self.assertEqual(refus.status_code, 404)
            self.assertIn("aucun compte", refus.json()["detail"])

        with self.subTest("un co-auteur n'ajoute personne — sabotage n°1 du RFC-004 §8"):
            self.assertEqual(self.client.post(
                "/membres", json={"email": "patronne@exemple.test"}, headers=compagnon
            ).status_code, 403)

        with self.subTest("retirer le rend étranger à nouveau"):
            self.client.delete(f"/membres/{self.autre.id}", headers=patronne)
            self.assertEqual(self.client.get("/conception", headers=compagnon).status_code, 403)


class AdopterUnHarnessExogene(unittest.TestCase):
    """Scénario 8 — RFC-008 N0 : des prompts faits main à la capture.

    Le nominal du §9, joué d'un bout à l'autre : importer deux textes, les
    forger passe-plat, vérifier qu'ils s'offrent au chat comme n'importe quel
    kata, converser, et laisser la vraie veille ramasser — sans carré, la
    cible `nue` ne demandant rien (l'honnêteté d'affichage du §8 commence là).
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.racine = Path(self._tmp.name)
        self.journal = self.racine / "journal"
        self.journal.mkdir()
        textes = self.racine / "textes"
        textes.mkdir()
        (textes / "ouvrir.md").write_text(
            "Tu aides à ouvrir le sujet, une question à la fois.", encoding="utf-8"
        )
        (textes / "conclure.md").write_text(
            "Tu aides à conclure, en relisant ce qui est acquis.", encoding="utf-8"
        )
        from kokaji.adoption import importer

        self.harness = importer(
            [textes / "ouvrir.md", textes / "conclure.md"],
            vers=self.racine / "harness",
            identifiant="adopte",
            nom="Un harness adopté",
            source="fait main, avant la forge",
        )

    def test_des_prompts_au_corpus(self):
        with self.subTest("la forge est passe-plat, la trempe statique s'écarte"):
            resultat = forger_harness(self.harness, sortie=self.racine / "dist")
            self.assertEqual(len(resultat.coupes), 2)
            coupe = (self.racine / "dist" / "adopte" / "nue" / "ouvrir.md").read_text(
                encoding="utf-8"
            )
            self.assertTrue(
                coupe.startswith("Tu aides à ouvrir le sujet, une question à la fois.")
            )

        with self.subTest("le chat offre les kata adoptés comme les autres"):
            from fastapi.testclient import TestClient

            from kokaji.hds import charger_valides
            from kokaji.middleware.aiguilleur import creer_tous

            comptes = Comptes()
            self.addCleanup(comptes.fermer)
            qui = comptes.creer_utilisateur(
                "Un", "un@exemple.test", "un-mot-de-passe-assez-long"
            )
            comptes.enregistrer_harness("adopte", qui.id)
            charges, refuses = charger_valides(self.racine / "harness")
            self.assertEqual(refuses, [])
            client = TestClient(
                creer_tous(charges, self.journal, comptes, secret_chat=SECRET_DU_CHAT)
            )
            vu = client.get(
                "/v1/models",
                headers={"X-OpenWebUI-User-Jwt": jeton_du_chat("un@exemple.test")},
            ).json()
            self.assertEqual(
                [m["id"] for m in vu["data"]], ["adopte/ouvrir", "adopte/conclure"]
            )

        with self.subTest("une session au journal, et la veille la ramasse"):
            ligne = {
                "session": "s-adoptee",
                "identite": {
                    "harness": "adopte", "kata": "ouvrir", "version_kata": "0.1.0",
                    "version_coupe": "abc123", "cible": "nue",
                    "date": "2026-01-01T10:00:00+00:00",
                },
                "messages": [
                    {"role": "system", "content": "LA COUPE"},
                    {"role": "user", "content": "mon sujet"},
                ],
                "reponse": "une réponse sans bloc — le texte importé n'en demande pas",
                "debut": "2026-01-01T10:00:00+00:00", "fin": "2026-01-01T10:00:00+00:00",
                "moteur": "m", "fournisseur": "f",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            (self.journal / "2026-01-01.jsonl").write_text(
                json.dumps(ligne, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            passe = veiller(
                self.harness, self.journal, repos=60,
                maintenant="2026-01-01T11:00:00+00:00",
            )
            self.assertEqual([v.kata for v in passe.veilles], ["ouvrir"])

        with self.subTest("aucun carré : rien n'a été promis, rien n'est jugé"):
            dossier = next(self.harness.corpus.glob("CAS-*"))
            self.assertFalse((dossier / "carre.md").is_file())
            self.assertEqual(passe.veilles[0].carre, "")

        with self.subTest("N2 : déclarer les champs allume l'instrumentation"):
            manifest = self.harness.racine / "harness.yaml"
            texte = manifest.read_text(encoding="utf-8")
            texte = texte.replace(
                "personas: personas/",
                "etat:\n  champs:\n  - sujet\npersonas: personas/",
            )
            texte = texte.replace(
                "trempe:",
                "  - id: instrumentee\n    etat_structure: true\n"
                "    en_tete: Un harness adopté\n    packaging: dossier\ntrempe:",
            )
            manifest.write_text(texte, encoding="utf-8")
            self.harness = charger(self.harness.racine)
            forger_harness(self.harness, sortie=self.racine / "dist")
            armee = (
                self.racine / "dist" / "adopte" / "instrumentee" / "ouvrir.md"
            ).read_text(encoding="utf-8")
            self.assertTrue(armee.startswith("Tu aides à ouvrir le sujet"))
            self.assertIn("kokaji_state", armee)

        with self.subTest("une session instrumentée produit un état capturé"):
            ligne = {
                "session": "s-armee",
                "identite": {
                    "harness": "adopte", "kata": "ouvrir", "version_kata": "0.1.0",
                    "version_coupe": "def456", "cible": "instrumentee",
                    "date": "2026-01-01T12:00:00+00:00",
                },
                "messages": [
                    {"role": "system", "content": "LA COUPE ARMÉE"},
                    {"role": "user", "content": "mon sujet"},
                ],
                "reponse": "voici l'état\n\n" + bloc({"sujet": "fait_etabli"}),
                "debut": "2026-01-01T12:00:00+00:00", "fin": "2026-01-01T12:00:00+00:00",
                "moteur": "m", "fournisseur": "f",
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            with (self.journal / "2026-01-01.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
            passe = veiller(
                self.harness, self.journal, repos=60,
                maintenant="2026-01-01T13:00:00+00:00",
            )
            armee = next(v for v in passe.veilles if v.session == "s-armee")
            self.assertEqual(armee.blocs, 1)
            self.assertEqual(armee.fautes, 0)

        with self.subTest("et le carré reste éteint : toujours aucune promesse"):
            self.assertEqual(armee.carre, "")
            dossier = next(
                d for d in self.harness.corpus.glob("CAS-*") if "instrumentee" in d.name
            )
            self.assertFalse((dossier / "carre.md").is_file())
            self.assertIn('"sujet": "fait_etabli"',
                          (dossier / "etats.jsonl").read_text(encoding="utf-8"))

        with self.subTest("le judge sur grille note le transcript — RFC-008 §7"):
            from kokaji.trempe.banc.client import Passerelle as ClientBanc
            from kokaji.trempe.banc.jugement import juger_grille

            manifest = self.harness.racine / "harness.yaml"
            manifest.write_text(
                manifest.read_text(encoding="utf-8").replace(
                    "  checks_session: []",
                    "  checks_session: []\n  grille_judge:\n"
                    "  - { id: avancee, question: \"L'échange fait-il avancer le sujet ?\","
                    " echelle: \"1-5\" }",
                ),
                encoding="utf-8",
            )
            papier = PasserelleDePapier()
            self.addCleanup(papier.fermer)
            papier.prochaine = (
                '```json\n{ "critere": "avancee", "note": 4, "motif": "questions nettes" }\n```'
            )
            fait = juger_grille(
                charger(self.harness.racine), dossier,
                ClientBanc(papier.base, "sk-juge"), "un/juge",
            )
            self.assertEqual(fait.scores[0].note, 4)
            ecrit = (dossier / "jugements.jsonl").read_text(encoding="utf-8")
            self.assertIn('"juge": "un/juge"', ecrit)
            self.assertIn('"kata": "ouvrir"', ecrit)
