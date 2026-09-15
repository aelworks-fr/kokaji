# Le Dojo — l'exécution d'une instance

Le runtime des harness (SPECS §3). Rien n'est développé sur mesure ici : la
stack est assemblée, et le seul code du Dojo est la paire de hooks de la
passerelle. Tout le reste est le paquet `kokaji`, dans son image.

```
compose.yaml            postgres + litellm + open-webui + kokaji + veilles + vigie (+ caddy)
litellm/moteurs.yaml    quel moteur incarne quel kata — la seule part qui ne se dérive pas
litellm/config.yaml     la liste des modèles virtuels, engendrée depuis les harness
litellm/hooks/          injection de la coupe + journal des ha
caddy/Caddyfile         publier deux hôtes en TLS — profil `web`
verif/                  le critère « juste assez », et les tests de rendu en conteneur
vigie/                  l'image de la vigie — la seule à porter un navigateur
harness/                les harness servis — hors git, un repo chacun (RFC-009 D9.1)
journal/                le journal des ha — généré, hors git
comptes/                le magasin des comptes — hors git (R12.2)
```

## Démarrer

Depuis la racine du dépôt, une fois le paquet installé (`pip install -e .`) :

```bash
cd dojo
cp .env.example .env                 # renseigner les secrets et une clé moteur
mkdir -p harness && cp -r ../atelier harness/atelier
kokaji forge harness/atelier         # les coupes, dans dojo/dist/coupes
kokaji passerelle harness --config litellm/config.yaml \
    --moteurs litellm/moteurs.yaml --nu banc/persona
docker compose up -d --build
docker compose ps                    # puis `docker stats` une minute : rien ne doit boucler
```

Le `--build` construit les deux images depuis le dépôt. Elles sont aussi
publiées à chaque commit sur `main` — `ghcr.io/aelworks-fr/kokaji` et
`ghcr.io/aelworks-fr/kokaji-vigie`, étiquettes `latest` et `sha-<commit>` —
pour qu'une instance puisse tourner sans cloner le produit : dans son compose,
`image:` remplace `build:`.

Les dépôts nus des harness (RFC-012) vivent sous `KOKAJI_DEPOTS_HOST`
(`./depots` par défaut), monté en `/depots` : c'est le seul dossier où le
service enregistre, pousse, tire et clone. Depuis son poste, on clone un
harness par `git clone <machine>:<dossier>/depots/<id>.git`.

Les services sont en `restart: on-failure:5` et plafonnés en mémoire et CPU
(voir l'en-tête de `compose.yaml`). Un conteneur qui plante au démarrage
finit en `Exited` au lieu de redémarrer sans fin : le lire dans
`docker compose logs <service>`, corriger, puis `docker compose up -d <service>`.

L'instance est vide et fonctionnelle quand les quatre coches tiennent :

- [ ] la passerelle répond : `curl -s http://localhost:4000/health/liveliness`
- [ ] la liste des modèles porte les kata de l'Atelier :
      `curl -s http://localhost:4000/v1/models -H "Authorization: Bearer $LITELLM_MASTER_KEY"`
- [ ] Kokaji répond : `http://localhost:8100/`
- [ ] le chat s'ouvre : `http://localhost:3000`

## Les clés

Une clé virtuelle par usage, révocable (R3.4). Après le premier démarrage :

```bash
curl -sS http://127.0.0.1:4000/key/generate \
  -H "Authorization: Bearer $LITELLM_MASTER_KEY" \
  -H "Content-Type: application/json" \
  -d '{"key_alias":"chat","models":["atelier/idee","atelier/cadrage","atelier/decoupage","banc/persona"]}'
```

Reporter la clé dans `.env` (`DOJO_CLE_CHAT`), de même pour le banc, puis
`docker compose up -d`. Ensuite, `kokaji passerelle harness --publier` tient
l'autorisation de la clé à jour quand des harness naissent — `sceller` le fait
seul depuis le service. Révoquer : `POST /key/delete`.

Le compte administrateur du chat se crée une fois, inscriptions ouvertes
(`DOJO_CHAT_INSCRIPTIONS=True`), puis on les referme. Sa clé d'API
(`DOJO_CLE_CHAT_ADMIN`) laisse Kokaji activer les comptes qu'il invite. Le
premier compte Kokaji se crée par `kokaji comptes` — voir `docs/middleware.md`.

## Ce que fait le hook

Le nom de modèle virtuel `<harness>/<kata>` est la seule chose que la passerelle
sait du domaine. Un suffixe facultatif `@<cible>` force une incarnation
particulière — `atelier/idee@instrumentee` — ce qui permet d'exposer deux
cibles d'un même kata côte à côte et de les comparer. Sans suffixe, la cible du
Dojo s'applique (`KOKAJI_CIBLE_DEFAUT`) ; si elle n'est pas forgée et qu'une
seule l'est, celle-là est prise.

À chaque appel, le hook :

1. résout la coupe sous `<coupes>/<harness>/<cible>/<kata>.md` ;
2. **écarte toute consigne système envoyée par le client** et la remplace par la
   coupe — les clients ne voient jamais les coupes (R3.1) ;
3. attache l'identité de ha (`harness`, `kata`, `version_kata`, `version_coupe`,
   `cible`, `modele_virtuel`, `date`) aux métadonnées loggées (R3.3).

Le moteur effectivement appelé est résolu par la passerelle après le hook.
L'identité passe par la clé `spend_logs_metadata` : c'est la seule que la
passerelle recopie jusque dans sa charge de logging standard.

Après toute modification d'un fichier sous `litellm/hooks/`, il faut
`docker compose restart litellm` : les hooks sont importés au démarrage.

## Le journal des ha

La table de logs de la passerelle ne convient pas comme trace : sa file
d'attente n'est vidée qu'au-delà d'un seuil, et une session isolée peut n'y
jamais apparaître. Le Dojo écrit donc sa propre trace, en append seul, dans
`journal/` : une ligne JSON par appel, un fichier par jour.

```
statut      abouti | echoue
session     la conversation à laquelle l'appel appartient
etat_avant  empreinte de l'état d'où part l'appel
etat_apres  empreinte de l'état qu'il laisse derrière lui
moteur      résolu par la passerelle, + fournisseur
identite    harness, kata, version_kata, version_coupe, cible, date
messages    le transcript tel que le moteur l'a reçu, coupe comprise
reponse, usage, erreur
```

Rattacher un appel à sa conversation, dans cet ordre : le client déclare sa
session (`litellm_session_id`, ou `metadata.session_id`) ; sinon l'appel
prolonge un état connu — son `etat_avant` est l'`etat_apres` d'un précédent — et
hérite de sa session ; sinon c'est une racine. Deux conversations identiques,
rejouées, ont donc deux racines distinctes. La chaîne vit en mémoire
(`KOKAJI_CHAINE_MAX`, 4096 états) ; le journal reste reconstructible hors
ligne, chaque ligne portant les deux empreintes.

Le journal ne juge, n'agrège et ne supprime rien : c'est la matière première de
la veille, qui en compose les ha. Son contenu n'est pas versionné.

Avec `KOKAJI_BASE_URL` posée (RFC-014), le hook écrit chaque appel **en base**,
table `appel`, dans la base `kokaji` du Postgres du dojo — et dans `journal/`
seulement si la base ne répond pas, pour ne rien perdre. La veille et le QG
lisent alors le journal par requête, harness par harness, et relisent aussi
`journal/` sans compter un appel deux fois. L'image de la passerelle est
celle de LiteLLM plus le pilote Postgres (`litellm/Dockerfile`).

## Les coupes

`KOKAJI_COUPES_HOST` pointe sur `./dist/coupes`, la sortie de `kokaji forge`
— et de `sceller`, depuis le service. L'arborescence attendue est celle que la
forge produit : `<harness>/<cible>/<kata>.md` et son `.json`. Une coupe
modifiée est reprise au prochain appel, sans redémarrage : le hook relit le
fichier à chaque fois. Reforger suffit.

## Vérifier le « juste assez »

```bash
DOJO_CLE_BANC=sk-... ./verif/juste-assez.sh
```

Le script converse avec `atelier/idee`, relit la dernière ligne du journal et
sort en erreur si l'identité de ha est incomplète. Le troisième critère —
changer le moteur en une ligne — se vérifie en éditant `litellm/moteurs.yaml`
et en réengendrant la liste. Les tests de rendu, sur un poste sans navigateur :
`./verif/rendu.sh`.

## Publier

Un vrai domaine par surface dans `.env` (`DOJO_HOTE_CHAT`, `DOJO_HOTE_KOKAJI`),
`DOJO_BIND=0.0.0.0`, `KOKAJI_CHAT_URL` et `KOKAJI_BASE` en conséquence, puis
`docker compose --profile web up -d`. Caddy obtient ses certificats tout seul.
Derrière un routeur déjà en place, on se passe du profil `web` et on route les
deux ports publiés sur loopback.
