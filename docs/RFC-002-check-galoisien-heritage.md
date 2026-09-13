# RFC-002 — Le check galoisien de l'héritage

**Statut : squelette — à marteler ensemble.**
Les blocs marqués `⚒ À toi` attendent tes coups. Le reste est le fruit des 5 keiko ; conteste librement.

---

## 1. Contexte et motivation

Kokaji déclare déjà la moitié du contrat : l'aval déclare son héritage (les champs attendus
de l'amont). Mais rien ne relie aujourd'hui ce contrat à ce que la **pratique vivante**
produit réellement. Un kata peut promettre un héritage qu'aucune session ne livre, ou
livrer un savoir que le contrat ignore — et la trempe n'a aucun moyen de le voir.

Le RFC-002 verrouille cette liaison par une loi unique, vérifiable par la trempe :
**abstraire puis transformer = transformer puis abstraire** (à la variante de régime près,
voir §5). Ce carré rend l'héritage *sûr* : ce que l'aval lit dans une déclaration est
garanti par ce que l'amont a réellement pratiqué.

## 2. Vocabulaire (rappel des keiko)

| Terme | Définition opérationnelle |
|---|---|
| **monde riche (R)** | les états de connaissance du kin, en pleine épaisseur, ordonnés par « en sait plus » |
| **monde des contrats (D)** | les déclarations d'héritage, ordonnées par « exige plus » |
| **α (abstraire)** | d'un état riche, la déclaration la plus forte qu'il peut signer dans le vocabulaire d'héritage |
| **γ (concrétiser)** | d'une déclaration, le candidat générique : l'état le plus ignorant qui la signe |
| **loi de connexion** | α(r) ≥ d ⟺ r ≥ γ(d) — propriété de l'outillage, testée une fois à la forge du vocabulaire |
| **f** | la pratique vivante d'un kata : sa transformation réelle du kin (monde riche) |
| **f♯** | le contrat de l'arête : le couple (héritage attendu, héritage produit) déclaré par le kata |
| **état officiel** | γ(α(r)) : ce que le système retient de r une fois passé l'interface |

## 3. Le carré

Pour chaque kata générateur f : A → B de la chaîne :

```
        f♯ (la promesse)
  α(A) ─────────────────→ α(B)        monde des contrats (D)
   ↑                        ↑
   α                        α
   │                        │
   A ──────────────────────→ B         monde riche (R)
        f (la pratique)
```

Lecture : F = la pratique réelle et G = le monde des contrats sont deux foncteurs
depuis la chaîne (keiko 2) ; α est une **transformation naturelle** F ⇒ G (keiko 3) ;
le carré ci-dessus est son carré de naturalité, et la liberté de la chaîne (keiko 1)
réduit la vérification aux seuls générateurs.

**Matérialité de f♯** : f♯ vit sur chaque arête de la chaîne. Il est écrit par le
forgeron du harness au moment du design de la chaîne. L'« héritage déclaré par l'aval »
existant devient le domaine de f♯ ; le RFC-002 ajoute son codomaine : **chaque kata
déclare aussi ce qu'il produit**.

> ⚒ À toi — valider : où ranges-tu f♯ concrètement dans le format actuel de la chaîne
> (métadonnée d'arête ? section du kata ?) et qui a le droit de le modifier ?

## 4. La loi

**Régime retenu : prudence** (décision keiko — passage de grade) :

```
α(f(a)) ≥ f♯(α(a))        pour tout kata générateur f, tout état riche a
```

La pratique livre **au moins** la promesse. Sous-promettre est permis (le slack).

**Interdit absolu** (les deux régimes le partagent) : sur-promettre —
f♯ annonce un champ que la pratique ne garantit pas. L'aval bâtirait sur du savoir
fantôme. Une coupe qui sur-promet est non conforme : la trempe la casse.

## 5. Options réelles de la décision « prudence » (vs « exactitude »)

**Ce que le choix ferme :**
- La détection automatique du savoir qui meurt non déclaré : un écart contrat/réalité
  peut être du slack volontaire ou une fuite — le rapport de perte (r − γ(α(r)))
  devient bruité et demande une lecture humaine.
- La garantie que l'état officiel suffit à tout l'aval : un aval peut avoir besoin de
  re-dériver un savoir que l'amont possédait mais n'avait pas promis.

**Ce que le choix ouvre :**
- Les kata s'améliorent sans reforge des contrats : le slack absorbe l'évolution.
- Les reforges (keiko 3) sont plus faciles : la naturalité n'est exigée qu'à
  inégalité près.
- Les contrats restent stables pendant que la pratique vit — moins de churn de
  vocabulaire.

**Réversibilité :** passer de prudence à exactitude plus tard = resserrer chaque f♯
au niveau réellement livré ; c'est un lint qui peut le proposer automatiquement.
L'inverse (exactitude → prudence) est gratuit. La décision est donc **réversible à
coût borné** — c'est ce qui la rend signable aujourd'hui.

> ⚒ À toi — amender : d'autres options fermées/ouvertes vues de l'intérieur de Kokaji ?

## 6. Vérifications (le travail de la trempe)

### 6.1 À la forge du vocabulaire d'héritage — une fois
- **Loi de connexion** : α(r) ≥ d ⟺ r ≥ γ(d) sur les cas de banc.
  Une divergence est un bug de l'outillage (α, γ ou vocabulaire), jamais de la session.

### 6.2 Lint statique — à chaque coupe, à chaque modification de chaîne
- Chaque arête porte un f♯ complet (attendu **et** produit).
- Typage : le produit de l'amont couvre l'attendu de l'aval (raccord des bornes, keiko 2).
- Le chemin vide promet le vide (pas de couplage caché).

### 6.3 Banc dynamique — par kata générateur, sur kin de banc
- **Le carré** : exécuter f sur un kin de banc, abstraire le résultat, comparer à
  f♯ appliqué à l'abstraction de l'entrée. Vérifier α(f(a)) ≥ f♯(α(a)).
  Un carré par générateur suffit (liberté + collage, keiko 1 & 3).
- **Test du candidat générique** (anti-contrebande, keiko 4) : exécuter le kata aval
  sur l'état riche réel et sur γ(α(r)) ; au grain déclaré, résultats identiques —
  sinon l'aval lit hors contrat.

### 6.4 Aux jonctions de branches (keiko 5)
- Compatibilité sur le chevauchement ; en cas de conflit : **non-recollement signalé**,
  résolution uniquement par kata déclaré (jamais dans le merge).
- Factorisation : le recollé canonique se verse dans tout merge candidat — l'échec
  nomme le péché (invention ou écrasement).

> ⚒ À toi — prioriser : lesquels de ces checks entrent dans la v1 de la trempe,
> lesquels attendent ? (Mon marteau : 6.2 et le carré de 6.3 d'abord — le reste
> s'appuie dessus.)

## 7. Questions ouvertes

1. **Grain par défaut du carré** : le carré se compare « au grain déclaré » — lequel,
   par défaut ? Proposition : le vocabulaire d'héritage lui-même (D est le grain).
2. **Évolution du vocabulaire** : enrichir D (pour sauver un savoir qui meurt, ex. RGPD)
   change α et γ — donc invalide potentiellement des carrés certifiés. Politique de
   re-certification ?
3. **Reforge et RFC-002 combinés** : une reforge η : F ⇒ F′ doit-elle préserver les f♯
   (mêmes contrats) ou peut-elle les renégocier ? Si renégociation : nouveau harness ?
4. ⚒ À toi — ajouter les tiennes.

## 8. Glossaire de correspondance

| Kokaji | Mathématique |
|---|---|
| chaîne | graphe ; catégorie libre engendrée |
| grain / invariant | quotient de la catégorie libre |
| forge | foncteur défini sur les générateurs |
| reforge | transformation naturelle |
| héritage | connexion de Galois α ⊣ γ |
| RFC-002 | naturalité (laxe) de α entre pratique et contrats |
| recollement | colimite (pushout), candidat initial |
