# La forge

```bash
kokaji forge <harness> [--cible <id>]... [--sortie <racine>]
```

Assemble le template et les configurations de kata en coupes, une par kata et
par cible. Sans `--cible`, toutes les cibles du manifest sont forgées.

## Ce qui est produit

```
dist/coupes/<harness>/
  CHANGEMENTS.md         le relevé de cette forge
  <cible>/
    <kata>.md            la coupe, prête à être injectée comme prompt système
    <kata>.json          son estampille
```

L'id du harness préfixe la sortie : deux harness forgés côte à côte ne se
recouvrent jamais (R2.2). C'est aussi l'arborescence que la passerelle du Dojo
lit — il suffit de pointer `KOKAJI_COUPES_HOST` sur `dist/coupes`.

**`dist/` est un produit.** Rien ne s'y édite à la main. Le dossier n'est pas
versionné : il se régénère.

## Le déterminisme

Deux forges successives sur une source inchangée produisent des **octets
identiques** — aucune horodate n'entre dans une coupe. C'est ce qui rend un écart
mesuré attribuable : si deux sessions divergent à coupe identique, la cause est
ailleurs que dans l'incarnation.

## L'estampille

```json
{
  "harness": "…", "kata": "…",
  "version_kata": "0.1.0",
  "version_coupe": "898732ce48aa",
  "cible": "…"
}
```

`version_kata` est déclarée par le kata : elle bouge quand la **forme** bouge.
`version_coupe` est l'empreinte du texte produit : elle bouge dès que
l'**incarnation** bouge — y compris à kata inchangé, si le template ou la cible
ont changé. Deux cibles d'un même kata ont donc la même `version_kata` et des
`version_coupe` différentes.

L'estampille est aussi inscrite en fin de coupe, en commentaire, pour qu'un
fichier isolé reste identifiable.

## Le bloc d'état

Pour les cibles `etat_structure: true`, la forge écrit le gabarit du bloc et,
**séparément**, les valeurs admises pour chaque marqueur :

```
"champs": { "besoin": "<statut_champ>", … }

`<statut_champ>` vaut exactement l'une de ces valeurs :
- `fait_etabli`
- `hypothese`
- `en_pause`
```

La séparation n'est pas cosmétique. Une première version glissait l'énumération
dans le gabarit lui-même — `"<champ>": "fait_etabli | hypothese | en_pause"`. À
l'usage, le modèle l'a lue comme un exemple à compléter : il a émis `etabli`,
`partiellement_etabli`, `etabli_pour_claire`, et inventé des clés de champs
absentes du registre. Le gabarit ne montre donc plus que des marqueurs, les
clés de `champs` sont énumérées en dur depuis le registre, et `pret_pour` ne
peut valoir que les nœuds que la chaîne place après ce kata.

## Les options (RFC-001)

Un kata déclaré `emet_options: true` reçoit deux sections de plus dans son bloc
d'état — `options` et `decision` — avec leurs valeurs admises fermées comme le
reste, et les nœuds de la chaîne énumérés en dur.

La coupe porte aussi la **vigilance #8** du carnet, en toutes lettres :

> Tu ne la comptes pas, tu la nommes : une option n'existe que si elle a été
> articulée en clair pendant l'échange. **Tu n'as aucun quota** — ni minimum, ni
> cible. Ne jamais en inventer pour étoffer la liste.

Une vigilance qui ne vit que dans la documentation ne protège personne : c'est le
kata qui remplit le bloc, c'est donc à lui qu'il faut le dire.

## Le relevé de forge

`CHANGEMENTS.md` compare chaque coupe à celle de la forge précédente et rend un
diff unifié des seules coupes qui ont bougé (R4.3). Quand rien n'a changé, il le
dit — c'est le cas nominal d'une reforge.

## La trempe

Les coupes sont assemblées en mémoire, **trempées**, puis écrites. Une anomalie
bloque tout : `dist/` ne reçoit jamais une coupe fautive. Voir
[trempe-statique.md](trempe-statique.md). `--sans-trempe` écrit quand même, pour
inspecter une coupe qu'on n'arrive pas à réparer à l'aveugle.

## Ce qui arrête l'assemblage

- une variable du template sans valeur ;
- une variable obligatoire vide (`role`, `questions`, `livrable_structure`,
  `passage`) ;
- un champ hérité absent du registre du harness ;
- une cible inconnue passée en `--cible`.

Aucune coupe n'est écrite avec un trou. Ces refus-là précèdent la trempe : ils
portent sur ce qui empêche d'assembler, pas sur ce qui rend le produit fautif.
