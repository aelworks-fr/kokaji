# Le carnet de vigilances

Ce que le projet sait pouvoir mal tourner, et ce qu'il oppose. Une vigilance
n'est pas une tâche : c'est un piège identifié, avec ses parades, qu'on relit
avant de décider.

> **Les vigilances #1 à #7 ne sont pas dans ce dépôt.** Le carnet est ouvert ici
> avec la seule que la RFC-001 a versée. Les précédentes vivent ailleurs — à
> reporter pour que le carnet soit lisible d'un bloc.

## #8 — Goodhart sur la santé des options

*Versée par la [RFC-001](rfc-001-sante-des-options.md), août 2026.*

La mesure des options est **descriptive, jamais un objectif**. Pas de cible
chiffrée d'options, sous peine d'inflation d'options fictives — un libellé sans
substance, articulé pour gonfler le compteur.

**Parades**

- Une option n'existe que **nommée et tracée en session**. Rien ne se déclare
  hors de l'échange qui l'a fait naître.
- Le QG **lit et n'évalue pas**. Il rend des comptes, des listes et des âges ; il
  ne produit ni score ni indice composite (RFC-001 §4).
- Toute lecture normative — « ce sujet brûle ses options » — reste un **jugement
  humain devant les données**, jamais une sortie de l'outil.

**Ce qui trahirait la vigilance** : un tableau de bord qui classe les sujets par
nombre d'options, un seuil d'alerte, un objectif d'options ouvertes par nœud, ou
un kata dont la coupe demande d'« identifier au moins trois options ».

## #9 — La justesse du diagnostic sans seuil d'acceptabilité

*Versée par la [RFC-003](rfc-003-diagnostic-de-nature.md), août 2026.*

Le RFC-003 fait du diagnostic de nature une **métrique** : le banc comparera la
nature émise par le kata à la `typologie:` déclarée du kin. Une métrique sans
seuil déclaré se lit comme on veut — on constate 60 % et on décide après coup si
c'est bon, ce qui revient à n'avoir mesuré que sa propre indulgence.

Le RFC pose un seuil pour lui-même — trois cas sur quatre, dont impérativement le
piège — mais c'est le critère du RFC, pas celui d'un kata en exploitation.

**À faire quand le banc tournera (pas 4)** : définir le **seuil d'acceptabilité
par kata**, écrit dans la trempe du harness avant de mesurer, jamais après. Un
kata d'ouverture n'a pas les mêmes exigences qu'un kata tardif, qui hérite d'un
diagnostic déjà posé.

**Parades**

- Le seuil est **déclaré dans le harness**, pas dans Kokaji : c'est un jugement
  de domaine. Kokaji compare et rapporte, il ne décide pas de ce qui est bon.
- Le seuil est **écrit avant la campagne** qu'il juge. Un seuil ajusté après
  coup ne mesure plus le kata, il mesure l'envie de le déclarer bon.
- **Le piège compte à part.** Une moyenne noie le cas qui portait toute la
  question : un harness qui réussit trois kin faciles et rate l'énoncé trompeur
  n'a rien démontré.
- La justesse reste **une mesure parmi d'autres**, jamais un score de qualité du
  harness — carnet [#8](#8--goodhart-sur-la-santé-des-options), même piège.

**Ce qui trahirait la vigilance** : un taux de justesse annoncé sans le seuil qui
l'accompagne, un seuil fixé après lecture des résultats, ou une moyenne où le kin
piège pèse autant qu'un kin facile.

## #10 — Le défaut qui n'existe qu'entre deux gestes

*Versée par la pratique, août 2026 — promue depuis NOTE-0018, NOTE-0020 et
NOTE-0022 du [carnet de pratique](../PRATIQUE.md).*

Trois défauts en quatre jours ont eu la même forme : **chaque pièce était juste,
et leur rencontre ne l'était pas**. Aucun test de pièce ne pouvait les voir,
parce qu'aucun ne fait deux gestes dans l'ordre sur le même objet.

- Un champ portait le nom du harness d'exemple en plein cœur du code générique.
  Rien ne détonnait tant qu'on ne pratiquait pas sur un *autre* harness.
- Le code servait plusieurs harness ; le déploiement n'en montait qu'un. Les
  conversations partaient, la passerelle répondait, et aucun ha n'était écrit.
- Ré-abstraire et capturer se défaisaient l'un l'autre : le ha gardait la marque
  de sa lecture et perdait ce qu'elle décrivait.

Le trait commun n'est pas la complexité, c'est la **composition**. Un test de
pièce vérifie qu'un geste fait ce qu'il promet ; il ne peut pas vérifier qu'il
ne défait pas ce qu'un autre venait d'établir.

**Parades**

- **Un scénario par parcours réel**, qui suit ce qu'une personne fait dans
  l'ordre où elle le fait, et ne s'arrête qu'au bout. C'est la façon la moins
  chère de provoquer le premier usage réel d'un enchaînement.
- **Le second passage fait partie du scénario.** La plupart de ces défauts
  n'apparaissent pas au premier tour mais au suivant, quand un service de fond
  repasse sur ce qu'un geste humain vient d'écrire. Un scénario qui s'arrête
  après le premier tour ne dit rien de la durée.
- **Le sabotage nomme la frontière.** Un scénario qui ne tombe pas quand on
  retire la garde n'éprouve pas ce qu'on croit : on retire, on regarde *quelle*
  assertion tombe, et c'est elle qui dit ce qui est réellement couvert.
- **Vérifier ce qui tourne, pas ce qu'on a écrit.** Deux de ces trois défauts
  vivaient dans le déploiement, pas dans le code. Un scénario vert et un service
  muet coexistent très bien.
- **Nommer la règle d'arbitrage** quand deux gestes touchent la même donnée :
  ici, une observation l'emporte sur une lecture, et la capture ne possède que
  ce qu'elle produit. Sans règle écrite, le dernier qui écrit gagne — et c'est
  l'ordonnanceur qui décide de la vérité.

**Ce qui trahirait la vigilance** : une suite où tous les tests construisent
leur objet et le jettent aussitôt ; un scénario qui n'appelle jamais deux fois
le même service de fond ; une correction posée sans qu'on ait fait tomber le
test qui la couvre ; un geste ajouté sans qu'on ait dit ce qu'il advient quand
un autre repasse derrière.


## #11 — Confondre la source d'un kata et son contrat

Un kata importé (RFC-011) a un prompt qui est un **texte**, pas un densho. La
tentation est de le tenir pour un citoyen de seconde zone : « un texte servi
tel quel ne tient pas de contrat ». C'est une confusion. Le contrat f♯ (RFC-002)
décrit la **structure de l'état** que le kata produit et hérite — ce qu'un ha
laisse derrière lui —, et cela ne dépend en rien de la forme du prompt qui l'a
produit. `carto-be`, harness exogène, déclarait six contrats complets pendant
que la page refusait de les éditer.

**Ce qu'on oppose** : la source (texte ou densho) et le contrat (le f♯) sont
deux axes séparés, deux gestes séparés. « Remplacer par un densho » change la
source ; « Contrats f♯ » édite le contrat ; l'un n'attend pas l'autre (RFC-015).

**Ce qui trahirait la vigilance** : une facette qui déclare un kata « sans
contrat » parce que sa source est un texte, et non parce qu'il ne produit rien ;
un nœud du QG éteint pour un kata importé qui déclare pourtant un `produit`.
