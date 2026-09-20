# SPECS — Kokaji
> **Forge générique de harness conversationnels.** Projet personnel, indépendant de tout employeur et de tout domaine d'application.
> Référence : dans la pièce de nô *Kokaji*, le forgeron Munechika forge une lame impériale en alternant les coups avec l'esprit d'Inari — un humain et un esprit co-forgeant ce qu'aucun n'aurait produit seul.
> Version 1.5 — 2026-08 — issue de la relecture collaborative (vocabulaire redécouvert par domain discovery), **validée intégralement en relecture à deux voix, section par section (8 arrêts)**, puis étendue par la [RFC-001 — La santé des options](docs/rfc-001-sante-des-options.md), la [RFC-002 — Le check galoisien de l'héritage](docs/rfc-002-check-galoisien.md), la [RFC-003 — Le diagnostic de nature du sujet](docs/rfc-003-diagnostic-de-nature.md), la [RFC-004 — Utilisateurs et co-autorat de harness](docs/rfc-004-utilisateurs-co-autorat.md) et la [RFC-005 — Le harness courant et la surface des modèles](docs/rfc-005-harness-courant.md). Point de vérité du projet : toute décision qui contredit ce document le met d'abord à jour.

---

## 0. Ce qu'est Kokaji — et ce qu'il n'est pas

Un **harness** est un ensemble cohérent de **kata** — des formes codifiées d'étapes décisionnelles — appliqué à un **domaine** (le processus qu'il couvre) et porté par une doctrine commune : une posture, un langage, des interdits, des relais entre kata. Kokaji est **la forge de ces harness** : il les génère depuis une source unique, les éprouve, les observe et les fait vivre — **sans jamais rien savoir de leur domaine**.

**Principe de découplage (non négociable) :** Kokaji ne connaît aucun domaine ; il ne connaît que la *structure* des harness. Aucun nom de processus, de rôle, d'organisation ou de domaine n'existe dans le code, les schémas, les tests ou les fixtures de Kokaji. Tout le spécifique vit dans la **définition du harness** (§2), chargée comme une donnée. Le repo n'embarque qu'un harness d'exemple sur un domaine fictif (§9).

**Principe d'observabilité (fondateur) :** la raison d'être de la forge est de **comprendre ce qui marche réellement au niveau du harness**. L'unité d'observation est le **ha** : une exécution « cette fois-ci » — un kata appliqué, avec le contexte et les connaissances du moment, à une matière première singulière (le **sujet**, *kin*). Toute session naît ha, avec son identité complète ; l'annotation humaine est une promotion ultérieure, jamais une condition de capture.

**Au périmètre :** le **co-autorat de harness** ([RFC-004](docs/rfc-004-utilisateurs-co-autorat.md)) — un harness a un et un seul propriétaire, et autant de contributeurs que voulu. Le RFC-004 renverse ici un non-objectif scellé, et le renversement est partiel : co-forger à plusieurs entre, ouvrir un service à des tiers reste dehors.

**Au périmètre également :** le **harness courant** ([RFC-005](docs/rfc-005-harness-courant.md)) — une personne choisit le harness qu'elle pratique, et la surface des modèles qui lui est offerte s'en déduit. Le RFC-005 entame à son tour le non-objectif « hébergement pour des tiers », et l'entame est nommée : **servir plusieurs harness à plusieurs personnes sur un même Dojo** entre au périmètre ; ce qui fait d'un service un produit vendu — quotas, facturation, catalogue de harness — reste dehors.

**Non-objectifs (v1) :** hébergement pour des tiers *au-delà de ce que le RFC-005 fait entrer* (donc : quotas, facturation, catalogue ou installation de harness par un tiers), données réelles de quelque organisation que ce soit, intégration à des outils d'entreprise, organisations et équipes, harness publics ou découvrables, partage de sujets.

## 1. Modèle conceptuel et vocabulaire

### 1.1 La chaîne des états — du figé au vivant

```
KATA (la forme, unique)          — codification d'une étape décisionnelle : ordre des
  │  forge, par cible              questions, posture, interdits, points d'étape
  ▼
COUPE (l'incarnation, ×N cibles)  — le fichier compilé, prêt à être injecté comme prompt
  │  pratique                      système (analogie : source → binaire → processus)
  ▼
SESSION (l'événement, ×N)        — la conversation vivante, enregistrée par le runtime
  │  capture par défaut
  ▼
HA / CAS (l'observation)         — kata + contexte + kin + déroulé + résultat : l'unité
                                   qui permet de comprendre ce qui marche
```

Ce que la distinction kata/coupe permet de dire : *« le kata n'a pas changé, on a reforgé ses coupes »* (packaging seul) vs *« le kata a changé, toutes ses coupes sont périmées »* — indispensable pour attribuer un écart mesuré à la **forme** ou à son **incarnation**.

### 1.2 Vocabulaire à deux registres

| Concept | Technique (code, manifest, API) | Imagerie interne (doc, culture) |
|---|---|---|
| L'ensemble cohérent | **harness** | ryū |
| Le champ d'application | **domaine** | — |
| La forme d'une étape décisionnelle | **kata** | kata |
| L'artefact compilé par cible | **coupe** (`dist/coupes/<harness>/<cible>/`) | kiri |
| L'événement conversationnel brut | **session** | keiko |
| L'unité d'observation (session + identité + kin) | **cas** (`CAS-XXXX`) | ha |
| Le sujet travaillé, matière première de la pratique | **sujet** | kin |
| La source du harness (template + configs) | **source** | tamahagane |
| La source d'un kata — les variables que le gabarit remplit | **source** (`kata/<id>.yaml`) | densho |
| Le build | **build** | la forge |
| Lint statique + banc d'évaluation | **checks / bench** | la trempe |
| La stack d'exécution | **runtime** | le dojo |

Règle : le registre technique est seul admis dans le code, les schémas et les APIs ; l'imagerie vit dans la documentation et la culture du projet. Le terme « mode guidé » (et tout équivalent hérité d'outils tiers) est banni des deux registres.

## 2. HDS — Harness Definition Standard (le cœur du découplage)

Un harness = **un dossier autonome** (repo séparé recommandé pour les harness non publics), décrit par un manifest. Kokaji ne fait qu'interpréter ce standard.

```yaml
# harness.yaml — manifest HDS v0
harness:
  id: ""                      # slug unique, choisi par l'auteur du harness
  nom: ""
  version: ""                 # versionnage propre au harness
  langue: fr
  domaine: ""                 # le processus couvert, en une phrase — documentaire, jamais interprété par Kokaji

kata:                         # les formes, dans l'ordre logique du domaine
  - id: ""                    # slug propre au harness
    nom: ""
    source: kata/<id>.yaml    # config du kata (variables du template)
    livrable: ""              # nom du document produit
    amont: []                 # ids des kata dont il hérite
    herite: []                # f♯ domaine — <kata>.<champ>, ou <kata>.<champ>: <statut minimal exigé>
    produit: []               # f♯ codomaine — <kata>.<champ>: <statut minimal garanti>
    emet_options: false       # true = ce kata élicite et suit des options (§7, R8.4)
    raccourci: echange        # RFC-016 — echange (défaut) | sonde | production | commande
    intention: ""             # RFC-016 — l'objet décisionnel de l'étape (libre)
    perception: { entrees: [], retours: [] }   # RFC-016 — retours = par où l'on constate les effets
    effets: { monde_lecture: [], monde_ecriture: [] }  # RFC-016 — le canal modele est universel (le bloc d'état)
    trempe: { verificateurs: [ { type: executable, check: "", source: "" } ] }  # RFC-016 D16.6 — juge le résultat ; exigé si le kata touche le monde
    capacites: []             # RFC-016 D16.2 — capacités requises du moteur (ex. execution_shell) ; exigé si le kata touche le monde

chaine:                       # topologie pour le QG (nœuds, jalons, arêtes)
  noeuds: [ { id: "", type: "kata | jalon | externe", nom: "" } ]
  aretes: [ { de: "", vers: "", label: "" } ]   # RFC-016 — une arête peut refermer une boucle
  cycles: [ { noeuds: [], budget: { passages: 0, cout: 0.0 } } ]  # RFC-016 — toute boucle déclarée, avec budget

template: template.md         # le template commun du harness (blocs fixes/variables)

cibles:                       # profils de forge — remplace toute cible nommée en dur
  - id: ""                    # ex. "contrainte" / "instrumentee" — au choix du harness
    etat_structure: false     # true = les coupes émettent le bloc d'état
    en_tete: ""               # en-tête injecté (ex. nom + version publique)
    packaging: "dossier | zip"

trempe:
  vocabulaire_interdit: []    # mots bannis des coupes de CE harness
  registre: registre.yaml     # noms canoniques (kata, rôles, jalons) — toute citation est vérifiée
  checks_session: []          # règles dynamiques déclaratives (voir §5), ex. :
    # - { id: propositions-min, type: regex-par-tour, ... }
    # - { id: pas-de-verdict, type: interdit, motif: "..." }  # le harness définit SES interdits

etat:                         # spécialisation du bloc d'état (§7)
  statuts_champ: [fait_etabli, hypothese, en_pause]   # défaut Kokaji, surchargeable
  statuts_hypothese: [en_cours, validee, infirmee, en_pause]

personas: personas/           # profils d'utilisateur simulé pour le banc
corpus: corpus/               # les ha capturés et promus (standard §6)
```

**Exigences :**
- R2.1 — Kokaji valide un manifest HDS et refuse tout harness incomplet (erreurs explicites).
- R2.2 — Plusieurs harness chargeables côte à côte, isolés (id préfixe tout : modèles virtuels, logs, ha, corpus).
- R2.3 — Le HDS est versionné indépendamment de Kokaji ; ce fichier en est la **v0.1**.
- R2.4 — **Le contrat d'un kata (f♯) vit sur le kata, pas sur l'arête** : le couple (`herite`, `produit`), dans le vocabulaire des champs des blocs d'état. La loi qui les relie à la pratique — *l'état final d'un ha livre au moins ce que `produit` promet* — est vérifiée par la trempe (§5) et, en continu, par le middleware (§7). Sous-promettre est permis ; sur-promettre est une non-conformité. L'ordre des statuts est celui de leur déclaration dans `etat.statuts_champ`, du plus fort au plus faible. Voir [RFC-002](docs/rfc-002-check-galoisien.md).
- R2.7 — **Une boucle se déclare avec un budget** ([RFC-016](docs/rfc-016-kata-d-action.md) D16.4). La chaîne cesse d'être linéaire : une arête peut refermer un cycle (tests → correction → tests). Toute boucle réelle du graphe des arêtes doit figurer dans `chaine.cycles` avec un `budget` (`passages` et/ou `cout`, au moins l'un) ; une boucle non déclarée, un cycle déclaré qui n'en est pas, ou un budget vide sont refusés par la validation du manifeste. Budget épuisé arme la conduite d'urgence (RFC-003 : état gelé, main rendue) — c'est l'interdit n°3, pas de surprise avalée. L'évaluation du budget à l'exécution suit avec le routage (D16.3).
- R2.6 — **Toute étape est une action ; la conversation en est un cas** ([RFC-016](docs/rfc-016-kata-d-action.md)). Un kata déclare un triplet — perception (`entrees`, `retours`), intention méta, effets par canal (`modele` universel, `monde_lecture`, `monde_ecriture`). Absent, il vaut l'`echange` : un manifeste d'avant la RFC-016 reste valide et se joue à l'identique. Interdit n°1, tenu par la validation du manifeste : tout effet du monde exige son retour de perception **et** un vérificateur (`trempe.verificateurs`, D16.6) — pas d'action aveugle. Interdit n°2 : un vérificateur déclare la `source` qu'il échantillonne, jamais le rapport du pratiquant. D16.2 : la coupe d'un kata d'action est un **outil prêt à l'usage** — son estampille empaquette capacités, effets et vérificateurs pour l'agent CLI, et un kata qui touche le monde requiert au moins une capacité (le manifeste déclare une capacité, jamais un produit ; l'instance la mappe sur son moteur). L'exécution des vérificateurs, le moteur agentique lui-même et le routage conditionnel suivent au dernier lot de la RFC-016 (D16.3).
- R2.5 — **Natif ou orphelin dit la source du prompt, pas le contrat.** Un kata est *natif* quand son prompt s'assemble depuis le gabarit et un densho, *orphelin* quand sa source est un texte servi tel quel (`source: …/<id>.md`, RFC-011) ; un harness est *exogène* quand tous ses kata sont orphelins (RFC-008). Un kata orphelin **porte et édite un contrat f♯ comme un natif** — le contrat décrit l'état, pas la forme du prompt ; seule sa réécriture en densho attend (RFC-011 D11.3, amendée par [RFC-015](docs/rfc-015-contrats-des-harness-importes.md)).

## 3. Le Dojo — passerelle + chat

**Stack :** Docker Compose : LiteLLM (proxy, clés virtuelles, logs Postgres) + Caddy (HTTPS, accès VPN/token) + Open WebUI (chat assemblé, aucun développement custom). Moteurs : APIs propriétaires (Anthropic, OpenAI...) + **modèles open-weight via API compatible OpenAI** (ex. IONOS AI Model Hub, hébergement UE) — le VPS cible (6 vCores / 8 Go, sans GPU) n'héberge pas de modèle local ; un Ollama optionnel (petits modèles ≤3B) reste possible pour expérimentation, jamais pour le banc.

- R3.1 — Chaque kata de chaque harness chargé devient un **modèle virtuel** `<harness_id>/<kata_id>` : moteur + coupe (cible au choix) injectée côté passerelle via hook — les clients ne voient jamais les coupes.
- R3.2 — Changer le moteur sous un kata = une ligne de config ; A/B natif local (GPU) vs API. Cette ligne vit dans `dojo/litellm/moteurs.yaml` : quel moteur incarne un kata est une décision de **déploiement**, jamais de définition — un harness dit ce qu'un kata *est*, pas sur quoi on le fait tourner.
- R3.3 — Toute session loggée avec l'**identité de ha complète** : `(harness, kata, version_kata, version_coupe, cible, moteur, date, praticien)`. Le praticien vient de l'identité signée que le chat transmet ([RFC-005](docs/rfc-005-harness-courant.md) §3.3, amendant le RFC-004 §6 qui l'attendait de la clé appelante) ; il est vide tant que le Dojo ne sert qu'un seul utilisateur.
- R3.4 — Une clé virtuelle par usage (chat / banc / QG), révocables. Elle dit **quel appelant**, ce qui range le ha dans le bon corpus — pas **qui**, qui vient de l'identité.
- R3.5 — La **surface des modèles est servie par Kokaji**, non par la passerelle : `GET /v1/models` calcule la liste depuis la définition du harness courant de l'appelant, `POST /v1/chat/completions` est relayé ([RFC-005](docs/rfc-005-harness-courant.md) §3.2). Une liste énumérée à la main décroche de la forge sans que rien ne le signale — c'est arrivé, c'est `NOTE-0002`. Une liste calculée ne le peut pas.
- R3.7 — **Les deux registres de la passerelle sont dérivés de la forge**, jamais tenus à la main : ce qui **route** (`model_list`, engendrée par `kokaji passerelle --config` en croisant les harness et `moteurs.yaml`) et ce qui **autorise** (la liste de modèles portée par la clé appelante, publiée par `kokaji passerelle --publier`). Ils peuvent décrocher séparément, et un modèle autorisé mais non routé répond 404 là où on attendait une conversation. Trois pannes en sont sorties, aucune ne s'est signalée : un modèle refusé se lit comme un modèle absent.
- R3.8 — **Le décrochage se constate en continu**, et se voit : `kokaji vigie` confronte les deux registres à ce que la forge déclare, et son verdict est rendu à l'administration. Un verdict qui cesse d'être rafraîchi est rendu **comme un échec**, jamais comme une absence — une vigie morte ne dit rien du tout, et ne rien dire se lit comme aller bien. C'est le seul mécanisme qui attrape un processus de vérification arrêté.
- R3.6 — L'identité transmise par le chat est **signée** (JWT, secret partagé) : des en-têtes en clair sont déclaratifs, donc usurpables par qui atteint le point d'entrée. Un kata hors du harness courant de l'appelant est **refusé au relais**, pas seulement absent de sa liste — sinon le filtrage est un confort d'affichage, pas une frontière.

**Juste assez :** converser avec `<demo>/<kata>` via curl, moteur changé en une ligne, session retrouvée dans les logs avec son identité complète. Puis, à deux harness : chacun ne voit que les kata du sien, et forger un kata neuf le rend offert **sans qu'aucune liste ait été éditée** — ni celle qui route, ni celle qui autorise. Enfin, arrêter la vigie : l'administration doit le dire.

## 4. La Forge — build multi-cibles

- R4.1 — `kokaji forge <harness> [--cible <id>]` : assemble template + configs kata → coupes, pour chaque cible du manifest. Déterministe ; aucun édit manuel dans `dist/`.
- R4.2 — Les cibles `etat_structure: true` reçoivent l'instruction d'émission du bloc d'état aux points d'étape ; les autres n'en portent aucune trace.
- R4.3 — Chaque coupe est stampée `(harness, kata, version_kata, version_coupe, cible)` ; changelog généré par diff de source.
- R4.4 — **La coupe se voit avant d'être scellée.** La coupe d'un kata pour une cible se rend en mémoire depuis une définition non scellée — le gabarit, les densho et les contrats tels qu'on les propose — sans rien écrire dans `dist/` ni dans la source ([RFC-010](docs/rfc-010-gabarit-et-densho.md) D10.3). Ce rendu est la forge ordinaire sur une copie : ce qu'on voit est ce qui serait servi.

**Juste assez :** le harness d'exemple se régénère intégralement dans ses deux cibles, à l'identique sur deux builds successifs.

## 5. La Trempe — lint statique + banc dynamique

**Statique (bloque la forge) :**
- R5.1 — Aucun marqueur de gabarit résiduel (`[...]` de structure, `{{...}}` non résolu, sections de chantier) dans une coupe.
- R5.2 — `vocabulaire_interdit` du manifest appliqué aux coupes de chaque cible.
- R5.3 — Tout nom cité (kata, rôle, jalon) doit exister dans le registre canonique du harness ; cohérence des décomptes annoncés vs listés.
- R5.7 — **Les lints du contrat (RFC-002 §6.2)** : chaque kata porte un f♯ complet ; le `produit` de l'amont couvre le `herite` de l'aval — la présence du champ toujours, et **son statut quand l'aval déclare un seuil** (`<kata>.<champ>: <statut>`) ; le chemin vide promet le vide ; la source d'un kata ne référence que des champs de son `herite` (anti-contrebande).

**Dynamique (le banc) :**
- R5.4 — Le runner charge un ha du corpus (ou un scénario), joue l'utilisateur via un persona simulé du harness (appel LLM scénarisé, tour par tour, plafond de tours), à travers le Dojo — produisant de nouveaux ha, comme toute session.
- R5.5 — Évaluation à 3 étages : **déterministe** (les `checks_session` déclarés par le harness + les invariants Kokaji : bloc d'état bien formé, un tour = une question) ; **LLM-as-judge** (grille par variable de design déclarée dans le registre du harness) ; **humain** (échantillonnage, grille fournie par le harness).
- R5.6 — Résultats rattachés aux ha ; rapport comparatif versions × moteurs ; mode non-régression : rejouer les ha exerçant les variables touchées par un diff de source.

**Juste assez :** 3 ha × 2 moteurs comparés en table, un écart réel détecté.

## 6. Le corpus — les ha et leur cycle de vie

Un ha = un dossier `CAS-XXXX-titre/` : `fiche.md` (frontmatter YAML) + `transcript.md` + `sortie.md` + `materiau/`.

**Cycle de vie (capture par défaut) :**
1. **brut** — créé automatiquement par le middleware à la clôture de toute session : identité complète, transcript, sortie, blocs d'état. Zéro geste humain.
2. **anonymisé** — le kin est vérifié/neutralisé (automatique si le sujet est fictif déclaré, sinon passage humain).
3. **annoté** — promotion humaine : `design_exerce` (variables du registre du harness), verdict, constats, enseignements.

Frontmatter : `harness`, `kata`, `version_kata`, `version_coupe`, `cible`, `moteur`, `date`, `praticien`, `visibilite: privee|verse`, `source: reel|scenario|simule`, `statut: brut|anonymise|annote`, `completude: A|B|C`, `design_exerce: []`, `verdict`, `scores`. La taxonomie `design_exerce` appartient au harness (registre), pas à Kokaji.

**Kin de banc et personas** ([RFC-003](docs/rfc-003-diagnostic-de-nature.md) §5.3) : leur frontmatter porte en plus `typologie:` — la nature *réelle* du sujet, telle que l'auteur du kin la déclare — et, pour les pièges, `enonce_comme:` — la nature que son énoncé suggère. Les deux sont du vocabulaire de harness : Kokaji les transporte et les compare, il ne les interprète pas. C'est ce couple qui rend la justesse du diagnostic mesurable, et les kin où les deux diffèrent sont ceux où la qualité d'un harness se voit.

## 7. Le middleware — capture et état

Service léger (FastAPI) adossé aux logs du Dojo.

- R7.1 — Extrait les blocs ` ```json kokaji_state ` des réponses, les valide contre le schéma (spécialisé par le manifest), les stocke horodatés, rattachés au ha.
```json
{ "kokaji_state": {
    "harness": "", "kata": "", "version": "",
    "sujet": "", "objet": "", "etape": "",
    "champs": { "<champ>": "<statut_champ>" },
    "hypotheses": [ { "id": "", "libelle": "", "statut": "<statut_hypothese>", "confiance": "faible|moyen|eleve" } ],
    "options": [ { "id": "OPT-1", "libelle": "", "noeud": "", "statut": "ouverte|engagee|ecartee" } ],
    "decision": { "libelle": "", "ferme": ["OPT-2"], "ouvre": ["OPT-4"] },
    "nature": { "valeur": "<nature>", "confiance": "faible|moyen|eleve", "revisee_le": "<etape>" },
    "actions": [ { "intention": "", "canal": "monde_lecture|monde_ecriture", "artefact": "",
                   "verdict": { "valeur": "", "detail": "", "confiance": 0.0 } } ],
    "pret_pour": null } }
```
`nature` est **facultatif** et appartient au [RFC-003](docs/rfc-003-diagnostic-de-nature.md) : le kata l'émet dès l'ouverture puis à chaque révision, et **Kokaji le transporte sans jamais l'interpréter**. Le HDS ne change pas d'un iota — les natures sont du vocabulaire de harness, écrit dans son template — c'est un pattern de template, pas une structure de manifest. Le diagnostic dit dans quel genre de problème on se trouve, et le kata en adapte sa conduite ; la valeur peut basculer en cours de session, et chaque bascule est déclarée.

`actions` est **facultatif en échange, obligatoire dès qu'un kata touche le monde** ([RFC-016](docs/rfc-016-kata-d-action.md) D16.5) : un kata dont les `effets` dépassent `modele` doit dire ce qu'il a fait — l'intention, le canal exercé, l'artefact laissé, et un **verdict** (valeur, détail, confiance dans [0, 1]) qui est ce qu'il *constate* de son effet, jamais ce qu'il affirme sans preuve. Émettre des actions sans agir sur le monde, ou déclarer un effet qu'aucune action n'exerce, sont des fautes ; en nature émergente, une écriture du monde sans lecture préalable en est une aussi (RFC-003 A16.2). Le canal `modele` reste universel et implicite (le bloc lui-même).

`options` et `decision` sont **facultatifs** : seuls les kata déclarés `emet_options: true` les émettent. Une option est une possibilité nommée et non engagée ; une décision déclare le delta de possibles qu'elle referme et qu'elle ouvre. On mesure l'espace **déclaré**, jamais l'espace réel — même geste épistémique que les statuts de champs.
- R7.2 — Bloc malformé : loggé, jamais bloquant pour la session.
- R7.3 — **Capture par défaut** : toute session close devient un ha `brut` complet (cf. §6) — la promotion est humaine, la capture ne l'est jamais.
- R7.4 — (Ultérieur) Interface MCP lecture seule : `list_ha`, `get_transcript`, `get_state(sujet)`.

## 8. Le QG — fil d'ariane d'hypothèses

- R8.1 — Le QG rend la `chaine` déclarée par le manifest (nœuds/jalons/arêtes) — il ne connaît aucune chaîne en dur.
- R8.2 — Chaque nœud se colore **graduellement** selon l'état agrégé du sujet (ratio des statuts de champs + statuts d'hypothèses) — jamais de tout-ou-rien.
- R8.3 — v1 : un sujet, une vue, détail d'un nœud au clic (champs, hypothèses, horodatage du dernier état). Le QG lit l'état du middleware, n'interprète ni ne modifie rien.
- R8.4 — **Seconde lecture du fil d'ariane : la santé des options.** Par nœud et par sujet : le compte d'options vivantes, leur liste, leur âge ; par décision : son delta (fermées / ouvertes). Visuel v1 : un badge numérique par nœud + un panneau « possibles vivants » du sujet. Pas de halo ni d'animation en v1.
  - Métriques v1, et rien de plus : nombre d'options ouvertes (par nœud, par sujet), âge médian des options ouvertes, delta par décision. **Aucun indice composite, aucun score de fécondité** — un chiffre agrégé magique inviterait au pilotage aveugle.
  - La mesure est descriptive, jamais un objectif — [carnet de vigilances #8](carnet.md).

**Juste assez :** dérouler une session en chat et voir le nœud se colorer sans saisie manuelle. Pour R8.4 : dérouler une session `<demo>/<kata émettant des options>`, voir le nœud afficher ses n options vivantes, prendre une décision en session, et voir son delta apparaître — sans aucune saisie manuelle.

## 9. Le harness d'exemple — « Atelier » (domaine fictif, embarqué)

Pour développer et démontrer Kokaji sans aucun couplage : un petit harness de démonstration, domaine volontairement personnel et neutre — accompagner un porteur de projet *perso* **de l'Idée à la feuille de route** :

- `idee` — clarifier une **Idée** : le besoin, pour qui, la valeur visée, ce qui existe déjà
- `cadrage` — transformer l'Idée en projet cadré : hypothèses de valeur, premier incrément, critères de réussite. `emet_options: true` : les hypothèses de valeur non retenues et les variantes de premier incrément sont les options de démonstration
- `decoupage` — découper le premier incrément en étapes réalisables, chacune testable ; déclare ses décisions (delta fermé / ouvert) sur le choix des étapes

Trois kata suffisent à exercer tout Kokaji : héritage entre kata, chaîne pour le QG, deux cibles, checks, personas, corpus de démonstration. **Tout le contenu de l'Atelier est rédigé from scratch pour ce projet** — aucun matériau importé d'ailleurs.

## 10. Hygiène de séparation (règles du repo)

- R10.1 — Le repo Kokaji ne contient **aucune référence** à un employeur, un outil interne, un cadre méthodologique propriétaire, un processus d'entreprise ou un harness professionnel — ni dans le code, ni dans les commentaires, commits, fixtures, issues ou docs. Le terme « mode guidé » est explicitement banni.
- R10.2 — **La trempe s'applique à Kokaji lui-même** : la CI du repo porte sa propre liste de vocabulaire interdit (maintenue en local, hors repo public le cas échéant) et échoue si un terme y apparaît. La forge se forge elle-même.
- R10.3 — Développement exclusivement sur matériel, comptes, clés et temps personnels ; adresse mail personnelle dans les commits.
- R10.4 — Les harness professionnels, s'il en existe, vivent dans des dépôts distincts, sur leur infrastructure, et consomment Kokaji comme un outil externe — jamais l'inverse.
- R10.5 — Choisir et poser une licence dès le premier commit, et un fichier `NOTICE` établissant le caractère personnel du projet et sa date de commencement. **Close** ([RFC-009](docs/rfc-009-separation-produit-instance.md) D9.3) : le produit est sous Apache-2.0.
- R10.6 — **Le repo produit ne contient aucun contenu d'instance** : toute coupe, tout ha, tout harness non-démonstration vit hors du repo produit ([RFC-009](docs/rfc-009-separation-produit-instance.md) D9.2). Seul l'Atelier (§9) y vit, comme démonstration. La trempe du produit le vérifie et refuse.

## 11. Ordre de construction

1. Dojo (§3) → 2. HDS v0 + harness Atelier minimal (§2, §9) → 3. Forge + trempe statique (§4, §5) → 4. Banc v0 (§5 dynamique) → 5. Middleware (§7) → 6. QG v0 (§8). Un critère « juste assez » vérifié par brique avant d'ouvrir la suivante ; re-décision à chaque étape.

## 12. Sécurité

Clés API en variables d'environnement, `.env` hors git ; exposition réseau minimale (VPN d'abord, sinon HTTPS + token) ; middleware en lecture seule sur les corpus et l'état — les seules écritures admises depuis l'extérieur sont celles de l'autorat ([RFC-004](docs/rfc-004-utilisateurs-co-autorat.md)) : ouvrir une session, gérer les membres d'un harness, régler la visibilité d'un de ses propres ha ; aucune donnée personnelle de tiers dans les corpus — les kin sont fictifs ou strictement personnels.

Le co-autorat ([RFC-004](docs/rfc-004-utilisateurs-co-autorat.md)) ajoute quatre exigences :

- R12.1 — **Authentification locale.** Comptes locaux, mot de passe haché en argon2. L'identifiant d'un utilisateur est un uuid stable, indépendant de tout fournisseur, pour qu'un rattachement OAuth ultérieur n'ait rien à réécrire.
- R12.2 — **Les secrets d'authentification vivent hors git.** Empreintes de mots de passe et jetons de session sont dans un magasin ignoré par le dépôt, jamais dans un corpus ni dans une définition de harness.
- R12.3 — **L'isolation par ACL est vérifiée par sabotage.** Chaque droit refusé du RFC-004 §3 a un test qui tente le geste et exige un refus net. Un droit qu'aucun sabotage n'attaque n'est pas tenu pour acquis.
- R12.4 — **L'autorat ne donne pas la pratique.** Posséder un harness ne donne aucun accès aux ha non versés de ses contributeurs. C'est l'exigence dont tout le reste dépend : un harness partagé où le propriétaire lirait la pratique d'autrui par défaut tuerait l'honnêteté des sessions.

La séparation produit / instance ([RFC-009](docs/rfc-009-separation-produit-instance.md) D9.4) en ajoute une cinquième :

- R12.5 — **Souveraineté.** Chaque instance est souveraine : aucune télémétrie, aucun compte central, aucune émission réseau hors des appels aux moteurs qu'elle configure. Toute destination réseau en dur dans le produit, hors ces appels, est un bug ; la trempe du produit la détecte.
