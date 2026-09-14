# RFC-013 — La page v2 : quatre orientations, trois passes, et ce qu'elles concilient

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : l'audit ergonomique du 14 septembre 2026 et le handoff « Kokaji v2 » (`docs/design/handoff-v2/`), RFC-004 §4 (le design fait foi pour la forme), RFC-006 §5 (archiver, jamais supprimer), RFC-010 (l'axe des coupes), RFC-012 (le panneau Dépôt). Objet : sceller les quatre orientations produit de l'audit comme décisions, concilier le prototype avec ce que le produit a déjà décidé, et ordonner le travail en trois passes.

---

## 1. Motivation

L'audit du 14 septembre dit le produit en une phrase : *« un produit d'auteur, très lisible pour son auteur ; la prochaine itération doit en faire un produit pour un second utilisateur »*. Il compte quatre constats critiques — une modale traversée par la page, le lien « pratiquer » hors de l'écran entre 800 et 1 040 px, une navigation mobile invisible, une administration sans retour — huit majeurs, cinq modérés, six mineurs, et quatre orientations de structure.

Le handoff qui l'accompagne est **haute fidélité** : couleurs, typographie, espacements et libellés sont finaux, tous tirés de la feuille Organic, qui n'a pas bougé. La RFC-004 §4 a posé la règle : le design réalisé fait foi pour la forme ; toute divergence entre le design et le modèle se résout par amendement de l'un ou de l'autre, explicitement. Ce RFC est cet amendement, dans les trois endroits où le prototype et le produit ne disent pas la même chose.

## 2. Décisions scellées

### D13.1 — Les quatre orientations de l'audit sont adoptées telles quelles

1. **Un menu en trois territoires** — *Harness* (le sélecteur, puis Design et QG comme ses deux sous-vues, puis « créer »), *Moi* (Profil, déconnexion), *Kokaji* (Découvrir, Vigie, Comptes et invitations, en pied de menu). Le nom du harness actif figure dans le titre de Design et de QG.
2. **L'administration scindée** — la Vigie et les Comptes deviennent deux vues du territoire Kokaji, avec la navigation principale ; l'autorat rejoint le harness, dans une section ouverte depuis « qui forge avec moi ». Plus aucune page sans retour.
3. **Un graphe unique du Design** — les mêmes nœuds, le même ordre, les mêmes noms que le QG, en tête du Design, persistant d'un axe à l'autre. Les axes sont des **facettes du nœud sélectionné**, pas des pages. Le nœud porte ses indicateurs par facette.
4. **Le cycle de vie d'un harness** — un geste de propriétaire, visuellement isolé dans la section Autorat, confirmé par la saisie du nom exact, dont la portée est dite précisément.

Avec elles, les corrections transverses du handoff : routage et titres, en-tête du QG qui se replie, badge « miroir » à un seul emplacement, pastilles du QG qui sont de vrais boutons, vocabulaire unifié, aide contextuelle, contrastes, modales en `<dialog>` natif, hygiène.

### D13.2 — Le geste du cycle de vie est *archiver*, avec le parcours de *supprimer*

L'orientation 4 dit « supprimer, irréversible dans Kokaji ». La RFC-006 §5 dit « archiver, jamais supprimer », et l'archivage existe : le harness reste au sélecteur, marqué de sa date, ses ha restent lisibles par ceux qui les ont pratiqués, seuls ses modèles au chat s'éteignent. Le principe d'observabilité (SPECS §0) tient : ce qui a été observé ne se détruit pas parce que la forme qui l'a produit ne sert plus.

Le parcours du prototype est adopté **en entier** — zone isolée, saisie du nom exact, bouton inactif tant que le nom ne correspond pas, texte de portée, bandeau de confirmation — et branché sur l'archivage. Le mot est « archiver », le texte de portée devient : *« Le harness cesse d'être servi : plus de modèles au chat, plus de pratique. Sa définition, ses sujets, ses cas et son journal restent lisibles, marqués archivés. Le dépôt git reste intact. Réservé au propriétaire. »* Désarchiver est un geste symétrique, au même endroit, sans confirmation par le nom.

`supprimer` reste dans la matrice du RFC-004 §3, et reste non construit.

### D13.3 — Le panneau « Dépôt » vit dans la section Autorat

Le prototype ne connaît pas la RFC-012. Le panneau Dépôt — état, dépôt nu, pousser, tirer, enregistrer — prend place dans la section Autorat, entre les membres et la zone d'archivage, qui mentionne déjà que « le dépôt git reste intact ». Même carte, même vocabulaire, aucune forme nouvelle.

### D13.4 — La facette Coupes reprend l'axe de la RFC-010, dans la forme du prototype

L'axe « 4 · Coupes » livré par la RFC-010 devient la facette Coupes du nœud sélectionné : le densho en pleine largeur, quatre zones à hauteur libre, l'aperçu de la coupe rendue à droite, collé au défilement, avec la mention « densho incomplet » quand une variable obligatoire est vide. Le gabarit du harness — commun à toute la chaîne, donc à aucun nœud — se place au-dessus du graphe, replié par défaut. La route `POST /conception/coupe` et la mécanique de proposition ne changent pas.

### D13.5 — La vigie est nourrie, jamais contournée

Quatre verdicts entrent : un palier **800 à 1 024 px** aux mesures existantes ; « le CTA principal est dans le viewport » ; « rien ne se superpose à une modale ouverte » ; la **mesure des contrastes** des textes secondaires. L'audit le dit : la moitié des constats critiques ne pourra alors plus revenir.

### D13.6 — Le mobile à 375 px n'est pas improvisé

Le handoff ne le maquette pas : le tiroir ou la barre basse en trois territoires reste à concevoir. En attendant, la passe 1 rend le défilement horizontal **lisible** — dégradé de bord, premier élément partiellement visible, sélecteur au nom complet — sans inventer la forme.

## 3. Les trois passes

| Passe | Ce qu'elle livre | Constats |
|---|---|---|
| **1 · Correctifs** — rendre le produit montrable | `<dialog>` natif pour les trois modales ; en-tête du QG en `flex-wrap`, « pratiquer » ancré, sélecteur borné ; affordance de la navigation mobile ; retour et résumé en tête de l'administration ; `lang="fr"`, labels, `<main>`, lien d'évitement ; les trois premiers verdicts de vigie | K-01, K-02, K-03, K-04, K-12, K-18 à K-21 |
| **2 · Structure** — les quatre orientations | trois territoires ; routage et titres ; Vigie et Comptes dans la page ; Autorat dans le harness, avec Dépôt et archivage ; graphe unique et facettes ; vocabulaire unifié | remarques 1 à 4, K-05 à K-09, K-13, K-17, K-22, K-23 |
| **3 · Confort** — écrire et lire mieux | densho pleine largeur ; contrastes et mesure ; aide contextuelle vers le lexique ; cartes de coût en mobile | K-10, K-14, K-15, K-16 |

Chaque passe se livre seule, tests et mesures de rendu compris, et la vigie de la première instance la regarde dès le déploiement.

## 4. Ce qui change

| Document | Changement |
|---|---|
| RFC-006 §5 | inchangé — D13.2 l'applique ; le parcours de confirmation vient du prototype |
| RFC-010 §4.4 | l'axe devient une facette (D13.4) ; le gabarit au-dessus du graphe |
| RFC-012 D12.5 | le panneau Dépôt vit dans la section Autorat (D13.3) |
| RFC-004 §4 | le handoff v2 devient la référence visuelle, à la place du handoff QG d'août |
| docs/qg.md | la page en trois territoires ; les verdicts de vigie |

## 5. Non-objectifs

- Le mobile 375 px (D13.6) — demande une maquette.
- Le chat de pratique, et le repli mobile des cartes de coût au-delà de K-16.
- Toute évolution de la trempe, des comptes ou du chat — chacune a sa RFC.

## 6. Critère « juste assez » — avec sabotages

**Nominal** : sur la première instance, la vigie tient ses mesures aux quatre largeurs, la modale « créer » s'ouvre devant tout, au clavier, se ferme à Échap et rend le focus ; « pratiquer » est visible à 800 px ; l'administration a un retour. Puis, passe 2 : un lien `/h/atelier/design/contrats?noeud=cadrage` ouvre exactement cette facette, et le titre de l'onglet le dit.

**Sabotages** :

1. Une pastille du QG posée en `z-index` par-dessus la modale ouverte → la vigie refuse. *Mesuré : « rien ne se superpose à une modale ouverte », quatre largeurs.*
2. Un « pratiquer » qui sort du viewport à 800 px → la vigie refuse. *Mesuré : « le CTA principal est dans le viewport », quatre largeurs.*
3. Un texte secondaire sous 4,5 : 1 de contraste → la vigie refuse. *Mesuré : « les textes tiennent le contraste » et « aucun texte sous 12 px », par module et par largeur — et vu refuser trois fois en construction : le lien d'évitement, le bouton primaire, les tags à 11 px.*
4. Archiver depuis un compte contributeur → 403 ; archiver avec un nom qui ne correspond pas → le bouton reste inactif, aucune requête ne part.
5. Un `<button class="onglet">` sans `href` après la passe 2 → le test de page refuse.

## 7. Tableau d'application

| Passe | État (14 septembre 2026) |
|---|---|
| 1 · Correctifs | appliquée — `kokaji/qg/vue.html`, `admin.html`, `kokaji/rendu.py` ; 64 mesures aux quatre largeurs |
| 2 · Structure | appliquée — trois territoires et routage (796a1a5), Autorat avec Dépôt et archivage (39a2f4f), graphe unique et facettes, vocabulaire unifié ; les nœuds de chaîne qui ne sont pas des kata se lisent dans le graphe sans s'y éditer |
| 3 · Confort | appliquée — gris secondaires en neutral-700, aucun texte sous 12 px, bouton primaire et tags outline assombris ; lexique et « ? » contextuels ; cartes de coût empilées sous 480 px ; fondu de navigation sous `prefers-reduced-motion` ; la vigie mesure contrastes et tailles, 105 mesures |

---
*Note d'établi : l'audit dit ce qu'il faut garder — le lexique, le ton, la promesse rendue visible, la carte des étapes. Ce RFC ne touche à rien de cela : il change la mécanique autour, pour qu'un second utilisateur y arrive.*
