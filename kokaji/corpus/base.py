"""Le dépôt de ha en base — le régime de travail d'une instance (RFC-014 D14.1, D14.3).

Même interface que le dépôt des fichiers, même jeu de tests. Un ha est une
ligne de `ha` ; ses pièces sont ses lignes dans `materiau`, `etat`, `carre`,
`jugement` ; les écartés d'un corpus dans `ecart`. La fiche, le transcript et
la sortie restent des textes entiers : c'est ce qui rend l'export identique,
octet pour octet, au dossier `CAS-XXXX/` (sabotage 4) — les colonnes de `ha`
(kata, cible, statut, visibilité…) en sont *tirées* à l'écriture, pour que
les lectures suivantes soient des requêtes et non des parcours.

Un corpus est nommé par son chemin sur l'instance — celui que le manifest
donne — et, quand ce chemin a la forme `<harness>/corpus/<nom>`, par le
harness et le nom qu'on y lit. Rien de plus que ce que les fichiers portent.

Le pilote est `psycopg` (extra `base`) ; sans lui, sans `KOKAJI_BASE_URL`,
le produit reste en régime fichiers.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from .depot import RefHa

__all__ = ["SCHEMA", "BaseInjoignable", "DepotBase", "JournalBase"]


class BaseInjoignable(RuntimeError):
    """La base déclarée ne répond pas : on le dit, on ne montre rien de périmé."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS ha (
    corpus        text NOT NULL,           -- le chemin du corpus sur l'instance
    nom           text NOT NULL,           -- CAS-0012-titre
    harness       text NOT NULL DEFAULT '',
    corpus_nom    text NOT NULL DEFAULT '',
    id            text NOT NULL DEFAULT '',-- CAS-0012
    kata          text NOT NULL DEFAULT '',
    version_kata  text NOT NULL DEFAULT '',
    version_coupe text NOT NULL DEFAULT '',
    cible         text NOT NULL DEFAULT '',
    moteur        text NOT NULL DEFAULT '',
    date          text NOT NULL DEFAULT '',
    session       text NOT NULL DEFAULT '',
    praticien     text NOT NULL DEFAULT '',
    visibilite    text NOT NULL DEFAULT '',
    source        text NOT NULL DEFAULT '',
    statut        text NOT NULL DEFAULT '',
    completude    text NOT NULL DEFAULT '',
    verdict       text NOT NULL DEFAULT '',
    scores        json,
    design_exerce json,
    titre         text NOT NULL DEFAULT '',
    fiche         text,
    transcript    text,
    sortie        text,
    etats_ecrits  boolean NOT NULL DEFAULT false,
    cree_le       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (corpus, nom)
);
CREATE INDEX IF NOT EXISTS ha_harness_kata ON ha (harness, kata);
CREATE INDEX IF NOT EXISTS ha_session ON ha (session);

CREATE TABLE IF NOT EXISTS materiau (
    corpus text NOT NULL, ha text NOT NULL, nom text NOT NULL, texte text NOT NULL,
    PRIMARY KEY (corpus, ha, nom),
    FOREIGN KEY (corpus, ha) REFERENCES ha (corpus, nom) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS etat (
    corpus text NOT NULL, ha text NOT NULL, rang integer NOT NULL,
    horodatage text NOT NULL DEFAULT '', bloc json NOT NULL,
    PRIMARY KEY (corpus, ha, rang),
    FOREIGN KEY (corpus, ha) REFERENCES ha (corpus, nom) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS carre (
    corpus text NOT NULL, ha text NOT NULL, rendu text NOT NULL,
    PRIMARY KEY (corpus, ha),
    FOREIGN KEY (corpus, ha) REFERENCES ha (corpus, nom) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS jugement (
    corpus text NOT NULL, ha text NOT NULL, rang serial,
    juge text NOT NULL DEFAULT '', version_coupe text NOT NULL DEFAULT '',
    quand text NOT NULL DEFAULT '', contenu json NOT NULL,
    PRIMARY KEY (corpus, ha, rang),
    FOREIGN KEY (corpus, ha) REFERENCES ha (corpus, nom) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS appel (
    id          text PRIMARY KEY,           -- id_appel de la passerelle
    session     text NOT NULL DEFAULT '',
    harness     text NOT NULL DEFAULT '',
    kata        text NOT NULL DEFAULT '',
    cible       text NOT NULL DEFAULT '',
    moteur      text NOT NULL DEFAULT '',
    cle         text NOT NULL DEFAULT '',   -- la clé appelante : chat, banc, QG
    statut      text NOT NULL DEFAULT '',
    etat_avant  text,
    etat_apres  text,
    debut       text NOT NULL DEFAULT '',
    fin         text NOT NULL DEFAULT '',
    ligne       json NOT NULL               -- l'appel entier, tel que le hook l'a écrit
);
CREATE INDEX IF NOT EXISTS appel_harness_debut ON appel (harness, debut);
CREATE INDEX IF NOT EXISTS appel_session ON appel (session);
CREATE TABLE IF NOT EXISTS ecart (
    corpus text NOT NULL, rang serial, session text NOT NULL,
    raison text NOT NULL DEFAULT '', quand text NOT NULL DEFAULT '',
    PRIMARY KEY (corpus, rang)
);
"""

COLONNES_DE_LA_FICHE = (
    "kata", "version_kata", "version_coupe", "cible", "moteur", "date", "session",
    "praticien", "visibilite", "source", "statut", "completude", "verdict", "titre",
)


def _cle(corpus: Path) -> str:
    return str(Path(corpus).resolve())


def _harness_et_nom(corpus: Path) -> tuple[str, str]:
    """`<harness>/corpus/<nom>` → (harness, nom) ; sinon ('', le dossier)."""
    chemin = Path(corpus).resolve()
    if chemin.parent.name == "corpus":
        return chemin.parent.parent.name, chemin.name
    return "", chemin.name


def _entete_de(texte: str | None) -> dict:
    if not texte or not texte.startswith("---"):
        return {}
    morceaux = texte.split("---", 2)
    if len(morceaux) < 3:
        return {}
    try:
        donnees = yaml.safe_load(morceaux[1]) or {}
    except yaml.YAMLError:
        return {}
    return donnees if isinstance(donnees, dict) else {}


def _dumps(valeur) -> str:
    return json.dumps(valeur, ensure_ascii=False, default=str)


def _texte(valeur) -> str:
    if valeur is None:
        return ""
    return valeur if isinstance(valeur, str) else str(valeur)


class _Base:
    """Une connexion au Postgres de l'instance, et le schéma posé une fois."""

    def __init__(self, url: str):
        try:
            import psycopg
        except ImportError as err:  # pragma: no cover — l'extra `base` manque
            raise BaseInjoignable("le pilote `psycopg` manque : pip install 'kokaji[base]'") from err
        self._psycopg = psycopg
        self.url = url
        self._connexion = None
        self._schema_pose = False

    # --- la connexion ---------------------------------------------------------

    def _co(self):
        if self._connexion is None or self._connexion.closed:
            try:
                self._connexion = self._psycopg.connect(self.url, autocommit=True)
            except self._psycopg.OperationalError as err:
                raise BaseInjoignable(f"la base ne répond pas : {err}") from err
            if not self._schema_pose:
                self._connexion.execute(SCHEMA)
                self._schema_pose = True
        return self._connexion

    def _lire_une(self, requete: str, *params):
        with self._co().cursor() as cur:
            cur.execute(requete, params)
            return cur.fetchone()

    def _lire_toutes(self, requete: str, *params):
        with self._co().cursor() as cur:
            cur.execute(requete, params)
            return cur.fetchall()

    def _executer(self, requete: str, *params) -> None:
        self._co().execute(requete, params)

    def _json(self, valeur):
        """Un `json`, pas un `jsonb` : le texte est gardé tel quel, clés dans
        l'ordre — l'export d'un bloc redonne la ligne JSONL d'origine."""
        return self._psycopg.types.json.Json(valeur, dumps=_dumps)

    def fermer(self) -> None:
        if self._connexion is not None and not self._connexion.closed:
            self._connexion.close()
        self._connexion = None


class DepotBase(_Base):
    """Le corpus dans le Postgres de l'instance."""

    # --- les ha d'un corpus ---------------------------------------------------

    def tous(self, corpus: Path) -> list[RefHa]:
        corpus = Path(corpus)
        lignes = self._lire_toutes(
            "SELECT nom FROM ha WHERE corpus = %s AND nom LIKE 'CAS-%%' ORDER BY nom", _cle(corpus)
        )
        return [RefHa(corpus, nom) for (nom,) in lignes]

    def trouver(self, corpus: Path, identifiant: str) -> RefHa | None:
        corpus = Path(corpus)
        ligne = self._lire_une(
            "SELECT nom FROM ha WHERE corpus = %s AND (nom LIKE %s OR nom = %s) ORDER BY nom LIMIT 1",
            _cle(corpus), identifiant + "-%", identifiant,
        )
        return RefHa(corpus, ligne[0]) if ligne else None

    def existe(self, ref: RefHa) -> bool:
        return self._lire_une(
            "SELECT 1 FROM ha WHERE corpus = %s AND nom = %s", _cle(ref.corpus), ref.nom
        ) is not None

    def numero_suivant(self, corpus: Path) -> int:
        numeros = [
            int(m.group(1))
            for (nom,) in self._lire_toutes("SELECT nom FROM ha WHERE corpus = %s", _cle(corpus))
            if (m := re.match(r"CAS-(\d+)", nom))
        ]
        return max(numeros, default=0) + 1

    def creer(self, corpus: Path, nom: str) -> RefHa:
        corpus = Path(corpus)
        harness, corpus_nom = _harness_et_nom(corpus)
        self._executer(
            "INSERT INTO ha (corpus, nom, harness, corpus_nom, id) VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT DO NOTHING",
            _cle(corpus), nom, harness, corpus_nom, RefHa(corpus, nom).identifiant,
        )
        return RefHa(corpus, nom)

    def supprimer(self, ref: RefHa) -> None:
        self._executer("DELETE FROM ha WHERE corpus = %s AND nom = %s", _cle(ref.corpus), ref.nom)

    # --- les pièces -------------------------------------------------------------

    def _colonne(self, ref: RefHa, colonne: str) -> str | None:
        ligne = self._lire_une(
            f"SELECT {colonne} FROM ha WHERE corpus = %s AND nom = %s", _cle(ref.corpus), ref.nom
        )
        return ligne[0] if ligne else None

    def _poser(self, ref: RefHa, colonne: str, texte: str) -> None:
        self.creer(ref.corpus, ref.nom)
        self._executer(
            f"UPDATE ha SET {colonne} = %s WHERE corpus = %s AND nom = %s",
            texte, _cle(ref.corpus), ref.nom,
        )

    def fiche(self, ref: RefHa) -> str | None:
        return self._colonne(ref, "fiche")

    def entete(self, ref: RefHa) -> dict:
        return _entete_de(self.fiche(ref))

    def ecrire_fiche(self, ref: RefHa, texte: str) -> None:
        """La fiche entière, et ses colonnes tirées du frontmatter — pour requêter."""
        self.creer(ref.corpus, ref.nom)
        entete = _entete_de(texte)
        colonnes = {c: _texte(entete.get(c)) for c in COLONNES_DE_LA_FICHE}
        affectations = ", ".join(f"{c} = %s" for c in colonnes)
        self._executer(
            f"UPDATE ha SET fiche = %s, {affectations}, scores = %s, design_exerce = %s"
            " WHERE corpus = %s AND nom = %s",
            texte, *colonnes.values(),
            self._json(entete.get("scores")), self._json(entete.get("design_exerce")),
            _cle(ref.corpus), ref.nom,
        )

    def transcript(self, ref: RefHa) -> str | None:
        return self._colonne(ref, "transcript")

    def ecrire_transcript(self, ref: RefHa, texte: str) -> None:
        self._poser(ref, "transcript", texte)

    def sortie(self, ref: RefHa) -> str | None:
        return self._colonne(ref, "sortie")

    def ecrire_sortie(self, ref: RefHa, texte: str) -> None:
        self._poser(ref, "sortie", texte)

    def materiau(self, ref: RefHa, nom: str) -> str | None:
        ligne = self._lire_une(
            "SELECT texte FROM materiau WHERE corpus = %s AND ha = %s AND nom = %s",
            _cle(ref.corpus), ref.nom, nom,
        )
        return ligne[0] if ligne else None

    def ecrire_materiau(self, ref: RefHa, nom: str, texte: str) -> None:
        self.creer(ref.corpus, ref.nom)
        self._executer(
            "INSERT INTO materiau (corpus, ha, nom, texte) VALUES (%s, %s, %s, %s)"
            " ON CONFLICT (corpus, ha, nom) DO UPDATE SET texte = EXCLUDED.texte",
            _cle(ref.corpus), ref.nom, nom, texte,
        )

    def materiaux(self, ref: RefHa) -> list[str]:
        """Les noms des matériaux d'un ha — pour l'export."""
        return [
            nom for (nom,) in self._lire_toutes(
                "SELECT nom FROM materiau WHERE corpus = %s AND ha = %s ORDER BY nom",
                _cle(ref.corpus), ref.nom,
            )
        ]

    def etats(self, ref: RefHa) -> list[dict]:
        return [
            bloc for (bloc,) in self._lire_toutes(
                "SELECT bloc FROM etat WHERE corpus = %s AND ha = %s ORDER BY rang",
                _cle(ref.corpus), ref.nom,
            )
        ]

    def a_des_etats(self, ref: RefHa) -> bool:
        return bool(self._colonne(ref, "etats_ecrits"))

    def ecrire_etats(self, ref: RefHa, releves: list[dict]) -> None:
        self.creer(ref.corpus, ref.nom)
        cle = _cle(ref.corpus)
        with self._co().transaction():
            self._executer("DELETE FROM etat WHERE corpus = %s AND ha = %s", cle, ref.nom)
            for rang, releve in enumerate(releves):
                # Le relevé passe par le même sérialiseur que le fichier : ce qui
                # n'est pas du JSON (une date) devient un texte, ici comme là.
                bloc = json.loads(json.dumps(releve, ensure_ascii=False, default=str))
                self._executer(
                    "INSERT INTO etat (corpus, ha, rang, horodatage, bloc) VALUES (%s, %s, %s, %s, %s)",
                    cle, ref.nom, rang, _texte(bloc.get("horodatage")), self._json(bloc),
                )
            self._executer(
                "UPDATE ha SET etats_ecrits = true WHERE corpus = %s AND nom = %s", cle, ref.nom
            )

    def carre(self, ref: RefHa) -> str | None:
        ligne = self._lire_une(
            "SELECT rendu FROM carre WHERE corpus = %s AND ha = %s", _cle(ref.corpus), ref.nom
        )
        return ligne[0] if ligne else None

    def ecrire_carre(self, ref: RefHa, texte: str) -> None:
        self.creer(ref.corpus, ref.nom)
        self._executer(
            "INSERT INTO carre (corpus, ha, rendu) VALUES (%s, %s, %s)"
            " ON CONFLICT (corpus, ha) DO UPDATE SET rendu = EXCLUDED.rendu",
            _cle(ref.corpus), ref.nom, texte,
        )

    def retirer_carre(self, ref: RefHa) -> None:
        self._executer("DELETE FROM carre WHERE corpus = %s AND ha = %s", _cle(ref.corpus), ref.nom)

    def jugements(self, ref: RefHa) -> list[dict]:
        return [
            contenu for (contenu,) in self._lire_toutes(
                "SELECT contenu FROM jugement WHERE corpus = %s AND ha = %s ORDER BY rang",
                _cle(ref.corpus), ref.nom,
            )
        ]

    def ajouter_jugement(self, ref: RefHa, jugement: dict) -> None:
        self.creer(ref.corpus, ref.nom)
        self._executer(
            "INSERT INTO jugement (corpus, ha, juge, version_coupe, quand, contenu)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            _cle(ref.corpus), ref.nom, _texte(jugement.get("juge")),
            _texte(jugement.get("version_coupe")), _texte(jugement.get("le")), self._json(jugement),
        )

    # --- les écartés -------------------------------------------------------------

    def ecartes(self, corpus: Path) -> list[dict]:
        return [
            {"session": session, "raison": raison, "le": quand}
            for session, raison, quand in self._lire_toutes(
                "SELECT session, raison, quand FROM ecart WHERE corpus = %s ORDER BY rang",
                _cle(corpus),
            )
        ]

    def ecarter(self, corpus: Path, session: str, raison: str, quand: str) -> None:
        self._executer(
            "INSERT INTO ecart (corpus, session, raison, quand) VALUES (%s, %s, %s, %s)",
            _cle(corpus), session, raison, quand,
        )



class JournalBase(_Base):
    """Le journal des appels dans la base — ce que le hook y écrit à la source
    (D14.4). Une ligne par appel, entière ; les colonnes en sont tirées pour
    demander par harness, par session, par date."""

    def ecrire(self, ligne: dict) -> None:
        identite = ligne.get("identite") or {}
        self._executer(
            "INSERT INTO appel (id, session, harness, kata, cible, moteur, cle, statut,"
            " etat_avant, etat_apres, debut, fin, ligne)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            " ON CONFLICT (id) DO NOTHING",
            _texte(ligne.get("id_appel")) or f"{ligne.get('session')}/{ligne.get('etat_apres')}",
            _texte(ligne.get("session")), _texte(identite.get("harness")),
            _texte(identite.get("kata")), _texte(identite.get("cible")),
            _texte(ligne.get("moteur")), _texte(identite.get("cle")), _texte(ligne.get("statut")),
            ligne.get("etat_avant"), ligne.get("etat_apres"),
            _texte(ligne.get("debut")), _texte(ligne.get("fin")),
            self._json(json.loads(_dumps(ligne))),
        )

    def appels(self, harness: str | None = None, session: str | None = None) -> list[dict]:
        clauses, params = [], []
        if harness:
            clauses.append("harness = %s")
            params.append(harness)
        if session:
            clauses.append("session = %s")
            params.append(session)
        ou = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        return [
            ligne for (ligne,) in self._lire_toutes(
                f"SELECT ligne FROM appel{ou} ORDER BY debut, id", *params
            )
        ]

    def compter(self, harness: str | None = None) -> int:
        ou = " WHERE harness = %s" if harness else ""
        return self._lire_une(f"SELECT count(*) FROM appel{ou}", *([harness] if harness else []))[0]
