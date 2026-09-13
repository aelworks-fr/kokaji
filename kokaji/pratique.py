"""Le carnet de pratique — ce que la main remarque avant que la tête ne trie.

Kokaji capture les sessions par défaut et laisse l'annotation à un geste humain
ultérieur. Ce carnet applique le même principe à l'observateur : **on note, on
ne classe pas**. Une remarque prise en pratique est chaude et mal formée ; lui
demander sa catégorie au moment où elle arrive, c'est la perdre.

Le tri est un second geste, à la main, dans le fichier — pas un champ à remplir
à la volée.

Trois statuts, et trois seulement :

- `brut` — noté, pas encore relu. Tout entre ici.
- `promu` — devenu quelque chose : une vigilance au carnet, une RFC, un
  changement de harness, une annotation de ha. Le `vers :` dit quoi.
- `sans-suite` — relu, écarté. Écarter est une décision qu'on écrit, pas un
  silence : une note qui disparaît revient sous une autre forme six mois après.

Le carnet est un fichier Markdown que l'on peut éditer à la main, depuis
n'importe où, y compris l'éditeur web de GitHub. La ligne de commande n'est
qu'un raccourci pour l'ajout — jamais un passage obligé.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

__all__ = ["STATUTS", "Note", "ajouter", "brutes", "lire"]

CARNET_DEFAUT = Path("PRATIQUE.md")
STATUTS = ("brut", "promu", "sans-suite")

ENTREE = re.compile(
    r"^## (NOTE-\d{4}) · (\d{4}-\d{2}-\d{2})\s*$\n+^\*\*([\w-]+)\*\*(.*?)$\n+(.*?)(?=\n## NOTE-|\Z)",
    re.MULTILINE | re.DOTALL,
)

EN_TETE = """# Carnet de pratique

Ce que la pratique fait remarquer, noté sur le vif.

**On note, on ne classe pas.** Une remarque arrive mal formée et c'est très
bien : lui demander sa catégorie au moment où elle arrive, c'est la perdre.
Le tri est un second geste, à froid.

Trois statuts, et trois seulement :

| statut | ce qu'il dit |
| --- | --- |
| `brut` | noté, pas encore relu — tout entre ici |
| `promu` | devenu quelque chose ; `vers :` dit quoi |
| `sans-suite` | relu et écarté — une décision qu'on écrit, pas un silence |

Pour ajouter sans ouvrir le fichier :

```
kokaji note "le kata redemande le bénéficiaire" --kata idee@instrumentee
kokaji note --brutes
```

Ce carnet-ci est celui de la **pratique**. Celui des **vigilances** de design
vit dans `docs/carnet.md` : il ne reçoit que ce qui a été promu ici.

---
"""


@dataclass(frozen=True)
class Note:
    id: str
    date: str
    statut: str
    contexte: str
    texte: str

    @property
    def connu(self) -> bool:
        return self.statut in STATUTS

    def __str__(self) -> str:
        ou = f" · {self.contexte}" if self.contexte else ""
        premiere = self.texte.strip().splitlines()[0] if self.texte.strip() else ""
        return f"{self.id}  {self.date}  [{self.statut}]{ou}\n    {premiere}"


def lire(carnet: Path = CARNET_DEFAUT) -> list[Note]:
    """Les notes du carnet, dans l'ordre où elles ont été prises."""
    chemin = Path(carnet)
    if not chemin.is_file():
        return []
    texte = chemin.read_text(encoding="utf-8")
    return [
        Note(
            id=id_note,
            date=date,
            statut=statut,
            contexte=reste.lstrip(" —").strip(),
            texte=corps.strip(),
        )
        for id_note, date, statut, reste, corps in ENTREE.findall(texte)
    ]


def brutes(carnet: Path = CARNET_DEFAUT) -> list[Note]:
    """Ce qui attend d'être relu."""
    return [n for n in lire(carnet) if n.statut == "brut"]


def _prochain(notes: list[Note]) -> str:
    rangs = [int(n.id.split("-")[1]) for n in notes if n.id.startswith("NOTE-")]
    return f"NOTE-{max(rangs, default=0) + 1:04d}"


def ajouter(
    texte: str,
    carnet: Path = CARNET_DEFAUT,
    sujet: str = "",
    kata: str = "",
    ha: str = "",
    quand: datetime | None = None,
) -> Note:
    """Ajoute une note brute à la fin du carnet, en le créant au besoin.

    Le contexte est facultatif de bout en bout : une note sans rattachement
    vaut mieux qu'une note non prise.
    """
    if not texte.strip():
        raise ValueError("une note vide ne dit rien")

    chemin = Path(carnet)
    existantes = lire(chemin)
    note = Note(
        id=_prochain(existantes),
        date=(quand or datetime.now(UTC)).strftime("%Y-%m-%d"),
        statut="brut",
        contexte=" · ".join(
            morceau
            for morceau in (
                f"`{kata}`" if kata else "",
                f"sujet : {sujet}" if sujet else "",
                ha,
            )
            if morceau
        ),
        texte=texte.strip(),
    )

    if not chemin.is_file():
        chemin.write_text(EN_TETE, encoding="utf-8")

    ligne = f"**{note.statut}**" + (f" — {note.contexte}" if note.contexte else "")
    ancien = chemin.read_text(encoding="utf-8").rstrip("\n")
    chemin.write_text(
        f"{ancien}\n\n## {note.id} · {note.date}\n\n{ligne}\n\n{note.texte}\n",
        encoding="utf-8",
    )
    return note
