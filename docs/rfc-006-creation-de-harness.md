# RFC-006 — Créer un harness

> **Statut : proposé** (établi, août 2026).
> ⚠️ **Ce RFC entame une troisième fois le non-objectif « hébergement pour des tiers »** (SPECS §0). L'entame est nommée : **tout compte peut créer ses propres harness et en devenir propriétaire**. Ce qui reste dehors : les quotas et la facturation (§6), et le catalogue de harness proposés par des tiers. Entraîne une mise à jour de SPECS §0 et §2, et une extension de la matrice du RFC-004 §3.

---

## 1. Motivation

Kokaji sait forger, servir et observer des harness. Il ne sait pas en **faire naître un**. Aujourd'hui il faut écrire à la main les six pièces d'une définition — l'Atelier en compte 488 lignes —, puis `kokaji rattacher` pour en déclarer le propriétaire, puis redémarrer le service.

Tant que naître est un geste d'administrateur système, il n'y a pas d'usine : il y a un dojo avec un harness dedans. Ce RFC pose le geste manquant.

## 2. Qui crée, et ce que ça change à la matrice

**Tout compte peut créer.** Le harness créé lui appartient : un propriétaire, toujours exactement un, comme le RFC-004 l'exige.

**`creer` est le premier geste sans objet.** Toute la matrice du RFC-004 §3 demande « quel est ton rôle *sur ce harness* » ; créer demande « as-tu le droit d'en faire un », ce qui ne se répond pas par un rôle puisqu'il n'y a pas encore de harness. `GESTES` refuse par défaut ce qu'elle ne connaît pas : le geste est aujourd'hui littéralement inexprimable, et ce n'est pas un oubli — c'est que la matrice ne sait parler que d'œuvres existantes.

Elle gagne donc une seconde famille : les **gestes de service**, qui se pèsent sur le compte et non sur un harness. `creer` en est le premier. `administrer` — déjà tenu par `est_admin`, hors matrice — y trouve rétrospectivement sa place.

Cette séparation est ce qui empêche `creer` d'être accordé par erreur : un geste sans objet ne peut pas emprunter le rôle d'un autre.

## 3. À partir de quoi

**Un harness neuf est toujours une copie.** Une semence vide validerait, mais livrerait 488 lignes à écrire avant le premier échange — et le premier pas est le seul qui décide si quelqu'un reste. On part d'une œuvre qui marche.

> **Amendement du 16 août 2026 — la semence entre au périmètre.**
>
> Le paragraphe écarte la semence vide au motif qu'elle livrerait 488 lignes à écrire. L'argument tenait pour une semence qui serait un *fichier vide* ; il ne tient pas pour une semence qui **vaut, se forge et se trempe telle quelle**. Celle-ci compte une étape, une cible, un registre — on peut pratiquer avant d'avoir écrit une ligne, et remplacer ensuite.
>
> Les deux voies restent distinctes et ont chacune leur usage : **on copie quand une méthode voisine existe, on sème quand la sienne ne ressemble à rien de ce qu'on a déjà.** Fermer la seconde obligeait à partir d'une forme qu'on allait tout entière défaire.
>
> La semence n'est pas un second harness d'exemple (SPECS §9) : elle ne décrit **aucun** métier. Son manifest dit « à décrire », ses questions disent « à écrire ». Ce qu'elle garantit est plus étroit que d'être exemplaire — elle garantit de tenir debout.

### 3.1 Ce qui se copie, et ce qui ne se copie pas

**La définition se copie ; la pratique jamais.** Le corpus d'un harness copié est **vide**. Les ha appartiennent à leur praticien (R12.4) et ne suivent pas la définition : copier un harness ne donne aucun regard sur ce que d'autres y ont pratiqué.

C'est l'invariant le plus important de ce RFC. Sans lui, copier deviendrait le contournement de tout le RFC-004 : il suffirait de copier pour lire.

### 3.2 De quoi l'on a le droit de partir

- **d'un harness où l'on a déjà un rôle** — propriétaire ou contributeur : on copie ce qu'on a le droit de lire ;
- **du harness d'exemple**, déclaré par le déploiement, copiable par tout compte sans en être membre. C'est ce qui rend un compte neuf autonome dès l'inscription.

Le repo n'en embarque qu'un, sur un domaine fictif (SPECS §9). Il ne devient pas pour autant un catalogue : **être copiable est une propriété déclarée au déploiement**, pas une découvrabilité. Un harness qu'on ne possède pas et qui n'est pas déclaré exemple reste invisible — le RFC-004 §7 tient.

### 3.3 L'id, et le nom

L'`id` est choisi à la création et **immuable** : il est écrit dans chaque ligne du journal et dans chaque ha (RFC-005 §2.1). Il doit être libre sur le service — deux harness de même id mélangeraient leurs corpus sous une seule clé d'archive.

Le `nom` est libre et modifiable. C'est lui qu'on voit ; l'id ne se montre pas.

## 4. Naître brouillon, être servi au scellement *(amendé — voir plus bas)*

**Un harness créé naît brouillon.** Il est chargé et pratiquable au QG par ses co-auteurs — l'ACL suffit à écarter les autres. Mais il **n'offre aucun modèle au chat** tant qu'il n'a pas été scellé.

Ce n'est pas une politique, c'est un fait : un harness dont les coupes ne sont pas forgées n'a rien à servir, et un modèle virtuel sans coupe répondrait 404. Le scellement — geste qui existe déjà (`/conception/scellement`) — **devient le moment où un harness entre en service** : il forge ses coupes, et le service prend en compte l'application du harness neuf.

Deux bénéfices que le brouillon donne gratuitement :

- on adapte une copie avant que quiconque puisse la pratiquer par le chat ;
- **le rechargement se rattache à un événement du produit** et non à une écriture de fichier. Le service n'a pas à surveiller un dossier : il apprend qu'un harness existe quand quelqu'un le scelle.

> **Amendement du 16 août 2026 — le scellement n'est pas ce qui met en service.**
>
> Le paragraphe ci-dessus prend le scellement pour la condition du service. C'est faux, et le produit le prouvait déjà : **l'Atelier n'a jamais été scellé** — son journal de scellements était vide — et il sert le chat depuis des semaines. Ses coupes avaient été forgées par `kokaji forge`, jamais par un scellement.
>
> Deux gestes ont été confondus. **Sceller arrête une définition** : c'est un acte de versionnage et de responsabilité, qui porte le nom de son auteur. **Forger produit les coupes** : c'est ce qui rend un kata appelable. Ce qui décide du service est donc l'existence des coupes, jamais la présence d'un scellement.
>
> Appliquer la règle telle qu'écrite aurait coupé le chat en service. Elle n'a pas été implémentée.
>
> **Ce qui est vrai**, et remplace le paragraphe : un harness offre ses kata au chat **quand ses coupes sont forgées et servies par la passerelle**. Un harness dont elles ne le sont pas ne peut rien servir — non par interdiction, mais parce qu'il n'y a rien à appeler.
>
> **Ce qui reste vrai du lien avec le scellement** : sceller (ou arrêter) est le bon moment pour forger, puisque c'est le moment où une définition est arrêtée. Le scellement ne *rend pas* le service licite, il *produit* ce dont le service a besoin. La nuance décide de ce qu'on code : on ne vérifie pas un scellement pour autoriser, on forge après un scellement pour rendre appelable.
>
> **Une seconde conséquence**, trouvée par la pratique le même jour : on ne pouvait pas sceller un harness qu'on n'avait pas modifié. Un nouveau-né étant une copie exacte, la porte que ce paragraphe désignait était **murée**. Le geste d'arrêt (`sceller` sur une proposition vide) a été ajouté pour l'ouvrir — sans lui, le §7.1 était injouable.

## 5. Archiver, jamais supprimer

Un harness retiré cesse d'être servi, cesse d'être proposé au sélecteur, cesse d'offrir des modèles. **Son dossier et son corpus demeurent.**

Le principe d'observabilité est fondateur (SPECS §0) : ce qui a été observé ne se détruit pas parce que la forme qui l'a produit ne sert plus. Un harness archivé garde ses ha lisibles par ceux qui les ont pratiqués, et ses agrégats restent justes.

`supprimer` reste donc dans la matrice du RFC-004 §3 comme un geste de propriétaire, et **n'est toujours pas construit**. Archiver le remplace partout où l'on aurait voulu supprimer.

> **Amendement du 16 août 2026 — « cesse d'être proposé » ne peut pas vouloir dire « disparaît ».**
>
> Le paragraphe promet deux choses dans la même phrase : le harness archivé cesse d'être proposé au sélecteur, **et** ses ha restent lisibles par ceux qui les ont pratiqués. Les deux ne tiennent pas ensemble : on ne lit les ha d'un harness qu'en le choisissant, et on ne choisit que ce qui est proposé.
>
> Le harness archivé **reste donc au sélecteur, marqué de sa date d'archivage**. Il est montré pour ce qu'il est — hors service, pas disparu. Ce qu'il cesse d'offrir, ce sont ses **modèles au chat** : `/v1/models` rend une liste vide et le relais refuse ses kata. On ne le pratique plus, on le consulte encore.
>
> C'est la lecture qui honore les deux promesses ; l'autre en sacrifiait une en silence.

## 6. Non-objectifs de ce RFC

**Les quotas et la facturation.** Un plafond de créations par compte est voulu et n'est pas codé : le service reste inondable par un compte, et c'est une dette assumée plutôt qu'un oubli. Elle sera payée quand il y aura quelqu'un à plafonner.

Également dehors : un catalogue de harness proposés par des tiers ; la découvrabilité (RFC-004 §7 tient) ; l'import d'un dossier de harness depuis l'extérieur ; la suppression ; le transfert d'un harness archivé.

## 7. Critère « juste assez » (avec sabotages)

1. **Nominal** — un compte neuf, membre d'aucun harness, copie le harness d'exemple sous un id à lui. Il en est propriétaire. Le harness apparaît à son sélecteur au QG ; **le chat ne peut appeler aucun de ses kata, faute de coupes**. Il l'arrête tel quel, ou l'adapte au module design puis le scelle : les coupes sont forgées, et le chat lui offre ses kata sous leurs noms.
2. **Le corpus ne suit pas** — l'original a des ha ; la copie en a zéro. Aucune route ne rend un ha de l'original au propriétaire de la copie.
3. **Sabotages** — chacun doit produire un refus net :
   - copier un harness dont on n'est ni membre ni auquel on accède comme exemple → refusé, **sans confirmer qu'il existe** ;
   - créer sous un id déjà porté par un harness du service → refusé ;
   - pratiquer au chat un kata d'un harness encore brouillon → refusé, comme tout kata hors du harness courant (RFC-005 §3.4) ;
   - un contributeur de la copie tente d'archiver → refusé : archiver porte sur la possession.
4. **L'archivage ne détruit rien** — archiver un harness qui porte des ha, puis vérifier que ses ha restent lisibles par leur praticien et que ses agrégats sont inchangés.
5. **Invariant de naissance** — le harness créé **valide, forge et trempe sans retouche**. Une copie qu'il faudrait réparer à la main avant de s'en servir ne serait pas une naissance, mais un gabarit.
