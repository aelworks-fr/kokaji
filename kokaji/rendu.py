"""Ce qu'un navigateur affiche vraiment, mesuré — NOTE-0008.

Les mesures vivent ici et non dans les tests, parce qu'elles ont **deux
appelants** : `tests/test_rendu.py`, qui les exige vertes, et la vigie, qui les
reprend en continu. Une mesure qui n'existerait que dans un test ne pourrait
jamais tourner en service — et une vérification qu'on ne lance qu'à la main
retombe dans le silence qu'elle combat (NOTE-0011).

Quatre défauts sont passés par ce trou en une semaine, tous visibles au premier
coup d'œil sur un téléphone, aucun visible dans le HTML :

- `hidden` annulé par un `display`, et trois modules affichés à la fois ;
- un flanc de 224 px sur un écran de 360, qui débordait ;
- deux noms de nœud imprimés l'un sur l'autre ;
- « aucun changement » imprimé par-dessus le paragraphe suivant.

On regarde donc des **rectangles**, pas des chaînes de caractères.
"""

from __future__ import annotations

from .vigie import Verdict

__all__ = ["ETROIT", "LARGE", "TRES_LARGE", "navigateur_indisponible", "regarder"]

# Un téléphone fait 360 px de large. C'est la mesure du problème, pas un choix.
ETROIT = (360, 780)
LARGE = (1280, 900)
# Le palier que l'audit a trouvé vide (K-02) : les portables 13″ à fenêtre non
# maximisée vivent entre 800 et 1 024 px, et c'est là que « pratiquer » sortait
# de l'écran sans qu'aucune mesure ne le voie.
PALIER = (800, 900)
# Un ultra-large courant. Ajouté après coup : le produit y tenait dans le tiers
# gauche, collé au flanc, et aucune des deux mesures précédentes ne pouvait le
# montrer — sous 1180 px le défaut n'existe pas. Une mesure ne voit que les
# tailles qu'on lui donne, et l'on ne lui avait donné que les siennes.
TRES_LARGE = (2560, 1080)

# Ce qu'on regarde sur un très grand écran : non pas que ça tienne — tout tient
# — mais que la colonne soit **centrée** dans la place disponible. Un vide de
# plus d'un cinquième d'écart entre les deux marges est une mise en page qui a
# oublié qu'elle avait grandi.
DESEQUILIBRE = """() => {
  const vu = [...document.querySelectorAll('.contenu > section')]
    .find(n => n.offsetParent !== null);
  if (!vu) return null;
  // La colonne, et la place qu'elle avait. Les comparer l'une à l'autre — et
  // non la colonne à elle-même, ce que faisait la première version de cette
  // mesure : elle rendait toujours zéro, donc toujours vert.
  const place = vu.parentElement.getBoundingClientRect();
  const colonne = (vu.querySelector('.page') || vu).getBoundingClientRect();
  const gauche = colonne.left - place.left;
  const droite = place.right - colonne.right;
  return { gauche: Math.round(gauche), droite: Math.round(droite),
           ecart: Math.round(Math.abs(gauche - droite)),
           colonne: Math.round(colonne.width),
           large: Math.round(place.width) };
}"""

# Ce qui déborde de l'écran sans qu'aucun ancêtre ne défile. Dépasser n'est pas
# la faute — sous 760 px la barre d'onglets défile volontairement, et un onglet
# hors de l'écran s'atteint au pouce. Dépasser **sans recours** l'est.
HORS_D_ATTEINTE = """() => [...document.querySelectorAll('body *')]
    .filter(n => n.offsetParent !== null && n.getBoundingClientRect().width > 0)
    .filter(n => n.getBoundingClientRect().right > window.innerWidth + 1)
    .filter(n => {
      for (let a = n.parentElement; a; a = a.parentElement) {
        const d = getComputedStyle(a).overflowX;
        if (d === 'auto' || d === 'scroll') return false;
      }
      return true;
    })
    .map(n => (n.className || n.tagName) + ' « ' +
              (n.textContent || '').trim().slice(0, 20) + ' »')"""

# Deux textes imprimés au même endroit. On ne compare que des feuilles de texte
# non positionnées : une étiquette posée en `absolute` par-dessus un nœud est un
# choix de design, pas un accident. Ce qui se chevauche ici aurait dû se pousser.
CHEVAUCHENT = """() => {
  const rects = [...document.querySelectorAll('body *')].filter(n => {
    if (n.offsetParent === null) return false;
    if (n.children.length) return false;
    if (!(n.textContent || '').trim()) return false;
    const s = getComputedStyle(n);
    if (s.position === 'absolute' || s.position === 'fixed') return false;
    const r = n.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }).map(n => ({ quoi: (n.className || n.tagName) + ' « ' +
                   (n.textContent || '').trim().slice(0, 24) + ' »',
                 r: n.getBoundingClientRect() }));

  const chevauchent = [];
  for (let i = 0; i < rects.length; i++)
    for (let j = i + 1; j < rects.length; j++) {
      const a = rects[i].r, b = rects[j].r;
      // Une marge d'un pixel : les arrondis de rendu ne sont pas des fautes.
      const largeur = Math.min(a.right, b.right) - Math.max(a.left, b.left);
      const hauteur = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
      if (largeur > 1 && hauteur > 1)
        chevauchent.push(rects[i].quoi + '  ⨯  ' + rects[j].quoi);
    }
  return chevauchent;
}"""

# Le CTA du QG : visible → entièrement dans l'écran ; caché (pas d'adresse de
# chat) → on le dit, ce n'est pas un vert.
CTA_DANS_L_ECRAN = """() => {
  const a = document.getElementById('vers-chat');
  if (!a) return { tient: false, detail: 'aucun CTA dans la page' };
  if (a.hidden || a.offsetParent === null)
    return { tient: true, detail: "CTA absent : pas d'adresse de chat" };
  const r = a.getBoundingClientRect();
  const dedans = r.left >= 0 && r.right <= window.innerWidth + 1 && r.top >= 0;
  return { tient: dedans, detail: dedans ? '' :
           'pratiquer : right = ' + Math.round(r.right) + ' pour ' + window.innerWidth + ' px' };
}"""

# La modale devant tout : ouverte, chaque point sondé de sa carte doit
# répondre par un élément qui vit dans la modale.
MODALE_DEVANT_TOUT = """() => {
  const d = document.getElementById('voile-naissance');
  if (!d || typeof d.showModal !== 'function') return { tient: false, detail: 'pas de <dialog> de naissance' };
  const etait = d.open;
  if (!etait) d.showModal();
  const carte = d.querySelector('.dialogue') || d;
  const r = carte.getBoundingClientRect();
  const points = [[r.left + 8, r.top + 8], [r.right - 8, r.top + 8],
                  [r.left + r.width / 2, r.top + r.height / 2],
                  [r.left + 8, r.bottom - 8], [r.right - 8, r.bottom - 8]];
  const intrus = points.map(([x, y]) => document.elementFromPoint(x, y))
    .filter(n => n && !d.contains(n))
    .map(n => (n.className || n.tagName) + ' « ' + (n.textContent || '').trim().slice(0, 20) + ' »');
  if (!etait) d.close();
  return { tient: intrus.length === 0, detail: intrus.join(' · ') };
}"""

# Les axes du module design, dans l'ordre de la page.
AXES_DU_DESIGN = ("partition", "contrats", "trempe", "coupes")

MODULES_VISIBLES = """() => ['module-decouvrir','module-profil','module-qg','module-design','module-vigie','module-comptes']
    .filter(id => document.getElementById(id).getBoundingClientRect().height > 0)"""


def navigateur_indisponible() -> str:
    """Pourquoi on ne peut pas regarder — vide si l'on peut.

    Un navigateur manquant se **dit**. Une mesure qui disparaît en silence
    finit par ne plus exister, et c'est le motif que tout ce module combat.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError:
        return "playwright n'est pas installé"
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as err:  # noqa: BLE001 — la cause exacte importe peu, on la dit
        return str(err).strip().splitlines()[0][:160]
    return ""


def regarder(url: str) -> list[Verdict]:
    """Ouvre la page et rend un verdict par mesure.

    Le module design est regardé **en ouvrant son onglet**, comme on l'ouvre à
    la main : une mesure qui ne verrait que la page d'accueil ignorerait les
    deux tiers du produit — et c'est précisément là qu'était le dernier défaut.
    """
    motif = navigateur_indisponible()
    if motif:
        # Ne pas pouvoir regarder n'est pas « rien à signaler ».
        return [Verdict("rendu", False, f"aucun navigateur : {motif}")]

    from playwright.sync_api import sync_playwright

    verdicts: list[Verdict] = []
    with sync_playwright() as pw:
        navigateur = pw.chromium.launch()
        try:
            for largeur, hauteur in (ETROIT, PALIER, LARGE, TRES_LARGE):
                contexte = navigateur.new_context(viewport={"width": largeur, "height": hauteur})
                page = contexte.new_page()
                page.goto(url, wait_until="networkidle")
                ou = f"{largeur} px"

                deborde = page.evaluate("document.documentElement.scrollWidth")
                verdicts.append(
                    Verdict(
                        f"la page tient dans l'écran ({ou})",
                        deborde <= largeur,
                        "" if deborde <= largeur else f"la page déborde de {deborde} px",
                    )
                )
                verdicts.append(_liste(f"rien n'est hors d'atteinte ({ou})", page, HORS_D_ATTEINTE))
                verdicts.append(_liste(f"rien ne se chevauche ({ou})", page, CHEVAUCHENT))

                # L'action principale du QG (K-02) : si « pratiquer » est
                # affiché, il est dans l'écran — pas au bout d'un défilement
                # horizontal. Sans adresse de chat il est caché, et la mesure
                # le dit plutôt que de passer au vert sur rien.
                cta = page.evaluate(CTA_DANS_L_ECRAN)
                verdicts.append(
                    Verdict(
                        f"le CTA principal est dans le viewport ({ou})",
                        cta["tient"],
                        "" if cta["tient"] else cta["detail"],
                    )
                )
                # Une modale ouverte est devant tout (K-01) : on ouvre celle de
                # la naissance, on regarde ce qui répond sous quelques points
                # de sa carte, et ça doit être elle.
                modale = page.evaluate(MODALE_DEVANT_TOUT)
                verdicts.append(
                    Verdict(
                        f"rien ne se superpose à une modale ouverte ({ou})",
                        modale["tient"],
                        "" if modale["tient"] else modale["detail"],
                    )
                )

                visibles = page.evaluate(MODULES_VISIBLES)
                verdicts.append(
                    Verdict(
                        f"un seul module visible ({ou})",
                        visibles == ["module-qg"],
                        "" if visibles == ["module-qg"] else f"visibles : {visibles}",
                    )
                )

                # Chaque module, un par un. Mesurer le seul module d'accueil
                # ne prouve rien des autres : le défaut d'écran large ne vivait
                # que dans « Découvrir », et le module d'accueil, lui, était
                # centré depuis toujours — une mesure prise sur lui serait
                # passée au vert sans rien regarder.
                for onglet, module in (
                    ("#onglet-decouvrir", "#module-decouvrir"),
                    ("#onglet-profil", "#module-profil"),
                    ("#onglet-vigie", "#module-vigie"),
                    ("#onglet-design", "#module-design"),
                ):
                    page.click(onglet)
                    page.wait_for_selector(module, state="visible")
                    page.wait_for_timeout(300)
                    nom = module.removeprefix("#module-")
                    if module == "#module-design":
                        verdicts.append(
                            _liste(f"rien ne se chevauche dans le design ({ou})", page, CHEVAUCHENT)
                        )
                        # Chaque axe, un par un : le module s'ouvre sur le
                        # premier, et un axe qu'on ne clique pas n'est pas
                        # regardé — le quatrième (RFC-010) pose deux colonnes
                        # et un gabarit entier, ce que les trois autres n'ont pas.
                        for axe in AXES_DU_DESIGN:
                            page.click(f"#axe-{axe}")
                            page.wait_for_timeout(200)
                            deborde_axe = page.evaluate("document.documentElement.scrollWidth")
                            verdicts.append(
                                Verdict(
                                    f"l'axe {axe} tient dans l'écran ({ou})",
                                    deborde_axe <= largeur,
                                    "" if deborde_axe <= largeur else f"déborde de {deborde_axe} px",
                                )
                            )
                            verdicts.append(
                                _liste(f"rien ne se chevauche dans l'axe {axe} ({ou})", page, CHEVAUCHENT)
                            )
                        page.click("#axe-partition")
                        page.wait_for_timeout(200)
                    if (largeur, hauteur) != TRES_LARGE:
                        continue
                    vu = page.evaluate(DESEQUILIBRE)
                    tient = vu is not None and vu["ecart"] <= vu["large"] / 5
                    # La prose garde sa mesure, les surfaces tabulaires
                    # s'élargissent : on vérifie donc que le design et le QG
                    # profitent de la place, pas que tout la remplisse.
                    if nom == "design":
                        assez = vu is not None and vu["colonne"] >= 1400
                        verdicts.append(
                            Verdict(
                                f"le design profite de la place ({ou})",
                                assez,
                                "" if assez else f"colonne de {vu and vu['colonne']} px",
                            )
                        )
                    verdicts.append(
                        Verdict(
                            f"la colonne de {nom} est centrée ({ou})",
                            tient,
                            "" if tient else (
                                f"marges {vu['gauche']} / {vu['droite']} "
                                f"sur {vu['large']} px" if vu else "aucune section visible"
                            ),
                        )
                    )
                contexte.close()
        finally:
            navigateur.close()
    return verdicts


def _liste(quoi: str, page, mesure: str) -> Verdict:
    fautes = page.evaluate(mesure)
    return Verdict(quoi, not fautes, "\n".join(f"  - {f}" for f in fautes))
