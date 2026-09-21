# RFC-018 — L'agent qui raisonne : la passerelle depuis le bac à sable

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : RFC-016 (le kata d'action, la coupe-outil D16.2, le budget D16.4), RFC-017 (l'isolement d'exécution — le mur, la boîte aux lettres, le verrou par kata, la capacité réseau D17.4), RFC-009 (séparation produit/instance, souveraineté), RFC-014 (le journal en base). Objet : décider comment un agent CLI qui **raisonne** — qui appelle un modèle — le fait depuis le bac à sable, sans ouvrir Internet, sans que le produit connaisse ni l'agent ni la clé. C'est le trou réseau étroit que la RFC-017 nommait sans le percer.

---

## 1. Motivation

La RFC-017 a prouvé l'exécution avec une **sonde déterministe** : un agent qui n'appelle aucun modèle, dans un bac au réseau coupé. C'était le bon premier pas — le plus sûr. Mais un kata d'action, en général, **raisonne** : il perçoit, décide, agit, révise. Pour cela il appelle un modèle, et appeler un modèle demande le réseau. Or le bac a le réseau coupé (RFC-017 D17.4), et la souveraineté (RFC-009) interdit toute émission qu'on ne puisse nommer.

La réponse était déjà écrite en creux : la RFC-017 D17.4 dit qu'un kata qui a besoin du réseau le déclare comme une **capacité**, et que l'instance ouvre **exactement** ce qu'elle accorde. Cette RFC pose ce que « exactement » veut dire pour le seul réseau qu'un agent de Kokaji a le droit de vouloir : **la passerelle de l'instance**, jamais Internet.

## 2. Décisions scellées

### D18.1 — L'agent n'atteint que la passerelle, jamais Internet

Un agent qui raisonne appelle un modèle **par la passerelle litellm de l'instance**, et rien d'autre. La capacité `reseau_passerelle`, accordée par l'instance (RFC-017 D17.3), attache le bac à un réseau interne d'où **seule la passerelle** est joignable — pas de sortie vers le large. Un agent qui tente une autre adresse est **bloqué par le mur** (RFC-017 D17.4), pas seulement grondé. C'est la souveraineté portée au raisonnement : le seul trafic sortant reste celui que le Dojo a toujours eu, la passerelle vers les moteurs (SPECS §3).

### D18.2 — La coupe pilote l'agent comme le prompt pilote le chat

La coupe-outil (RFC-016 D16.2) est le prompt système de l'agent : elle le pilote comme la coupe conversationnelle pilote le moteur du chat. L'agent CLI reste **interchangeable** — le manifeste déclare des capacités, jamais un produit ; l'instance mappe `reseau_passerelle` et le modèle de raisonnement sur son agent. Le produit ne connaît ni le nom de l'agent, ni la clé, ni le modèle : il passe la coupe-outil et le dossier de travail (RFC-017 D17.1), et lit le résultat.

### D18.3 — La clé est celle de l'instance, l'agent ne voit aucun secret externe

L'agent s'authentifie à la passerelle avec une **clé d'instance à portée réduite** — comme le banc a la sienne (`DOJO_CLE_BANC`) —, accordée avec la capacité. Il n'a **jamais** de clé de moteur externe : c'est la passerelle qui détient les clés des fournisseurs (SPECS §3, RFC-009). Un agent qui fuit sa clé ne fuit qu'un jeton d'instance révocable, jamais l'`ANTHROPIC_API_KEY` du Dojo.

### D18.4 — Le modèle de raisonnement est accordé, pas choisi par l'agent

Le manifeste peut requérir une capacité de raisonnement (ex. `raisonnement`) ; l'instance la mappe sur **un modèle précis** de sa passerelle, jamais un modèle libre. Un agent qui demande un autre modèle que celui accordé est refusé par la portée de sa clé (la passerelle ne lui sert que ce qu'elle autorise). Quel moteur incarne le raisonnement est, comme pour un kata (RFC-003 §3.2, R3.2), une décision de **déploiement**, dans `dojo/litellm/moteurs.yaml` — jamais de définition.

### D18.5 — Le raisonnement est journalisé comme tout appel

Les appels du modèle passent par la passerelle : ils entrent donc au **journal en base** (RFC-014 D14.4) comme n'importe quel appel, avec leur identité de ha. L'observabilité de l'agent s'appuie sur ce que la passerelle journalise déjà (RFC-016 D16.2) ; un runner dédié ne naîtra que si cette trace ne suffit pas. Le raisonnement d'un agent n'est pas une boîte noire : il laisse la même trace que le chat.

### D18.6 — Les trois interdits tiennent, le budget aussi

Rien de la RFC-016 ni de la RFC-017 ne fléchit parce que l'agent raisonne : il n'écrit que le dossier de travail (le mur), le vérificateur échantillonne le monde de l'extérieur (interdit n°2), l'écart non résolu remonte (interdit n°3), et un cycle qui ne converge pas épuise son budget et sort en urgence (RFC-016 D16.4, RFC-003 A16.3). Un agent qui raisonne coûte : le budget d'un cycle peut se dire en **enveloppe de coût** autant qu'en passages, et la passerelle mesure ce coût.

## 3. La surface

- Manifeste : un kata d'action peut requérir `reseau_passerelle` et `raisonnement` parmi ses `capacites` (RFC-016 D16.2). Le produit les transporte, ne les interprète pas.
- Instance : un réseau interne restreint qui n'expose que la passerelle ; une clé d'instance à portée réduite ; le mappage de `raisonnement` sur un modèle de `moteurs.yaml` ; l'image de l'agent, avec l'agent CLI installé, comme extension du bac à sable.
- Produit : rien de neuf. `ExecuteurBoite` (RFC-017) dépose la coupe-outil ; le surveillant du bac câble l'agent réel à la place de l'agent déterministe. La capacité `reseau_passerelle` non accordée fait refuser le run (RFC-017 D17.3).

## 4. Ce qui change

| Document | Changement |
|---|---|
| RFC-017 D17.4 | l'unique réseau accordable à un agent est la passerelle (D18.1) — jamais Internet |
| SPECS §3 (dojo) | le bac à sable peut joindre la passerelle par un réseau interne restreint, avec une clé d'instance |
| dojo (instance) | le réseau interne agent↔passerelle, la clé réduite, le mappage `raisonnement`, l'image de l'agent |
| Carnet de vigilances | + « un agent qui raisonne n'appelle que la passerelle ; une clé d'instance, jamais celle d'un fournisseur ; et son raisonnement se journalise comme le chat » |

## 5. Non-objectifs

- Ouvrir Internet au bac, ou une API externe en direct : jamais (D18.1, souveraineté).
- Choisir ou empaqueter un agent CLI précis : il reste interchangeable, mappé par l'instance.
- Un agent qui écrit le monde hors du dossier de travail, ou qui contourne le vérificateur : le mur et l'interdit n°2 tiennent (RFC-017).
- Le multi-agent, l'orchestration distribuée (RFC-016 §6).
- Faire tourner l'agent **ailleurs** que dans le bac à sable (RFC-017 D17.2 : jamais l'hôte).

## 6. Critère « juste assez » — avec sabotages

**Nominal** : un kata d'action `correction` incarné par un agent réel, dans le bac, qui appelle la passerelle pour raisonner, produit un patch dans le dossier de travail, dont le vérificateur constate qu'il fait passer la suite ; le cycle `tests → correction → tests` converge sous son budget, et chaque appel du modèle est au journal en base.

**Sabotages** :

1. **Sortie Internet** : l'agent tente une adresse hors passerelle → bloqué par le mur (D18.1) ; rien ne sort.
2. **Modèle non accordé** : l'agent demande un autre modèle → refusé par la portée de sa clé (D18.4).
3. **Fuite de clé** : la clé de l'agent est un jeton d'instance révocable, jamais une clé de fournisseur (D18.3) — on la révoque, le Dojo n'est pas exposé.
4. **Boucle qui coûte** : un agent qui ne converge pas épuise l'enveloppe de coût du cycle → sortie d'urgence (D18.6, RFC-016 D16.4).
5. **Raisonnement muet** : un agent dont aucun appel n'apparaît au journal → anomalie d'observabilité ; le raisonnement se trace comme le chat (D18.5).
6. **Sur-promesse** : l'agent conclut « corrigé » alors que la suite échoue encore → le vérificateur le dément (RFC-017 D17.5), le carré porte `action-sur-promesse` (RFC-002 α).

## 7. Plan d'implémentation

À jouer après la RFC-017 (le mur, la boîte, le verrou, la sonde déterministe — faits) et **avant** tout usage réel d'un agent qui raisonne.

**Lot A — le réseau et la clé (instance)** : un réseau interne restreint agent↔passerelle ; une clé d'instance à portée réduite (un modèle, un budget) ; le mappage `reseau_passerelle` et `raisonnement`. Sabotages 1, 2, 3.

**Lot B — l'agent réel (instance)** : l'image du bac étendue avec l'agent CLI ; le surveillant câble l'agent à la place du déterministe, piloté par la coupe-outil, la clé injectée. Le résultat capturé comme pour la sonde (actions, artefacts, verdict du vérificateur).

**Lot C — la bascule gardée** : sur un kata d'essai `correction` (verrou par kata, RFC-017), le cycle complet joué de bout en bout ; les six sabotages vus tomber ; puis, seulement, l'ouverture à un vrai kata.

## 8. Tableau d'application

| Lot | État |
|---|---|
| A — le réseau et la clé (instance) | à faire |
| B — l'agent réel (instance) | à faire |
| C — la bascule gardée | à faire |

---
*Note d'établi : la sonde déterministe a prouvé le mur sans risque ; celle-ci ouvre la seule porte que le mur doit avoir, et pas un pouce de plus. Un agent qui raisonne reste, du point de vue du Dojo, un client de la passerelle comme le chat — même clé d'instance, même journal, même souveraineté. On ne lui donne pas le monde : on lui donne un modèle, un dossier de travail, et un vérificateur qui le regarde.*
