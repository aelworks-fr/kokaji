# RFC-021 — Kokaji par MCP : un agent forge au nom de son compte

> **Statut : proposé** (établi, 19 octobre 2026).
> Dépend de : RFC-004 (comptes, matrice des droits, R12.4), RFC-005 (le harness courant, l'aiguilleur), RFC-006 (naître : copier, semer), RFC-008 et RFC-011 (adopter, importer un texte), RFC-010 (proposition, épreuve, coupe, scellement), RFC-012 (le dépôt du harness), SPECS §7 R7.4 (la surface MCP annoncée), §12 (sécurité). Objet : ouvrir **l'autorat** de Kokaji — créer un harness, le lire, le concevoir, l'éprouver, le sceller — à un agent qui parle le protocole MCP, **au nom d'un compte existant**, sans rien ouvrir de la pratique ni de l'administration.

---

## 1. Motivation

Tout ce qu'un co-auteur fait au module Design passe par une page. Or l'essentiel du travail de conception est déjà fait, ailleurs, avec un agent : on rédige un densho avec lui, on lui fait relire un gabarit, on lui demande pourquoi l'épreuve refuse. Puis on recopie à la main dans la page. La copie est le geste le moins sûr de toute la chaîne : c'est là qu'un champ hérité se perd, qu'une provenance s'oublie, qu'un texte importé se réécrit sans qu'on l'ait voulu.

Le protocole MCP (Model Context Protocol) est la façon commune dont un agent appelle des outils. Si Kokaji le parle, l'agent du co-auteur **lit la définition telle qu'elle est servie, propose, fait éprouver par la trempe elle-même, et scelle** — et la discipline de Kokaji tient, parce que ce sont ses propres gestes qu'on appelle, pas une copie de leur logique.

La SPECS l'annonçait (R7.4) sous une autre forme : une interface MCP **en lecture seule sur la pratique** (`list_ha`, `get_transcript`, `get_state`). Cette RFC prend l'autre bout. La pratique reste hors MCP pour l'instant (§6) ; c'est l'**autorat** qui entre, parce que c'est là que l'agent travaille déjà.

Trois choses manquent, et ce sont elles que la RFC décide :

1. **Qui parle.** Un agent n'ouvre pas de session par mot de passe et ne passe pas par le portail de l'instance. Il lui faut une identité qui désigne un compte existant, révocable, et plus étroite que la personne.
2. **Où il agit.** Toute la surface d'une œuvre est aujourd'hui portée par le *harness courant* de l'appelant (RFC-005 §5). Un agent qui conçoit trois harness à la fois ne peut pas changer le harness courant de la personne à chaque appel : ce serait changer, en silence, ce que le chat lui sert.
3. **Ce qu'il peut.** La matrice du RFC-004 §3 dit ce qu'un rôle peut sur un harness. Elle ne dit pas ce qu'une personne délègue à son agent.

## 2. Ce qu'un agent fait, et par où il passe

```
agent (client MCP)
  │  Authorization: Bearer <jeton d'agent>         — un compte, une portée, révocable
  ▼
POST /mcp   (MCP, transport HTTP « streamable »)   kokaji/mcp/
  │  identifie le compte par le jeton, et par lui seul (D21.2)
  │  plafonne la qualité à `compte`, jamais `administration` (D21.3)
  ▼
gestes   kokaji/gestes/  — la même fonction que la route HTTP, la même matrice (D21.6)
  │  le harness est nommé à chaque appel, jamais emprunté au harness courant (D21.5)
  ▼
définition · dépôt · ACL · journal des scellements    — la pratique n'est pas sur ce chemin
```

## 3. Décisions scellées

### D21.1 — Un agent parle au nom d'un compte, par un jeton d'agent

Un agent n'a pas de compte à lui. Il agit **au nom d'un compte existant**, par un **jeton d'agent** que la personne crée elle-même, depuis sa session, et qu'elle confie à son client MCP.

- Le jeton est tiré au hasard (32 octets), préfixé `kkj_` pour qu'un scanner de secrets le reconnaisse, **montré une seule fois** à la création. Le magasin n'en garde que l'empreinte (SHA-256 : l'entropie du jeton rend l'argon2 inutile ici, à la différence d'un mot de passe choisi par un humain).
- Il porte un **nom** (« l'agent de mon poste »), une **portée** (D21.4), une **échéance** (90 jours par défaut, jamais sans échéance), sa date de dernier usage, et sa révocation éventuelle.
- Il se crée et se révoque depuis le **Profil** (section « Accès des agents »), et par la commande `kokaji jeton creer|lister|revoquer --compte <email>` pour l'exploitant.
- **Un jeton ne crée jamais un jeton.** Seule une session humaine en émet ; un agent ne peut pas s'étendre lui-même.
- Un jeton désigne un compte, il n'en crée aucun — même règle que le portail et le chat (RFC-019 D19.3). Un compte supprimé emporte ses jetons.

```
jetons_agent : id · utilisateur_id · nom · empreinte · portee · cree_le · expire_le · dernier_usage_le · revoque_le
```

La table vit dans le magasin de comptes, hors git (R12.2), aux deux régimes (fichiers et base, RFC-014 D14.7).

**L'OAuth est différé, et sa forme est déjà décidée.** Certains clients MCP n'acceptent pas un jeton collé à la main et exigent le parcours d'autorisation du protocole (OAuth 2.1). Quand il viendra, Kokaji sera son propre serveur d'autorisation : l'écran de consentement est une page Kokaji, derrière l'authentification ordinaire de l'instance (portail ou session) ; ce qu'il émet **est un jeton d'agent** comme ceux-ci, avec la même table, la même portée, la même révocation depuis le Profil. Rien de ce qui suit n'est donc à réécrire ; l'OAuth n'est qu'une autre façon de le remettre. Aucun fournisseur d'identité extérieur n'est requis (D9.4).

### D21.2 — Sur `/mcp`, le jeton est la seule identité qui vaille

La surface MCP vit sous un seul préfixe, `/mcp`. Sur ce préfixe, `Identification` ne regarde **que** l'`Authorization: Bearer` d'un jeton d'agent :

- l'en-tête d'identité du portail (`--entete-identite`) est **ignoré** ;
- le jeton signé du chat est **ignoré** ;
- le biscuit de session et un jeton de session sont **ignorés**.

La raison tient à la topologie. Un client MCP n'est pas un navigateur : il ne franchit pas un portail interactif. L'instance devra donc exposer `/mcp` **sans** le portail devant, et Kokaji ne peut plus compter sur la condition qui rend l'en-tête d'identité sûr (« le portail écrase cet en-tête »). Lire l'en-tête sur ce chemin rendrait l'identité déclarative : quiconque atteint `/mcp` pourrait s'annoncer sous n'importe quelle adresse. Sur `/mcp`, c'est le jeton qui garde, et rien d'autre.

Réciproquement, un jeton d'agent **ne vaut rien hors de `/mcp`** : il n'ouvre ni le QG, ni la page, ni `/v1/chat/completions`. Une fuite de jeton n'est pas une fuite de session.

Un jeton absent, inconnu, expiré ou révoqué reçoit un 401 qui ne dit pas lequel des quatre.

### D21.3 — Un jeton ne porte jamais l'administration

La qualité d'un appelant identifié par jeton est **plafonnée à `compte`** (RFC-006 §2), même si le compte est administrateur de l'exploitation. L'administration (comptes, invitations, activation au chat, vigie d'administration) n'est atteignable que par une session humaine. Elle n'est pas absente de MCP par oubli d'outil : elle y est **inexprimable**, parce que la qualité qui l'autorise ne peut pas y naître.

### D21.4 — Deux portées : lire, concevoir

Une personne délègue moins qu'elle n'a. La portée s'ajoute à la matrice, elle ne la remplace pas : **un geste n'est permis que si le rôle le permet ET la portée le couvre**.

| Portée | Ce qu'elle couvre |
|---|---|
| `lecture` | lire ses harness, leur définition, leurs coupes, l'état de leur dépôt, leurs membres ; éprouver une proposition (rien n'est écrit) |
| `conception` | tout `lecture`, plus : faire naître un harness, ajouter une étape adoptée, sceller, pousser et tirer le dépôt, et les gestes de possession du D21.7 |

Une portée inconnue ne couvre rien (même discipline que `peut` : refuser ce qu'on ne connaît pas).

### D21.5 — Le harness se nomme à chaque appel ; le harness courant n'est jamais touché

Chaque outil qui porte sur une œuvre prend un argument `harness` (l'`id`). L'appel est remis à l'application de **ce** harness, avec l'ACL de **ce** harness — l'isolation par la portée de l'aiguilleur (RFC-005 §5) tient, simplement résolue par l'argument au lieu du choix enregistré.

Le harness courant du compte n'est **jamais** lu pour résoudre un appel MCP, ni écrit par un appel MCP. Il appartient à la pratique : il décide ce que le chat sert à la personne. Un agent qui le changerait pour travailler changerait, à l'insu de la personne, les modèles qu'on lui offre.

Un harness où le compte est étranger se refuse comme un harness qui n'existe pas (RFC-004 §7) : `aucun harness à ce nom`.

### D21.6 — Un geste, une fonction : MCP et HTTP appellent les mêmes gestes

Les gestes d'autorat vivent aujourd'hui dans les fermetures des routes (`service.py`, `exploitation.py`). Les recopier dans un serveur MCP ferait deux autorités sur les mêmes droits, qui divergeraient au premier amendement. Ils sont donc **extraits** en fonctions (`kokaji/gestes/`) qui reçoivent un appelant, un harness et des arguments, exigent leur geste à la matrice, et rendent un résultat ou lèvent un refus. La route HTTP et l'outil MCP n'en sont que deux traductions : codes HTTP d'un côté, erreurs d'outil de l'autre.

L'extraction ne change **aucun** comportement de la surface HTTP ; les tests existants le prouvent en restant verts sans retouche.

### D21.7 — Ce qui entre : l'autorat, possession comprise, sauf le transfert

Tout geste d'**œuvre** entre. Les gestes de **possession** (RFC-004 §3) entrent aussi, parce que la personne les a sur ses harness et qu'ils se défont : archiver se désarchive, un contributeur retiré se rajoute, un dépôt désenregistré se réenregistre (RFC-012 D12.2 : rien n'est détruit).

**Le transfert de propriété reste hors MCP.** C'est le seul geste d'autorat que son auteur ne peut pas défaire : une fois transféré, il n'est plus propriétaire, et seul le nouveau peut rendre. Un geste sans retour se fait de sa main, depuis la page.

`supprimer` reste non construit (RFC-006 §5) ; MCP ne l'invente pas.

### D21.8 — L'auteur d'un scellement est le compte, et le chemin se dit

Par HTTP, `POST /conception/scellement` reçoit `auteur` dans le corps. Par MCP, **l'auteur n'est pas un argument** : c'est le nom du compte que le jeton désigne. Un agent ne signe pas au nom de quelqu'un d'autre.

Et la trace dit par où le geste est passé : le journal des scellements gagne `via: "mcp"` et le nom du jeton (« scellé par Nicole, via l'agent de son poste »). La responsabilité reste la personne (c'est son jeton) ; l'observabilité garde la différence entre ce qu'elle a fait de sa main et ce qu'elle a fait faire. Les gestes de possession passés par MCP sont journalisés de la même façon.

### D21.9 — Le standard voyage avec la surface

Un agent qui conçoit un harness doit savoir ce qu'est un harness. La surface MCP expose donc, en **ressources** lisibles, le standard tel que le produit le connaît : le HDS (`docs/hds-v0.md`), le vocabulaire d'une proposition (les clés de `Proposition.CLES` et leur forme), et le registre des statuts du harness lu. Ce sont des fichiers du produit, servis tels quels : rien d'une instance, rien d'une pratique.

## 4. La surface

### 4.1 Le point d'entrée

`POST /mcp` (et `GET /mcp` pour le flux serveur du transport HTTP « streamable » du protocole), servi par le même processus que le service, **avant** l'aiguilleur et hors de toute application de harness. Le serveur MCP est un extra : `pip install -e '.[mcp]'` ajoute le SDK Python officiel du protocole. Sans l'extra, `/mcp` n'existe pas — il ne répond pas 500.

Aucune émission réseau nouvelle : le serveur MCP **reçoit**, il n'appelle personne (R12.5 intacte).

### 4.2 Les outils

Noms en registre technique, en français, comme les routes. Chaque outil dit le geste qu'il exige ; la colonne « route » nomme la fonction HTTP dont il est la traduction (D21.6).

**Lire** — portée `lecture`

| Outil | Ce qu'il rend | Geste | Route |
|---|---|---|---|
| `harness_lister` | mes harness (servis ou archivés), mon rôle, l'état du dépôt, et le harness d'exemple copiable | — (compte) | `GET /harness` |
| `harness_lire(harness)` | la définition en forme éditable : gabarit, cibles, kata (triplet, densho, contrat), chaîne, trempe, dernier scellement, membres | `lire` | `GET /conception` |
| `coupe_voir(harness, kata, cible, proposition?)` | la coupe forgée en mémoire, depuis la définition ou un brouillon — rien n'est écrit | `lire` | `POST /conception/coupe` |
| `depot_etat(harness)` | l'état du dépôt : propre, avance, retard, divergé, dernier commit | `lire` | `GET /depot` |
| `membres_lister(harness)` | propriétaire et contributeurs | `lire` | `GET /membres` |
| `proposition_eprouver(harness, proposition)` | le verdict de la trempe sur une copie : tient ou non, fautes, anomalies, changements, versions prévues | `editer` | `POST /conception/epreuve` |

**Créer** — portée `conception`

| Outil | Ce qu'il fait | Geste | Route |
|---|---|---|---|
| `harness_creer(id, nom, source?, depot?)` | copier un harness (le sien, ou l'exemple) ou semer si `source` est vide ; lier un dépôt nu tout de suite | `creer` | `POST /harness` |
| `harness_cloner(id, chemin, branche?)` | faire naître un harness d'un dépôt nu qui en est déjà un | `creer` | `POST /harness` (`cloner_depuis`) |
| `harness_adopter(id, nom, textes, provenance)` | adopter des textes faits main, chacun servi tel quel (RFC-008 N0) | `creer` | `POST /harness/adoption` |
| `etape_adoptee_ajouter(harness, nom, texte)` | un texte de plus, comme étape d'un harness adopté | `editer` | `POST /harness/{id}/etape-adoptee` |

**Concevoir** — portée `conception`

| Outil | Ce qu'il fait | Geste | Route |
|---|---|---|---|
| `proposition_sceller(harness, proposition, motif)` | sceller : versionner, commiter, pousser si réglé, forger, publier à la passerelle — l'auteur est le compte (D21.8) | `sceller` | `POST /conception/scellement` |
| `depot_pousser(harness)` | pousser la branche, en avance rapide | `pousser` | `POST /depot/pousser` |
| `depot_tirer(harness)` | tirer, en avance rapide, clone propre exigé | `pousser` | `POST /depot/tirer` |

Importer un prompt (RFC-011) et éditer un contrat f♯ (RFC-015) ne sont pas des outils à part : ce sont des **propositions**, qu'on éprouve puis qu'on scelle, comme à la page.

**Posséder** — portée `conception`, propriétaire seul

| Outil | Ce qu'il fait | Geste | Route |
|---|---|---|---|
| `harness_archiver(harness, archive)` | archiver, ou sortir d'archive | `archiver` | `POST /harness/{id}/archive` |
| `membres_candidats(harness)` | les comptes qu'on peut ajouter | `gerer_membres` | `GET /membres/candidats` |
| `membre_ajouter(harness, email)` · `membre_retirer(harness, utilisateur_id)` | ajouter ou retirer un contributeur | `gerer_membres` | `POST`/`DELETE /membres` |
| `depot_enregistrer(harness, chemin, branche?, pousser_au_scellement?)` · `depot_desenregistrer(harness)` | lier un dépôt nu, ou délier — la ligne, pas le clone | `enregistrer` | `PUT`/`DELETE /depot` |

### 4.3 Les ressources

| Ressource | Contenu |
|---|---|
| `kokaji://standard/hds` | le HDS, tel que le produit le versionne |
| `kokaji://standard/proposition` | le vocabulaire d'une proposition et un exemple minimal sur l'Atelier |
| `kokaji://harness/{id}/statuts` | les statuts de champ du harness (lisible si `lire`) |

### 4.4 Les jetons

| Route | Geste | Qui |
|---|---|---|
| `GET /moi/jetons` | mes jetons : nom, portée, échéance, dernier usage — jamais l'empreinte | session humaine |
| `POST /moi/jetons` | créer : `nom`, `portee`, `echeance_jours` (≤ 365) ; rend le jeton **une fois** | session humaine |
| `DELETE /moi/jetons/{id}` | révoquer | session humaine |

Ces routes vivent du côté des comptes (`routeur_comptes`), pas sous `/mcp`. Elles refusent un appelant identifié par jeton d'agent (D21.1).

### 4.5 Côté instance (rappel, hors de ce dépôt)

Le produit ne connaît ni le portail ni le proxy de l'instance. Ce qu'il exige d'elle s'énonce en deux conditions, comme RFC-019 D19.2 le faisait pour le relais :

- `/mcp` est publié **sans** le portail devant, par une règle qui ne publie **que** ce préfixe ;
- toutes les autres routes restent derrière le portail, comme aujourd'hui.

Si l'instance ne publie pas `/mcp`, rien ne change pour elle.

## 5. Ce qui change

| Document | Changement |
|---|---|
| SPECS §0 | au périmètre : l'autorat par un agent, au nom d'un compte (RFC-021) |
| SPECS §7 R7.4 | reformulée : la surface MCP existe, sur l'autorat ; la lecture de la pratique par MCP reste ultérieure |
| SPECS §12 | + R12.6 — un jeton d'agent désigne un compte, ne vaut que sur `/mcp`, n'y laisse valoir rien d'autre, ne porte jamais l'administration, ne crée jamais de jeton |
| RFC-004 §3 | la portée d'un jeton s'ajoute au rôle : un geste exige les deux (D21.4) ; le transfert reste à la main (D21.7) |
| RFC-004 §4 | le Profil gagne « Accès des agents » — la forme attend un design, comme le §4 l'exige |
| RFC-005 §5 | un appel MCP nomme son harness ; le harness courant n'est ni lu ni écrit (D21.5) |
| RFC-010 §4.3 | par MCP, l'auteur du scellement est le compte ; la trace gagne `via` (D21.8) |
| `docs/middleware.md` | la surface MCP, son extra, ses outils |
| Carnet de vigilances | + « sur un chemin sans portail, aucun en-tête d'identité ne vaut ; un jeton d'agent est plus étroit que la personne, jamais plus large » |

## 6. Non-objectifs

- **La pratique.** Lire les ha, les transcripts, les états d'un sujet ; rapporter une conversation (RFC-020) ; verser un ha aux co-auteurs ; choisir le harness courant ; appeler un kata. R7.4 reste ultérieure, et quand elle viendra elle demandera sa propre portée — R12.4 rend la décision assez lourde pour qu'on ne la prenne pas en passant.
- **L'administration**, rendue inexprimable par D21.3.
- **Le transfert de propriété** (D21.7) et la suppression (non construite).
- **Le banc.** Il n'a pas encore de surface HTTP et il appelle des moteurs : le confier à un agent avant d'avoir des quotas serait ouvrir une dépense sans plafond (RFC-006 §6).
- **L'OAuth**, différé mais déjà décidé (D21.1).
- Un transport `stdio` local : un agent sur la machine de l'instance passe par `/mcp` comme les autres.
- Des quotas ou un débit plafonné par jeton : même dette que les créations par compte (RFC-006 §6), payée quand il y aura quelqu'un à plafonner.

## 7. Critère « juste assez » — avec sabotages

**Nominal** : une personne crée depuis son Profil un jeton `conception` et le confie à son agent. L'agent liste ses harness, en sème un neuf, le lit, propose un kata, le fait éprouver jusqu'à ce qu'il tienne, voit sa coupe, puis le scelle. Le journal des scellements dit « par <la personne>, via <le nom du jeton> » ; le commit existe ; les coupes sont forgées ; le harness apparaît dans la page de la personne comme si elle l'avait fait elle-même. Son harness courant n'a pas bougé.

**Sabotages** — chacun doit produire un refus net :

1. **En-tête du portail forgé** : un appel à `/mcp` portant l'en-tête d'identité d'un autre compte, sans jeton → 401 ; avec le jeton d'un premier compte → c'est le premier compte qui agit, l'en-tête est ignoré (D21.2).
2. **Jeton hors de `/mcp`** : le même jeton sur `/conception`, `/qg`, `/v1/chat/completions` → refusé (D21.2).
3. **Jeton révoqué, expiré, inconnu** → 401, et le même message pour les trois (D21.1, D21.2).
4. **Administration** : un jeton du compte administrateur appelle tout geste d'administration, ou tente d'atteindre `/admin/*` → refusé (D21.3).
5. **Un jeton qui s'étend** : créer un jeton en présentant un jeton d'agent → refusé (D21.1).
6. **Portée** : un jeton `lecture` tente de sceller, de créer, d'archiver → refusé ; il peut éprouver (D21.4).
7. **Le rôle tient sous la portée** : un jeton `conception` d'un contributeur tente d'archiver, de gérer les membres, d'enregistrer un dépôt → refusé (RFC-004 §3).
8. **Harness d'autrui** : nommer un harness où le compte est étranger → `aucun harness à ce nom`, indiscernable d'un id qui n'existe pas (D21.5, RFC-004 §7).
9. **Harness courant** : une suite d'appels sur trois harness différents ; le harness courant du compte est inchangé, et `/v1/models` sert la même liste avant et après (D21.5).
10. **Signer pour un autre** : un `auteur` glissé dans les arguments de `proposition_sceller` est refusé comme argument inconnu ; la trace porte le nom du compte (D21.8).
11. **La pratique est absente** : aucun outil ne rend un ha, un transcript, un état de sujet ; le propriétaire d'un harness n'obtient par MCP aucun ha non versé de ses contributeurs (R12.4).
12. **Transfert** : aucun outil ne transfère (D21.7).
13. **Une seule autorité** : la surface HTTP passe ses tests sans retouche après l'extraction des gestes (D21.6).
14. **Souveraineté** : la trempe du produit ne trouve aucune destination réseau nouvelle (R12.5).

## 8. Plan d'implémentation

**Lot A — les jetons d'agent** (`kokaji/comptes/`, `identite.py`, `cli.py`, tests)
- La table `jetons_agent` aux deux régimes ; créer, lister, révoquer, résoudre une empreinte ; le dernier usage.
- `GET`/`POST`/`DELETE /moi/jetons`, réservés à une session humaine ; `kokaji jeton …`.
- Sabotages 3 et 5.

**Lot B — les gestes extraits** (`kokaji/gestes/`, `service.py`, `exploitation.py`)
- Les gestes d'autorat du §4.2 sortent des fermetures ; les routes les appellent. Aucun changement de contrat HTTP.
- Sabotage 13 : la suite de tests existante, verte sans retouche.

**Lot C — la surface MCP en lecture** (`kokaji/mcp/`, extra `mcp`, tests)
- `/mcp` monté avant l'aiguilleur ; l'identification par jeton seul, la qualité plafonnée, la portée ; la résolution du harness par argument.
- Les outils « Lire » et les ressources du §4.3.
- Sabotages 1, 2, 4, 6 (pour la lecture), 8, 9, 11, 14.

**Lot D — la surface MCP en écriture** (`kokaji/mcp/`, `conception/sceller.py`, tests)
- Les outils « Créer », « Concevoir », « Posséder » ; l'auteur du scellement tiré du compte, `via` à la trace.
- Sabotages 6, 7, 10, 12 ; le nominal de bout en bout, sur l'Atelier.

**Lot E — la page et les documents** (`vue.html`, docs)
- « Accès des agents » au Profil : la forme attend le design ; à défaut, la commande `kokaji jeton` suffit pour éprouver les lots A à D.
- SPECS, RFC-004, RFC-005, RFC-010, `docs/middleware.md`, carnet ; ce tableau.

La publication de `/mcp` sur une instance est un geste de l'instance (§4.5), hors de ce dépôt.

## 9. Tableau d'application

| Lot | État |
|---|---|
| A — les jetons d'agent | proposé |
| B — les gestes extraits | proposé |
| C — la surface MCP en lecture | proposé |
| D — la surface MCP en écriture | proposé |
| E — la page et les documents | proposé |

---
*Note d'établi : la tentation était de donner à l'agent la session de la personne, et de s'arrêter là. Ce serait lui donner tout ce qu'elle a, y compris ce qu'elle n'a jamais voulu déléguer — l'administration, la pratique, le choix de ce que le chat lui sert. Un agent agit au nom de quelqu'un ; il n'est pas quelqu'un. Son jeton est donc plus étroit que la personne, jamais plus large, et tout ce qu'il fait se signe du nom de la personne avec, à côté, le nom de l'agent.*
