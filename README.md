# Kokaji — la forge de harness conversationnels

Kokaji sert des conversations qui suivent une méthode. On décrit la méthode
une fois — un **harness** : ses étapes (**kata**), leurs contrats, ses règles —
et le chat la tient à chaque fois, avec la même exigence et les mêmes
interdits. Ce qui s'y passe est ensuite observable : la raison d'être de la
forge est de comprendre ce qui marche vraiment, plutôt que de le supposer.

Quatre pièces :

- **la forge** — assemble les coupes (prompts système) depuis la définition ;
- **la trempe** — vérifie, statiquement et au banc, que la forme tient ;
- **le dojo** — l'exécution : passerelle de modèles, chat, capture ;
- **le QG** — l'observation : les sujets, l'état, jamais un score.

## Souveraineté

Chaque instance est souveraine (RFC-009 D9.4) : son contenu, ses comptes, ses
clés moteurs lui appartiennent. Le produit **ne voit rien** — aucune
télémétrie, aucun compte central, aucune émission réseau hors des appels
moteurs que l'instance configure. Les instances ne se connaissent pas ; le
seul canal entre elles est l'export/import de harness (RFC-006).

## Démarrer une instance

```
git clone https://github.com/npelloux/kokaji
cd kokaji/dojo
cp .env.example .env    # renseigner ses clés moteurs
docker compose up -d
```

L'instance est vide et fonctionnelle quand les trois coches tiennent :

- [ ] la passerelle répond : `curl -s http://localhost:4000/health/liveliness`
- [ ] le chat s'ouvre : `http://localhost:3000`
- [ ] le modèle configuré y figure dans la liste des modèles

Le harness de démonstration vit dans `atelier/` — il est au produit ce que le
lorem ipsum est au QG. Vos harness vivent **hors de ce repo** : un repo git
par harness, enregistré auprès de votre instance (RFC-009 D9.1).

## Lire ensuite

`docs/SPECS.md` d'abord — tout part de là — puis les RFC dans l'ordre.
La licence est Apache-2.0 (`LICENSE`, `NOTICE`).
