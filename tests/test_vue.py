"""Le contrat structurel de la page — ce qu'aucun test de service ne regarde.

Ce fichier ne remplace pas un navigateur, et ne prétend pas le faire : il ne
mesure ni le rendu, ni la mise en page. Il vérifie une chose plus modeste et
qui a manqué deux fois : que les fils sont branchés.

Deux défauts sont passés par ce trou — un `hidden` sans effet parce qu'une
classe déclarait un `display`, et un onglet qui n'appelait jamais son
chargement. Les deux se voyaient au premier coup d'œil sur un téléphone, et
aucun des 336 autres tests ne les regardait.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from typing import ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kokaji.qg import racine_html

PAGE = racine_html().read_text(encoding="utf-8")
# Ce que la page **affiche**, commentaires retirés. Une phrase citée dans un
# commentaire pour dire qu'elle était fausse ne doit pas compter comme si la
# page la disait encore.
RENDU = "\n".join(
    l for l in PAGE.splitlines() if not l.strip().startswith("//")
)
ADMIN = (racine_html().parent / "admin.html").read_text(encoding="utf-8")
INVITATION = (racine_html().parent / "invitation.html").read_text(encoding="utf-8")


class Coque(unittest.TestCase):
    def test_les_six_modules_existent(self):
        for module in ("module-decouvrir", "module-profil", "module-qg", "module-design",
                       "module-vigie", "module-comptes"):
            self.assertIn(f'id="{module}"', PAGE, module)

    def test_seul_le_qg_est_visible_au_chargement(self):
        """Le QG est le module qui existe vraiment : c'est lui qui s'ouvre."""
        for module, cache in (
            ("module-decouvrir", True), ("module-profil", True),
            ("module-design", True), ("module-qg", False),
            ("module-vigie", True), ("module-comptes", True),
        ):
            balise = re.search(rf'<section id="{module}"([^>]*)>', PAGE)
            self.assertIsNotNone(balise, module)
            self.assertEqual("hidden" in balise.group(1), cache, module)

    def test_hidden_ne_peut_pas_etre_ecrase_par_une_classe(self):
        """`hidden` est une intention, pas une mise en forme.

        Sans cette règle, toute classe portant un `display` l'annule en
        silence — les trois modules et le dialogue s'affichaient à la fois.
        """
        self.assertIn("[hidden] { display: none !important; }", PAGE)

    def test_chaque_onglet_declenche_ce_qu_il_montre(self):
        """Un onglet qui n'appelle pas son chargement affiche une coque vide."""
        self.assertIn('if (nom === "profil") rendreProfil();', PAGE)
        self.assertIn('if (nom === "design" && !def) { chargerDesign(); chargerDepense(); }', PAGE)

    def test_ce_qui_est_appele_est_defini(self):
        for fonction in ("rendreProfil", "chargerDesign", "rendreDesign", "eprouver"):
            self.assertIn(f"function {fonction}(", PAGE, fonction)


class LesTroisTerritoires(unittest.TestCase):
    """RFC-013 D13.1, remarque 1 — un menu en trois territoires, pas une liste plate."""

    def test_les_territoires_sont_nommes_dans_l_ordre(self):
        aside = PAGE[PAGE.index('<aside class="flanc"'):PAGE.index("</aside>")]
        i = [aside.index(f'<span class="flanc-groupe{s}">{n}</span>')
             for s, n in (("", "Harness"), (" flanc-groupe-suite", "Moi"), ("", "Kokaji"))]
        self.assertEqual(i, sorted(i))

    def test_les_onglets_sont_des_liens_avec_une_adresse(self):
        """K-07 : un onglet a une adresse, le bouton précédent le connaît."""
        for onglet, href in (("design", "#/design"), ("qg", "#/qg"), ("profil", "#/moi/profil"),
                             ("decouvrir", "#/kokaji/decouvrir"), ("vigie", "#/kokaji/vigie"),
                             ("comptes", "#/kokaji/comptes")):
            self.assertRegex(RENDU, rf'<a class="onglet[^"]*" id="onglet-{onglet}" href="{re.escape(href)}"')
        self.assertNotIn('<button class="onglet"', RENDU)

    def test_le_selecteur_commande_ses_deux_sous_vues(self):
        aside = PAGE[PAGE.index('<aside class="flanc"'):PAGE.index("</aside>")]
        self.assertLess(aside.index('id="flanc-harness"'), aside.index('id="onglet-design"'))
        self.assertLess(aside.index('id="onglet-design"'), aside.index('id="btn-creer-harness"'))
        self.assertIn('class="onglet onglet-sous" id="onglet-design"', aside)

    def test_le_territoire_kokaji_est_en_pied_et_discret(self):
        aside = PAGE[PAGE.index('<aside class="flanc"'):PAGE.index("</aside>")]
        self.assertLess(aside.index('class="flanc-espace"'), aside.index(">Kokaji</span>"))
        self.assertIn(".onglet-kokaji { padding: 8px 14px; font-size: 13px; }", PAGE)

    def test_le_nom_du_harness_entre_au_titre_des_deux_sous_vues(self):
        self.assertIn('$("qg-marque").textContent = `${h} — QG`', PAGE)
        self.assertIn('$("design-titre").textContent = `${h} — Design`', PAGE)

    def test_l_administration_n_est_plus_un_cul_de_sac(self):
        """K-04 : la vigie et les comptes vivent dans la page, avec la navigation ; /admin renvoie."""
        self.assertNotIn('btn-admin', PAGE)
        self.assertIn('url=/#/kokaji/comptes', ADMIN)
        self.assertIn('id="vigie-resume"', PAGE)
        self.assertIn("remonté(s) en premier", PAGE)
        self.assertIn('identifiants techniques', PAGE)


class LeRoutage(unittest.TestCase):
    """K-07, K-17 — chaque vue a une adresse et un titre."""

    def test_l_adresse_se_lit_et_s_ecrit(self):
        for fonction in ("lireRoute", "routeDe", "aller", "appliquerRoute", "titrer"):
            self.assertIn(f"function {fonction}(", PAGE, fonction)
        self.assertIn('window.addEventListener("hashchange", appliquerRoute);', PAGE)

    def test_le_titre_dit_le_harness_la_vue_et_l_axe(self):
        self.assertIn('document.title = morceaux.filter(Boolean).join(" · ") + " — Kokaji";', PAGE)
        self.assertIn('if (vue === "design") morceaux.push(NOMS_D_AXE[axe] || "");', PAGE)

    def test_un_axe_change_l_adresse(self):
        self.assertIn('$(id).onclick = () => { axe = nom; aller(routeDe("design", { axe: nom })); };', PAGE)

    def test_un_lien_vers_un_autre_harness_le_prend(self):
        self.assertIn("r.harness !== offreHarness.courant", PAGE)

    def test_la_vue_vient_de_l_adresse_au_chargement(self):
        self.assertIn("  appliquerRoute();\n", PAGE)


class LaPageNeMentPas(unittest.TestCase):
    """Ce qu'affiche le module design doit être vrai, pas rassurant.

    « La définition affichée est celle qui est scellée » : c'était faux. La page
    montre ce qui est sur le disque, scellé ou non — et l'Atelier sert depuis des
    semaines sans avoir jamais été scellé. Un forgeron cherchait où « valider »
    son harness ; la page lui répondait que c'était déjà fait.
    """

    def test_la_page_ne_dit_pas_que_l_affiche_est_scelle(self):
        self.assertNotIn("celle qui est scellée", RENDU)

    def test_l_absence_de_scellement_se_dit(self):
        self.assertIn("jamais été scellé", PAGE)
        self.assertIn("jamais scellé", PAGE)

    def test_la_page_dit_ce_qu_arreter_fait(self):
        """La phrase a changé avec le produit : le bouton n'est plus gris.

        Elle expliquait pourquoi sceller était impossible ; elle dit maintenant
        ce que le geste fait, puisqu'il existe.
        """
        self.assertIn("l'inscrit au journal", RENDU)
        self.assertIn("sans changer sa version", RENDU)


class ArreterUneVersion(unittest.TestCase):
    """RFC-006 — le geste qu'un forgeron a cherché sans le trouver."""

    def test_le_bouton_vit_meme_sans_changement(self):
        """Sans lui, un harness qui vient de naître ne peut jamais être scellé."""
        self.assertIn("scellable = true;", RENDU)
        self.assertIn("Arrêter cette version…", RENDU)

    def test_le_dialogue_dit_qu_aucune_version_ne_bouge(self):
        """Annoncer « v1.0.0 → v1.0.0 » laisserait croire qu'il se passe quelque chose."""
        self.assertIn("aucune version ne bouge", RENDU)


class VersLeChat(unittest.TestCase):
    """Les liens vers le chat existaient dans le HTML et n'étaient jamais branchés."""

    def test_l_adresse_du_chat_est_lue_au_service(self):
        """Elle n'est pas écrite en dur : elle deviendrait fausse au déménagement."""
        self.assertIn('CHAT = sante.chat', RENDU)
        self.assertIn('lire("/sante")', RENDU)

    def test_le_lien_de_la_barre_est_branche(self):
        """Il existait, caché, sans href — personne ne l'a jamais vu."""
        self.assertIn('$("vers-chat").href = CHAT', RENDU)
        self.assertIn('$("vers-chat").hidden = false', RENDU)

    def test_le_module_design_mene_au_chat(self):
        self.assertIn("pratiquer ↗", RENDU)

    def test_le_scellement_ne_dit_plus_que_les_coupes_sont_perimees(self):
        """Sceller les forge désormais : le message d'avant est devenu faux."""
        self.assertNotIn("Les coupes sont périmées", RENDU)
        self.assertIn("coupe(s) forgée(s)", RENDU)


class CreerUnHarness(unittest.TestCase):
    """Le geste existait par la route et par nulle part ailleurs — RFC-006."""

    def test_le_bouton_est_branche(self):
        self.assertIn('id="btn-creer-harness"', RENDU)
        self.assertIn('$("btn-creer-harness").onclick = ouvrirNaissance', RENDU)

    def test_il_reste_offert_meme_avec_un_seul_harness(self):
        """Le sélecteur n'a de sens qu'à deux ; créer en a toujours."""
        self.assertIn('$("btn-creer-harness").hidden = false', RENDU)

    def test_les_sources_offertes_sont_celles_qu_on_peut_copier(self):
        """En proposer d'autres mènerait à un refus que rien n'aurait annoncé."""
        self.assertIn("o.exemple", RENDU)
        self.assertIn("le mien", RENDU)

    def test_le_dialogue_dit_que_la_pratique_ne_suit_pas(self):
        """C'est l'invariant du RFC-006 : il doit se lire avant, pas se découvrir."""
        self.assertIn("la pratique jamais", RENDU)

    def test_il_previent_que_l_identifiant_est_definitif(self):
        self.assertIn("définitif", RENDU)
        self.assertIn("ne pourra plus changer", RENDU)

    def test_partir_de_rien_est_offert(self):
        """Toujours, et en dernier : on copie s'il y a de quoi, on sème sinon."""
        self.assertIn("partir d'un harness vide", RENDU)
        self.assertIn('sources.push(["", ', RENDU)

    def test_une_source_vide_n_empeche_pas_de_valider(self):
        """C'est un choix, pas un champ non rempli."""
        self.assertIn('bon && $("ne-nom").value.trim()', RENDU)

    def test_la_voie_de_l_adoption_est_offerte(self):
        """RFC-008 : sans elle, l'import n'existe pas pour qui n'a pas de shell."""
        self.assertIn("adopter des textes faits main", RENDU)
        self.assertIn('"/harness/adoption"', RENDU)
        self.assertIn('id="ne-provenance"', RENDU)

    def test_adopter_exige_au_moins_un_texte_complet(self):
        self.assertIn("textesAdoptes().every(p => p.nom && p.texte.trim())", RENDU)

    def test_l_identifiant_est_verifie_avant_l_envoi(self):
        """Un refus après coup se lit comme une panne ; un refus annoncé, non."""
        self.assertIn("minuscules, chiffres et tirets", RENDU)


class AjouterUneEtape(unittest.TestCase):
    """Le geste manquait à la page — RFC-006."""

    def test_le_bouton_existe_et_choisit_son_geste(self):
        """Deux natures d'étape : une source à remplir, ou un texte adopté."""
        self.assertIn('id="btn-ajouter-kata"', RENDU)
        self.assertIn("def.harness.exogene ? ouvrirAdoptionEtape : ajouterUnKata", RENDU)

    def test_l_etape_adoptee_part_vers_la_bonne_route(self):
        self.assertIn('"/etape-adoptee"', RENDU)
        self.assertIn("def = null; await chargerDesign();", RENDU)

    def test_un_refus_se_dit_sans_fermer_le_formulaire(self):
        self.assertIn('$("etape-dit").textContent = err.message', RENDU)

    def test_il_est_rebranche_a_chaque_axe(self):
        """Il est reconstruit avec l'axe : sans ça il existerait sans agir."""
        self.assertIn("if ($(\"btn-ajouter-kata\"))", RENDU)

    def test_la_proposition_porte_le_livrable(self):
        """Le manifest l'exige : sans lui le refus parlerait d'un champ que la
        page n'a jamais montré."""
        self.assertIn("entree.livrable = k.livrable", RENDU)

    def test_l_etape_arrive_sans_amont_et_le_dit(self):
        """Un enchaînement se décide, il ne se devine pas."""
        self.assertIn("sans amont", RENDU)
        self.assertIn("Rien n'est écrit avant le scellement", RENDU)


class LesAdjonctions(unittest.TestCase):
    """L'écran contrats sait ajouter, pas seulement régler — amont et aval."""

    def test_l_amont_s_ajoute_depuis_ce_qui_existe(self):
        """Un héritage tapé de mémoire donnerait un lien rompu : on offre la liste."""
        self.assertIn('id="herite-ajouter"', RENDU)
        self.assertIn("garanti par « ${e(nomDe(x.par))} »", RENDU)

    def test_l_amont_de_chaine_suit_le_contrat(self):
        """Hériter sans amont est une faute de manifest : le lien suit."""
        self.assertIn("if (producteur && !k.amont.includes(producteur)) k.amont.push(producteur)", RENDU)

    def test_l_aval_nait_au_statut_le_plus_faible(self):
        """Sous-promettre est permis ; monter le seuil est un geste, pas un défaut."""
        self.assertIn('id="produit-ajouter"', RENDU)
        self.assertIn("def.statuts_champ[def.statuts_champ.length - 1]", RENDU)

    def test_chaque_ligne_sait_se_retirer(self):
        self.assertIn('data-ret-min="${i}"', RENDU)
        self.assertIn('data-ret-prod="${i}"', RENDU)

    def test_un_nom_de_champ_fautif_est_dit_avant_l_envoi(self):
        self.assertIn("minuscules, chiffres, tirets ou tirets bas", RENDU)

    def test_un_doublon_est_dit(self):
        self.assertIn("est déjà garanti.", RENDU)


class LaTrempeS_Ajoute(unittest.TestCase):
    """L'axe trempe sait ajouter — un check, un critère — pas seulement régler."""

    def test_un_check_s_ajoute_avec_son_motif(self):
        self.assertIn('id="check-ajouter"', RENDU)
        self.assertIn("un check sans motif ne vérifie rien", RENDU)

    def test_interdit_prend_des_formulations_et_les_regex_un_motif(self):
        self.assertIn('type === "interdit" ? { id, type, motifs: [motif] } : { id, type, motif }',
                      RENDU)

    def test_la_grille_du_judge_se_voit_et_s_ajoute(self):
        self.assertIn('id="crit-ajouter"', RENDU)
        self.assertIn("Aucun critère — le judge refusera de juger.", RENDU)
        self.assertIn("bas-haut", RENDU)

    def test_la_grille_entre_dans_la_proposition(self):
        """Sans ce diff, l'écran ajouterait et le scellement n'écrirait rien."""
        self.assertIn("tr.grille_judge = brouillon.trempe.grille_judge", RENDU)

    def test_checks_et_criteres_savent_se_retirer(self):
        self.assertIn('data-ret-check="${i}"', RENDU)
        self.assertIn('data-ret-crit="${i}"', RENDU)


class LaPasseUn(unittest.TestCase):
    """RFC-013, passe 1 — rendre le produit montrable (K-01, K-02, K-03, K-12, K-18 à K-21)."""

    def test_la_page_parle_francais(self):
        self.assertIn('<html lang="fr">', PAGE)
        self.assertIn('<html lang="fr">', ADMIN)

    def test_les_modales_sont_des_dialog_natifs(self):
        self.assertIn('<dialog class="voile" id="voile" aria-labelledby="scel-titre">', PAGE)
        self.assertIn('<dialog class="voile" id="voile-naissance" aria-labelledby="ne-titre">', PAGE)
        self.assertIn('showModal()', PAGE)
        # Plus aucune modale ne se montre par `hidden` : `[hidden]` l'emporterait sur `[open]`.
        self.assertNotIn('$("voile").hidden', PAGE)
        self.assertNotIn('$("voile-naissance").hidden', PAGE)
        self.assertIn("dialog.voile::backdrop", PAGE)

    def test_le_premier_champ_recoit_le_focus(self):
        self.assertIn('id="scel-auteur" style="margin:6px 0 14px" autocomplete="off" autofocus>', PAGE)
        self.assertIn('id="ne-source" style="margin:6px 0 14px" autofocus>', PAGE)

    def test_le_contenu_a_son_landmark_et_son_lien_d_evitement(self):
        self.assertIn('<main class="contenu" id="contenu">', PAGE)
        self.assertIn('<a class="evitement" href="#contenu">Aller au contenu</a>', PAGE)
        self.assertNotIn('<div class="contenu">', PAGE)

    def test_l_en_tete_du_qg_se_replie_et_ancre_pratiquer(self):
        self.assertIn(".nav-qg { flex-wrap: wrap;", PAGE)
        self.assertIn(".nav-qg .nav-cta { white-space: nowrap; flex: none; margin-left: auto; }", PAGE)
        self.assertIn(".nav-qg #sujets { max-width: 240px;", PAGE)
        # Le badge « miroir » : court, à un seul endroit, l'explication en info-bulle (K-11).
        self.assertIn('title="L\'état vient de la pratique : rien ne s\'écrit ici."', PAGE)

    def test_le_rang_mobile_montre_qu_il_defile(self):
        self.assertIn(".flanc::after { content: \"\"; flex: none; position: sticky; right: 0;", PAGE)
        self.assertIn(".flanc-harness { flex: none; padding: 0; min-width: 11rem; }", PAGE)

    def test_l_administration_a_un_retour_et_un_resume(self):
        self.assertIn('href="/#/kokaji/vigie"', ADMIN)
        self.assertIn('id="vigie-resume"', PAGE)
        self.assertIn("remonté(s) en premier", PAGE)


class LAutoratDansLeHarness(unittest.TestCase):
    """RFC-013 D13.2 et D13.3 — l'autorat, le dépôt et le cycle de vie, dans le harness."""

    def test_la_section_porte_le_nom_du_harness(self):
        self.assertIn("Autorat de « ${e(nom)} »", PAGE)

    def test_les_roles_sont_des_etiquettes_et_le_geste_d_invitation_existe(self):
        self.assertIn('"propriétaire", "accent-200", "accent-900"', PAGE)
        self.assertIn('"co-auteur", "neutral-300", "neutral-800"', PAGE)
        self.assertIn(">Inviter un co-auteur</button>", PAGE)

    def test_le_cycle_de_vie_est_archiver_et_la_portee_est_dite(self):
        """Archiver, pas supprimer (RFC-006 §5) — avec le parcours du prototype."""
        self.assertIn("Archiver ce harness", PAGE)
        self.assertIn("reste intact. Réservé au propriétaire.", PAGE)
        self.assertNotIn("Supprimer définitivement", PAGE)
        self.assertIn("class=\"zone-isolee\"", PAGE)
        self.assertIn("border: 1.5px solid var(--color-neutral-400)", PAGE)

    def test_l_archivage_se_confirme_par_le_nom_exact(self):
        self.assertIn('<dialog class="voile" id="voile-archive" aria-labelledby="arch-titre">', PAGE)
        self.assertIn('$("arch-valider").disabled = ev.target.value.trim() !== (def ? def.harness.nom : "");', PAGE)
        self.assertIn('/archive"', PAGE)
        self.assertIn("JSON.stringify({ archive })", PAGE)

    def test_un_harness_archive_se_dit_et_se_remet_en_service(self):
        self.assertIn("Archivé le ${e(String(archiveLe).slice(0, 10))}", PAGE)
        self.assertIn('id="btn-desarchiver"', PAGE)

    def test_le_depot_se_lit_dans_l_autorat(self):
        self.assertIn('id="depot-panneau"', PAGE)
        self.assertIn('d = await lire("/depot")', PAGE)
        self.assertIn("(RFC-012) ; le panneau suit", PAGE)

    def test_les_gestes_de_proprietaire_ne_sont_offerts_qu_au_proprietaire(self):
        self.assertIn('${jeSuisLePatron ? `<div><button class="btn-fantome btn-encre" id="btn-archiver"', PAGE)


class LeGrapheUnique(unittest.TestCase):
    """RFC-013 D13.1, remarque 3 — un seul graphe, les axes en facettes du nœud sélectionné."""

    def test_le_graphe_est_en_tete_et_les_axes_sous_lui(self):
        design = PAGE[PAGE.index('<section id="module-design"'):PAGE.index('<section id="module-qg"')]
        self.assertLess(design.index('id="graphe-rang"'), design.index('id="axe-partition"'))
        self.assertLess(design.index('id="axe-coupes"'), design.index('id="axe-corps"'))

    def test_les_formes_sont_celles_du_fil_du_qg(self):
        self.assertIn(".noeud-g.jalon { border-radius: var(--radius-md); }", PAGE)
        self.assertIn(".noeud-g.externe { border-style: dashed;", PAGE)
        self.assertIn('.noeud-g[aria-pressed="true"] { outline: 2px solid var(--color-neutral-900);', PAGE)

    def test_la_selection_est_partagee_par_les_facettes(self):
        for facette in ("rendrePartition(k)", "rendreContrats(k)", "rendreTrempe(k)", "rendreCoupes(k)"):
            self.assertIn(f"function {facette}", PAGE, facette)
        self.assertIn("const k = brouillon.kata.find(x => x.id === kataChoisi);", PAGE)
        self.assertNotIn('id="coupe-kata"', PAGE)

    def test_le_noeud_porte_ses_marques_par_facette(self):
        self.assertIn("function marquesDe(k)", PAGE)
        self.assertIn('title="contrat violé"', PAGE)
        self.assertIn(">densho incomplet</span>", PAGE)
        self.assertIn(">seuil par défaut</span>", PAGE)

    def test_un_noeud_choisi_entre_dans_l_adresse(self):
        self.assertIn('history.replaceState(null, "", routeDe("design", { noeud: n.id }));', PAGE)

    def test_le_partitionnement_edite_le_nom_d_affichage_et_confirme_le_retrait(self):
        """K-06, K-22 : la seule source de nom, et un retrait en deux temps sur des cibles de 40 px."""
        self.assertIn("Nom d'affichage — la seule source, reprise partout", PAGE)
        self.assertIn('confirmer le retrait de « ${e(k.nom || k.id)} »', PAGE)
        self.assertIn(".plus { width: 40px; height: 40px;", PAGE)
        self.assertIn("← avancer dans la chaîne", PAGE)

    def test_les_contrats_parlent_francais_et_offrent_les_deux_issues(self):
        self.assertIn('const HUMAIN = { fait_etabli: "fait établi", hypothese: "hypothèse", en_pause: "en pause",', PAGE)
        self.assertIn("abaisser l'exigence à « ${e(humain(promesse.statut))} »", PAGE)
        self.assertIn("relever la garantie de l'amont ♯", PAGE)
        self.assertIn('lu par " + lu.map(n => `« ${e(n)} »`)', PAGE)

    def test_le_densho_est_en_pleine_largeur_avec_l_apercu_colle(self):
        """K-10 : hauteur libre, police de lecture, l'aperçu à côté."""
        self.assertIn(".densho-grille { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));", PAGE)
        self.assertIn("field-sizing: content;", PAGE)
        self.assertIn(".apercu-coupe {", PAGE)
        self.assertIn("Densho incomplet :", PAGE)

    def test_le_gabarit_est_au_dessus_du_graphe_replie(self):
        design = PAGE[PAGE.index('<section id="module-design"'):PAGE.index('<section id="module-qg"')]
        self.assertLess(design.index('id="gabarit-pli"'), design.index('id="graphe"'))
        self.assertIn('<div id="gabarit-corps" hidden></div>', PAGE)
        self.assertIn("let gabaritOuvert = false;", PAGE)


class LaPasseTrois(unittest.TestCase):
    """RFC-013, passe 3 — écrire et lire mieux (K-14, K-15, K-16, K-17)."""

    def test_aucun_gris_qui_se_fond_et_aucun_texte_sous_douze_pixels(self):
        """K-14 : neutral-500 et 600 font 2,4 et 3,6 : 1 sur crème ; neutral-700 fait 5,5."""
        style = PAGE.split("<style>")[1].split("</style>")[0]
        self.assertNotIn("color: var(--color-neutral-500)", style)
        self.assertNotIn("color: var(--color-neutral-600)", style)
        self.assertNotRegex(PAGE, r"font-size: ?(?:10|10\.5|11|11\.5)px")
        self.assertIn(".tag-outline { color: var(--color-accent-700); }", PAGE)

    def test_le_lexique_existe_avec_ses_six_entrees(self):
        for terme in ("chaleur", "possible-vivant", "hypothese-infirmee", "contrat", "densho", "sceller"):
            self.assertIn(f'<dt id="lexique-{terme}">', PAGE, terme)

    def test_l_aide_mene_au_lexique_l_entree_surlignee(self):
        """K-15 : un « ? » par bloc — la chaîne, les possibles, les contrats, le densho."""
        for terme in ("chaleur", "hypothese-infirmee", "possible-vivant", "contrat", "densho"):
            self.assertIn(f'href="#/kokaji/decouvrir?terme={terme}"', PAGE, terme)
        self.assertIn('entree.classList.add("surligne")', PAGE)
        self.assertIn("terme: q.terme || null", PAGE)
        self.assertIn(".aide { width: 26px; height: 26px;", PAGE)

    def test_les_cartes_de_cout_s_empilent_sous_480_px(self):
        self.assertIn("@media (max-width: 480px) {", PAGE)
        self.assertIn(".depense-kata .rangee { flex-direction: column; align-items: flex-start;", PAGE)

    def test_la_navigation_s_annonce_sans_forcer_le_mouvement(self):
        """K-17 : un fondu léger, et rien pour qui a demandé moins de mouvement."""
        self.assertIn(".contenu > section:not([hidden]) { animation: apparait .18s ease-out; }", PAGE)
        self.assertIn("@media (prefers-reduced-motion: reduce)", PAGE)


class LesCoupes(unittest.TestCase):
    """L'axe 4 — le gabarit, les densho, la coupe qu'on voit (RFC-010 §4.4)."""

    def test_l_axe_existe_et_se_rend(self):
        self.assertIn('id="axe-coupes"', RENDU)
        self.assertIn('coupes: "axe-coupes"', RENDU)
        self.assertIn("coupes: rendreCoupes", RENDU)

    def test_le_gabarit_et_le_densho_s_editent(self):
        self.assertIn('id="gabarit-texte"', RENDU)
        # Les zones sont engendrées : on vérifie que chaque variable du densho
        # en reçoit une, et que la liste est celle que la forge lit (HDS).
        for variable in ("role", "questions", "interdits", "livrable_structure", "passage", "natures"):
            self.assertIn(f'zone("{variable}",', RENDU)
        self.assertIn('data-densho="livrable_nom"', RENDU)
        self.assertIn(
            'const DENSHO = ["role", "interdits", "questions", "livrable_nom", '
            '"livrable_structure", "passage", "natures"]', RENDU)

    def test_le_gabarit_et_les_densho_entrent_dans_la_proposition(self):
        """Sans ce diff, l'écran éditerait et le scellement n'écrirait rien."""
        self.assertIn("p.template = brouillon.template", RENDU)
        self.assertIn("p.source = src", RENDU)

    def test_la_coupe_se_demande_au_serveur_et_ne_s_invente_pas(self):
        self.assertIn('fetch("/conception/coupe"', RENDU)
        self.assertIn("rien n'est écrit tant qu'on ne scelle pas", RENDU)
        self.assertIn("Pas encore rendue", RENDU)

    def test_un_refus_de_la_forge_se_dit(self):
        self.assertIn("la forge refuse :", RENDU)

    def test_la_coupe_se_copie_et_se_telecharge(self):
        self.assertIn('id="coupe-copier"', RENDU)
        self.assertIn('id="coupe-telecharger"', RENDU)

    def test_une_retouche_perime_la_coupe_rendue(self):
        self.assertIn("function retoucheCoupe() { coupeRendue = null;", RENDU)

    def test_un_harness_adopte_se_lit_sans_s_editer(self):
        self.assertIn("ses étapes sont des textes\n      servis tels quels", RENDU)
        self.assertIn("if (exogene) return;", RENDU)

    def test_les_adjonctions_ne_s_editent_pas_ici(self):
        """Elles vivent à l'axe Contrats et se lisent dans la coupe (RFC-010 §2)."""
        self.assertNotIn('data-densho="herite"', RENDU)
        self.assertNotIn('data-densho="produit"', RENDU)


class LaDepense(unittest.TestCase):
    """Le coût se lit là où l'on modifie la forme — pas au terminal."""

    def test_l_onglet_design_charge_la_depense(self):
        self.assertIn("chargerDepense()", RENDU)
        self.assertIn('lire("/qg/usage")', RENDU)

    def test_elle_est_muette_si_elle_echoue(self):
        """Elle éclaire la définition, elle ne la conditionne pas."""
        self.assertIn("catch { return; }", RENDU)

    def test_le_prix_d_un_bloc_est_montre_comme_ce_qui_compare(self):
        self.assertIn("par bloc d'état", RENDU)
        self.assertIn("il est muet", RENDU)

    def test_la_part_comptee_deux_fois_est_dite_sur_la_carte(self):
        """Un total faux présenté comme juste est pire qu'un total absent."""
        self.assertIn("depense-double", RENDU)
        self.assertIn("comptés deux fois", RENDU)

    def test_les_conformes_se_rapportent_aux_ha_juges(self):
        """Compter les non-jugés ferait passer pour un échec un ha muet de droit."""
        self.assertIn('${t.conformes}/${t.juges || "—"}', RENDU)

    def test_un_bloc_absent_se_dit_et_ne_vaut_pas_zero(self):
        self.assertIn('d.par_bloc === null ? "—"', RENDU)


class Membres(unittest.TestCase):
    """On reconnaît quelqu'un à son nom, jamais à un UUID."""

    def test_la_rangee_montre_le_nom_et_non_l_identifiant(self):
        self.assertIn("${e(qui.nom)}", RENDU)
        self.assertIn("${e(qui.email)}", RENDU)

    def test_le_proprietaire_peut_ajouter_et_retirer(self):
        self.assertIn('id="membre-ajouter"', RENDU)
        self.assertIn('data-retirer="${e(qui.id)}"', RENDU)
        self.assertIn('envoyer("POST", "/membres"', RENDU)
        self.assertIn('envoyer("DELETE", "/membres/"', RENDU)

    def test_un_ajout_refuse_le_dit_a_l_ecran(self):
        """Un refus muet se lit comme un ajout fait."""
        self.assertIn('$("membre-dit").textContent = err.message', RENDU)

    def test_les_gestes_ne_sont_offerts_qu_au_proprietaire(self):
        """Offrir un bouton qui refuse vaut moins que ne rien offrir."""
        self.assertIn("if (!def.membres || !jeSuisLePatron) return;", RENDU)

    def test_le_propietaire_ne_se_retire_pas_lui_meme(self):
        """Le modèle le refuse ; la page ne doit pas proposer le geste."""
        self.assertIn('rangee(def.membres.proprietaire, "propriétaire", "accent-200", "accent-900", false)', RENDU)

    def test_on_choisit_dans_une_liste_et_non_de_memoire(self):
        self.assertIn('<select id="membre-email"', RENDU)
        self.assertIn('lire("/membres/candidats")', RENDU)

    def test_une_liste_vide_se_dit_et_ferme_le_bouton(self):
        """Une liste vide et une liste non chargée ont la même apparence."""
        self.assertIn("aucun compte à ajouter", RENDU)
        self.assertIn('$("membre-ajouter").disabled = true', RENDU)
        self.assertIn("liste indisponible", RENDU)

    def test_ajouter_n_est_pas_inviter(self):
        """On choisit parmi les comptes du service ; ouvrir un compte est un autre geste."""
        self.assertIn("On choisit parmi les comptes du service", RENDU)
        self.assertIn("se fait aux Comptes & invitations", RENDU)


class PageD_Invitation(unittest.TestCase):
    """Le premier invité réel s'est connecté avec son nom, et s'est fait refuser."""

    def test_l_identifiant_est_dit_avant_l_inscription(self):
        """Le dire sur l'écran de confirmation, c'est le dire une fois passé."""
        self.assertIn('id="identifiant"', INVITATION)
        self.assertIn("Ce n'est pas ton identifiant", INVITATION)

    def test_le_champ_du_nom_ne_se_lit_plus_comme_un_identifiant(self):
        self.assertIn("celui qu'on affichera", INVITATION)

    def test_la_confirmation_nomme_le_mot_que_la_porte_emploie(self):
        """La porte dit « nom d'utilisateur » et attend une adresse."""
        self.assertIn("nom d'utilisateur", INVITATION)


class VersL_Administration(unittest.TestCase):
    """Une vue qu'on n'atteint qu'en tapant son adresse n'existe pas — et depuis
    la RFC-013 elle vit dans la page, territoire Kokaji."""

    def test_le_menu_mene_aux_comptes(self):
        self.assertIn('id="onglet-comptes" href="#/kokaji/comptes"', RENDU)
        self.assertIn('if (nom === "comptes") chargerComptes();', RENDU)

    def test_elle_n_est_montree_qu_a_qui_l_a(self):
        """La proposer à tous ferait cliquer vers un refus."""
        self.assertIn('$("onglet-comptes").hidden = !offre.administration', RENDU)

    def test_la_vigie_se_lit_sans_administration(self):
        self.assertIn('d = { vigie: await lire("/vigie") }', RENDU)


class L_AdministrationRejoint(unittest.TestCase):
    """Deux vues qui disent chacune la vérité doivent s'expliquer l'une l'autre."""

    def test_l_absence_du_selecteur_est_dite_et_le_geste_offert(self):
        self.assertIn("il n'apparaît pas dans ton sélecteur", RENDU)
        self.assertIn('data-rejoindre="${e(h.id)}"', RENDU)
        self.assertIn("/rejoindre", RENDU)

    def test_l_autorat_se_lit_a_son_nom(self):
        self.assertIn("quiEstCe(h.autorat.proprietaire)", RENDU)


class NomsDeClasse(unittest.TestCase):
    """Une classe déclarée deux fois s'écrase en silence — et ça s'est vu.

    `.pastille` nommait à la fois le verdict du module design (une étiquette de
    texte) et la puce de la légende de chaleur (16×16). La seconde déclaration
    gagnait : le verdict passait en 16 px et son libellé s'imprimait par-dessus
    le paragraphe suivant, sur téléphone.

    Le partage reste permis quand il est **voulu** — une déclaration coupée en
    deux sur le même élément. Il doit alors être écrit ici : c'est la différence
    entre une intention et un accident.
    """

    # Deux déclarations additives sur le même élément, et rien d'autre.
    PARTAGES_VOULUS: ClassVar[set[str]] = {".noeud", ".nom-noeud"}

    def classes_declarees_deux_fois(self) -> set[str]:
        import collections

        style = PAGE.split("<style>")[1].split("</style>")[0]
        # Une couche étroite redéclare légitimement : on ne regarde qu'hors media.
        hors_media, profondeur = [], 0
        for bloc in re.split(r"(@media[^{]*\{)", style):
            if bloc.startswith("@media"):
                profondeur += 1
                continue
            if profondeur:
                continue
            hors_media.append(bloc)
        noms = re.findall(r"(?m)^\s*(\.[a-z0-9-]+)\s*\{", "".join(hors_media))
        return {n for n, c in collections.Counter(noms).items() if c > 1}

    def test_aucun_partage_de_nom_qui_ne_soit_declare(self):
        self.assertEqual(self.classes_declarees_deux_fois(), self.PARTAGES_VOULUS)

    def test_le_verdict_n_a_pas_de_taille_imposee(self):
        """Une étiquette de texte qui reçoit une largeur fixe déborde."""
        declaration = re.search(r"(?m)^\s*\.pastille\s*\{([^}]*)\}", PAGE)
        self.assertIsNotNone(declaration)
        self.assertNotIn("width", declaration.group(1))


class Decouvrir(unittest.TestCase):
    """Le seul module qui s'adresse à quelqu'un qui arrive.

    Il explique le cycle, pas la mécanique. Un produit qui se comprend en le
    pratiquant est un produit qu'on ne pratique pas.
    """

    def test_l_onglet_existe_et_ouvre_son_module(self):
        self.assertIn('id="onglet-decouvrir"', RENDU)
        self.assertIn("decouvrir: \"module-decouvrir\"", RENDU)

    def test_les_quatre_mots_y_sont_definis(self):
        for mot in ("Un harness", "Un kata", "Un sujet", "Un cas"):
            with self.subTest(mot=mot):
                self.assertIn(f"<dt>{mot}</dt>", RENDU)

    def test_le_cycle_a_ses_cinq_pas(self):
        self.assertEqual(RENDU.count('class="pas-du-cycle-rang"'), 5)

    def test_il_dit_aussi_ce_que_kokaji_ne_fait_pas(self):
        """Une présentation qui ne promet que des bienfaits ne se croit pas."""
        self.assertIn("Ce que Kokaji ne fait pas", RENDU)


class SelecteurDeHarness(unittest.TestCase):
    """RFC-005 §2 — il commande les trois onglets, donc il vit dans la coque."""

    def test_le_selecteur_est_declenche_au_demarrage(self):
        """Sans cet appel, la liste reste vide et le choix devient impossible."""
        self.assertIn("await chargerHarness();", PAGE)
        self.assertIn("async function chargerHarness()", PAGE)

    def test_le_selecteur_vise_un_champ_qui_existe(self):
        self.assertIn('id="harness-courant"', PAGE)
        self.assertIn('id="flanc-harness"', PAGE)

    def test_il_est_cache_tant_qu_il_n_y_a_rien_a_choisir(self):
        """Un choix d'un seul élément demande de décider là où rien ne se décide."""
        balise = re.search(r'<div class="flanc-harness"([^>]*)>', PAGE)
        self.assertIsNotNone(balise)
        self.assertIn("hidden", balise.group(1))
        self.assertIn("offre.harness.length < 2", PAGE)

    def test_changer_de_harness_recharge_la_page(self):
        """Chaque module lit le harness courant : en rafraîchir un seul mentirait."""
        self.assertIn("location.reload()", PAGE)


class Etroit(unittest.TestCase):
    """Un téléphone fait 360 px. Rien ici ne mesure, tout ici se déclare."""

    def test_les_trois_pages_declarent_le_viewport(self):
        for nom, page in (("qg", PAGE), ("admin", ADMIN), ("invitation", INVITATION)):
            self.assertIn('name="viewport"', page, nom)
            self.assertIn("width=device-width", page, nom)

    def test_les_trois_pages_ont_une_couche_etroite(self):
        for nom, page in (("qg", PAGE), ("admin", ADMIN), ("invitation", INVITATION)):
            self.assertIn("@media (max-width: 760px)", page, nom)

    def test_le_fil_ne_peut_pas_ecraser_ses_noeuds(self):
        """Une enveloppe sans plancher laissait deux noms de nœud se superposer."""
        self.assertRegex(PAGE, r"\.enveloppe \{[^}]*min-width: 104px")


class Honnetete(unittest.TestCase):
    """Ce que la page promet de ne pas faire."""

    def test_l_echec_de_lecture_se_dit_dans_le_module_concerne(self):
        """Le panneau de panne vit dans l'onglet QG : d'ailleurs, il ne se voit pas."""
        self.assertIn("La définition n'a pas pu être lue", PAGE)

    def test_l_adresse_du_chat_n_est_pas_ecrite_en_dur(self):
        """Une adresse figée dans la page devient fausse au premier déménagement."""
        self.assertNotIn("chat.aelworks.fr", PAGE)
        self.assertIn('let CHAT = "";', PAGE)


if __name__ == "__main__":
    unittest.main()
