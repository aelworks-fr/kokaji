# RFC-017 — L'isolement d'exécution : où un agent touche le monde en sûreté

> **Statut : proposé** (établi, septembre 2026).
> Dépend de : RFC-016 (le kata d'action — le triplet, les capacités D16.2, les vérificateurs D16.6, l'exécuteur inerte D16.3, le budget D16.4), RFC-009 (séparation produit/instance, souveraineté — aucune émission réseau nouvelle côté produit), RFC-014 (les données vivantes, la capture sous régime base). Objet : décider **où** et **comment** un agent CLI incarne une coupe-outil et touche le monde, pour que l'exécuteur cesse d'être inerte sans mettre la machine en danger. La RFC-016 §6 renvoyait ce choix ici, explicitement.

---

## 1. Motivation

La RFC-016 a tout posé pour agir : un kata déclare ses effets, ses capacités, ses vérificateurs ; la forge en fait une coupe-outil ; le dojo route mécaniquement ; le budget borne les boucles. Une seule chose reste inerte, par décision : **l'exécution**. L'exécuteur par défaut n'exécute rien (D16.3), parce qu'exécuter un agent qui écrit le monde n'est pas un geste anodin — et que la première instance **est** une machine partagée : ce VPS fait tourner la production de Kokaji, mais aussi d'autres piles. Y lâcher un agent doté d'`execution_shell` sans mur, c'est lui donner les clés de tout.

La RFC-016 §6 a tranché la répartition : le produit norme le manifeste et la capture ; **l'isolement d'exécution n'est pas son affaire**, c'est celle de l'instance, et il méritait sa propre RFC. La voici. Elle ne fait rien exécuter : elle décide le mur derrière lequel, un jour, on le fera.

Le principe directeur vient de la souveraineté (RFC-009) et des trois interdits (RFC-016 §2) : **une capacité se donne, elle ne se prend pas** ; **le monde s'échantillonne de l'extérieur de l'agent** ; **rien ne s'absorbe en silence**.

## 2. Décisions scellées

### D17.1 — Le produit invoque une commande, jamais un agent en dur

L'exécuteur du produit (la façade `kokaji/execution.py`) reçoit une coupe-outil et des entrées, et invoque une **commande configurée par l'instance** — un point d'entrée que l'instance mappe sur son agent, dans son mur. Le produit ne connaît ni le nom de l'agent, ni le mur : il passe la coupe-outil, un dossier de travail, et il lit ce qui en revient. Un agent interchangeable (RFC-016 D16.2) l'exige, et la souveraineté aussi : le produit n'ouvre aucun canal qu'il ne pourrait pas expliquer.

Tant qu'aucune commande n'est configurée, l'exécuteur **reste inerte** (D16.3) — le régime d'aujourd'hui. Câbler un agent est un geste d'instance, jamais un défaut du produit.

### D17.2 — Sur cette instance, le mur est un conteneur dédié — jamais l'hôte

La première instance exécute dans un **conteneur bac à sable du dojo**, à côté des autres services, et **jamais sur l'hôte directement**. Ce conteneur :

- est **plafonné** (CPU, mémoire) et en `on-failure` borné, comme tout le dojo (leçon de la boucle de restart) ;
- n'a **aucun accès à l'hôte** au-delà d'un **dossier de travail jetable**, créé par run et détruit après — la seule surface où l'agent écrit ;
- a le **réseau fermé** par défaut (D17.4) ;
- ne monte ni le dépôt des harness, ni le journal, ni les comptes, ni le dossier des dépôts nus : un agent qui agit ne voit pas la matière vivante de l'instance.

Le produit ne crée pas ce conteneur et n'en connaît pas la forme : il invoque la commande (D17.1) que l'instance a câblée pour y entrer. La RFC-016 §6 tient — le produit norme, l'instance isole.

### D17.3 — Une capacité se donne, elle ne s'assume pas

Un kata déclare les capacités qu'il **requiert** (RFC-016 D16.2). L'instance les **accorde** une à une, en les mappant sur un moyen concret dans le mur : `execution_shell` → un shell dans le bac à sable ; une capacité d'accès à un dépôt → un montage précis en lecture seule ; etc. Une capacité **requise mais non accordée** ne dégrade pas la conduite en silence : le run **refuse de partir**, et le dit. Agir sur une capacité qu'on n'a pas reçue est impossible, pas seulement interdit.

### D17.4 — Le réseau est fermé, la souveraineté par défaut

Le bac à sable n'a **aucune sortie réseau** par défaut. Un kata qui a besoin du réseau le déclare comme une capacité, et l'instance ouvre **exactement** ce qu'elle accorde — un hôte, un port —, jamais le large. C'est la souveraineté (RFC-009) portée à l'exécution : aucune émission qu'on ne puisse nommer. Un agent qui tente une sortie non accordée est **bloqué par le mur**, pas seulement grondé par une règle.

### D17.5 — L'interdit n°2 est tenu par la construction, pas par la confiance

Le verdict qui route (RFC-016 D16.3) est écrit par l'agent lui-même : il peut sur-promettre. Le garde-fou n'est pas de le croire, c'est de **vérifier ailleurs**. Les vérificateurs (RFC-016 D16.6) lisent la `source` — un artefact du dossier de travail, le monde — **depuis l'extérieur de l'agent**, dans un pas distinct qui ne partage pas son processus. Le mur rend cette séparation réelle : l'agent produit dans le dossier de travail, le vérificateur l'y lit après, sans passer par le dire de l'agent. C'est là que la trempe devient le contrôle d'honnêteté du routage.

### D17.6 — Rien ne s'absorbe : la trace est gardée, la brèche remonte

Tout ce qu'un run produit — actions, artefacts, journal de l'agent — entre dans le ha sous le régime base (RFC-014), capturé par défaut, jugé juste assez (RFC-016 D16.6 : la trace n'est pas évaluée en v1). Et tout écart que le run ne résout pas **remonte** (interdit n°3) : une capacité non accordée, une tentative de sortie du mur, un budget de cycle épuisé (RFC-016 D16.4) **arrêtent** le run et le rendent à un checkpoint humain, avec la conduite d'urgence (RFC-003 A16.3) — état gelé, main rendue. Jamais une boucle de plus, jamais une brèche tue.

### D17.7 — La bascule est un geste gardé, validé par les sabotages

Passer de l'inerte au réel n'est pas une option de config qu'on coche : c'est une bascule que l'on **valide** d'abord, en voyant le mur **refuser** (§6). L'exécuteur inerte reste le défaut du produit ; un agent réel ne se câble sur la première instance qu'une fois le bac à sable posé, ses limites mesurées, et les sabotages de cette RFC vus tomber. La doctrine tient : rien n'est cru avant le sabotage.

### D17.8 — Le canal est une boîte aux lettres sur volume — ni socket, ni réseau

Le produit tourne dans le conteneur `kokaji` ; il atteint le bac à sable **sans
recevoir le socket Docker** (qui vaut root sur l'hôte) et **sans réseau** (le bac
garde `network_mode: none`, D17.4). Le canal est une **boîte aux lettres sur un
volume partagé** entre `kokaji` et le bac à sable, et **rien d'autre** :

- le produit dépose un **job** (la coupe-outil, les entrées, un dossier de
  travail neuf) dans la boîte ;
- le bac à sable **surveille** la boîte, prend le job, exécute l'agent sur le
  dossier de travail, y écrit un **résultat** (actions, artefacts, verdict) ;
- le produit lit le résultat, le capture dans le ha (régime base), et efface le
  job. Un résultat qui n'arrive pas dans le délai imparti est un **écart qui
  remonte** (interdit n°3) : le run sort en urgence, il ne s'oublie pas.

La seule surface commune est ce volume ; le bac à sable ne voit toujours ni
réseau, ni matière vivante, ni hôte. C'est le canal le plus étroit qu'on
puisse donner à quelque chose qui touche le monde.

## 3. La surface

- Produit : un `ExecuteurCommande` à côté de l'`ExecuteurInerte` (`kokaji/execution.py`) — il invoque la commande configurée, passe la coupe-outil et le dossier de travail, lit le résultat (actions, artefacts, verdict) et le rend tel quel. `executeur_pour` choisit l'un ou l'autre selon la configuration de l'instance ; aucune n'est câblée par défaut.
- Instance : le conteneur bac à sable au `compose.yaml` (plafonné, réseau fermé, dossier de travail jetable), et le mappage capacité → moyen. Rien de tout cela n'est au produit.
- Configuration : une variable qui nomme la commande d'exécution (vide = inerte), et le mappage des capacités accordées. Aucune émission réseau nouvelle côté produit.

## 4. Ce qui change

| Document | Changement |
|---|---|
| RFC-016 §6 | l'isolement d'exécution, renvoyé « RFC dédiée si besoin », est cette RFC |
| SPECS §3 (dojo) | le bac à sable d'exécution : conteneur plafonné, réseau fermé, dossier de travail jetable ; l'exécution n'a lieu que là |
| `kokaji/execution.py` | `ExecuteurCommande` s'ajoute à l'inerte ; `executeur_pour` lit la configuration |
| dojo (instance) | le service bac à sable, le mappage des capacités, la bascule gardée |
| Carnet de vigilances | + « un agent qui écrit le monde ne s'exécute jamais sur l'hôte partagé — un mur, un dossier jetable, un réseau fermé, et le monde vérifié de l'extérieur » |

## 5. Non-objectifs

- Faire exécuter quoi que ce soit **maintenant** : cette RFC décide le mur, elle ne le pose pas. L'exécuteur reste inerte tant que D17.7 n'a pas été jouée.
- Un durcissement multi-locataire au-delà du conteneur (namespaces fins, seccomp sur mesure) : le conteneur plafonné et le réseau fermé suffisent en v1 ; une RFC dédiée si l'usage l'exige.
- L'orchestration distribuée, les files de jobs, la reprise sur panne (RFC-016 §6 les exclut déjà).
- Exécuter sur l'hôte, jamais — c'est le seul absolu de cette RFC.
- L'évaluation de la trace (RFC-016 D16.6, différée).

## 6. Critère « juste assez » — avec sabotages

**Nominal**, une fois le bac à sable posé : un kata d'action `tests` incarné par un agent réel, dans le mur, sur un dossier de travail jetable ; il produit un artefact, le vérificateur le lit **de l'extérieur**, le verdict route la chaîne, le ha capture actions et artefacts. Puis le mur se retire, l'exécuteur redevient inerte, et rien du reste n'a changé.

**Sabotages** — la RFC n'est prouvée que lorsqu'on a vu le mur refuser :

1. **Écrire hors du dossier de travail** → bloqué par le mur, le run s'arrête et remonte (D17.2, D17.6).
2. **Une capacité requise mais non accordée** → le run **refuse de partir**, il ne dégrade pas en silence (D17.3).
3. **Une sortie réseau non accordée** → bloquée ; la souveraineté tient à l'exécution (D17.4).
4. **L'agent sur-promet** (« tous_passes » alors qu'un test a échoué) → le vérificateur, qui lit l'artefact du dossier de travail sans passer par l'agent, **le dément**, et le routage ne suit pas le faux verdict (D17.5).
5. **Un budget de cycle épuisé** → sortie d'urgence, état gelé, main rendue — jamais une boucle de plus (D17.6, RFC-016 D16.4).
6. **Aucune commande configurée** → l'exécuteur est inerte, et le dit : le défaut est sûr (D17.1, D17.7).

## 7. Plan d'implémentation

À jouer **le jour où l'on veut exécuter pour de vrai** — pas avant.

**Lot A — le mur (instance)** : le conteneur bac à sable au `compose.yaml` (plafonné, `on-failure`, réseau fermé, dossier de travail jetable, aucun montage de la matière vivante) ; le mappage capacité → moyen ; la commande d'entrée.

**Lot B — l'exécuteur commande (produit) + la boîte aux lettres (instance)** :
`ExecuteurCommande` dans `kokaji/execution.py` (dépose un job dans la boîte,
attend le résultat, capture dans le ha au régime base, sort en urgence sur
délai dépassé) ; `executeur_pour` qui le choisit sur configuration, inerte tant
qu'aucune boîte n'est déclarée ; une commande `kokaji executer <harness> <kata>`
qui déclenche un run et un pas de routage (pas d'orchestrateur autonome, §6) ;
le refus d'une capacité non accordée (D17.3) ; les vérificateurs lus de
l'extérieur (D17.5). Côté instance : le volume partagé `kokaji`↔bac à sable, le
surveillant du bac (une boucle qui prend un job, exécute, rend un résultat sur
un dossier jetable), et le mappage capacité → moyen. Le bac garde
`network_mode: none`.

**Lot C — la bascule gardée** : jouer les six sabotages sur la première instance, les voir tomber, puis câbler un agent réel sur un kata d'essai — et seulement lui. La conduite d'urgence (RFC-003), armée par le budget, vérifiée sur une boucle qui ne converge pas.

## 8. Tableau d'application

| Lot | État |
|---|---|
| A — le mur (instance) | à faire — le jour de l'exécution réelle |
| B — l'exécuteur commande (produit) | à faire |
| C — la bascule gardée | à faire |

---
*Note d'établi : la RFC-016 a appris à la forge que couper, c'est agir. Celle-ci pose la seule condition pour qu'agir ne soit pas dangereux : un mur, et le monde regardé de l'extérieur. Le produit sait déjà tout déclarer et tout valider ; il reste inerte non par incapacité, mais par prudence — parce que la première instance est la machine qui nous porte, et qu'on ne lâche pas un agent dans la pièce où l'on travaille sans avoir d'abord bâti la pièce d'à côté.*
