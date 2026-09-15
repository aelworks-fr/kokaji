"""Le magasin des comptes et des ACL — RFC-004 §2, SPECS R12.1 et R12.2.

Un fichier SQLite, **hors git** — ou, quand l'instance déclare `KOKAJI_BASE_URL`,
les mêmes tables dans son Postgres (RFC-014 D14.7) : il contient des empreintes
de mots de passe et des jetons de session. C'est la seule donnée de Kokaji qui
ne doit jamais entrer dans un corpus ni dans une définition de harness.

Un seul magasin, deux moteurs : le SQL est écrit une fois, avec des `?`, et
chaque moteur le traduit. Ce qui diffère tient en trois lignes de schéma — la
casse de l'email, l'ordre des contributeurs, une clé étrangère que Postgres
veut voir déclarée après sa cible.

Pourquoi une base ici, alors que tout le reste du projet est en fichiers lisibles
à l'œil : parce que ces données ont des invariants qui se tiennent par des
contraintes (unicité d'un email, unicité d'un propriétaire) et qu'on ne veut ni
les relire ni les fusionner à la main. Un corpus se lit ; un magasin de comptes
se vérifie.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .droits import exiger
from .modele import ETRANGER, Acl, AclInvalide, Enregistrement, Utilisateur, email_plausible

__all__ = ["Comptes", "IdentiteInconnue", "ou_ouvrir", "transvaser"]

DUREE_SESSION = timedelta(hours=12)
# Une invitation qui traîne est une porte ouverte : elle se périme d'elle-même.
DUREE_INVITATION = timedelta(days=7)

SCHEMA = """
CREATE TABLE IF NOT EXISTS utilisateurs (
    id        TEXT PRIMARY KEY,
    nom       TEXT NOT NULL,
    email     TEXT NOT NULL UNIQUE COLLATE NOCASE,
    empreinte TEXT NOT NULL,
    cree_le   TEXT NOT NULL,
    -- L'administration **de l'exploitation** : comptes, invitations, ACL, état
    -- du service. Elle ne donne aucun accès à la pratique d'autrui — R12.4 tient
    -- pour l'admin comme pour tout le monde, et c'est vérifié par sabotage.
    admin     INTEGER NOT NULL DEFAULT 0,
    -- Le harness que cette personne pratique (RFC-005 §2.2). Nul est une
    -- réponse valide : tant qu'un seul harness est accessible, personne n'a à
    -- choisir. La clé étrangère fait le ménage le jour où un harness
    -- disparaît — une préférence caduque se lit comme absente, pas comme une
    -- faute.
    harness_courant TEXT REFERENCES harness_acl(harness_id) ON DELETE SET NULL
);

-- Une invitation est un jeton à usage unique, daté, adressé à un email. Elle ne
-- crée rien : c'est celui qui la consomme qui crée son compte, avec le mot de
-- passe qu'il choisit. Personne d'autre ne l'a jamais connu.
CREATE TABLE IF NOT EXISTS invitations (
    jeton          TEXT PRIMARY KEY,
    email          TEXT NOT NULL COLLATE NOCASE,
    cree_par       TEXT NOT NULL REFERENCES utilisateurs(id),
    cree_le        TEXT NOT NULL,
    expire_le      TEXT NOT NULL,
    consomme_le    TEXT,
    utilisateur_id TEXT REFERENCES utilisateurs(id)
);

-- Réservée pour un rattachement OAuth ultérieur (RFC-004 §2.1). Vide en v1, et
-- c'est délibéré : la place est tenue pour que l'id d'un utilisateur n'ait
-- jamais à changer le jour où un fournisseur externe entrera en jeu.
CREATE TABLE IF NOT EXISTS identites_externes (
    utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    fournisseur    TEXT NOT NULL,
    sujet_externe  TEXT NOT NULL,
    PRIMARY KEY (fournisseur, sujet_externe)
);

-- Un harness, une ligne : la contrainte de clé primaire *est* l'invariant
-- « exactement un propriétaire ». En avoir deux n'est pas refusé, c'est
-- inexprimable.
CREATE TABLE IF NOT EXISTS harness_acl (
    harness_id   TEXT PRIMARY KEY,
    proprietaire TEXT NOT NULL REFERENCES utilisateurs(id),
    -- Quand il a été archivé, ou nul. Une date plutôt qu'un booléen : archiver
    -- est un geste daté, et le principe d'observabilité veut qu'on sache
    -- *quand* une forme a cessé de servir, pas seulement qu'elle a cessé.
    archive_le   TEXT
);

CREATE TABLE IF NOT EXISTS contributeurs (
    harness_id     TEXT NOT NULL REFERENCES harness_acl(harness_id) ON DELETE CASCADE,
    utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    PRIMARY KEY (harness_id, utilisateur_id)
);

-- RFC-012 D12.2 : le dépôt nu d'un harness — métadonnée d'instance.
CREATE TABLE IF NOT EXISTS harness_depot (
    harness_id            TEXT PRIMARY KEY REFERENCES harness_acl(harness_id) ON DELETE CASCADE,
    chemin                TEXT NOT NULL,
    branche               TEXT NOT NULL DEFAULT 'main',
    commit_reference      TEXT NOT NULL DEFAULT '',
    pousser_au_scellement INTEGER NOT NULL DEFAULT 1,
    enregistre_le         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    jeton          TEXT PRIMARY KEY,
    utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,
    expire_le      TEXT NOT NULL
);
"""


# Le même schéma pour Postgres, à trois différences près : pas de `COLLATE
# NOCASE` (un index unique sur `lower(email)` tient l'invariant), un `rowid`
# déclaré pour l'ordre des contributeurs (SQLite l'a d'office), et la clé
# étrangère `harness_courant` non déclarée — Postgres exige que `harness_acl`
# existe avant, et aucune ligne de `harness_acl` n'est jamais effacée.
SCHEMA_POSTGRES = (
    SCHEMA.replace(" UNIQUE COLLATE NOCASE", "")
    .replace(" COLLATE NOCASE", "")
    .replace(
        "harness_courant TEXT REFERENCES harness_acl(harness_id) ON DELETE SET NULL",
        "harness_courant TEXT",
    )
    .replace(
        "    utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,\n"
        "    PRIMARY KEY (harness_id, utilisateur_id)",
        "    utilisateur_id TEXT NOT NULL REFERENCES utilisateurs(id) ON DELETE CASCADE,\n"
        "    rowid          SERIAL,\n"
        "    PRIMARY KEY (harness_id, utilisateur_id)",
    )
    + "CREATE UNIQUE INDEX IF NOT EXISTS utilisateurs_email ON utilisateurs (lower(email));\n"
)


class _Resultat:
    """Ce qu'une requête a rendu : des lignes qu'on lit par nom, et un compte."""

    def __init__(self, lignes: list[dict], rowcount: int):
        self._lignes = lignes
        self.rowcount = rowcount

    def fetchone(self) -> dict | None:
        return self._lignes[0] if self._lignes else None

    def fetchall(self) -> list[dict]:
        return list(self._lignes)

    def __iter__(self):
        return iter(self._lignes)


class _Sqlite:
    """Le moteur d'un poste seul et des tests : un fichier, ou la mémoire."""

    def __init__(self, chemin: Path | str):
        self._db = sqlite3.connect(str(chemin), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys = ON")
        self._db.executescript(SCHEMA)
        self._migrer()
        self._db.commit()
        self.Integrite = sqlite3.IntegrityError

    def _migrer(self) -> None:
        """Les colonnes venues après coup, posées sur une base déjà écrite.

        `CREATE TABLE IF NOT EXISTS` ne touche pas une table qui existe : sans
        ce geste, un magasin ouvert avant le RFC-005 garderait son schéma
        d'alors, et la faute n'apparaîtrait qu'à la première lecture du harness
        courant — c'est-à-dire en service, pas au démarrage.
        """
        colonnes = {r["name"] for r in self._db.execute("PRAGMA table_info(utilisateurs)")}
        if "harness_courant" not in colonnes:
            self._db.execute(
                "ALTER TABLE utilisateurs ADD COLUMN harness_courant TEXT "
                "REFERENCES harness_acl(harness_id) ON DELETE SET NULL"
            )
        acl = {r["name"] for r in self._db.execute("PRAGMA table_info(harness_acl)")}
        if "archive_le" not in acl:
            self._db.execute("ALTER TABLE harness_acl ADD COLUMN archive_le TEXT")

    def execute(self, sql: str, params: tuple = ()) -> _Resultat:
        cur = self._db.execute(sql, params)
        lignes = [dict(r) for r in cur.fetchall()] if cur.description else []
        return _Resultat(lignes, cur.rowcount)

    def executemany(self, sql: str, seq) -> None:
        self._db.executemany(sql, seq)

    def commit(self) -> None:
        self._db.commit()

    def close(self) -> None:
        self._db.close()


class _Postgres:
    """Le moteur d'une instance : la base `kokaji` de son Postgres (RFC-014)."""

    def __init__(self, url: str):
        import psycopg
        from psycopg.rows import dict_row

        self._db = psycopg.connect(url, row_factory=dict_row)
        self._db.execute(SCHEMA_POSTGRES)
        self._db.commit()
        self.Integrite = psycopg.errors.IntegrityError

    @staticmethod
    def _traduire(sql: str) -> str:
        return sql.replace("?", "%s")

    def execute(self, sql: str, params: tuple = ()) -> _Resultat:
        try:
            cur = self._db.execute(self._traduire(sql), params)
        except self.Integrite:
            self._db.rollback()  # une transaction fautive ne bloque pas la suivante
            raise
        lignes = cur.fetchall() if cur.description else []
        return _Resultat(lignes, cur.rowcount)

    def executemany(self, sql: str, seq) -> None:
        with self._db.cursor() as cur:
            cur.executemany(self._traduire(sql), list(seq))

    def commit(self) -> None:
        self._db.commit()

    def close(self) -> None:
        self._db.close()


def _moteur(chemin: Path | str):
    if str(chemin).startswith(("postgresql://", "postgres://")):
        return _Postgres(str(chemin))
    return _Sqlite(chemin)


def ou_ouvrir(chemin: Path | str | None) -> Path | str | None:
    """Le magasin que l'instance veut : sa base si `KOKAJI_BASE_URL` est là,
    sinon le chemin donné — SQLite, comme toujours. `None` reste `None` : un
    service sans comptes le reste."""
    if chemin is None:
        return None
    url = os.environ.get("KOKAJI_BASE_URL", "").strip()
    return url or chemin


class IdentiteInconnue(Exception):
    """Identifiants refusés, ou jeton périmé."""


def _instant(texte: str) -> datetime:
    quand = datetime.fromisoformat(texte)
    return quand if quand.tzinfo else quand.replace(tzinfo=UTC)


class Comptes:
    """Le magasin. Ouvert sur un chemin, ou en mémoire pour les tests."""

    def __init__(self, chemin: Path | str = ":memory:"):
        self.chemin = chemin
        self._db = _moteur(chemin)
        self._hacheur = PasswordHasher()

    @property
    def en_base(self) -> bool:
        return isinstance(self._db, _Postgres)

    def fermer(self) -> None:
        self._db.close()

    # --- les utilisateurs (§2.1) ------------------------------------------

    def creer_utilisateur(
        self, nom: str, email: str, mot_de_passe: str, admin: bool = False
    ) -> Utilisateur:
        if not email_plausible(email):
            raise AclInvalide(f"email invraisemblable : {email!r}")
        if len(mot_de_passe) < 12:
            raise AclInvalide("mot de passe trop court : douze caractères au moins")

        utilisateur = Utilisateur(
            id=str(uuid.uuid4()), nom=nom.strip(), email=email.strip(), cree_le=datetime.now(UTC)
        )
        try:
            self._db.execute(
                "INSERT INTO utilisateurs (id, nom, email, empreinte, cree_le, admin) "
                "VALUES (?,?,?,?,?,?)",
                (
                    utilisateur.id,
                    utilisateur.nom,
                    utilisateur.email,
                    self._hacheur.hash(mot_de_passe),
                    utilisateur.cree_le.isoformat(),
                    1 if admin else 0,
                ),
            )
        except self._db.Integrite as err:
            raise AclInvalide(f"email déjà pris : {email}") from err
        self._db.commit()
        return utilisateur

    def _utilisateur(self, ligne: dict | None) -> Utilisateur | None:
        if ligne is None:
            return None
        return Utilisateur(
            id=ligne["id"],
            nom=ligne["nom"],
            email=ligne["email"],
            cree_le=_instant(ligne["cree_le"]),
        )

    def utilisateur(self, utilisateur_id: str) -> Utilisateur | None:
        return self._utilisateur(
            self._db.execute("SELECT * FROM utilisateurs WHERE id = ?", (utilisateur_id,)).fetchone()
        )

    def par_email(self, email: str) -> Utilisateur | None:
        return self._utilisateur(
            self._db.execute(
                "SELECT * FROM utilisateurs WHERE lower(email) = lower(?)", (email.strip(),)
            ).fetchone()
        )

    def est_admin(self, utilisateur_id: str) -> bool:
        ligne = self._db.execute(
            "SELECT admin FROM utilisateurs WHERE id = ?", (utilisateur_id,)
        ).fetchone()
        return bool(ligne and ligne["admin"])

    def promouvoir(self, utilisateur_id: str, admin: bool = True) -> None:
        self._db.execute(
            "UPDATE utilisateurs SET admin = ? WHERE id = ?", (1 if admin else 0, utilisateur_id)
        )
        self._db.commit()

    def utilisateurs(self) -> list[dict]:
        """Tous les comptes — la liste de la page admin. Aucun secret n'en sort."""
        return [
            {
                "id": l["id"],
                "nom": l["nom"],
                "email": l["email"],
                "cree_le": l["cree_le"],
                "admin": bool(l["admin"]),
            }
            for l in self._db.execute("SELECT * FROM utilisateurs ORDER BY cree_le")
        ]

    def changer_mot_de_passe(self, utilisateur_id: str, nouveau: str) -> None:
        if len(nouveau) < 12:
            raise AclInvalide("mot de passe trop court : douze caractères au moins")
        self._db.execute(
            "UPDATE utilisateurs SET empreinte = ? WHERE id = ?",
            (self._hacheur.hash(nouveau), utilisateur_id),
        )
        self._db.commit()

    # --- les invitations ---------------------------------------------------

    def inviter(self, email: str, par: str, duree: timedelta = DUREE_INVITATION) -> str:
        """Ouvre une porte nominative, à usage unique et datée.

        Elle ne crée aucun compte : elle autorise quelqu'un à s'en créer un, avec
        un mot de passe que lui seul choisira. C'est ce qui évite de transmettre
        un secret — un mot de passe qu'on envoie est un mot de passe partagé.
        """
        if not email_plausible(email):
            raise AclInvalide(f"email invraisemblable : {email!r}")
        if self.par_email(email) is not None:
            raise AclInvalide(f"un compte existe déjà pour {email}")
        if self.utilisateur(par) is None:
            raise AclInvalide("invitant inconnu")

        jeton = secrets.token_urlsafe(32)
        maintenant = datetime.now(UTC)
        self._db.execute(
            "INSERT INTO invitations (jeton, email, cree_par, cree_le, expire_le) "
            "VALUES (?,?,?,?,?)",
            (jeton, email.strip(), par, maintenant.isoformat(), (maintenant + duree).isoformat()),
        )
        self._db.commit()
        return jeton

    def invitations(self) -> list[dict]:
        return [
            {
                "jeton": l["jeton"],
                "email": l["email"],
                "cree_par": l["cree_par"],
                "cree_le": l["cree_le"],
                "expire_le": l["expire_le"],
                "consomme_le": l["consomme_le"],
                "vivante": l["consomme_le"] is None
                and _instant(l["expire_le"]) > datetime.now(UTC),
            }
            for l in self._db.execute("SELECT * FROM invitations ORDER BY cree_le DESC")
        ]

    def invitation(self, jeton: str) -> dict:
        """L'invitation, si elle vaut encore. Le refus ne dit pas laquelle des
        trois raisons — inconnue, consommée ou périmée : une porte fermée n'a
        pas à renseigner sur ce qu'il y a derrière."""
        ligne = self._db.execute(
            "SELECT * FROM invitations WHERE jeton = ?", (jeton or "",)
        ).fetchone()
        if (
            ligne is None
            or ligne["consomme_le"] is not None
            or _instant(ligne["expire_le"]) < datetime.now(UTC)
        ):
            raise IdentiteInconnue("invitation inconnue, déjà utilisée ou périmée")
        return {"jeton": ligne["jeton"], "email": ligne["email"], "expire_le": ligne["expire_le"]}

    def consommer(self, jeton: str, nom: str, mot_de_passe: str) -> Utilisateur:
        """Crée le compte de l'invité. Un jeton ne sert qu'une fois."""
        ouverte = self.invitation(jeton)
        utilisateur = self.creer_utilisateur(nom, ouverte["email"], mot_de_passe)
        self._db.execute(
            "UPDATE invitations SET consomme_le = ?, utilisateur_id = ? WHERE jeton = ?",
            (datetime.now(UTC).isoformat(), utilisateur.id, jeton),
        )
        self._db.commit()
        return utilisateur

    def revoquer(self, jeton: str) -> None:
        """Ferme une invitation non consommée. Une porte se referme sans trace
        d'usage : on la marque consommée, elle ne vaut plus."""
        self._db.execute(
            "UPDATE invitations SET consomme_le = ? WHERE jeton = ? AND consomme_le IS NULL",
            (datetime.now(UTC).isoformat(), jeton),
        )
        self._db.commit()

    # --- les sessions (§6 : le middleware authentifie) ---------------------

    def ouvrir_session(self, email: str, mot_de_passe: str) -> str:
        """Rend un jeton de session, ou refuse.

        Le refus est le même que l'email soit inconnu ou le mot de passe faux :
        distinguer les deux dirait à un inconnu qui possède un compte ici.
        """
        ligne = self._db.execute(
            "SELECT * FROM utilisateurs WHERE lower(email) = lower(?)", (email.strip(),)
        ).fetchone()
        if ligne is None:
            # Une vérification à vide, pour que le temps de réponse ne trahisse
            # pas l'existence du compte.
            self._hacheur.hash("sans objet")
            raise IdentiteInconnue("identifiants refusés")
        try:
            self._hacheur.verify(ligne["empreinte"], mot_de_passe)
        except VerifyMismatchError as err:
            raise IdentiteInconnue("identifiants refusés") from err

        jeton = secrets.token_urlsafe(32)
        self._db.execute(
            "INSERT INTO sessions (jeton, utilisateur_id, expire_le) VALUES (?,?,?)",
            (jeton, ligne["id"], (datetime.now(UTC) + DUREE_SESSION).isoformat()),
        )
        self._db.commit()
        return jeton

    def session(self, jeton: str) -> Utilisateur:
        ligne = self._db.execute(
            "SELECT * FROM sessions WHERE jeton = ?", (jeton or "",)
        ).fetchone()
        if ligne is None or _instant(ligne["expire_le"]) < datetime.now(UTC):
            raise IdentiteInconnue("session inconnue ou périmée")
        connu = self.utilisateur(ligne["utilisateur_id"])
        if connu is None:
            raise IdentiteInconnue("session orpheline")
        return connu

    def fermer_session(self, jeton: str) -> None:
        self._db.execute("DELETE FROM sessions WHERE jeton = ?", (jeton,))
        self._db.commit()

    # --- l'autorat (§2.2) --------------------------------------------------

    def enregistrer_harness(self, harness_id: str, proprietaire: str) -> Acl:
        """Attache un harness à son propriétaire. Un harness n'en a qu'un."""
        if self.utilisateur(proprietaire) is None:
            raise AclInvalide("propriétaire inconnu")
        acl = Acl(harness_id, proprietaire)
        try:
            self._db.execute(
                "INSERT INTO harness_acl (harness_id, proprietaire) VALUES (?,?)",
                (acl.harness_id, acl.proprietaire),
            )
        except self._db.Integrite as err:
            raise AclInvalide(f"harness déjà enregistré : {harness_id}") from err
        self._db.commit()
        return acl

    # --- le dépôt nu d'un harness (RFC-012) ---------------------------------

    def depot(self, harness_id: str) -> Enregistrement | None:
        ligne = self._db.execute(
            "SELECT * FROM harness_depot WHERE harness_id = ?", (harness_id,)
        ).fetchone()
        if ligne is None:
            return None
        return Enregistrement(
            harness_id=ligne["harness_id"], chemin=ligne["chemin"], branche=ligne["branche"],
            commit_reference=ligne["commit_reference"],
            pousser_au_scellement=bool(ligne["pousser_au_scellement"]),
            enregistre_le=ligne["enregistre_le"],
        )

    def enregistrer_depot(
        self, harness_id: str, chemin: str, branche: str = "main",
        pousser_au_scellement: bool = True, commit_reference: str = "",
    ) -> Enregistrement:
        """Lie un harness à un dépôt nu. Un harness n'en a qu'un : relier remplace."""
        if self.acl(harness_id) is None:
            raise AclInvalide(f"harness inconnu : {harness_id}")
        if not chemin.strip():
            raise AclInvalide("un enregistrement sans chemin n'enregistre rien")
        quand = datetime.now(UTC).isoformat()
        self._db.execute(
            "INSERT INTO harness_depot (harness_id, chemin, branche, commit_reference, "
            "pousser_au_scellement, enregistre_le) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(harness_id) DO UPDATE SET chemin=excluded.chemin, "
            "branche=excluded.branche, commit_reference=excluded.commit_reference, "
            "pousser_au_scellement=excluded.pousser_au_scellement, "
            "enregistre_le=excluded.enregistre_le",
            (harness_id, chemin.strip(), branche.strip() or "main", commit_reference,
             1 if pousser_au_scellement else 0, quand),
        )
        self._db.commit()
        return self.depot(harness_id)

    def desenregistrer_depot(self, harness_id: str) -> bool:
        """Efface la ligne — le clone reste, le dépôt nu vit sa vie (D12.2)."""
        fait = self._db.execute("DELETE FROM harness_depot WHERE harness_id = ?", (harness_id,))
        self._db.commit()
        return fait.rowcount > 0

    def poser_reference(self, harness_id: str, commit_reference: str) -> None:
        """Le dernier commit connu du dépôt nu — posé après chaque pousser ou tirer."""
        self._db.execute(
            "UPDATE harness_depot SET commit_reference = ? WHERE harness_id = ?",
            (commit_reference, harness_id),
        )
        self._db.commit()

    def acl(self, harness_id: str) -> Acl | None:
        ligne = self._db.execute(
            "SELECT proprietaire FROM harness_acl WHERE harness_id = ?", (harness_id,)
        ).fetchone()
        if ligne is None:
            return None
        contributeurs = tuple(
            r["utilisateur_id"]
            for r in self._db.execute(
                "SELECT utilisateur_id FROM contributeurs WHERE harness_id = ? ORDER BY rowid",
                (harness_id,),
            )
        )
        return Acl(harness_id, ligne["proprietaire"], contributeurs)

    def role(self, harness_id: str, utilisateur_id: str) -> str:
        """Le rôle d'un utilisateur sur un harness — `etranger` si aucune ACL."""
        acl = self.acl(harness_id)
        return acl.role(utilisateur_id) if acl else "etranger"

    def _remplacer(self, acl: Acl) -> Acl:
        self._db.execute(
            "UPDATE harness_acl SET proprietaire = ? WHERE harness_id = ?",
            (acl.proprietaire, acl.harness_id),
        )
        self._db.execute("DELETE FROM contributeurs WHERE harness_id = ?", (acl.harness_id,))
        self._db.executemany(
            "INSERT INTO contributeurs (harness_id, utilisateur_id) VALUES (?,?)",
            [(acl.harness_id, c) for c in acl.contributeurs],
        )
        self._db.commit()
        return acl

    def _exigee(self, harness_id: str) -> Acl:
        acl = self.acl(harness_id)
        if acl is None:
            raise AclInvalide(f"harness non enregistré : {harness_id}")
        return acl

    def ajouter_contributeur(self, harness_id: str, utilisateur_id: str) -> Acl:
        if self.utilisateur(utilisateur_id) is None:
            raise AclInvalide("contributeur inconnu")
        return self._remplacer(self._exigee(harness_id).avec(utilisateur_id))

    def retirer_contributeur(self, harness_id: str, utilisateur_id: str) -> Acl:
        return self._remplacer(self._exigee(harness_id).sans(utilisateur_id))

    def transferer(self, harness_id: str, vers: str, garder_ancien: bool = True) -> Acl:
        if self.utilisateur(vers) is None:
            raise AclInvalide("destinataire inconnu")
        return self._remplacer(self._exigee(harness_id).transferee_a(vers, garder_ancien))

    # --- le harness courant (RFC-005 §2.2) ---------------------------------

    def harness_courant(self, utilisateur_id: str) -> str | None:
        """L'ensemble des kata que cette personne pratique — ou rien.

        Une préférence dont le rôle a été retiré n'est pas une erreur : elle se
        lit comme absente et le défaut reprend la main. Ce défaut est le seul
        harness accessible s'il n'y en a qu'un — un déploiement mono-harness
        n'oblige donc personne à choisir, et n'a rien à migrer.
        """
        ligne = self._db.execute(
            "SELECT harness_courant FROM utilisateurs WHERE id = ?", (utilisateur_id,)
        ).fetchone()
        choisi = ligne["harness_courant"] if ligne else None
        if choisi and self.role(choisi, utilisateur_id) != ETRANGER:
            return choisi
        siens = self.harness_de(utilisateur_id)
        return siens[0][0] if len(siens) == 1 else None

    def choisir_harness(self, utilisateur_id: str, harness_id: str | None) -> str | None:
        """Pose le harness courant ; `None` efface le choix et rend au défaut.

        Choisir suppose de pouvoir lire : c'est le geste `lire` de la matrice du
        RFC-004 §3, pas un droit nouveau. Laisser passer un harness où l'on est
        étranger ferait d'une préférence un contournement d'ACL — la surface des
        modèles se calcule sur ce champ (RFC-005 §3.2).
        """
        if self.utilisateur(utilisateur_id) is None:
            raise AclInvalide("utilisateur inconnu")
        if harness_id is not None:
            exiger("lire", self.role(harness_id, utilisateur_id), harness_id)
        self._db.execute(
            "UPDATE utilisateurs SET harness_courant = ? WHERE id = ?",
            (harness_id, utilisateur_id),
        )
        self._db.commit()
        return self.harness_courant(utilisateur_id)

    # --- l'archivage (RFC-006 §5) ------------------------------------------

    def archiver(self, harness_id: str, quand: datetime | None = None) -> str:
        """Retire un harness du service, sans rien détruire.

        Le principe d'observabilité est fondateur : ce qui a été observé ne
        disparaît pas parce que la forme qui l'a produit ne sert plus. Le
        dossier et le corpus demeurent — seule cette date change.
        """
        self._exigee(harness_id)
        le = (quand or datetime.now(UTC)).isoformat(timespec="seconds")
        self._db.execute(
            "UPDATE harness_acl SET archive_le = ? WHERE harness_id = ?", (le, harness_id)
        )
        self._db.commit()
        return le

    def desarchiver(self, harness_id: str) -> None:
        """Remet un harness au service. Archiver n'est pas un aller simple."""
        self._exigee(harness_id)
        self._db.execute(
            "UPDATE harness_acl SET archive_le = NULL WHERE harness_id = ?", (harness_id,)
        )
        self._db.commit()

    def archive_le(self, harness_id: str) -> str | None:
        ligne = self._db.execute(
            "SELECT archive_le FROM harness_acl WHERE harness_id = ?", (harness_id,)
        ).fetchone()
        return (ligne["archive_le"] or None) if ligne else None

    def harness_de(self, utilisateur_id: str) -> list[tuple[str, str]]:
        """Les harness d'un utilisateur, avec son rôle — la liste de l'onglet Profil."""
        possedes = [
            (r["harness_id"], "proprietaire")
            for r in self._db.execute(
                "SELECT harness_id FROM harness_acl WHERE proprietaire = ? ORDER BY harness_id",
                (utilisateur_id,),
            )
        ]
        contribues = [
            (r["harness_id"], "contributeur")
            for r in self._db.execute(
                "SELECT harness_id FROM contributeurs WHERE utilisateur_id = ? ORDER BY harness_id",
                (utilisateur_id,),
            )
        ]
        return sorted(possedes + contribues)


TABLES = (
    "utilisateurs", "harness_acl", "invitations", "identites_externes",
    "contributeurs", "harness_depot", "sessions",
)


def transvaser(de: Comptes, vers: Comptes) -> dict[str, int]:
    """Tout ce qu'un magasin contient, dans un autre — la migration de D14.7,
    jouée une fois, et l'export des comptes (D14.8). Lignes recopiées telles
    quelles, table par table dans l'ordre des clés étrangères ; le harness
    courant, qui renvoie à une table créée après, est posé en dernier. Une
    ligne déjà là n'est pas réécrite : rejouer ne casse rien."""
    comptes: dict[str, int] = {}
    for table in TABLES:
        lignes = de._db.execute(f"SELECT * FROM {table}").fetchall()
        for ligne in lignes:
            ligne.pop("rowid", None)
            if table == "utilisateurs":
                ligne = {**ligne, "harness_courant": None}
            colonnes = ", ".join(ligne)
            marques = ", ".join("?" for _ in ligne)
            vers._db.execute(
                f"INSERT INTO {table} ({colonnes}) VALUES ({marques}) ON CONFLICT DO NOTHING",
                tuple(ligne.values()),
            )
        comptes[table] = len(lignes)
    for ligne in de._db.execute("SELECT id, harness_courant FROM utilisateurs"):
        if ligne["harness_courant"]:
            vers._db.execute(
                "UPDATE utilisateurs SET harness_courant = ? WHERE id = ?",
                (ligne["harness_courant"], ligne["id"]),
            )
    vers._db.commit()
    return comptes
