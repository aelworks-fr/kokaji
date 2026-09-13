# RFC-005 — Le harness courant et la surface des modèles

> **Statut : proposé** (établi, août 2026).
> ⚠️ **Ce RFC entame un non-objectif scellé** : « hébergement pour des tiers » (SPECS §0). L'entame est partielle et nommée — servir **plusieurs harness à plusieurs personnes sur un même Dojo** entre au périmètre ; les quotas, la facturation, les harness publics ou découvrables restent dehors. Entraîne une mise à jour de SPECS §0 (non-objectifs) et §3 (la passerelle), et un amendement au RFC-004 §6.

---

## 1. Motivation

Kokaji sait forger des harness ; il ne sait en servir qu'**un**. Le service, la veille et la passerelle sont liés à un dossier unique au démarrage, et le chat présente à tout le monde la même liste de modèles. Tant que c'est vrai, ajouter un harness est un geste d'administrateur système, pas un geste de produit.

Ce RFC pose ce qui manque pour qu'une personne **choisisse** le harness qu'elle pratique, et pour que le chat lui présente **exactement les kata de ce harness** — ni plus, ni moins.

## 2. Le harness courant

**Définition.** Le harness courant d'une personne est l'ensemble des kata qui lui sont offerts à la pratique. C'est une propriété de la *personne*, pas de la session ni du déploiement.

### 2.1 Deux désignations, deux statuts

Un harness porte déjà un `id` et un `nom`. Ils cessent d'être interchangeables :

- **`id`** — immuable. Il est écrit dans le nom du modèle virtuel `<harness>/<kata>`, donc dans `identite.harness` de chaque ligne du journal, donc dans chaque ha du corpus. Le renommer orphelinerait tout l'historique observé. Il n'est jamais montré.
- **`nom`** — libre, fixé par le propriétaire du harness, modifiable à tout moment. C'est le seul libellé que voient le QG et le chat.

Cette séparation est le prix de l'observabilité : un identifiant qui sert de clé d'archive ne peut pas servir d'étiquette.

### 2.2 Où vit le choix

Dans le magasin des comptes, une préférence par utilisateur. Le magasin sait déjà répondre à « quels harness sont les miens » (`Comptes.harness_de`), et l'ACL est déjà indexée par `harness_id` : rien du modèle de droits ne change.

**Invariant.** Le harness courant est toujours un harness où la personne a un rôle. Choisir un harness sur lequel on est `etranger` est refusé, pas ignoré. Une préférence devenue caduque — harness supprimé, rôle retiré — se lit comme absente.

**Défaut.** Sans préférence posée, le harness courant est le seul harness accessible s'il n'y en a qu'un, et rien sinon. Un déploiement mono-harness continue donc de fonctionner sans que personne n'ait à choisir.

## 3. La surface des modèles

### 3.1 Pourquoi elle ne peut pas rester où elle est

Deux constats, tenus par le code en service :

1. `dojo/litellm/config.yaml` énumère les modèles virtuels **à la main**. C'est NOTE-0002 : la forge produisait la coupe du découpage instrumenté, cette liste ne la servait pas, et rien ne l'a signalé. Une liste tenue à la main décroche ; à N harness, elle décroche en permanence.
2. Le chat parle à la passerelle avec **une seule clé pour tout le monde** (`compose.yaml`, `OPENAI_API_KEY: ${DOJO_CLE_CHAT}`). La liste des modèles est filtrée par la clé appelante : une clé partagée ne peut produire qu'une liste partagée.

### 3.2 Kokaji sert la surface

**Décision.** Le chat ne pointe plus sur la passerelle, mais sur Kokaji. Kokaji expose une façade compatible OpenAI :

- **`GET /v1/models`** — la liste est *calculée* depuis la définition du harness courant de l'appelant : un modèle par kata, `id` = `<harness_id>/<kata_id>`, libellé = le `nom` du kata. Elle n'est écrite nulle part, donc elle ne peut pas décrocher de la forge.
- **`POST /v1/chat/completions`** — relayé à la passerelle, qui garde l'injection de coupe et le journal inchangés.

Open WebUI le permet nativement : il demande la liste **par utilisateur** (`routers/openai.py`, cache indexé sur `user.id`) et transmet l'identité de l'appelant sur cette requête comme sur les complétions.

### 3.3 L'identité transmise doit être signée

Open WebUI sait envoyer l'identité de deux façons : des en-têtes `X-OpenWebUI-User-*` en clair, ou **un JWT HS256 signé** dès qu'un secret partagé est posé. Les en-têtes nus sont déclaratifs : qui atteint le point d'entrée se dit qui il veut. La façade **exige la forme signée** et refuse une requête non signée — un service qui prétend à la conformité ne peut pas croire son appelant sur parole.

### 3.4 Le relais refuse ce qui sort du harness courant

Un appel à un kata qui n'appartient pas au harness courant de l'appelant est refusé. La liste est déjà filtrée ; ce refus vaut pour ce que la liste n'a pas produit — un nom de modèle forgé à la main, un fil rouvert après un changement de harness. Sans lui, le filtrage est un confort d'affichage ; avec lui, c'est une frontière.

### 3.5 Une seule autorité sur la liste

Open WebUI a son propre contrôle d'accès par modèle et par groupe. Il s'applique **après** le nôtre et doit rester passant. Deux autorités qui filtrent la même liste sans se connaître, c'est exactement le motif de NOTE-0002 — et cette fois il serait invisible, puisque le résultat serait une liste plus courte, jamais une erreur.

## 4. L'aiguillage de la capture est déjà acquis

Rien à décider ici, et c'est à consigner : le harness voyage déjà avec la conversation, de bout en bout. Le hook d'injection lit `<harness>/<kata>` dans le nom du modèle et pose `harness` dans les métadonnées ; le journal le recopie dans `identite` sur chaque ligne ; le middleware ne retient que les lignes de son harness ; le corpus range le ha en le lisant. **Un journal partagé est déjà multi-harness.**

Deux conséquences :

- Les données sont isolées par construction — chaque corpus vit dans le dossier de son harness.
- Ce qui manque n'est pas l'aiguillage mais le **nombre de veilles** : `compose.yaml` déclare un conteneur par (harness × corpus), écrit à la main. La veille doit itérer sur les harness au lieu d'être instanciée par harness.

## 5. Impacts

- **Service** — le harness cesse d'être un objet capturé au démarrage : il devient un ensemble chargé depuis un dossier de harness, résolu par requête depuis la préférence de l'appelant. Compatibilité gardée : si le dossier fourni est lui-même un harness, le service reste mono-harness.
- **Veille** — itère sur les harness ; un processus, N harness, leurs corpus respectifs.
- **QG** — `/qg/profil` renvoie déjà une liste de harness bâtie avec un seul élément ; elle se remplit depuis `harness_de()`. Un sélecteur, et une route pour changer de harness courant. **L'URL ne change pas** : le harness courant est un état du compte, pas un segment d'adresse.
- **Dojo** — le montage passe du dossier d'un harness au dossier des harness ; Open WebUI pointe sur Kokaji ; un secret partagé pour le JWT d'identité.
- **RFC-004 §6, amendé** — il prévoyait des clés LiteLLM « par utilisateur et usage » (`chat-nicolas`) comme mécanisme d'attribution du praticien. L'identité signée transmise par le chat rend ce mécanisme inutile pour le chat : le praticien vient de l'identité, pas de la clé. Les clés par usage (`chat-public`, `banc`) restent — elles disent *quel appelant*, ce qui range le ha dans le bon corpus, et cela reste vrai.

## 6. Non-objectifs de ce RFC

Quotas et facturation ; harness publics ou découvrables ; catalogue ou installation de harness par un tiers ; un harness courant par fil de conversation (la préférence est par personne) ; organisations et équipes ; édition concurrente. Le harness courant ne change rien à la visibilité des ha : le RFC-004 §5 continue de régir qui lit quoi.

## 7. Critère « juste assez » (avec sabotages)

1. **Nominal** — deux harness enregistrés, une personne membre des deux. Elle choisit le premier au QG : le chat n'offre que les kata du premier, libellés par leur `nom`. Elle bascule : la liste suit. Elle pratique une session : le ha atterrit dans le corpus du harness choisi, et `identite.harness` le confirme.
2. **Le nom** — le propriétaire renomme son harness. Le QG et le chat affichent le nouveau nom ; le journal et les ha déjà capturés continuent de porter l'`id`, et restent rattachés.
3. **Sabotages** — chacun doit produire un refus net :
   - choisir comme harness courant un harness où l'on est `etranger` → refusé ;
   - appeler `<autre_harness>/<kata>` en complétion, hors de son harness courant → refusé (§3.4) ;
   - appeler la façade **sans identité signée**, ou avec un JWT mal signé → refusé (§3.3) ;
   - deux personnes de harness différents demandent la liste au même instant : chacune reçoit la sienne — *ce sabotage est le plus important, c'est celui qui prouve que la surface est bien par personne et non par déploiement.*
4. **Invariant de non-décrochage** — forger un kata nouveau le rend offert au chat sans qu'aucune liste ait été éditée. C'est NOTE-0002 réglée par construction, et c'est vérifiable : ajouter un kata, ne toucher à aucune configuration, le voir apparaître.
