# RFC-002 — Le check galoisien de l'héritage

> **Statut : v2 — martelée et scellée** (établi à deux voix, août 2026). Remplace le squelette v1.
> Dépend de : RFC-001 (santé des options / capture par défaut des ha). Entraîne HDS v0 → v0.1 et SPECS v1.2 → v1.3.

---

## 0. La clé de voûte (décision scellée)

Le squelette v1 présupposait une machinerie d'abstraction à construire. La v2 repose sur une identification qui la rend presque gratuite :

> **α existe déjà : c'est le bloc d'état.** À chaque checkpoint, le kata déclare `champs: {…: fait_etabli|hypothese|en_pause}` — la pratique **s'auto-abstrait**, en temps réel, dans le vocabulaire d'héritage. Il n'y a pas d'abstracteur à écrire : il y a un ordre à définir et des comparaisons à faire.

Conséquences en chaîne : le carré de naturalité devient un **check de données pures, sans LLM** ; et grâce à la capture par défaut (RFC-001), **chaque session réelle vérifie le carré gratuitement** — la naturalité ne se teste pas seulement au banc, elle se *surveille en continu sur le corpus*. RFC-001 capture ; RFC-002 juge la capture.

## 1. Contexte et motivation

Kokaji déclare la moitié du contrat : l'aval déclare son héritage. Rien ne relie ce contrat à ce que la pratique vivante produit réellement. Un kata peut promettre un héritage qu'aucune session ne livre (**sur-promesse** : l'aval bâtit sur du savoir fantôme), ou livrer un savoir que le contrat ignore (fuite silencieuse). Le RFC-002 verrouille la liaison par une loi unique, vérifiable par la trempe : **la pratique livre au moins la promesse.**

## 2. Vocabulaire

| Terme | Définition opérationnelle (v2) |
|---|---|
| **monde riche (R)** | les états de connaissance du kin en pleine épaisseur (le transcript, la session vécue) |
| **monde des contrats (D)** | les déclarations dans le **vocabulaire de champs des blocs d'état**, ordonnées ainsi : d₁ ≥ d₂ ssi d₁ couvre chaque champ de d₂ avec un statut au moins aussi fort, l'ordre des statuts étant **fait_etabli > hypothese > en_pause** |
| **α (abstraire)** | **l'émission du bloc d'état** — la pratique s'auto-abstrait (§0) |
| **γ (concrétiser)** | théorie seulement en v1 : non implémenté (cf. §7, différés) |
| **f** | la pratique vivante d'un kata : sa transformation réelle du kin |
| **f♯** | le contrat du kata : le couple (`herite:`, `produit:`) — voir §3 |
| **carré** | pour tout ha du kata f dont l'état d'entrée satisfait `herite:` : l'état final doit satisfaire `produit:` |

## 3. f♯ — matérialité (décision scellée)

Le contrat vit **sur le kata, dans le manifest** — pas sur l'arête :

```yaml
kata:
  - id: cadrage
    herite:   [idee.besoin, idee.cible]        # le domaine : ce que j'attends de l'amont
    produit:  [cadrage.hypotheses: hypothese,   # le codomaine : ce que je garantis,
               cadrage.increment: fait_etabli]  #   avec le statut minimal garanti
```

- Même vocabulaire des deux côtés : les champs des blocs d'état.
- **Tout co-auteur du harness modifie f♯** — propriétaire ou contributeur, la décision n'est pas un goulot ([RFC-004](rfc-004-utilisateurs-co-autorat.md) §3). Toute modification reste un **changement de version majeure du kata** — elle invalide mécaniquement ses certifications — et **chaque scellement porte le nom de son auteur** : c'est la traçabilité qui tient la responsabilité, non la rareté du droit.
- L'`heritage:` existant du HDS v0 est renommé `herite:` ; `produit:` est ajouté (HDS v0.1).

## 4. La loi — régime prudence (décision de keiko, confirmée)

```
état_final(ha) ≥ produit(f)      pour tout ha de f dont état_initial(ha) ≥ herite(f)
```

La pratique livre **au moins** la promesse. Sous-promettre est permis (le slack). **Interdit absolu : sur-promettre** — une coupe dont les ha violent le carré est non conforme ; la trempe la casse.

**α couvre les actions (amendement RFC-016).** Depuis la RFC-016, une pratique peut *agir* : α, le bloc d'état, porte alors des `actions[]`, et l'abstraction inclut ce que la pratique a **fait**. Le carré gagne un verdict, `action-sur-promesse` : quand une action rapporte un verdict que le **vérificateur** a démenti — le monde échantillonné hors du dire de l'agent (RFC-016 interdit n°2) —, le carré le nomme, car un routage sur un verdict démenti irait de travers. La sur-promesse de champ prime : on nomme d'abord ce que `produit` n'a pas livré, puis ce qu'une action a menti.

## 5. Options réelles de la décision « prudence » (complétées à l'établi)

**Fermé :**
- La détection automatique du savoir qui meurt non déclaré (écart = slack volontaire ou fuite ; lecture humaine requise).
- La garantie que l'état officiel suffit à tout l'aval (re-dérivations possibles).
- **La composition du slack** : trois kata qui sous-promettent un peu font un contrat de bout en bout très en dessous de la pratique — sur une chaîne longue, le savoir *déclaré* s'appauvrit par accumulation. Parade : le lint de resserrage (§6.4) propose de remonter `produit:` au niveau réellement observé sur le corpus.

**Ouvert :**
- Les kata s'améliorent sans reforge des contrats ; les reforges n'exigent la naturalité qu'à inégalité près ; les contrats restent stables pendant que la pratique vit.
- **L'admissibilité des moteurs devient certifiable** : le contrat est l'invariant, le slack absorbe la variance de style entre moteurs — « ce moteur est-il admissible pour ce kata ? » se répond en rejouant le carré sur ses ha. *(Retombée majeure pour le benchmarking ; critère documenté ici, outillé au pas 4-5.)*

**Réversibilité :** prudence → exactitude = resserrer chaque f♯ au niveau livré (le lint §6.4 peut le proposer) ; l'inverse est gratuit. Décision réversible à coût borné, donc signable.

## 6. Vérifications — la carte d'utilité (scellée : « utile d'abord »)

Chaque check est rangé au pas de construction où il devient implémentable sans machinerie neuve.

### 6.1 · Pas 2 (HDS v0.1) — le schéma, maintenant
`herite:`/`produit:` au manifest. Dix lignes. C'est la seule action immédiate du RFC.

### 6.2 · Pas 3 (trempe statique) — les lints
- Chaque kata porte un f♯ complet (`herite:` **et** `produit:`).
- Typage de chaîne : le `produit:` de l'amont couvre le `herite:` de l'aval (au sens de l'ordre de D).
- Le chemin vide promet le vide (pas de couplage caché).
- **Anti-contrebande statique** : la source du kata aval ne référence que des champs de son `herite:` — la contrebande se lit dans le texte avant de se voir dans la pratique. *(Remplace en v1 le test dynamique du candidat générique — 90 % du péché pour 1 % du prix.)*

### 6.3 · Pas 5 (middleware) — le carré continu
Pour chaque ha capturé : vérifier le carré (§4) par comparaison des blocs d'état d'entrée/sortie avec f♯. Check de données pur. Une violation = sur-promesse **détectée en production** ; le ha est marqué, le kata signalé.

### 6.4 · Pas 4 (banc) — la couverture et le resserrage
- Kin de banc pour couvrir les entrées limites du carré (états d'entrée minimaux satisfaisant tout juste `herite:`).
- **Lint de resserrage** : sur le corpus, proposer le `produit:` observé quand il excède durablement le déclaré (parade à la composition du slack ; l'acceptation reste au forgeron — version majeure).

### Différés (sans regret, réveillés par leur besoin)
γ et le test dynamique du candidat générique · le recollement aux jonctions (la chaîne de l'Atelier est linéaire — spécifier le merge aujourd'hui serait de l'optimisation prématurée) · le régime exactitude · la loi de connexion formelle (privée d'objet tant que γ n'est pas matérialisé).

## 7. Questions ouvertes — réponses scellées

1. **Grain par défaut du carré** : D lui-même — le vocabulaire de champs des blocs d'état. Confirmé.
2. **Évolution du vocabulaire** : D est versionné avec le harness. Un enrichissement n'invalide que les carrés des kata dont le f♯ touche les champs modifiés — **re-certification scopée**. Réserve honnête : les ha historiques portent l'ancien vocabulaire ; re-certifier sur l'historique exige de ré-abstraire les transcripts (travail de judge, coût borné, à n'engager que si le champ ajouté le justifie).
3. **Reforge et contrats** : une reforge **préserve les f♯** — c'est ce que la prudence achète. Renégocier un contrat n'est pas une reforge : c'est une **version majeure du harness**.
4. Nouvelle (établi) : **la certification est-elle par kata ou par (kata, coupe, moteur) ?** En toute rigueur, par triplet — le carré observé sur un moteur ne garantit pas un autre. V1 : certification agrégée par kata, ventilée par moteur dans les rapports ; l'admissibilité par moteur (§5) affine quand le besoin arrive.

## 8. Glossaire de correspondance (inchangé — la théorie reste le fondement)

| Kokaji | Mathématique |
|---|---|
| chaîne | graphe ; catégorie libre engendrée |
| grain / invariant | quotient de la catégorie libre |
| forge | foncteur défini sur les générateurs |
| reforge | transformation naturelle |
| héritage | connexion de Galois α ⊣ γ |
| RFC-002 | naturalité (laxe) de α entre pratique et contrats |
| recollement | colimite (pushout), candidat initial — *différé* |

---
*Note d'établi : ce RFC a été appris avant d'être écrit — cinq keiko de théorie des catégories, un passage de grade, deux marteaux. La v2 n'ajoute au fond qu'une chose : l'identification α = bloc d'état, qui transforme un théorème en instrument. Le reste est du rangement par utilité.*

## État d'application

| Changement | Pas | État |
|---|---|---|
| §6.1 — `herite:`/`produit:` au manifest, validés par le HDS v0.1 | 2 | appliqué |
| §6.2 — les lints de la trempe statique | 3 | appliqué — `contrat-complet`, `chemin-vide`, `typage-chaine`, `ordre-des-statuts`, `contrebande` |
| §6.4 — lint de resserrage | 4 | appliqué — `kokaji resserrer`, propose sans appliquer |
| §6.4 — couverture des entrées limites du carré | 4 | pas construit |
| §6.3 — le carré continu sur chaque ha capturé | 5 | appliqué — `carre.md` par ha, `sur-promesse` en erreur |
| §4 — α couvre les actions (amendement RFC-016) | — | appliqué — verdict `action-sur-promesse` quand le dire d'une action diverge du vérificateur ; les ha sans action jugés comme avant |

Décisions prises à l'application, hors du texte du RFC :

- **`herite:` accepte un seuil facultatif.** Le §3 montre `herite: [idee.besoin,
  idee.cible]` — des références nues. Le §6.2 promet pourtant que le `produit` de
  l'amont couvre le `herite` de l'aval *au sens de l'ordre de D*. Avec des
  références nues, cette clause n'a rien à comparer : elle se réduit à une
  présence, et c'est tout ce que le lint `typage-chaine` savait vérifier.
  L'écriture `<kata>.<champ>: <statut>` est donc admise en plus de l'écriture
  nue, qui garde exactement son sens. Le lint `ordre-des-statuts` compare alors
  le statut garanti par l'amont au seuil exigé par l'aval.
  Ce que cela attrape n'apparaîtrait nulle part à l'exécution : un kata qui exige
  un fait établi là où l'amont ne promet qu'une hypothèse laisse les deux carrés
  conformes et la chaîne fausse.

- **L'ordre de D est celui de la déclaration.** `statuts_champ` est surchargeable par
  le harness (SPECS §2) ; l'ordre fort → faible est donc celui dans lequel le
  harness les déclare. Le défaut de Kokaji, `[fait_etabli, hypothese, en_pause]`,
  donne exactement l'ordre du §2 de ce RFC.
- **`produit:` remplace la clé `champs:` de la source du kata.** Les deux
  décrivaient la même chose — ce dont le kata rend compte — à deux endroits.
  Le gabarit du bloc d'état est désormais construit depuis `herite:` puis
  `produit:`, une seule source de vérité.
