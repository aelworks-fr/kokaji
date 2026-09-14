# Le QG — le fil d'ariane

```bash
kokaji qg <harness> [--sujet …] [--liste]     # au terminal
kokaji service <harness>                       # puis http://127.0.0.1:8100/qg
```

Le QG rend la chaîne **déclarée par le manifest** (R8.1), peuplée de ce que les
blocs d'état ont observé. Il ne connaît aucune chaîne en dur, aucun sujet
d'avance : les sujets viennent des blocs eux-mêmes.

## Deux lectures d'un même fil

**La chaleur** (R8.2) — chaque nœud chauffe graduellement, du neutre à la
terracotta, en cinq marches. Jamais un binaire, jamais un fait/pas fait.

```
chaleur = (champs établis + hypothèses validées)
          ÷ (champs connus + hypothèses hors pause)
```

La formule est **imprimée dans la légende**, sous les marches — un agrégat dont
on cache le calcul est un score déguisé.

Deux règles y sont enfouies, et elles comptent :

- **Une hypothèse infirmée sort des deux termes.** Une réfutation est un gain de
  connaissance ; elle ne doit jamais refroidir un nœud en silence. Une trempe
  ratée est une information — elle se marque d'un losange, pas d'une couleur de
  honte.
- **Seuls les champs connus pèsent.** Un nœud que la pratique n'a jamais touché
  ne rend pas zéro mais **rien** : il affiche « — », en pointillés, et son
  dossier dit en une phrase que son état apparaîtra quand des sessions
  l'émettront. Ne pas savoir n'est pas un savoir nul.

**La santé des options** (R8.4) — un badge sauge par nœud, et un panneau
« possibles vivants » du sujet : le compte, la liste, l'âge. Pas de halo, pas
d'animation.

Les deux canaux — la chaleur en terracotta, les possibles en sauge — **ne
partagent jamais une teinte**. Ce sont deux lectures indépendantes du même fil,
et les confondre reviendrait à suggérer qu'un possible vivant réchauffe, ou
qu'un nœud chaud ferme des options.

Trois métriques, et rien de plus : options ouvertes par nœud et par sujet, âge
médian des options ouvertes, delta par décision. **Aucun indice composite, aucun
score de fécondité** — un chiffre agrégé magique inviterait au pilotage aveugle.

L'âge se compte depuis la **première apparition** d'une option jusqu'au dernier
état observé. « La dormance n'est pas un statut : c'est un âge » — elle se
dérive, elle ne se déclare pas.

## Ce que le QG ne fait pas

Il **lit et n'évalue pas** (carnet de vigilances #8). Aucune cible, aucun seuil,
aucun classement de sujets. Une lecture normative — « ce sujet brûle ses
options » — reste un jugement humain devant les données. Un test vérifie
qu'aucun mot de score n'apparaît dans ce qu'il rend.

Il ne modifie rien : il lit le corpus écrit par le middleware (§7).

## La question de l'ordre des hypothèses, tranchée

R8.2 demandait d'agréger « statuts de champs **+ statuts d'hypothèses », et je
l'avais laissé de côté : `[en_cours, validee, infirmee, en_pause]` n'est pas
rangé du plus fort au plus faible, et plier ça dans un ratio aurait demandé
d'inventer un ordre que personne n'avait déclaré.

Le handoff de design tranche autrement, et mieux : **pas d'ordre du tout**.
Seule `validee` compte au numérateur, `infirmee` et `en_pause` sortent des deux
termes, `en_cours` ne pèse qu'au dénominateur. Aucun rang n'est nécessaire —
c'est une partition, pas une échelle.

## La page

Servie par le middleware, sans dépendance externe : un seul fichier, styles et
script inclus, thème clair et sombre. Cliquer un nœud ouvre son détail — champs,
hypothèses, horodatage du dernier état (R8.3).

**Deux sélecteurs** : le corpus, puis le sujet. Un harness peut déclarer
plusieurs corpus — les cas vécus, les essais — et le QG ne mélange jamais les
deux, y compris pour les sessions en cours.

La liste des corpus indique combien de sujets chacun porte, et la page **ouvre
sur un corpus qui a quelque chose à montrer** plutôt que sur un écran vide. Un
corpus sans sujet le dit en clair : un sujet n'apparaît que si une session a émis
un bloc d'état, ce que seules les cibles instrumentées font.

## Design du harness — le quatrième axe : les coupes (RFC-010)

L'onglet « Design du harness » édite la définition en quatre axes :
partitionnement, contrats f♯, trempe, et **coupes**. Le quatrième est celui du
texte : à gauche le gabarit du harness, texte brut avec ses variables, puis le
densho du kata choisi — rôle, questions, interdits, livrable, passage, natures ;
à droite la coupe rendue pour une cible, telle que le chat la recevrait,
forgée en mémoire depuis le brouillon par `POST /conception/coupe`. Rien n'est
écrit tant qu'on ne scelle pas ; une retouche périme la coupe rendue, qu'on
redemande. Elle se copie et se télécharge telle quelle, avec son estampille.

Les adjonctions — ce que le kata hérite de l'amont, ce qu'il produit pour
l'aval — n'ont pas de zone sur cet axe : elles vivent à l'axe « Contrats » et
entrent à la forge, où on les lit dans la coupe. Un harness adopté (RFC-008) y
montre le texte de ses étapes sans l'éditer : c'est le geste du RFC-011.

**Sceller commite.** La définition d'un harness vit dans un dépôt git (RFC-009
D9.1) : le scellement, une fois écrit, commite le harness — et seulement lui —
dans le dépôt qui le contient, avec ses versions, le motif et l'auteur dans le
message. Sans git, hors de tout dépôt, ou si le commit échoue, le scellement
tient et la trace dit pourquoi rien n'a été commité. Pousser vers le distant
est un réglage du harness, `pousser_au_scellement`, posé à l'enregistrement
d'un dépôt nu (RFC-012) : le service pousse alors après chaque scellement, en
avance rapide, et la trace dit « commité et poussé » ou pourquoi non.

## Au backlog, non bloquant — la nature au détail du nœud (RFC-003 §5.5)

Le bloc d'état peut désormais porter un champ `nature` : dans quel genre de
problème le kata estime se trouver, avec quelle confiance, et à quelle étape il
l'a révisé. Le middleware le transporte et le range comme le reste de l'état.

Le QG ne l'affiche pas encore. Quand il le fera, ce sera **une donnée de plus au
détail d'un nœud** — à côté des champs et des hypothèses — et non une vue
nouvelle. Une nature n'est pas un score : elle ne colore rien, elle ne classe
rien, elle se lit.

## La page v2 — la passe 3 (RFC-013)

Écrire et lire mieux. Les gris secondaires sont en `neutral-700` — 5,5 : 1 sur
crème — et aucun texte ne descend sous 12 px ; le bouton primaire et les tags
« outline » sont assombris. Un « ? » discret par bloc — la chaîne, les
possibles, les contrats, le densho — mène au lexique de Découvrir, l'entrée
surlignée (`#/kokaji/decouvrir?terme=…`). Les cartes de coût s'empilent sous
480 px. Une vue qui arrive s'annonce d'un fondu léger, et pas du tout sous
`prefers-reduced-motion`. La vigie mesure désormais les contrastes et les
tailles de texte, par module et par largeur : la moitié des constats de
l'audit ne peut plus revenir sans qu'elle le dise.

## La page v2 — la passe 2 (RFC-013)

Le menu tient en trois territoires : *Harness* — le sélecteur, puis Design et
QG comme ses sous-vues, puis créer —, *Moi* — Profil, se déconnecter —, et
*Kokaji* en pied — Découvrir, Vigie, Comptes & invitations. Chaque vue a une
adresse dans le fragment (`#/h/<harness>/design/<axe>?noeud=<id>`,
`#/kokaji/vigie`…) et un titre d'onglet qui dit le harness, la vue et l'axe.

Le Design tient sur **un seul graphe** — les mêmes nœuds, le même ordre, les
mêmes noms que le QG, le nom d'affichage venant du kata — et les quatre axes
sont des facettes du nœud sélectionné : Partitionnement (nom, identifiant,
type, avancer, reculer, retirer en deux temps), Contrats f♯ (ce qu'il exige,
ce qu'il garantit, les deux issues d'une ligne cassée sur la ligne), Trempe
(le seuil du nœud, le reste commun à la chaîne), Coupes (le densho en pleine
largeur, l'aperçu de la coupe collé à côté). Le nœud porte ses marques : contrat
violé, densho incomplet, seuil par défaut. Le gabarit, commun à toute la
chaîne, se replie au-dessus du graphe.

L'autorat vit dans le harness, ouvert par « qui forge avec moi » : les
membres, inviter un co-auteur, le panneau Dépôt (RFC-012) — l'état du dépôt,
enregistrer un dépôt nu ou le désenregistrer (propriétaire), pousser et tirer
en avance rapide (co-auteurs), pousser à chaque scellement —, et la zone
d'archivage — archiver, jamais supprimer, confirmé par le nom exact. La
naissance sait aussi cloner un dépôt nu, ou en lier un tout de suite.

## La page v2 — la passe 1 (RFC-013)

L'audit du 14 septembre 2026 et son handoff vivent dans `docs/design/handoff-v2/`.
La passe 1 rend le produit montrable sans changer sa structure : les modales
sont des `<dialog>` natifs — devant tout, Échap ferme, le focus revient — ;
l'en-tête du QG se replie et « pratiquer » reste ancré à droite ; le rang
d'onglets mobile montre qu'il défile ; l'administration a un retour et un
résumé « N sur N tiennent », écarts en tête ; `lang="fr"`, `<main>`, lien
d'évitement. La vigie gagne un palier à 800 px et deux verdicts : « le CTA
principal est dans le viewport » et « rien ne se superpose à une modale
ouverte ». Les passes 2 et 3 suivent la RFC.

## Regarder le rendu

`tests/test_rendu.py` ouvre un vrai navigateur sur un écran de 360 px et mesure
des rectangles : la page ne déborde pas, un seul module est visible, aucun texte
n'en recouvre un autre — dans l'accueil comme dans le module design.

Les autres tests vérifient que les fils sont branchés ; ceux-là seuls regardent
ce qui s'affiche. Quatre défauts sont passés par ce trou en une semaine, tous
visibles au premier coup d'œil sur un téléphone, aucun visible dans le HTML.

```
pip install playwright && playwright install chromium
sudo playwright install-deps      # les bibliothèques système
pytest tests/test_rendu.py
```

Sur un poste où l'on ne veut — ou ne peut — rien installer :

```
./dojo/verif/rendu.sh
```

Même fichier de test, même navigateur, dans un conteneur qui les porte.

**Sans navigateur, ces tests se sautent en le disant.** Un test qui se saute en
silence finit par ne plus exister, et c'est exactement la panne que le carnet
décrit trois fois : ce qui se tait se lit comme ce qui va bien.
