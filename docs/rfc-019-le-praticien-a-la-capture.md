# RFC-019 — Le praticien à la capture : une conversation du chat naît attribuée

> **Statut : proposé** (établi, 30 septembre 2026).
> Dépend de : RFC-004 (le praticien, la visibilité — R12.4), RFC-005 (le chat parle à Kokaji, qui relaie ; l'identité signée §3.3), RFC-014 (le journal en base). Objet : décider d'où vient le praticien d'un ha capturé depuis le chat, et par quel chemin il y arrive — pour qu'une conversation vécue ne naisse plus orpheline.

---

## 1. Motivation

Un ha sans praticien est **orphelin de porte** (RFC-004 §5) : personne ne peut le lire, pas même le propriétaire du harness. C'est voulu — posséder le harness ne donne pas la pratique d'autrui. Mais sur la première instance, **toute** conversation capturée depuis le chat naît orpheline : 154 sur 154 sur carto-be au 23 septembre 2026, et la première conversation née propre le 30 septembre (CAS-0155) l'est encore. Le QG les cache, la liste des conversations les cache, et l'écart depuis la page leur est fermé. Il a fallu les rattacher à la main, une par une, à un compte.

Trois maillons manquent, et aucun n'est une décision de conception : ce sont des trous.

1. **Le chat annonce la personne, dans un jeton signé.** Open WebUI envoie `X-OpenWebUI-User-Jwt` (HS256, secret partagé `KOKAJI_CHAT_SECRET`), que le service vérifie déjà pour servir `/v1/models` à la bonne personne (RFC-005 §3.3). Il n'envoie **pas** l'email en clair.
2. **Le relais jette tout.** `POST /v1/chat/completions` (kokaji:8100) reconstruit ses en-têtes de zéro avant d'appeler la passerelle : seule la clé de la passerelle passe. Le hook de la passerelle, qui sait poser `praticien_email` et `fil` au journal depuis les en-têtes, ne voit donc jamais rien.
3. **La capture attribue par la clé appelante**, via un mapping clé → compte que rien n'alimente — et qui ne pourrait pas marcher : une clé publique sert tout le monde.

Ce trou a été bouché une première fois le 23 septembre, éprouvé en direct, puis **remonté** avec un chantier voisin qui, lui, partait de travers (la ré-abstraction en continu). Cette RFC reprend le seul morceau qui était juste, et le scelle.

## 2. Décisions scellées

### D19.1 — Le praticien, c'est la personne que le chat a annoncée, signée

Le praticien d'un ha capturé depuis le chat est la personne dont l'identité voyage dans le **jeton signé** du chat. Aucun en-tête en clair ne vaut : ni `x-openwebui-user-email`, ni un `Remote-*` — une identité qu'on lit sans vérifier est déclarative, et quiconque atteint le point d'entrée peut l'écrire. Le relais ne fait confiance qu'à ce qu'Open WebUI a signé avec le secret partagé, et qu'il vérifie lui-même (`verifier_jeton`).

### D19.2 — Le relais transporte l'identité vérifiée, et rien du client

Le relais du chat tire l'email vérifié du jeton et le passe à la passerelle sous le nom que son hook attend (`x-openwebui-user-email`), avec le fil de conversation (`x-openwebui-chat-id`) tel qu'Open WebUI l'annonce. **Jamais** l'`Authorization` du client, ses cookies, ni le jeton lui-même : la passerelle n'a pas à les connaître. Un jeton absent ou invalide n'échoue pas le relais — l'attribution est un mieux, pas une porte : le ha naît alors orphelin, comme aujourd'hui.

C'est sûr dans la topologie de l'instance, et la RFC en fait une condition : kokaji:8100 n'est joignable que par Open WebUI sur le réseau interne (Traefik pointe sur Open WebUI:8080), et Open WebUI pose le jeton depuis la session authentifiée. Si l'une des deux conditions tombe, le relais reste sûr — il ne croit que la signature.

### D19.3 — Le journal garde l'email, la capture le résout en compte

Le journal enregistre ce que le chat a annoncé — l'email — et non un identifiant de compte. C'est la vérité observable, réutilisable : un compte peut naître **après** la conversation. La capture (`verser`) résout l'email en compte par le magasin de comptes, et pose ce compte comme praticien. Un email inconnu ne fabrique **aucun** compte (même règle que l'invitation, RFC-004) et laisse le ha orphelin. Le mapping par clé appelante subsiste en dernier recours, pour un Dojo qui ne sert qu'une personne.

### D19.4 — Le rafraîchissement attribue après coup, jamais ne désattribue

`praticien` est un champ « si connu » de la fiche (NOTE-0021) : un passage de la veille qui sait nommer le praticien le pose ; un passage qui ne le sait pas ne l'efface pas. Deux conséquences voulues : un ha né orphelin dont le journal porte l'email est attribué **dès que le compte existe**, au passage suivant ; et un ha rattaché à la main reste rattaché. Les ha d'avant cette RFC, dont le journal ne porte aucun email, restent orphelins — on ne devine pas un praticien.

### D19.5 — La veille détient le magasin de comptes, et survit sans lui

La veille reçoit le magasin de comptes (`--comptes`, le même que le service) pour résoudre l'email. Sans magasin, elle capture sans praticien — comme aujourd'hui — et le dit. Un magasin tombé ne fait pas tomber la veille (NOTE-0009) : la capture est le service, l'attribution un mieux.

## 3. La surface

- `kokaji/middleware/chat.py` : le relais reçoit le secret du chat ; sur `/v1/chat/completions`, il vérifie le jeton, en tire l'email, et passe `x-openwebui-user-email` et `x-openwebui-chat-id` à la passerelle.
- `kokaji/corpus/__init__.py` : `verser` accepte un résolveur email → compte ; le praticien vient de `praticien_email` résolu, sinon du mapping par clé.
- `kokaji/middleware/__init__.py`, `kokaji/cli.py` : la veille transporte le résolveur ; `kokaji middleware --comptes`.
- `dojo/compose.yaml` : `--comptes /comptes` sur la veille principale.
- Le hook de la passerelle ne change pas : il pose déjà `praticien_email` et `fil` depuis ces en-têtes.

## 4. Ce qui change

| Document | Changement |
|---|---|
| RFC-004 §5 | le praticien d'un ha du chat vient de l'identité signée du chat, résolue en compte à la capture (D19.1, D19.3) |
| RFC-005 §3.3 | le relais transporte l'identité vérifiée vers la passerelle, jamais les secrets du client (D19.2) |
| dojo (instance) | la veille reçoit `--comptes` ; la topologie (kokaji:8100 interne) est une condition nommée |
| Carnet de vigilances | + « une identité se lit signée, jamais en clair ; le journal garde l'email, la capture le résout ; un email inconnu ne crée aucun compte » |

## 5. Non-objectifs

- Attribuer rétroactivement les ha dont le journal ne porte aucun email : on ne devine pas un praticien (D19.4). Le rattachement à la main reste un geste possible, distinct.
- Ouvrir les ha orphelins au propriétaire du harness : ce serait défaire R12.4.
- La ré-abstraction en continu, ou toute forme d'état posé sans observation : hors sujet, et remontée à dessein.
- Changer la clé de regroupement des fils (`racine`) : `fil` est transporté pour le lien « reprendre », pas pour regrouper.

## 6. Critère « juste assez » — avec sabotages

**Nominal** : une personne connectée envoie un message dans le chat ; l'appel entre au journal avec son email et son fil ; au passage suivant, le ha naît avec son compte pour praticien ; elle le voit dans sa liste des conversations, peut l'ouvrir et l'écarter. Personne d'autre ne le voit.

**Sabotages** :

1. **En-tête en clair forgé** : une requête vers le relais avec `x-openwebui-user-email: autre@…` et sans jeton, ou avec un jeton invalide → aucune identité transmise ; le ha naît orphelin (D19.1, D19.2).
2. **Secrets du client** : le relais n'envoie jamais à la passerelle l'`Authorization` du client ni son jeton (D19.2).
3. **Email inconnu du magasin** : aucun compte créé, ha orphelin (D19.3).
4. **Compte créé après coup** : le ha orphelin est attribué au passage suivant de la veille (D19.4).
5. **Rattachement à la main** : un praticien posé à la main survit aux passages (D19.4).
6. **Magasin absent ou tombé** : la veille capture sans praticien et le dit ; elle ne s'arrête pas (D19.5).
7. **Propriétaire du harness** : il ne voit toujours pas le ha non versé d'autrui (RFC-004 inchangée).

## 7. Plan d'implémentation

Un seul lot, parce que les trois maillons ne valent qu'ensemble — et parce que le code existe, éprouvé le 23 septembre puis remonté avec un chantier voisin : branche `garde/attribution-relecture-2026-09-23`, commits b081e4a (relais + capture + veille) et c5cc343 (l'email tiré du jeton). On en reprend **ces deux-là**, en durcissant D19.1 : le relais ne lit plus l'en-tête en clair, seulement le jeton. Rien de 570cf94 (la ré-abstraction en continu).

- Produit : relais, capture, veille, tests des sept sabotages.
- Instance : `--comptes` sur la veille ; preuve en direct sur un message du chat.
- Documents : RFC-004, RFC-005, carnet ; ce tableau.

## 8. Tableau d'application

| Lot | État |
|---|---|
| unique — le praticien à la capture | appliqué (30 septembre 2026) — commits b081e4a et c5cc343 repris de la branche de garde, durcis : le relais ne lit plus que le jeton signé (D19.1), et n'y ajoute rien de 570cf94 ; `verser(praticien_par_email=…)`, `kokaji middleware --comptes`, `--comptes /comptes` sur la veille de l'instance ; les sept sabotages couverts par les tests (en-tête en clair forgé ignoré, jeton et Authorization du client non repassés, email inconnu → orphelin, compte créé après coup → attribué au passage suivant, praticien posé survit, magasin absent → capture sans praticien, propriétaire ≠ praticien → invisible) ; RFC-004 §5, RFC-005 §3.3 et carnet #12 amendés |

---
*Note d'établi : le 23 septembre, ce trou a été bouché en une matinée et prouvé sur quatre conversations — puis remonté le soir même, non parce que c'était faux, mais parce que c'était emballé avec ce qui l'était. Le geste juste ne coûte rien à refaire ; ce qu'il fallait, c'était le nommer seul.*
