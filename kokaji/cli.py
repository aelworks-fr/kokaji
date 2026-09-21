"""La ligne de commande de Kokaji.

Une commande par geste de la forge. Aujourd'hui : valider. Viendront `forge`
(§4) et `trempe` (§5).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from .corpus import ecarter, verser
from .corpus.depot import depot_pour, identifiant_de, ref_de
from .forge import SORTIE_DEFAUT, ForgeImpossible, TrempeEchouee, forger_harness
from .forge.coupe import charger_registre, forger
from .hds import ManifestInvalide, charger, charger_valides
from .middleware import veiller
from .middleware.reabstraction import reabstraire
from .pratique import CARNET_DEFAUT, ajouter, brutes, lire
from .qg import composer, rendre_texte, sujets
from .trempe.banc import Passerelle, Resultat, evaluer, jouer, juger, rapport
from .trempe.banc.juge import juger_conduite
from .trempe.banc.nature import mesurer
from .trempe.banc.persona import PersonaInvalide, charger_tous
from .trempe.depot import trempe_du_depot
from .trempe.statique import verifier


def _valider(chemins: list[Path]) -> int:
    """Valide un ou plusieurs harness, chargés côte à côte et isolés (R2.2)."""
    charges, refuses = [], 0

    for chemin in chemins:
        try:
            harness = charger(chemin)
        except ManifestInvalide as err:
            refuses += 1
            print(f"✗ {err}", file=sys.stderr)
            continue
        charges.append(harness)
        print(
            f"✓ {harness.id} — {harness.nom} v{harness.version} : "
            f"{len(harness.kata)} kata, {len(harness.cibles)} cible(s)"
        )

    doublons = {h.id for h in charges if [x.id for x in charges].count(h.id) > 1}
    if doublons:
        print(
            f"✗ id de harness partagé par plusieurs dossiers : {', '.join(sorted(doublons))}",
            file=sys.stderr,
        )
        return 1
    return 1 if refuses else 0


def _forge(chemin: Path, sortie: Path, cibles: tuple[str, ...], trempe: bool = True) -> int:
    try:
        harness = charger(chemin)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    try:
        resultat = forger_harness(harness, sortie=sortie, cibles=cibles, trempe=trempe)
    except (ForgeImpossible, TrempeEchouee) as err:
        print(f"✗ {harness.id} : {err}", file=sys.stderr)
        return 1

    print(f"✓ {harness.id} — {len(resultat.coupes)} coupe(s) dans {resultat.racine}")
    for changement in resultat.changements:
        marque = {"nouveau": "+", "modifie": "~", "inchange": " "}[changement.etat]
        print(f"  {marque} {changement.cible}/{changement.kata}")
    if not resultat.modifiees:
        print("  rien n'a changé depuis la forge précédente")
    return 0


def _trempe(chemin: Path) -> int:
    """La trempe seule : on assemble en mémoire, on vérifie, on n'écrit rien."""
    try:
        harness = charger(chemin)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    try:
        template = harness.template.read_text(encoding="utf-8")
        registre = charger_registre(harness.trempe.registre)
        coupes = [
            forger(harness, kata, cible, template, registre)
            for cible in harness.cibles
            for kata in harness.kata
        ]
    except ForgeImpossible as err:
        print(f"✗ {harness.id} : {err}", file=sys.stderr)
        return 1

    anomalies = verifier(harness, coupes, registre)
    if not anomalies:
        print(f"✓ {harness.id} — {len(coupes)} coupe(s) trempée(s), aucune anomalie")
        return 0

    print(f"✗ {harness.id} — {len(anomalies)} anomalie(s)", file=sys.stderr)
    for anomalie in anomalies:
        print(f"  - {anomalie}", file=sys.stderr)
    return 1


def _depot(racine: Path) -> int:
    """R10.2 — la forge se forge elle-même."""
    trouvailles = trempe_du_depot(racine)
    if not trouvailles:
        print(f"✓ {racine} — aucun terme interdit")
        return 0

    print(f"✗ {racine} — {len(trouvailles)} occurrence(s)", file=sys.stderr)
    for trouvaille in trouvailles:
        print(f"  - {trouvaille}", file=sys.stderr)
    return 1


def _corpus_choisi(harness, nom: str | None):
    """Le corpus visé, ou celui par défaut du harness."""
    if not nom:
        return None
    declare = harness.corpus_par_nom(nom)
    if declare is None:
        connus = ", ".join(c.nom for c in harness.corpus_nommes)
        raise SystemExit(f"✗ corpus inconnu : {nom!r} (connus : {connus})")
    return declare.chemin


def _middleware(args) -> int:
    """Capture les sessions closes, en extrait l'état, vérifie le carré (§7)."""
    harness, refuses = charger_valides(args.harness)
    for nom, motif in refuses:
        print(f"✗ {nom} — {motif}", file=sys.stderr)
    if not harness:
        print("✗ aucun harness exploitable", file=sys.stderr)
        return 1

    if args.boucle:
        return _veille_en_boucle(harness, args)

    maintenant = args.maintenant or datetime.now(UTC).isoformat()
    veilles, echecs, doubles = _une_passe(harness, args, maintenant)
    echecs = [*((nom, motif) for nom, motif in refuses), *echecs]
    for identifiant, motif in echecs:
        print(f"✗ {identifiant} — {motif}", file=sys.stderr)
    for identifiant, session, dossier in doubles:
        print(f"≠ {identifiant}/{session} déjà versée en {dossier.parent.name}/{dossier.name}")

    if not veilles:
        print("aucune session close à capturer")
        return 1 if echecs else 0

    for identifiant, veille in veilles:
        alerte = " ⚠" if veille.carre == "sur-promesse" else ""
        print(
            f"+ {identifiant}/{veille.ha}  {veille.kata}  {veille.blocs} bloc(s), "
            f"{veille.fautes} faute(s)  carré : {veille.carre or 'non requis'}{alerte}"
        )
    sur_promesses = [v for _, v in veilles if v.carre == "sur-promesse"]
    if sur_promesses:
        print(
            f"\n{len(sur_promesses)} ha en sur-promesse — "
            "le kata garantit ce que la pratique ne livre pas (RFC-002 §4).",
            file=sys.stderr,
        )
    return 1 if sur_promesses or echecs else 0


def _une_passe(harness: dict, args, maintenant: str) -> tuple[list, list, list]:
    """Un tour de veille sur chaque harness — les captures, les échecs, les doubles.

    **Un harness qui échoue n'arrête pas les autres.** La veille est un service :
    un manifest cassé, un corpus non déclaré ou un dossier retiré sur l'un ne
    doit pas priver les autres de capture. C'est la leçon de NOTE-0009, où un
    seul manifest refusé a fait sortir le processus — et deux jours sans capture
    ont suivi, sans que rien ne le dise.

    L'échec est donc rendu, jamais avalé : c'est l'appelant qui décide s'il
    arrête (une passe unique) ou s'il continue (la boucle).

    Les sessions refusées parce qu'elles sont déjà dans un autre corpus du
    harness sont rendues de la même façon. La capture continue est le chemin où
    un refus muet coûte le plus cher : elle tourne sans personne devant, et un
    ha jamais écrit ne manque qu'au moment où on le cherche.
    """
    veilles: list = []
    echecs: list = []
    doubles: list = []
    for identifiant, un_harness in sorted(harness.items()):
        try:
            corpus = _corpus_choisi(un_harness, args.corpus)
        except SystemExit as err:
            echecs.append((identifiant, str(err).removeprefix("✗ ")))
            continue
        try:
            captures = veiller(
                un_harness,
                journal=args.journal,
                repos=args.repos,
                maintenant=maintenant,
                source=args.source,
                rattraper=args.rattraper,
                corpus=corpus,
                cles=tuple(args.cle_appelante),
            )
        except Exception as err:  # noqa: BLE001 — voir la docstring : on rend, on ne meurt pas
            echecs.append((identifiant, f"{type(err).__name__} : {err}"))
            continue
        veilles.extend((identifiant, capture) for capture in captures.veilles)
        doubles.extend(
            (identifiant, session, dossier)
            for session, dossier in sorted(captures.doubles.items())
        )
    return veilles, echecs, doubles


def _veille_en_boucle(harness: dict, args) -> int:
    """La capture continue — un tour toutes les `--boucle` secondes.

    Aucun échec ne sort de la boucle. Un harness fautif se signale à chaque
    tour et les autres continuent d'être capturés : une veille morte et un dojo
    calme produisent le même silence, et c'est ce silence-là qu'on refuse.
    """
    noms = ", ".join(sorted(harness))
    print(
        f"veille de {len(harness)} harness ({noms}) toutes les {args.boucle:.0f}s "
        "(Ctrl-C pour arrêter)"
    )
    dits: set = set()
    try:
        while True:
            veilles, echecs, doubles = _une_passe(harness, args, datetime.now(UTC).isoformat())
            for identifiant, motif in echecs:
                print(f"✗ {identifiant} — {motif}", file=sys.stderr, flush=True)
            for identifiant, session, dossier in doubles:
                # Dit une fois par session, pas à chaque tour : la boucle
                # repasse sur tout le journal, et répéter le même double
                # toutes les trente secondes le rendrait aussi illisible
                # qu'un silence.
                if (identifiant, session) in dits:
                    continue
                dits.add((identifiant, session))
                print(
                    f"≠ {identifiant}/{session} déjà versée en "
                    f"{dossier.parent.name}/{dossier.name}",
                    flush=True,
                )
            for identifiant, veille in veilles:
                alerte = " ⚠" if veille.carre == "sur-promesse" else ""
                print(
                    f"+ {identifiant}/{veille.ha}  {veille.kata}  {veille.blocs} bloc(s)  "
                    f"carré : {veille.carre or 'non requis'}{alerte}",
                    flush=True,
                )
            time.sleep(args.boucle)
    except KeyboardInterrupt:
        print("\nveille arrêtée")
        return 0


def _usage(args) -> int:
    """Ce que la pratique a coûté, et ce qu'elle a rendu."""
    from .usage import mesurer, rendre

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    releve = mesurer(harness, _corpus_choisi(harness, args.corpus))
    if not releve.tout.ha:
        print("aucun ha mesuré — rien n'a encore été pratiqué")
        return 0
    print(rendre(releve))
    return 0


def _passerelle(args) -> int:
    """Confronte l'autorisation de la clé à ce que la forge déclare.

    Par défaut on **constate**, on n'écrit pas. Les trois pannes qu'a produites
    ce décrochage n'ont jamais été des erreurs d'écriture : elles ont été des
    silences. Réparer sans pouvoir constater, c'est repartir sans savoir quand
    ça recommencera.
    """
    import yaml

    from .passerelle import (
        PasserelleInjoignable,
        autorisation_de_la_cle,
        ecart_d_autorisation,
        entrees_de_la_passerelle,
        modeles_virtuels,
        poser_model_list,
        publier_autorisation,
        rendre_model_list,
    )

    harness, refuses = charger_valides(args.harness)
    for nom, motif in refuses:
        print(f"✗ {nom} — {motif}", file=sys.stderr)
    if not harness:
        print("✗ aucun harness exploitable", file=sys.stderr)
        return 1

    attendus = tuple(
        nom for _, h in sorted(harness.items()) for nom in modeles_virtuels(h)
    ) + tuple(args.nu)

    if args.config:
        moteurs = yaml.safe_load(Path(args.moteurs).read_text(encoding="utf-8")) or {}
        entrees = entrees_de_la_passerelle(harness, moteurs, tuple(args.nu))
        poser_model_list(args.config, rendre_model_list(entrees))
        print(f"✓ {len(entrees)} modèle(s) posés dans {args.config}")
        if not args.url:
            return 0
    url = args.url or "http://127.0.0.1:4000"

    try:
        autorises = autorisation_de_la_cle(url, args.admin, args.cle)
    except PasserelleInjoignable as err:
        print(f"✗ passerelle : {err}", file=sys.stderr)
        return 1

    ecart = ecart_d_autorisation(attendus, autorises)
    if not ecart:
        print(f"✓ la clé autorise exactement ce que la forge déclare — {len(attendus)} modèle(s)")
        return 0

    print(f"✗ la clé et la forge ont décroché — {len(ecart.manquants) + len(ecart.surnumeraires)} écart(s)",
          file=sys.stderr)
    print(ecart.rendre(), file=sys.stderr)

    if not args.publier:
        print("\n`--publier` réécrit l'autorisation. Rien n'a été touché.", file=sys.stderr)
        return 1

    try:
        publier_autorisation(url, args.admin, args.cle, attendus)
    except PasserelleInjoignable as err:
        print(f"✗ publication refusée : {err}", file=sys.stderr)
        return 1
    print(f"✓ autorisation publiée — {len(attendus)} modèle(s)")
    return 0


def _vigie(args) -> int:
    """Les vérifications en continu, et leur verdict déposé où le QG le lit.

    Une vérification qu'on lance à la main retombe dans le silence qu'elle
    combat : elle tourne donc seule. Et elle écrit **même quand tout va bien**,
    parce que c'est la fraîcheur du verdict qui trahit une vigie morte — pas
    son contenu.
    """
    from .vigie import Verdict, ecrire_verdicts, verifier_configuration, verifier_passerelle

    harness, refuses = charger_valides(args.harness)
    for nom, motif in refuses:
        print(f"✗ {nom} — {motif}", file=sys.stderr)
    if not harness:
        print("✗ aucun harness exploitable", file=sys.stderr)
        return 1

    def un_tour() -> list:
        verdicts = [
            Verdict(
                "harness chargés",
                not refuses,
                ", ".join(sorted(harness)) if not refuses else f"{len(refuses)} refusé(s)",
            )
        ]
        if args.url and args.cle:
            verdicts.append(
                verifier_passerelle(harness, args.url, args.admin, args.cle, tuple(args.nu))
            )
        if args.config:
            verdicts.append(verifier_configuration(harness, args.config, tuple(args.nu)))
        if args.rendu:
            from .rendu import regarder

            verdicts.extend(regarder(args.rendu))
        return verdicts

    if not args.boucle:
        verdicts = un_tour()
        ecrire_verdicts(args.verdicts, verdicts, 0)
        for v in verdicts:
            print(f"{'✓' if v.tient else '✗'} {v.quoi} — {v.detail}")
        return 0 if all(v.tient for v in verdicts) else 1

    print(f"vigie toutes les {args.boucle:.0f}s (Ctrl-C pour arrêter)", flush=True)
    try:
        while True:
            verdicts = un_tour()
            ecrire_verdicts(args.verdicts, verdicts, args.boucle)
            for v in verdicts:
                if not v.tient:
                    print(f"✗ {v.quoi} — {v.detail}", file=sys.stderr, flush=True)
            time.sleep(args.boucle)
    except KeyboardInterrupt:
        print("\nvigie arrêtée")
        return 0


def _service(args) -> int:
    try:
        from .middleware.service import servir
    except ModuleNotFoundError as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1
    return servir(
        args.harness, args.journal, args.hote, args.port, args.comptes,
        args.entete_identite, args.portail,
    )


def _qg(args) -> int:
    """Le fil d'ariane au terminal — la même vue que la page (§8)."""
    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    vise = args.corpus_nom or harness.corpus_nommes[0].nom
    if harness.corpus_par_nom(vise) is None:
        connus_noms = ", ".join(c.nom for c in harness.corpus_nommes)
        print(f"✗ corpus inconnu : {vise!r} (connus : {connus_noms})", file=sys.stderr)
        return 1
    connus = sujets(harness, args.journal, vise)
    if not connus:
        print("aucun sujet observé — le corpus ne porte aucun bloc d'état", file=sys.stderr)
        return 1
    if args.liste:
        for sujet in connus:
            print(f"  {sujet}")
        return 0

    choisi = args.sujet or connus[0]
    if choisi not in connus:
        print(f"✗ sujet inconnu : {choisi!r}", file=sys.stderr)
        return 1
    print(rendre_texte(harness, composer(harness, choisi, args.journal, vise)))
    return 0


def _reabstraire(args) -> int:
    """Reconstruire l'état d'un ha depuis son transcript (RFC-002 §7.2)."""
    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    racine = _corpus_choisi(harness, args.corpus_nom) or harness.corpus
    dossiers = [r.chemin for r in depot_pour(harness).tous(racine) if r.nom.startswith(args.ha)]
    if not dossiers:
        print(f"✗ aucun ha commençant par {args.ha!r} dans {racine}", file=sys.stderr)
        return 1

    reglages = {}
    if args.cle:
        reglages["cle"] = args.cle
    if getattr(args, "passerelle", None):
        reglages["base"] = args.passerelle
    passerelle = Passerelle(**reglages)
    if not passerelle.cle:
        print("✗ DOJO_CLE_BANC manquant — voir dojo/README.md", file=sys.stderr)
        return 1

    for dossier in dossiers:
        print(f"→ {dossier.name}", file=sys.stderr)
        faite = reabstraire(harness, dossier, passerelle, args.modele, args.temperature)
        print(
            f"  {faite.blocs} bloc(s), {faite.fautes} faute(s)  carré : {faite.carre}"
            f"  sujet : {faite.sujet or '—'}"
        )
    print("\nÉtat reconstruit, marqué `reabstrait` — c'est une lecture, pas une observation.")
    return 0


def _purger(args) -> int:
    """Écarter des ha du corpus — et le déclarer, sinon la veille les recrée."""

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    racine = _corpus_choisi(harness, args.corpus_nom) or harness.corpus
    quand = datetime.now(UTC).isoformat()
    vises = []

    depot = depot_pour(harness)
    for dossier in depot.tous(racine):
        texte = depot.fiche(dossier)
        if texte is None:
            continue
        if "statut: brut" not in texte:
            continue  # un ha annoté ne s'écarte pas à la volée
        session = texte.split("session `")[-1].split("`")[0] if "session `" in texte else ""
        if args.session:
            if session in args.session:
                # Le fichier des écartés est ce qu'on relira dans six mois :
                # « écarté nommément » y dit qui, jamais pourquoi.
                vises.append((dossier, session, args.raison or "écarté nommément"))
            continue
        contenu = depot.transcript(dossier) or ""
        if args.parasites and ("### Task:" in contenu or contenu.count("## Tour ") <= 1):
            vises.append((dossier, session, "appel d'interface, pas une session de kata"))

    if not vises:
        print("rien à écarter")
        return 0

    for dossier, session, raison in vises:
        print(f"  − {dossier.nom}  ({raison})")
        if not args.essai_seulement:
            ecarter(racine, session, raison, quand)
            depot.supprimer(dossier)

    if args.essai_seulement:
        print(f"\n{len(vises)} ha seraient écartés. Relance sans --essai pour le faire.")
    else:
        print(f"\n{len(vises)} ha écartés et déclarés dans .ecartes.jsonl —")
        print("la veille ne les recréera pas. Les transcripts restent au journal.")
    return 0


def _regression(args) -> int:
    """R5.6 — rejouer les ha qu'un changement de source a périmés."""
    from .trempe.banc.rejeu import modele_virtuel, perimes, rejouer

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    # La forge en mémoire donne la version de coupe d'aujourd'hui, sans rien écrire.
    try:
        template = harness.template.read_text(encoding="utf-8")
        registre = charger_registre(harness.trempe.registre)
        actuelles = {
            (kata.id, cible.id): forger(harness, kata, cible, template, registre).estampille.version_coupe
            for cible in harness.cibles
            for kata in harness.kata
        }
    except ForgeImpossible as err:
        print(f"✗ {harness.id} : {err}", file=sys.stderr)
        return 1

    candidats = perimes(harness, actuelles, _corpus_choisi(harness, args.corpus_nom))
    if args.variable:
        vises = set(args.variable)
        candidats = [c for c in candidats if vises & set(c.design_exerce)]
    if not candidats:
        print("aucun ha périmé — le corpus est à jour avec la forge")
        return 0

    print(f"{len(candidats)} ha périmé(s) par un changement de source :")
    for c in candidats:
        variables = ", ".join(c.design_exerce) or "aucune variable annotée"
        print(f"  {c.dossier.name}  {c.version_ha} → {c.version_actuelle}  ({variables})")
    if args.essai_seulement:
        print("\nRelance sans --essai pour les rejouer.")
        return 0

    reglages = {}
    if args.cle:
        reglages["cle"] = args.cle
    if getattr(args, "passerelle", None):
        reglages["base"] = args.passerelle
    passerelle = Passerelle(**reglages)
    if not passerelle.cle:
        print("✗ DOJO_CLE_BANC manquant — voir dojo/README.md", file=sys.stderr)
        return 1
    if not passerelle.cle.startswith("sk-"):
        # Une clé factice laissée dans `.env` produit un 401 par tour, et le
        # rejeu s'achève sur autant d'interruptions qu'il y a de ha. Autant le
        # dire avant de brûler des appels.
        print(
            f"✗ la clé ne ressemble pas à une clé de passerelle : {passerelle.cle[:6]}… "
            "— la passerelle attend une valeur commençant par `sk-`",
            file=sys.stderr,
        )
        return 1

    print()
    regressions = 0
    interrompus = 0
    for c in candidats[: args.plafond]:
        kata = harness.kata_par_id(c.kata)
        if kata is None:
            continue
        modele = args.modele or modele_virtuel(
            harness.id, c.kata, c.cible, args.cible_par_defaut
        )
        print(f"→ {c.dossier.name} contre {modele}", file=sys.stderr)
        ecart = rejouer(harness, kata, c, modele, passerelle, args.temperature)

        if ecart.interrompu:
            print(f"  ! {ecart.interrompu}")
            interrompus += 1
            continue
        if not ecart.mouvements:
            print(f"  = {ecart.ha} — rien n'a bougé")
            continue
        marque = "⚠" if ecart.regression else " "
        print(f"  {marque} {ecart.ha}")
        for regle, avant, apres in ecart.mouvements:
            sens = "↑" if apres > avant else "↓"
            print(f"      {sens} {regle} : {avant} → {apres}")
        regressions += 1 if ecart.regression else 0

    print()
    joues = len(candidats[: args.plafond]) - interrompus
    if interrompus:
        print(
            f"{interrompus} rejeu(x) interrompu(s) — ces ha n'ont pas été mesurés.",
            file=sys.stderr,
        )
    if regressions:
        print(f"{regressions} ha où une règle mord là où elle se taisait.", file=sys.stderr)
        return 1
    if not joues:
        # Ne jamais conclure sur un silence. Zéro rejeu abouti n'est pas zéro
        # régression : c'est zéro mesure, et l'annoncer comme un succès est
        # précisément la façon dont une instrumentation ment.
        print("aucun rejeu n'a abouti : rien n'a été mesuré.", file=sys.stderr)
        return 1
    print(
        f"aucune régression sur {joues} ha rejoué(s) : "
        "les règles ne mordent nulle part où elles se taisaient."
    )
    return 1 if interrompus else 0


def _resserrer(args) -> int:
    """RFC-002 §6.4 — proposer le `produit` que la pratique tient vraiment."""
    from .trempe.banc.resserrage import fragment, observer, proposer

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    corpus = _corpus_choisi(harness, args.corpus_nom)
    trouve = False

    for kata in harness.kata:
        observations = observer(harness, kata, corpus)
        if not observations or all(o.observes == 0 for o in observations):
            continue

        print(f"{kata.id} — {max(o.observes for o in observations)} ha observé(s)")
        propositions = []
        for observation in observations:
            proposition = proposer(harness, observation, args.minimum)
            if proposition is not None:
                propositions.append(proposition)
                print(f"  ↑ {proposition}")
            elif observation.observes < args.minimum:
                print(
                    f"  · {observation.champ} : {observation.observes} ha seulement "
                    f"(il en faut {args.minimum}) — rien à conclure"
                )
            else:
                print(f"  = {observation.champ} : `{observation.declare}` tient au plus juste")

        if propositions:
            trouve = True
            print("\n" + fragment(kata, propositions) + "\n")
        else:
            print()

    if not trouve:
        print("aucun resserrage à proposer — les contrats collent à la pratique.")
        return 0

    print(
        "Ces fragments ne sont pas appliqués : modifier un f♯ est une version\n"
        "majeure du kata, et cette décision appartient au forgeron (RFC-002 §3)."
    )
    return 0


def _rapport_nature(harness, kata: str, personas, diagnostics, passes: int = 1) -> str:
    """La justesse du diagnostic, sa couverture, et le verdict face au seuil.

    À `passes > 1`, on ne rend plus un verdict par campagne mais une
    **distribution** : un compte de réussite par kin, et un verdict de stabilité
    (RFC-003 §7)."""
    from .trempe.banc.nature import couverture, verdict, verdict_distribue

    if passes > 1:
        lignes = [f"justesse du diagnostic de nature — {passes} passes par kin"]
        rendu = verdict_distribue(harness, kata, diagnostics)
        for d in rendu.distributions:
            lignes.append(f"  {d}")
        naturelles = _natures_du_kata(harness, kata)
        couv = couverture(kata, personas, naturelles)
        if couv.manquantes:
            lignes.append(f"\n  natures jamais jouées : {', '.join(couv.manquantes)}")
        lignes.append(f"\n  {rendu}")
        if rendu.pieges and not rendu.pieges_stables:
            lignes.append("  un piège tombe sur au moins une passe — le §7 le veut tenu à chaque fois")
        if rendu.seuil == 0:
            lignes.append(
                "  aucun seuil déclaré dans `trempe.justesse` : rien à quoi confronter ces taux"
            )
        return "\n".join(lignes)

    lignes = ["justesse du diagnostic de nature"]
    for d in diagnostics:
        lignes.append(f"  {d}")
        if d.revisions:
            lignes.append(f"      {d.revisions} révision(s) en cours d'échange")

    naturelles = _natures_du_kata(harness, kata)
    couv = couverture(kata, personas, naturelles)
    if couv.manquantes:
        # Une nature jamais jouée n'est pas une nature réussie : elle est
        # inconnue. Le taire laisserait lire une bonne moyenne comme une
        # preuve de robustesse.
        lignes.append(f"\n  natures jamais jouées : {', '.join(couv.manquantes)}")

    rendu = verdict(harness, kata, diagnostics)
    lignes.append(f"\n  {rendu}")
    if rendu.pieges and not rendu.pieges_tenus:
        lignes.append("  le kin piège n'est pas tenu — le RFC-003 §7 l'exige séparément")
    if rendu.seuil == 0:
        lignes.append(
            "  aucun seuil déclaré dans `trempe.justesse` : rien à quoi confronter ce taux"
        )
    return "\n".join(lignes)


def _natures_du_kata(harness, kata: str) -> tuple[str, ...]:
    """Les natures que la source du kata déclare — Kokaji n'en connaît aucune."""
    import yaml as _yaml

    trouve = harness.kata_par_id(kata)
    if trouve is None:
        return ()
    source = _yaml.safe_load(trouve.source.read_text(encoding="utf-8")) or {}
    return tuple(str(n) for n in (source.get("natures") or []))


def _banc(args) -> int:
    try:
        harness = charger(args.harness)
        personas = charger_tous(harness.personas)
    except (ManifestInvalide, PersonaInvalide) as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    if args.persona:
        personas = tuple(p for p in personas if p.id in args.persona)
        inconnus = set(args.persona) - {p.id for p in personas}
        if inconnus:
            print(f"✗ persona(s) inconnu(s) : {', '.join(sorted(inconnus))}", file=sys.stderr)
            return 1
    if not personas:
        print(f"✗ {harness.id} : aucun persona à jouer", file=sys.stderr)
        return 1

    kata = harness.kata_par_id(args.kata)
    if kata is None:
        print(f"✗ kata inconnu : {args.kata!r}", file=sys.stderr)
        return 1

    reglages = {}
    if args.cle:
        reglages["cle"] = args.cle
    if getattr(args, "passerelle", None):
        reglages["base"] = args.passerelle
    passerelle = Passerelle(**reglages)
    if not passerelle.cle:
        print("✗ DOJO_CLE_BANC manquant — voir dojo/README.md", file=sys.stderr)
        return 1

    resultats: list[Resultat] = []
    diagnostics: list = []
    for modele in args.modele or [harness.espace(kata.id)]:
        for persona in personas:
            print(f"→ {persona.id} × {modele}", file=sys.stderr)
            tours, interrompu = jouer(
                persona,
                modele_kata=modele,
                modele_persona=args.persona_modele,
                passerelle=passerelle,
                tours_max=args.tours,
                temperature=args.temperature,
            )
            verdicts = ()
            if args.nature and tours:
                diagnostic = mesurer(persona, kata.id, tours)
                diagnostics.append(diagnostic)
                # RFC-003 §7 — la stabilité se mesure sur plusieurs passes du
                # même kin. Les passes de plus ne rejouent que le diagnostic :
                # pas de juge ni de constats, pour ne pas multiplier le coût.
                for passe in range(2, args.passes + 1):
                    print(f"→ {persona.id} × {modele} (passe {passe}/{args.passes})", file=sys.stderr)
                    tours_n, _ = jouer(
                        persona, modele_kata=modele, modele_persona=args.persona_modele,
                        passerelle=passerelle, tours_max=args.tours, temperature=args.temperature,
                    )
                    if tours_n:
                        diagnostics.append(mesurer(persona, kata.id, tours_n))
                if args.juge and diagnostic.finale:
                    conduite = juger_conduite(
                        harness, list(tours), diagnostic.finale,
                        passerelle, args.juge, args.temperature,
                    )
                    if conduite is not None:
                        verdicts += (conduite,)
            if args.juge and tours:
                try:
                    # `+=` et non `=` : le verdict de conduite est rendu juste
                    # au-dessus, et une affectation l'effacerait sans bruit.
                    verdicts += juger(
                        harness, list(tours), passerelle, args.juge,
                        variables=tuple(args.variable), temperature=args.temperature,
                    )
                except ValueError as err:
                    print(f"✗ {err}", file=sys.stderr)
                    return 1
            resultats.append(
                Resultat(
                    harness=harness.id,
                    kata=kata.id,
                    persona=persona.id,
                    modele=modele,
                    tours=tours,
                    constats=evaluer(harness, kata, tours),
                    interrompu=interrompu,
                    verdicts=verdicts,
                )
            )

    print()
    print(rapport(resultats))
    if args.nature:
        print()
        print(_rapport_nature(harness, kata.id, personas, diagnostics, passes=args.passes))
    if args.detail:
        for resultat in resultats:
            if not resultat.constats and not resultat.verdicts:
                continue
            print(f"\n{resultat.persona} × {resultat.modele}")
            for constat in resultat.constats:
                print(f"  {constat}")
            for verdict in resultat.verdicts:
                print(f"  {verdict}")
                if verdict.citation:
                    print(f"      « {verdict.citation[:90]} »")
    return 1 if any(r.constats or r.interrompu for r in resultats) else 0


def _corpus(args) -> int:
    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    versement = verser(
        harness,
        journal=args.journal,
        sessions=tuple(args.session),
        source=args.source,
        temperature=args.temperature,
        corpus=_corpus_choisi(harness, args.corpus_nom),
    )
    verses = versement.ha
    for session, dossier in sorted(versement.doubles.items()):
        # Dit avant le reste : sans cette ligne, un versement entièrement
        # refusé afficherait « tout est déjà au corpus », ce qui est faux et
        # rassurant à la fois.
        print(f"≠ session {session} déjà versée en {dossier.parent.name}/{dossier.name}")
    if not verses:
        print("aucune session à verser — tout est déjà au corpus")
        return 0

    for ha in verses:
        print(f"+ {ha.identifiant}  {ha.kata}/{ha.cible}  {ha.tours} tours, {ha.blocs} bloc(s)")
    print(f"\n{len(verses)} ha versés en `brut` — l'annotation reste à faire.")
    return 0


def _concevoir(args) -> int:
    """Le fond du module « Design du harness » : proposer, lire un verdict, sceller.

    Deux gestes et un seul chemin : on ne scelle jamais sans avoir jugé, parce
    que sceller *est* juger puis écrire. L'aperçu n'est que le même verdict
    rendu sans la suite.
    """
    import yaml as _yaml

    from .conception import Proposition, ScellementRefuse, juger, sceller

    try:
        brut = _yaml.safe_load(args.proposition.read_text(encoding="utf-8")) or {}
        proposition = Proposition.depuis(brut)
    except (OSError, _yaml.YAMLError, TypeError, ValueError) as err:
        print(f"✗ proposition illisible : {err}", file=sys.stderr)
        return 2

    verdict = juger(args.harness, proposition)
    for changement in verdict.changements:
        print(f"  ~ {changement}")
    if not verdict.changements:
        print("rien ne change")
        return 0

    if not verdict.tient:
        print(f"\n✗ {verdict}", file=sys.stderr)
        for faute in verdict.fautes:
            print(f"  - {faute}", file=sys.stderr)
        for anomalie in verdict.anomalies:
            print(f"  - {anomalie}", file=sys.stderr)
        print(
            "\nRien n'a été écrit : une définition qui ne tient pas ne se scelle pas.",
            file=sys.stderr,
        )
        return 1

    print(f"\n✓ {verdict}")
    if verdict.touche_contrat:
        print(
            "  le contrat de "
            + ", ".join(verdict.kata_touches)
            + " change : version majeure, et les certifications tombent (RFC-002 §3)"
        )
    if not args.sceller:
        print("\nAperçu seul. Relance avec --sceller --auteur « … » pour l'inscrire.")
        return 0

    try:
        trace = sceller(args.harness, proposition, auteur=args.auteur or "", motif=args.motif)
    except ScellementRefuse as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    print(f"\nscellé par {trace.auteur} — " + ", ".join(
        f"{quoi} v{version}" for quoi, version in sorted(trace.versions.items())
    ))
    print("Les coupes sont périmées : `kokaji forge`, puis `kokaji regression` pour")
    print("mesurer ce que ce changement fait à la pratique.")
    return 0


def _compte(args) -> int:
    """Crée un compte. Le mot de passe est demandé, jamais passé en argument :
    un argument se retrouve dans l'historique du shell et dans `ps`."""
    from getpass import getpass

    from .comptes import AclInvalide, Comptes, ou_ouvrir

    mot_de_passe = getpass("mot de passe (douze caractères au moins) : ")
    if mot_de_passe != getpass("confirmer : "):
        print("les deux saisies diffèrent", file=sys.stderr)
        return 2

    comptes = Comptes(ou_ouvrir(args.comptes))
    try:
        utilisateur = comptes.creer_utilisateur(
            args.nom, args.email, mot_de_passe, admin=getattr(args, "admin", False)
        )
        if args.harness:
            comptes.enregistrer_harness(args.harness, utilisateur.id)
    except AclInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 2
    finally:
        comptes.fermer()

    print(f"{utilisateur.nom} <{utilisateur.email}> — {utilisateur.id}")
    if args.harness:
        print(f"propriétaire de « {args.harness} »")
    return 0


def _inviter(args) -> int:
    """Ouvre une porte nominative et rend le lien à envoyer.

    Rien n'est transmis d'autre que ce lien : le mot de passe sera choisi par
    l'invité, et personne d'autre ne l'aura jamais connu.
    """
    from .comptes import AclInvalide, Comptes, ou_ouvrir

    comptes = Comptes(ou_ouvrir(args.comptes))
    try:
        invitant = comptes.par_email(args.par)
        if invitant is None:
            print(f"✗ aucun compte pour {args.par}", file=sys.stderr)
            return 2
        jeton = comptes.inviter(args.email, par=invitant.id)
    except AclInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 2
    finally:
        comptes.fermer()

    if not args.base:
        print("inviter : --base ou KOKAJI_BASE est requis — le lien porte le domaine de l'instance",
              file=sys.stderr)
        return 2
    print(f"{args.base.rstrip('/')}/invitation/{jeton}")
    print(f"  pour {args.email}, valable 7 jours, une seule fois.", file=sys.stderr)
    return 0


def _rattacher(args) -> int:
    """Lie un compte à ce qui existe déjà : le harness, et la pratique orpheline.

    Les ha capturés avant que les comptes existent n'ont pas de praticien. Sans
    lui, ils restent fermés à tout le monde — c'est la bonne lecture par défaut
    (pas de fuite rétroactive), mais elle laisse une pratique sans propriétaire.
    Ce geste la rattache, une fois, en connaissance de cause.
    """
    import yaml as _yaml

    from .comptes import AclInvalide, Comptes, ou_ouvrir

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    comptes = Comptes(ou_ouvrir(args.comptes))
    try:
        qui = comptes.par_email(args.email)
        if qui is None:
            print(f"✗ aucun compte pour {args.email}", file=sys.stderr)
            return 2
        if comptes.acl(harness.id) is None:
            comptes.enregistrer_harness(harness.id, qui.id)
            print(f"+ {harness.id} : propriétaire {qui.nom}")
        else:
            print(f"  {harness.id} : déjà enregistré, propriété inchangée")
    except AclInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 2
    finally:
        comptes.fermer()

    if not args.praticien:
        print("  (relance avec --praticien pour rattacher aussi les ha orphelins)")
        return 0

    rattaches = 0
    depot = depot_pour(harness)
    for corpus in harness.corpus_nommes:
        for dossier in depot.tous(corpus.chemin):
            texte = depot.fiche(dossier)
            if texte is None or not texte.startswith("---"):
                continue
            avant, entete, apres = texte.split("---", 2)
            donnees = _yaml.safe_load(entete) or {}
            if donnees.get("praticien"):
                continue
            donnees["praticien"] = qui.id
            depot.ecrire_fiche(
                dossier,
                avant + "---"
                + _yaml.safe_dump(donnees, allow_unicode=True, sort_keys=False)
                + "---" + apres,
            )
            rattaches += 1
    print(f"+ {rattaches} ha orphelin(s) rattaché(s) à {qui.nom}")
    print("  leur visibilité reste `privee` : rattacher n'est pas verser.")
    return 0


def _importer(args) -> int:
    """RFC-008 N0 — les prompts entrent tels quels, la provenance s'estampille."""
    from .adoption import AdoptionRefusee, adopter_etape, importer

    if args.dans:
        harness = None
        for chemin in args.prompts:
            chemin = Path(chemin)
            if not chemin.is_file():
                print(f"✗ fichier absent : {chemin} — rien n'a été ajouté", file=sys.stderr)
                return 1
            try:
                harness = adopter_etape(
                    args.dans, chemin.stem, chemin.read_text(encoding="utf-8")
                )
            except AdoptionRefusee as err:
                print(f"✗ {err}", file=sys.stderr)
                return 1
            print(f"  + {harness.espace(harness.kata[-1].id)}")
        print(f"✓ {harness.id} — {len(harness.kata)} kata désormais. Reforge, puis republie.")
        return 0

    if not (args.vers and args.identifiant and args.nom):
        print("✗ il faut --vers, --id et --nom pour créer — ou --dans pour étendre",
              file=sys.stderr)
        return 2

    try:
        harness = importer(
            args.prompts,
            vers=args.vers,
            identifiant=args.identifiant,
            nom=args.nom,
            source=args.provenance,
            version_source=args.version_source,
        )
    except AdoptionRefusee as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1

    print(f"✓ {harness.id} — {harness.nom} : {len(harness.kata)} kata adoptés, cible `nue`")
    for k in harness.kata:
        print(f"  + {harness.espace(k.id)}")
    print("\nla suite, pour le rendre joignable :")
    print(f"  kokaji forge {harness.racine}")
    print("  kokaji passerelle <harness> --config … --publier")
    return 0


def _juger(args) -> int:
    """RFC-008 §7 — la grille du harness, appliquée aux transcripts du corpus."""
    from .trempe.banc.jugement import JugeRefuse, deja_juge, juger_grille

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1
    if not harness.trempe.grille_judge:
        print(f"✗ {harness.id} : aucune grille — `trempe.grille_judge` au manifest",
              file=sys.stderr)
        return 1

    passerelle = Passerelle(cle=args.cle) if args.cle else Passerelle()
    racine = _corpus_choisi(harness, args.corpus_nom) or harness.corpus
    juges, sautes, refus = 0, 0, 0
    depot = depot_pour(harness)
    for dossier in depot.tous(racine):
        if args.ha and not dossier.nom.startswith(tuple(args.ha)):
            continue
        if depot.transcript(dossier) is None:
            continue
        version = ""
        if not args.rejuger:
            entete = depot.entete(dossier)
            version = str(entete.get("version_coupe") or "")
            if deja_juge(dossier, args.moteur, version):
                sautes += 1
                continue
        try:
            fait = juger_grille(harness, dossier, passerelle, args.moteur)
        except JugeRefuse as err:
            print(f"✗ {dossier.nom} — {err}", file=sys.stderr)
            refus += 1
            continue
        juges += 1
        dits = " · ".join(
            f"{s.critere} {s.note if s.note is not None else '—'}" for s in fait.scores
        )
        print(f"+ {fait.ha}  {fait.kata}@{fait.cible}  {dits}")

    if sautes:
        print(f"{sautes} ha déjà jugés par {args.moteur} — sautés (--rejuger pour forcer)")
    if not juges and not sautes and not refus:
        print("aucun transcript à juger dans ce corpus")
    return 1 if refus else 0


def _note(args) -> int:
    """Noter, ou relire ce qui attend d'être trié."""
    if args.liste or args.brutes:
        notes = brutes(args.carnet) if args.brutes else lire(args.carnet)
        if not notes:
            quoi = "note en attente" if args.brutes else "note"
            print(f"aucune {quoi} dans {args.carnet}.")
            return 0
        for note in notes:
            print(note)
        if args.brutes:
            print(f"\n{len(notes)} note(s) à relire.")
        else:
            restant = len(brutes(args.carnet))
            print(f"\n{len(notes)} note(s), dont {restant} brute(s).")
        return 0

    if not args.texte:
        print("rien à noter : donne un texte, ou `--brutes` pour relire.", file=sys.stderr)
        return 2

    try:
        note = ajouter(
            " ".join(args.texte),
            carnet=args.carnet,
            sujet=args.sujet,
            kata=args.kata,
            ha=args.ha,
        )
    except ValueError as err:
        print(f"note refusée : {err}", file=sys.stderr)
        return 2

    print(f"{note.id} noté dans {args.carnet}.")
    return 0


def _executer(args) -> int:
    """RFC-016 D16.3 / RFC-017 — exécuter un kata d'action, puis router un pas.

    L'exécuteur est celui que l'instance déclare : inerte par défaut (rien ne
    s'exécute), la boîte aux lettres si `KOKAJI_BOITE_EXECUTION` est là. On
    exécute, on lit le résultat, et on demande au routage le nœud suivant.
    """
    from .execution import CapaciteRefusee, ExecutionEnRetard, executeur_pour
    from .forge.coupe import _outil_de
    from .routage import Parcours, pas

    try:
        harness = charger(args.harness)
    except ManifestInvalide as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1
    kata = harness.kata_par_id(args.kata)
    if kata is None:
        print(f"✗ kata inconnu : {args.kata!r}", file=sys.stderr)
        return 1

    outil = _outil_de(kata) or {"capacites": [], "effets": {}, "verificateurs": []}
    executeur = executeur_pour()
    print(f"→ {harness.id}/{kata.id} via {type(executeur).__name__}")
    try:
        resultat = executeur.executer(outil, {})
    except CapaciteRefusee as err:
        print(f"✗ capacité refusée — {err}", file=sys.stderr)
        return 1
    except ExecutionEnRetard as err:
        print(f"⚠ urgence — {err} ; état gelé, main rendue (RFC-017 D17.6)", file=sys.stderr)
        return 2

    if resultat.inerte:
        print(f"  {resultat.note}")
    else:
        print(f"  {len(resultat.actions)} action(s), verdict : {resultat.verdict}")

    # Le pas de routage se lit sur l'état que l'exécution laisse — ses actions,
    # son verdict. Inerte, il n'y a pas de verdict : le routage rendra la main.
    etat = {"actions": list(resultat.actions)}
    if resultat.verdict is not None:
        etat["actions"] = list(resultat.actions) or [{"verdict": resultat.verdict}]
    etape = pas(harness, kata.id, etat, Parcours())
    if etape.urgence:
        print(f"  urgence : {etape.conduite}")
    elif etape.routage.tranche:
        print(f"  routage → {etape.routage.vers}")
    else:
        print(f"  checkpoint humain : {etape.routage.checkpoint}"
              + (f" (candidats : {', '.join(etape.routage.candidats)})" if etape.routage.candidats else ""))
    return 0


def _promouvoir(args) -> int:
    """La promotion est un geste humain (SPECS §6) : la fiche passe `annote`,
    et l'ha entre au dépôt du harness malgré l'ignore des ha bruts (RFC-014).
    En régime base, c'est aussi l'export : le `CAS-XXXX/` s'écrit dans le
    clone, où le scellement suivant le commitera (D14.5)."""
    import re

    from .corpus.base import DepotBase
    from .corpus.instance import ref_dans_les_fichiers
    from .depot import promouvoir_au_depot

    depot = depot_pour()
    try:
        harness = charger(args.harness)
    except ManifestInvalide:
        harness = None
    corpus_du_harness = [c.chemin for c in harness.corpus_nommes] if harness else []

    code = 0
    for nom in args.ha:
        ref = ref_de(Path(nom)) if Path(nom).is_dir() else None
        for corpus in corpus_du_harness if ref is None else []:
            trouve = depot.trouver(corpus, identifiant_de(nom))
            if trouve is not None and trouve.nom.startswith(nom):
                ref = trouve
                break
        if ref is None and harness is None:
            trouve = next(iter(args.harness.rglob(nom)), None)
            ref = ref_de(trouve) if trouve else None
        texte = depot.fiche(ref) if ref is not None else None
        if texte is None:
            print(f"✗ {nom} : aucun ha à ce nom sous {args.harness}", file=sys.stderr)
            code = 1
            continue
        neuf, n = re.subn(r"(?m)^statut:\s*\S+", "statut: annote", texte, count=1)
        if not n:
            print(f"✗ {ref.nom} : la fiche n'a pas de `statut`", file=sys.stderr)
            code = 1
            continue
        depot.ecrire_fiche(ref, neuf)
        if isinstance(depot, DepotBase):
            ref_dans_les_fichiers(ref, depot)
        au_depot = promouvoir_au_depot(args.harness, ref.chemin)
        print(f"✓ {ref.nom} — annote" + (" · ajouté au dépôt, à sceller" if au_depot else " · hors dépôt git"))
    return code


def _instance(args) -> int:
    """RFC-014 D14.8 — l'instance s'exporte entière au format fichiers, et s'importe."""
    from .comptes import Comptes
    from .corpus.base import BaseInjoignable, DepotBase, JournalBase
    from .corpus.instance import exporter, importer

    url = os.environ.get("KOKAJI_BASE_URL", "").strip()
    if not url:
        print("✗ aucune base déclarée (KOKAJI_BASE_URL) : rien à exporter ni où importer", file=sys.stderr)
        return 1
    base, journal, comptes = DepotBase(url), JournalBase(url), Comptes(url)
    try:
        if args.geste == "exporter":
            bilan = exporter(base, journal, args.dossier, comptes=comptes)
        else:
            bilan = importer(
                base, journal, args.dossier, journal_fichiers=args.journal,
                comptes=comptes, comptes_fichier=args.comptes,
            )
        sens = f"exporté vers {args.dossier}" if args.geste == "exporter" else f"importé depuis {args.dossier}"
        print(f"✓ {sens} — {bilan.ha} ha dans {len(bilan.corpus)} corpus, {bilan.ecartes} écartés,"
              f" {bilan.appels} appels, {bilan.comptes.get('utilisateurs', 0)} comptes")
        if args.geste == "importer":
            for corpus in bilan.corpus:
                print(f"  · {corpus}")
    except BaseInjoignable as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1
    finally:
        base.fermer()
        journal.fermer()
        comptes.fermer()
    return 0


def _geste_de_depot(args) -> int:
    from .depot import DepotRefuse, etat, lier, pousser, tirer

    try:
        if args.commande == "enregistrer":
            sha = lier(args.harness, args.nu, args.branche)
            print(f"✓ {args.harness.name} enregistré auprès de {args.nu} — {args.branche} à {sha}")
        elif args.commande == "pousser":
            print(f"✓ poussé — {args.branche} à {pousser(args.harness, args.branche)}")
        else:
            print(f"✓ tiré — {args.branche} à {tirer(args.harness, args.branche)}")
    except DepotRefuse as err:
        print(f"✗ {err}", file=sys.stderr)
        return 1
    print(f"  état : {etat(args.harness).mot}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="kokaji", description=__doc__)
    sous = parseur.add_subparsers(dest="commande", required=True)

    valider = sous.add_parser("valider", help="valide un manifest HDS")
    valider.add_argument("harness", nargs="+", type=Path, help="dossier(s) de harness")

    forge = sous.add_parser("forge", help="assemble les coupes d'un harness")
    forge.add_argument("harness", type=Path, help="dossier du harness")
    forge.add_argument("--cible", action="append", default=[], help="ne forger que cette cible")
    forge.add_argument("--sortie", type=Path, default=SORTIE_DEFAUT, help="racine de sortie")
    forge.add_argument(
        "--sans-trempe", action="store_true",
        help="écrire sans vérifier — pour inspecter une coupe fautive",
    )

    trempe = sous.add_parser("trempe", help="vérifie les coupes sans les écrire")
    trempe.add_argument("harness", type=Path, help="dossier du harness")

    depot = sous.add_parser("depot", help="cherche le vocabulaire interdit dans le dépôt")
    depot.add_argument("racine", nargs="?", type=Path, default=Path("."), help="racine du dépôt")

    middleware = sous.add_parser("middleware", help="capture les sessions closes et vérifie le carré")
    middleware.add_argument("harness", type=Path, help="dossier du harness")
    middleware.add_argument("--journal", type=Path, default=Path("dojo/journal"))
    middleware.add_argument(
        "--repos", type=float, default=300.0,
        help="secondes de silence après quoi une session est dite close",
    )
    middleware.add_argument("--maintenant", help="instant de référence ISO — pour rejouer")
    middleware.add_argument("--source", default="reel", choices=("reel", "scenario", "simule"))
    middleware.add_argument("--corpus", help="le corpus visé ; défaut : le premier déclaré")
    middleware.add_argument(
        "--cle-appelante", action="append", default=[], metavar="ALIAS",
        help="ne capturer que les sessions issues de cette clé ; répétable",
    )
    middleware.add_argument(
        "--boucle", type=float, metavar="SECONDES",
        help="veiller en continu au lieu d'un seul passage",
    )
    middleware.add_argument(
        "--rattraper", action="store_true",
        help="traiter aussi les ha versés avant l'existence du middleware",
    )

    qg = sous.add_parser("qg", help="le fil d'ariane d'un sujet, au terminal")
    qg.add_argument("harness", type=Path, help="dossier du harness")
    qg.add_argument("--sujet", help="le sujet à rendre ; défaut : le premier connu")
    qg.add_argument("--liste", action="store_true", help="lister les sujets observés")
    qg.add_argument("--corpus", dest="corpus_nom", help="le corpus lu ; défaut : le premier")
    qg.add_argument(
        "--journal", type=Path, default=Path("dojo/journal"),
        help="suivre aussi les sessions en cours ; --journal '' pour s'en passer",
    )

    reabs = sous.add_parser(
        "reabstraire", help="reconstruire l'état d'un ha depuis son transcript"
    )
    reabs.add_argument("harness", type=Path, help="dossier du harness")
    reabs.add_argument("--ha", required=True, help="identifiant du ha, ou son préfixe")
    reabs.add_argument("--corpus", dest="corpus_nom", help="le corpus où le chercher")
    reabs.add_argument("--modele", default="banc/persona", help="le modèle qui relit")
    reabs.add_argument("--temperature", type=float, default=0.0)
    reabs.add_argument("--cle", help="clé de la passerelle ; défaut : DOJO_CLE_BANC")

    regr = sous.add_parser("regression", help="rejouer les ha périmés par un changement de source")
    regr.add_argument("harness", type=Path, help="dossier du harness")
    regr.add_argument("--corpus", dest="corpus_nom", help="le corpus à rejouer")
    regr.add_argument("--modele", help="modèle virtuel ; défaut : celui du ha, cible comprise")
    regr.add_argument(
        "--variable", action="append", default=[],
        help="ne rejouer que les ha exerçant cette variable de design (R5.6)",
    )
    regr.add_argument("--plafond", type=int, default=5, help="nombre maximum de rejeux")
    regr.add_argument("--temperature", type=float, default=0.0)
    regr.add_argument("--cle", help="clé de la passerelle ; défaut : DOJO_CLE_BANC")
    regr.add_argument(
        "--passerelle",
        help="racine de la passerelle ; défaut : KOKAJI_PASSERELLE, sinon la locale",
    )
    regr.add_argument(
        "--cible-par-defaut",
        dest="cible_par_defaut",
        default="sobre",
        help="la cible que la passerelle sert sans suffixe (KOKAJI_CIBLE_DEFAUT du Dojo)",
    )
    regr.add_argument(
        "--essai", dest="essai_seulement", action="store_true",
        help="lister les ha périmés sans rien rejouer",
    )

    resser = sous.add_parser(
        "resserrer", help="proposer le `produit` que la pratique tient (RFC-002 §6.4)"
    )
    resser.add_argument("harness", type=Path, help="dossier du harness")
    resser.add_argument("--corpus", dest="corpus_nom", help="le corpus observé")
    resser.add_argument(
        "--minimum", type=int, default=3,
        help="nombre de ha en deçà duquel on ne conclut rien",
    )

    purger = sous.add_parser("purger", help="écarter des ha d'un corpus")
    purger.add_argument("harness", type=Path, help="dossier du harness")
    purger.add_argument("--corpus", dest="corpus_nom", help="le corpus à purger")
    purger.add_argument("--session", action="append", default=[], help="écarter cette session")
    purger.add_argument(
        "--raison",
        help="pourquoi — écrit tel quel dans .ecartes.jsonl, qui est la seule "
             "trace qui restera de la décision",
    )
    purger.add_argument(
        "--parasites", action="store_true",
        help="écarter les appels d'interface et les ha d'un seul tour",
    )
    purger.add_argument(
        "--essai", dest="essai_seulement", action="store_true",
        help="montrer ce qui serait écarté, sans rien supprimer",
    )

    usage = sous.add_parser("usage", help="ce que la pratique a coûté, et ce qu'elle a rendu")
    usage.add_argument("harness", type=Path, help="dossier du harness")
    usage.add_argument("--corpus", help="le corpus visé ; défaut : le premier déclaré")

    passerelle = sous.add_parser(
        "passerelle", help="confronte l'autorisation de la clé à ce que la forge déclare"
    )
    passerelle.add_argument(
        "harness", type=Path, help="dossier d'un harness, ou dossier qui en contient"
    )
    # Sans `--url`, `--config` écrit et s'arrête : la passerelle n'existe pas
    # encore au premier démarrage (le clone étranger l'a montré). Avec, ou sans
    # `--config`, on confronte — à l'adresse donnée ou à celle du Dojo local.
    passerelle.add_argument(
        "--url", default=None,
        help="racine de la passerelle (défaut : http://127.0.0.1:4000, sauf avec --config seul)",
    )
    passerelle.add_argument(
        "--admin", default=os.environ.get("LITELLM_MASTER_KEY", ""),
        help="clé d'administration de la passerelle (défaut : $LITELLM_MASTER_KEY)",
    )
    passerelle.add_argument(
        "--cle", default=os.environ.get("DOJO_CLE_CHAT", ""),
        help="la clé dont on règle l'autorisation (défaut : $DOJO_CLE_CHAT)",
    )
    passerelle.add_argument(
        "--nu", action="append", default=[], metavar="MODELE",
        help="un modèle servi sans coupe, donc sans harness (ex. banc/persona)",
    )
    passerelle.add_argument(
        "--config", type=Path, default=None,
        help="engendrer la `model_list` dans ce fichier, depuis les harness et les moteurs",
    )
    passerelle.add_argument(
        "--moteurs", type=Path, default=Path("dojo/litellm/moteurs.yaml"),
        help="quel moteur incarne quel kata — la part qui ne se dérive pas (R3.2)",
    )
    passerelle.add_argument(
        "--publier", action="store_true",
        help="réécrire l'autorisation ; sans lui, on constate sans rien toucher",
    )

    vigie = sous.add_parser("vigie", help="les vérifications en continu, et leur verdict")
    vigie.add_argument(
        "harness", type=Path, help="dossier d'un harness, ou dossier qui en contient"
    )
    vigie.add_argument(
        "--verdicts", type=Path, default=Path("dojo/verdicts.json"),
        help="où déposer le verdict — le QG le lit là",
    )
    vigie.add_argument(
        "--boucle", type=float, default=0,
        help="secondes entre deux tours ; sans lui, un seul tour",
    )
    vigie.add_argument("--url", default="", help="racine de la passerelle à vérifier")
    vigie.add_argument("--admin", default=os.environ.get("LITELLM_MASTER_KEY", ""))
    vigie.add_argument("--cle", default=os.environ.get("DOJO_CLE_CHAT", ""))
    vigie.add_argument("--nu", action="append", default=[], metavar="MODELE")
    vigie.add_argument(
        "--config", type=Path, default=None,
        help="la configuration de la passerelle, dont on vérifie qu'elle n'a pas décroché",
    )
    vigie.add_argument(
        "--rendu", default="", metavar="URL",
        help="regarder ce que le QG affiche à cette adresse — demande un navigateur",
    )

    service = sous.add_parser("service", help="expose le middleware en lecture seule")
    service.add_argument(
        "harness", type=Path, help="dossier d'un harness, ou dossier qui en contient"
    )
    service.add_argument("--journal", type=Path, default=Path("dojo/journal"))
    service.add_argument("--hote", default="127.0.0.1", help="exposition minimale par défaut (§12)")
    service.add_argument("--port", type=int, default=8100)
    # Sans magasin, le service reste mono-utilisateur : personne à isoler de
    # personne. Avec, l'authentification est exigée et les droits du RFC-004 §3
    # s'appliquent. Le fichier vit hors git (SPECS R12.2).
    service.add_argument(
        "--comptes", type=Path, help="magasin des comptes et ACL — active le partage (RFC-004)"
    )
    service.add_argument(
        "--entete-identite", dest="entete_identite", default="",
        help="en-tête posé par un portail et portant l'email (ex. Remote-Email) ; "
             "sûr seulement si le service n'est joignable que par ce portail",
    )
    service.add_argument(
        "--portail", type=Path,
        help="fichier d'utilisateurs du portail — consommer une invitation y inscrit aussi",
    )

    banc = sous.add_parser("banc", help="joue les personas d'un harness contre un kata")
    banc.add_argument("harness", type=Path, help="dossier du harness")
    banc.add_argument("--kata", required=True, help="le kata mis à l'épreuve")
    banc.add_argument(
        "--modele", action="append", default=[],
        help="modèle virtuel à éprouver ; répétable pour comparer (R5.6)",
    )
    banc.add_argument("--persona", action="append", default=[], help="ne jouer que ce persona")
    banc.add_argument(
        "--persona-modele", default="banc/persona",
        help="le modèle qui joue le persona — servi sans coupe",
    )
    banc.add_argument("--tours", type=int, help="plafond de tours ; défaut : celui du persona")
    banc.add_argument(
        "--temperature", type=float, default=0.0,
        help="figée à 0 par défaut : comparer sans la fixer, c'est mesurer deux variations",
    )
    banc.add_argument("--cle", help="clé de la passerelle ; défaut : DOJO_CLE_BANC")
    banc.add_argument(
        "--nature", action="store_true",
        help="mesurer la justesse du diagnostic de nature (RFC-003 §5.4)",
    )
    banc.add_argument(
        "--passes", type=int, default=1, metavar="N",
        help="rejouer chaque kin N fois et mesurer la stabilité du diagnostic (RFC-003 §7)",
    )
    banc.add_argument(
        "--juge", metavar="MODELE",
        help="appeler un juge sur les variables de design du registre (R5.5)",
    )
    banc.add_argument(
        "--variable", action="append", default=[],
        help="ne juger que cette variable de design ; répétable",
    )
    banc.add_argument("--detail", action="store_true", help="lister chaque constat")

    corpus = sous.add_parser("corpus", help="verse le journal du Dojo dans le corpus")
    corpus.add_argument("harness", type=Path, help="dossier du harness")
    corpus.add_argument("--journal", type=Path, default=Path("dojo/journal"), help="dossier du journal")
    corpus.add_argument("--session", action="append", default=[], help="ne verser que cette session")
    corpus.add_argument("--source", default="simule", choices=("reel", "scenario", "simule"))
    corpus.add_argument("--temperature", type=float, default=0.0, help="celle de la session jouée")
    corpus.add_argument("--corpus", dest="corpus_nom", help="le corpus visé")

    concevoir = sous.add_parser(
        "concevoir", help="proposer un changement de définition, le juger, le sceller"
    )
    concevoir.add_argument("harness", type=Path, help="dossier du harness")
    concevoir.add_argument(
        "--proposition", type=Path, required=True,
        help="fichier YAML décrivant ce qui change (kata, retirer, chaine, trempe, source)",
    )
    concevoir.add_argument("--sceller", action="store_true", help="écrire, si le verdict tient")
    concevoir.add_argument("--auteur", help="qui scelle — exigé pour sceller (RFC-004 §3)")
    concevoir.add_argument("--motif", default="", help="pourquoi ce changement")

    inviter = sous.add_parser("inviter", help="ouvrir une invitation et rendre son lien")
    inviter.add_argument("--comptes", type=Path, required=True, help="le magasin")
    inviter.add_argument("--email", required=True, help="qui est invité")
    inviter.add_argument("--par", required=True, help="email de celui qui invite")
    inviter.add_argument(
        "--base", default=os.environ.get("KOKAJI_BASE"),
        help="racine du lien — sinon KOKAJI_BASE ; le produit ne connaît aucun domaine (R12.5)",
    )

    rattacher = sous.add_parser(
        "rattacher", help="lier un compte au harness et à la pratique orpheline"
    )
    rattacher.add_argument("harness", type=Path, help="dossier du harness")
    rattacher.add_argument("--comptes", type=Path, required=True, help="le magasin")
    rattacher.add_argument("--email", required=True, help="le compte à lier")
    rattacher.add_argument(
        "--praticien", action="store_true",
        help="inscrire ce compte comme praticien des ha qui n'en ont pas",
    )

    compte = sous.add_parser("compte", help="crée un utilisateur dans le magasin (RFC-004)")
    compte.add_argument("--comptes", type=Path, required=True, help="le magasin")
    compte.add_argument("--nom", required=True)
    compte.add_argument("--email", required=True)
    compte.add_argument("--harness", help="id du harness dont il devient propriétaire")
    compte.add_argument(
        "--admin", action="store_true", help="administration de l'exploitation (RFC-004, R12.4)"
    )

    jugement = sous.add_parser(
        "juger", help="appliquer la grille du harness aux transcripts (RFC-008 §7)"
    )
    jugement.add_argument("harness", type=Path, help="dossier du harness")
    jugement.add_argument("--moteur", required=True,
                          help="le juge — jamais le moteur qui a conversé")
    jugement.add_argument("--corpus", dest="corpus_nom", help="le corpus jugé")
    jugement.add_argument("--ha", action="append", default=[],
                          help="ne juger que ce ha ; répétable")
    jugement.add_argument("--cle", default="", help="clé appelante de la passerelle")
    jugement.add_argument("--rejuger", action="store_true",
                          help="rejuger même ce que ce juge a déjà noté")

    adopter = sous.add_parser(
        "importer", help="adopter un harness né hors de la forge (RFC-008, N0)"
    )
    adopter.add_argument("prompts", nargs="+", type=Path, help="les textes, dans l'ordre des étapes")
    adopter.add_argument("--vers", type=Path, help="dossier qui recevra le harness neuf")
    adopter.add_argument("--id", dest="identifiant", help="id du harness neuf (slug)")
    adopter.add_argument("--nom", help="le nom qu'on affichera")
    adopter.add_argument(
        "--dans", type=Path,
        help="ajouter les textes comme étapes de ce harness adopté, au lieu d'en créer un",
    )
    adopter.add_argument(
        "--provenance", default="manuel", help="d'où viennent ces textes — libre : « manuel », URL…"
    )
    adopter.add_argument("--version-source", default="", help="version côté source, si elle existe")

    note = sous.add_parser("note", help="note une remarque de pratique, sans la classer")
    note.add_argument("texte", nargs="*", help="la remarque, telle qu'elle vient")
    note.add_argument("--carnet", type=Path, default=CARNET_DEFAUT, help="le fichier du carnet")
    note.add_argument("--sujet", default="", help="le sujet en cours, si on le sait")
    note.add_argument("--kata", default="", help="le kata ou le modèle virtuel, si on le sait")
    note.add_argument("--ha", default="", help="le ha concerné, si on le sait")
    note.add_argument("--brutes", action="store_true", help="ce qui attend d'être relu")
    note.add_argument("--liste", action="store_true", help="tout le carnet")

    # RFC-012 — le dépôt nu d'un harness, depuis la ligne de commande : ces trois
    # gestes agissent sur git seul (le distant `origin` du clone) ; l'enregistrement
    # au magasin de l'instance est le geste du service.
    for nom_geste, aide in (
        ("pousser", "pousse le harness à son dépôt nu, en avance rapide"),
        ("tirer", "tire le dépôt nu dans le harness, en avance rapide, clone propre exigé"),
    ):
        geste = sous.add_parser(nom_geste, help=aide)
        geste.add_argument("harness", type=Path, help="dossier du harness")
        geste.add_argument("--branche", default="main")
    enregistrer = sous.add_parser(
        "enregistrer", help="lie un harness à un dépôt nu (créé s'il n'existe pas) et y pousse son historique"
    )
    enregistrer.add_argument("harness", type=Path, help="dossier du harness")
    enregistrer.add_argument("--nu", required=True, type=Path, help="le dépôt nu — chemin de la machine")
    enregistrer.add_argument("--branche", default="main")

    promouvoir = sous.add_parser(
        "promouvoir", help="promeut un ha en `annote` et l'ajoute au dépôt du harness (RFC-014)"
    )
    promouvoir.add_argument("harness", type=Path, help="dossier du harness")
    promouvoir.add_argument("ha", nargs="+", help="dossier(s) CAS-XXXX à promouvoir")

    executer = sous.add_parser(
        "executer", help="exécute un kata d'action (inerte par défaut) et route un pas (RFC-016/017)"
    )
    executer.add_argument("harness", type=Path, help="dossier du harness")
    executer.add_argument("kata", help="id du kata à exécuter")

    instance = sous.add_parser(
        "instance", help="exporte la base de l'instance au format fichiers, ou l'importe (RFC-014)"
    )
    gestes = instance.add_subparsers(dest="geste", required=True)
    exporter_ = gestes.add_parser("exporter", help="tout ce que la base contient, en fichiers")
    exporter_.add_argument("dossier", type=Path, help="où écrire l'export")
    importer_ = gestes.add_parser(
        "importer", help="un export, ou le dossier des harness d'une instance en fichiers"
    )
    importer_.add_argument("dossier", type=Path, help="l'export, ou le dossier des harness")
    importer_.add_argument("--journal", type=Path, help="le journal en JSONL, s'il est ailleurs")
    importer_.add_argument("--comptes", type=Path, help="le magasin SQLite des comptes à migrer")

    args = parseur.parse_args(argv)
    if args.commande == "promouvoir":
        return _promouvoir(args)
    if args.commande == "executer":
        return _executer(args)
    if args.commande == "instance":
        return _instance(args)
    if args.commande in ("pousser", "tirer", "enregistrer"):
        return _geste_de_depot(args)
    if args.commande == "concevoir":
        return _concevoir(args)
    if args.commande == "compte":
        return _compte(args)
    if args.commande == "inviter":
        return _inviter(args)
    if args.commande == "rattacher":
        return _rattacher(args)
    if args.commande == "note":
        return _note(args)
    if args.commande == "importer":
        return _importer(args)
    if args.commande == "juger":
        return _juger(args)
    if args.commande == "valider":
        return _valider(args.harness)
    if args.commande == "forge":
        return _forge(args.harness, args.sortie, tuple(args.cible), not args.sans_trempe)
    if args.commande == "trempe":
        return _trempe(args.harness)
    if args.commande == "depot":
        return _depot(args.racine)
    if args.commande == "middleware":
        return _middleware(args)
    if args.commande == "qg":
        return _qg(args)
    if args.commande == "resserrer":
        return _resserrer(args)
    if args.commande == "regression":
        return _regression(args)
    if args.commande == "purger":
        return _purger(args)
    if args.commande == "reabstraire":
        return _reabstraire(args)
    if args.commande == "usage":
        return _usage(args)
    if args.commande == "passerelle":
        return _passerelle(args)
    if args.commande == "vigie":
        return _vigie(args)
    if args.commande == "service":
        return _service(args)
    if args.commande == "banc":
        return _banc(args)
    if args.commande == "corpus":
        return _corpus(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
