"""Ce que la pratique a coûté, et ce qu'elle a rendu — à deux niveaux.

Les compteurs existent depuis toujours : chaque ha porte ses tours, ses blocs
d'état et ses jetons dans sa fiche. Ce qui manquait était de les **additionner**
et de les mettre en regard de ce qu'ils ont produit.

Deux niveaux, parce que deux questions distinctes se posent :

- **le harness** — ce que cette forme coûte en tout, et si la dépense dérive ;
- **le kata** — quelle étape coûte, et laquelle rend.

Un total ne compare rien
------------------------

Une conversation de dix tours coûte plus qu'une de deux sans rien dire de
l'efficacité de la forme. Ce qui compare, ce sont les **ratios** : jetons par
tour, et surtout jetons par **bloc d'état** — le prix d'une unité
d'observation, qui est ce que la forge cherche à produire.

Un kata qui coûte peu et n'observe rien n'est pas économe : il est muet. C'est
pourquoi le carré figure à côté de la dépense — le coût sans ce qu'il achète
est un chiffre qu'on peut toujours faire baisser en cessant de travailler.
"""

from __future__ import annotations

import collections
from dataclasses import dataclass, field
from pathlib import Path

from .corpus.depot import depot_pour, ref_de
from .hds import Harness

__all__ = ["Depense", "Releve", "mesurer"]


@dataclass
class Depense:
    """Ce qu'un ensemble de ha a coûté et rendu."""

    ha: int = 0
    tours: int = 0
    blocs: int = 0
    entree: int = 0
    sortie: int = 0
    carres: collections.Counter = field(default_factory=collections.Counter)

    @property
    def jetons(self) -> int:
        return self.entree + self.sortie

    @property
    def par_tour(self) -> float:
        """Ce qu'un tour de conversation coûte, en moyenne."""
        return self.jetons / self.tours if self.tours else 0.0

    @property
    def par_bloc(self) -> float:
        """Ce qu'une unité d'observation coûte.

        Le ratio qui compare vraiment : un kata qui produit peu de blocs pour
        beaucoup de jetons parle sans rien établir.
        """
        return self.jetons / self.blocs if self.blocs else 0.0

    @property
    def conformes(self) -> int:
        return self.carres.get("conforme", 0)

    @property
    def juges(self) -> int:
        """Les ha sur lesquels un carré a été prononcé.

        Tous ne le sont pas : une cible qui ne demande aucun bloc d'état n'en
        reçoit pas. Rapporter les conformes au nombre total de ha compterait
        alors comme des échecs des ha qui n'avaient rien à prouver — c'est ce
        que ce relevé affichait, « 3 conformes sur 47 », quand 7 des 47 se
        déroulaient sur une cible non instrumentée.
        """
        return sum(self.carres.values())

    def ajouter(self, scores: dict, carre: str) -> None:
        self.ha += 1
        self.tours += int(scores.get("tours") or 0)
        self.blocs += int(scores.get("blocs_etat") or 0)
        self.entree += int(scores.get("jetons_entree") or 0)
        self.sortie += int(scores.get("jetons_sortie") or 0)
        if carre:
            self.carres[carre] += 1


@dataclass
class Releve:
    """La dépense d'un harness, en tout et étape par étape."""

    harness: str
    corpus: str
    tout: Depense
    par_kata: dict[str, Depense]
    par_cible: dict[str, Depense]
    par_moteur: dict[str, Depense]
    sans_scores: int = 0
    # La part du total qui est aussi comptée dans un autre corpus du harness.
    # Elle est **incluse** dans `tout` et non retranchée : retrancher en
    # silence rendrait juste un total que personne ne saurait relire. On dit
    # de combien il est faux, et de quel côté.
    doubles: Depense = field(default_factory=Depense)


def _carre_du_dossier(dossier) -> str:
    """Le verdict écrit à côté du ha, ou rien s'il n'a pas été prononcé."""
    texte = depot_pour().carre(ref_de(dossier))
    if not texte:
        return ""
    premiere = texte.splitlines()[0]
    return premiere.split("—")[-1].strip() if "—" in premiere else ""


def mesurer(harness: Harness, corpus: Path | None = None) -> Releve:
    """Additionne ce que le corpus a coûté, sans rien recalculer.

    Les compteurs viennent des fiches, c'est-à-dire de l'observation elle-même.
    Les recalculer depuis le journal donnerait des chiffres plus fins et une
    autre nature : le journal dit ce qui a été appelé, la fiche dit ce qui a été
    **observé**. On additionne des observations.

    Un ha sans compteurs est compté à part plutôt qu'ignoré : le taire ferait
    d'un corpus à moitié mesuré un corpus qui a l'air complet.
    """
    from .corpus import deja_ailleurs, existants

    racine = Path(corpus) if corpus is not None else harness.corpus
    ailleurs = deja_ailleurs(harness, racine)
    en_double = {
        dossier for session, dossier in existants(racine).items() if session in ailleurs
    }
    releve = Releve(
        harness=harness.id,
        corpus=racine.name,
        tout=Depense(),
        par_kata={},
        par_cible={},
        par_moteur={},
    )

    depot = depot_pour(harness)
    for ref in depot.tous(racine):
        dossier = ref.chemin
        texte = depot.fiche(ref)
        if texte is None or not texte.startswith("---"):
            continue
        entete = depot.entete(ref)
        scores = entete.get("scores") or {}
        if not scores:
            releve.sans_scores += 1
            continue

        carre = _carre_du_dossier(dossier)
        releve.tout.ajouter(scores, carre)
        if dossier in en_double:
            releve.doubles.ajouter(scores, carre)
        for table, cle in (
            (releve.par_kata, entete.get("kata")),
            (releve.par_cible, entete.get("cible")),
            (releve.par_moteur, entete.get("moteur")),
        ):
            table.setdefault(str(cle or "—"), Depense()).ajouter(scores, carre)

    return releve


def rendre(releve: Releve) -> str:
    """Le relevé au terminal — le harness d'abord, ses kata ensuite."""
    tete = (
        f"{releve.harness} · corpus {releve.corpus} — {releve.tout.ha} ha, "
        f"{releve.tout.tours} tour(s), {releve.tout.blocs} bloc(s) d'état"
    )
    jetons = (
        f"  jetons : {releve.tout.jetons} "
        f"({releve.tout.entree} en entrée, {releve.tout.sortie} en sortie)"
    )
    ratio = f"  par tour : {releve.tout.par_tour:.0f} · par bloc d'état : " + (
        f"{releve.tout.par_bloc:.0f}" if releve.tout.blocs else "aucun bloc"
    )
    lignes = [tete, jetons, ratio]
    if releve.tout.carres:
        dit = " · ".join(f"{n} {v}" for v, n in releve.tout.carres.most_common())
        lignes.append(f"  carré : {dit}")
    if releve.sans_scores:
        lignes.append(f"  {releve.sans_scores} ha sans compteurs, non comptés")
    if releve.doubles.ha:
        lignes.append(
            f"  ⚠ {releve.doubles.ha} ha sont aussi dans un autre corpus : "
            f"{releve.doubles.jetons} jetons comptés deux fois, ci-dessus compris"
        )

    for titre, table in (
        ("kata", releve.par_kata),
        ("cible", releve.par_cible),
        ("moteur", releve.par_moteur),
    ):
        if len(table) < 1:
            continue
        lignes += ["", f"  par {titre}"]
        lignes.append(
            f"    {'':22} {'ha':>4} {'tours':>6} {'jetons':>9} "
            f"{'/tour':>6} {'/bloc':>7}  conformes"
        )
        for cle, d in sorted(table.items(), key=lambda x: -x[1].jetons):
            bloc = f"{d.par_bloc:.0f}" if d.blocs else "—"
            lignes.append(
                f"    {cle[:22]:22} {d.ha:>4} {d.tours:>6} {d.jetons:>9} "
                f"{d.par_tour:>6.0f} {bloc:>7}  {d.conformes}/{d.juges or '—'}"
            )
    return "\n".join(lignes)
