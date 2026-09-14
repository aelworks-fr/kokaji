# Handoff : Kokaji v2 — refonte post-audit (14 sept. 2026)

## Overview
Refonte structurelle de l'interface Kokaji (kokaji.aelworks.fr) implémentant les quatre orientations produit de l'audit ergonomique du 14 septembre 2026 (joint : `audit-ergonomique-2026-09-14.pdf`) plus les correctifs qu'il absorbe. Le prototype couvre : le menu en trois territoires, le QG (observation d'un sujet), le Design du harness (graphe unique + quatre axes en facettes), l'Autorat avec suppression de harness, la Vigie, Comptes & invitations, Découvrir (lexique), Profil, et les modales Créer / Supprimer / Sceller.

## About the Design Files
`Kokaji v2.dc.html` est une **référence de design en HTML** — un prototype fonctionnel montrant l'apparence et le comportement visés, pas du code de production. La tâche est de **recréer ce design dans l'environnement existant du site** (page unique lisant l'API JSON du middleware, VPS modeste, sans dépendance lourde — vanilla JS ou équivalent Preact/lit), en s'appuyant sur ses patterns établis. L'interface est en français ; les libellés du prototype sont les libellés finaux.

## Fidelity
**Haute fidélité.** Couleurs, typo, espacements, rayons et interactions sont finaux et viennent du design system Organic (`organic-styles.css`). Recréer au pixel en sourçant chaque valeur depuis les variables CSS, jamais en dur.

## Les quatre orientations produit (structure obligatoire)

### 1. Menu latéral en trois territoires (remarque 1, absorbe K-05, K-14)
Colonne fixe 236px, `padding: 22px 14px 18px`, `border-right: 1px solid var(--color-neutral-200)`. Marque « Kokaji » Caprasimo 22px.
- Intitulés de groupe : 12.5px, weight 700, `letter-spacing: .07em`, `--color-neutral-700` (contraste relevé, K-14) : **HARNESS**, **MOI**, **KOKAJI** (ce dernier en pied de menu, poussé par un `flex:1`, ton discret — items 13px).
- **HARNESS** : le sélecteur de harness (select pill, nom complet + version « Atelier · v2.1 »), puis ses deux sous-vues indentées (8px) **Design** et **QG**, puis « + Créer un harness » (ghost, dans le territoire, pas en tête de liste).
- **MOI** : Profil, Se déconnecter.
- **KOKAJI** : Découvrir, Vigie (badge encre = nombre d'écarts), Comptes & invitations.
- Onglet : pill `padding: 10px 14px`, point d'état 8px. Actif = `accent-200` / `accent-900` / weight 600 / point `accent-600` ; inactif = transparent / `neutral-800` / point `neutral-400`, hover `neutral-200`.
- Le nom du harness actif figure dans le H1 de Design et QG (« Atelier — QG »).

### 2. Admin scindée (remarque 2, absorbe K-04, K-13, K-23)
- **Vigie** (territoire Kokaji, navigation principale conservée) : résumé en tête « 55 sur 56 verdicts tiennent · dernier tour il y a 3 min · 1 écart, remonté en premier ». Les écarts d'abord : carte `elev-md` avec pastille encre ✕ 24px, nom du verdict (14px/700), détail, mesure en monospace 11.5px, bouton « rejouer ». Puis les familles conformes **repliées** : une carte par famille (Chargement, Passerelle, Tenue à 360 / 800–1024 (nouveau palier) / 1280 / 2560 px, Contrastes (nouvelle famille)), tag sage « N sur N tiennent », toggle « détailler » listant les verdicts (✓ sage).
- **Comptes & invitations** (territoire Kokaji, admin seulement) : bouton primaire « Ouvrir une invitation » ; par compte, e-mail et UUID **repliés par défaut** derrière « identifiants techniques » (bloc monospace `neutral-200`).
- **Autorat dans le harness** : voir orientation 4. Plus aucune page sans navigation.

### 3. Design du harness : un graphe unique, les axes en facettes (remarque 3, absorbe K-06, K-09, réduit K-10, K-15)
- **Un seul graphe** en tête du Design : mêmes nœuds, même ordre, **mêmes noms d'affichage que le QG** (source unique = densho). Formes identiques au fil du QG (cercle = kata/externe, carré arrondi `--radius-md` = jalon, bord tireté = externe), 56px, sans chaleur ni possibles.
- **Repli identique au fil du QG (défaut corrigé en cours de conception — critique)** : colonne de nœud `width:100%; min-width:96px; max-width:150px; flex:none; padding:4px 2px` dans un wrapper `flex:1 1 0; min-width:0` (dernier nœud `0 0 auto`), libellés `overflow-wrap:break-word`, connecteur `flex:1; min-width:48px` avec traits `flex:1; min-width:4px` autour du bouton « + » (40px fixe). Les 4 nœuds tiennent à ~570px de contenu ; `overflow-x:auto` seulement en secours des longues chaînes. Tester à 800 et 1280px.
- **Sélection partagée** : cliquer un nœud (anneau encre `outline: 2px solid var(--color-neutral-900)`, nom weight 700) le sélectionne pour TOUS les axes. Les axes (pills : Partitionnement · Contrats f♯ · Trempe · Coupes ; actif `accent-200`/`accent-900` ; badge encre = anomalies sur Contrats) sont des **facettes du nœud sélectionné**, pas des pages.
- **Indicateurs par facette sur le nœud** : ✕ encre 20px en haut-droite = contrat violé ; tag tireté « densho incomplet » ; tag neutre « seuil par défaut ». Légende implicite par les libellés.
- **Partitionnement** (facette) : nom d'affichage (« la seule source, reprise partout »), identifiant technique (monospace, fond `neutral-200`), type (select kata/jalon/externe) ; boutons « ← avancer / reculer → », « retirer ce nœud… » à confirmation en deux temps (le libellé devient « confirmer le retrait de “X” ») — cibles ≥ 40px (K-22). Insertion par les « + » 40px du graphe.
- **Contrats f♯** (facette) : lignes hérite (« exige ») et produit (« garantit au moins ») du nœud sélectionné. **Libellés humains** dans les selects (« présence seule / en pause / hypothèse / fait établi »), identifiant technique en monospace 11px secondaire (K-06). Ligne satisfaite : `neutral-200` + puce ✓ terracotta ; ligne cassée : `accent-100` + puce ✕ encre + tag encre, avec **les deux issues en boutons sur la ligne** (« abaisser l'exigence… » / « relever la garantie de l'amont ♯ »). Consommateurs affichés (« lu par “Mettre en œuvre” »). Version : « — v2.0.0 au sceau ♯ » si le contrat change, sinon « — inchangé ».
- **Trempe** (facette, jamais f♯) : seuil de justesse du nœud (input nombre, placeholder = défaut 0,75, « Vide : le défaut s'applique ») ; checks_de_session à bascule pill (exigé = `accent-200`/`accent-900`, inactif = `neutral-300`/`neutral-800`) ; vocabulaire_interdit (chips monospace supprimables + input « ajouter un mot… », Entrée ajoute) marqué « commun à toute la chaîne ».
- **Coupes** (facette, K-10) : le densho du nœud en **pleine largeur** — grid `repeat(auto-fit, minmax(380px, 1fr))` : à gauche 4 zones (Rôle, Questions, Structure du livrable, Passage) en textarea pleine largeur, `padding: 12px 16px`, 14px/1.6, `resize: vertical`, hauteur libre (en prod : `field-sizing: content`) ; à droite l'**aperçu de la coupe rendue** (fond `neutral-200`, sticky) avec mention « Densho incomplet : le “passage” est vide » quand c'est le cas.

### 4. Cycle de vie : supprimer un harness (remarque 4, s'appuie sur K-12)
Dans la section **Autorat** (ouverte par « qui forge avec moi · 2 » dans l'en-tête du Design) : membres (propriétaire = tag terracotta, co-auteur = neutre), « Inviter un co-auteur », puis la **zone de suppression visuellement isolée** : bordure `1.5px solid var(--color-neutral-400)`, titre encre, portée dite précisément (« Irréversible dans Kokaji : la définition, les sujets, les cas et le journal ne seront plus servis. Le dépôt git lié reste intact. Réservé au propriétaire. »).
Modale de confirmation : rappel de portée, **saisie du nom exact** (monospace, placeholder = le nom), bouton « Supprimer définitivement » inactif tant que la saisie ≠ nom. Après suppression : retour au territoire Harness, harness suivant sélectionné, bandeau sage nommant ce qui a été retiré.

## Corrections transverses (obligatoires)
- **Routage et titres (K-07, K-17)** : chaque vue a une URL (`/h/atelier/qg?sujet=vol`, `/h/atelier/design/contrats?noeud=cadrage`, `/moi/profil`, `/kokaji/vigie`…) et un `document.title` (« Atelier · Design · Contrats f♯ — Kokaji »). Le prototype affiche la route simulée dans une barre en haut du contenu — **en prod, c'est la vraie URL (History API ou hash) et cette barre disparaît** ; onglets en `<a href>`. Transition légère respectant `prefers-reduced-motion`.
- **En-tête QG (K-02)** : `flex-wrap`, H1 `flex:1 1 auto; min-width:200px`, sélecteur de sujet `max-width:240px` avec ellipse, **« pratiquer ↗ » `white-space:nowrap` ancré à droite** — jamais hors viewport de 800 à 1440px. C'est un lien (`<a>`), pas un bouton.
- **Badge « miroir en lecture » (K-11)** : un seul emplacement — tag outline sous le H1, `white-space:nowrap`, explication en `title`. (Design : « rien n'est écrit sans sceau », même position.)
- **Pastilles du QG (K-08)** : de vrais boutons avec `aria-label` complet (« Cadrer le projet, 80 %, 1 possible vivant — ouvrir le dossier »), curseur pointer, le clic ouvre le dossier du nœud en place (sélection = anneau sage).
- **Vocabulaire unifié (K-06)** : noms d'affichage du densho partout (« Clarifier l'idée · Cadrer le projet · Découper le premier incrément · Mettre en œuvre ») ; identifiants techniques (idee, cadrage, decoupage, mise_en_oeuvre) en monospace secondaire ou info-bulle seulement. Statuts humains : « fait établi / hypothèse / en pause / validée / en cours / infirmée ».
- **Aide contextuelle (K-15)** : boutons « ? » 26px discrets par bloc (chaîne, possibles, contrats) → ouvrent Découvrir avec l'entrée du lexique surlignée (`accent-100`). Lexique : chaleur, possible vivant, hypothèse infirmée, contrat f♯, densho, sceller.
- **Contrastes (K-14)** : textes secondaires en `--color-neutral-700` minimum sur crème, aucun texte sous 12px (métas 12–12.5px). À vérifier à la mesure.
- **Modales (K-01, K-12, K-21)** : les trois modales (Créer, Supprimer, Sceller) en **`<dialog>` natif avec `showModal()`** — focus initial sur le premier champ, Échap ferme, retour du focus au déclencheur, `aria-labelledby`. Le prototype simule avec `role="dialog"` + `aria-modal` + `isolation:isolate` ; en prod, `<dialog>` obligatoire. Fond `rgba(32,30,29,.45)`, carte `max-width` 520–560px, radius `--radius-lg`, `--shadow-lg`.
- **Hygiène (K-18–K-20)** : `<html lang="fr">`, tous les champs avec `label for`/`aria-label` (le prototype les a), `<main>` + lien d'évitement.
- **Vigie nourrie** : nouveaux verdicts à implémenter — palier 800–1024px, « le CTA principal est dans le viewport », « rien ne se superpose à une modale ouverte », mesure des contrastes.

## Écrans conservés du prototype v1 (déjà spécifiés, inchangés en logique)
- **QG** : fil de chaleur (rampe neutre→terracotta 5 paliers, formule affichée en légende, % dans le nœud, jalon = carré arrondi, jamais pratiqué = tireté + « — », fraîcheur en italique si > 30j), badge sage = possibles vivants au nœud, losange encre = hypothèse infirmée (« ne refroidit jamais ») ; dossier de nœud en place (champs, hypothèses, journal de pratique avec transcriptions dépliables — kata en terracotta, humain en sauge — et « blocs d'état émis ») ; panneaux Possibles vivants (« comptés, jamais notés ») et Décisions (delta fermé barré / ouvert +sage).
- **Barre de verdict du Design** : « aucun changement » (neutre) / « non éprouvé » (tireté, « rien n'est écrit, aucun brouillon n'est gardé ») / « la définition ne tient pas » (encre, anomalie nommée et localisée) / « la définition tient » (terracotta) ; Éprouver (primaire) ; Sceller… inactif sauf si ça tient. Toute édition ré-invalide le verdict. Sceau : auteur requis journalisé, motif, avertissement « Sceller périme le corpus » AVANT, entrée de journal monospace `accent-100` après.
- **Profil** : avatar sauge, activités accessibles (rôle praticien/observateur, « ouvrir le QG » avec le sujet chargé), mes harness (« ouvrir le design »).

## Interactions & State
- État global : `view`, `harnessId`, `axis`, `selNode` (partagé entre axes), `selQG`, `openSession`, `subjectId`, `changes[]` (chemins modifiés), `tested`, modales. En prod : routé dans l'URL (vue, harness, axe, nœud, sujet).
- « ouvrir le QG » (Profil) → territoire Harness, QG, sujet chargé, sélection vidée. Changement de sujet vide la sélection. Toute mutation du Design ajoute son chemin à la proposition et remet le verdict à « non éprouvé ».
- Hover/pressed/focus : hérités de la feuille Organic ; `:focus-visible` = anneau accent 2px, jamais le bleu navigateur.

## Design Tokens
Tout vient d'`organic-styles.css` : fond `--color-bg` #f5ead8, texte `--color-text` #201e1d, chaleur/positif `--color-accent` #c67139 (rampe 100–900), possibles `--color-accent-2` #7a8a5e (rampe), **encre `--color-neutral-900`** = troisième voix (f♯, contrat violé, « ne tient pas », écarts de vigie — jamais de rouge), neutres 100–900 ; `--font-heading` Caprasimo (weight 400 uniquement), `--font-body` Figtree, monospace système pour identifiants/mesures ; radii `--radius-md/lg` + pills 999px ; ombres `--shadow-sm/md/lg`. Icônes : Lucide, stroke 2.75.

## Hors périmètre de ce prototype
- **Mobile 375px (K-03)** : non maquetté — le tiroir/barre basse en trois territoires reste à concevoir. Ne pas improviser : demander une maquette.
- Le chat de pratique, les flux réels Éprouver/Sceller côté serveur (le prototype simule), le repli mobile des cartes de coût (K-16 — les cartes de coût ne sont pas dans ce prototype).

## Assets
Aucun. Losange, points, pastilles et rampe sont en CSS pur. Polices chargées par la feuille de style.

## Files
- `Kokaji v2.dc.html` — le prototype (toutes les vues, données d'exemple réalistes et lacunaires : sujet jamais pratiqué, nœud jamais pratiqué, densho incomplet, contrat cassé avec ses issues).
- `organic-styles.css` — la feuille Organic (tokens + classes `.nav`, `.card`, `.tag`, `.btn`, `.input`, `.dialog`).
- `audit-ergonomique-2026-09-14.pdf` — l'audit source : orientations produit 1–4 et constats K-01 à K-23. Le lire avant d'implémenter ; la priorisation (passes 1–3) y figure page 10.
