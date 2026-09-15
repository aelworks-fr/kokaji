# Structure du dépôt

Ce dépôt est le produit, et rien d'autre (RFC-009, R10.6). Rien ici ne connaît
de domaine : tout le spécifique vit dans une définition de harness (SPECS §2),
hors de ce dépôt — sauf l'Atelier, la démonstration.

```
kokaji/              La forge — paquet Python, CLI `kokaji`
  cli.py             valider, forge, trempe, banc, corpus, middleware, qg, service…
  hds/               Chargement et validation du manifest HDS         (§2)
  forge/             Build multi-cibles : source → coupes             (§4)
  trempe/
    statique/        Lint des coupes et du contrat, bloque la forge   (§5)
    banc/            Runner, personas, judge sur grille               (§5)
    depot/           La trempe qu'un dépôt s'applique à lui-même   (R10.2)
  corpus/            Versement du journal vers les ha                 (§6)
    depot.py         L'interface du dépôt de ha, et les fichiers   (RFC-014)
    base.py          Le dépôt de ha dans le Postgres de l'instance (RFC-014)
  middleware/        Capture, état, carré continu, surface HTTP  (§7, §12)
  qg/                Fil d'ariane : agrégation + pages, sans CDN (§8, R12.5)
  comptes/           Comptes locaux, droits, portail            (RFC-004)
  conception/        Concevoir et sceller une définition        (RFC-006)
  adoption.py        Adopter un harness né hors de la forge     (RFC-008)
  depot/             Un harness, un dépôt git — init, état      (RFC-012)
  semence/           Le gabarit d'un harness neuf               (RFC-006)

tests/               Tests du produit — jamais de fixture de domaine  (§0)
pyproject.toml       Le paquet et ses extras : service, dev
Dockerfile           L'image du service et de la veille              (§7, §8)

dojo/                Le kit d'une instance — Docker Compose           (§3)
  litellm/           Passerelle : moteurs, liste engendrée, hooks
  caddy/             Publier deux hôtes en TLS — profil `web`
  verif/             Le critère « juste assez », les tests de rendu
  vigie/             L'image de la vigie, avec navigateur
  harness/ journal/ comptes/   L'instance elle-même — hors git
atelier/             Le harness de démonstration, domaine fictif      (§9)
trempe/              La trempe du produit : check.sh, exemptions, gabarit
docs/                SPECS, RFC 001→014, HDS v0, et la doc de chaque commande
  design/handoff-v2/ L'audit ergonomique et le prototype v2 — la référence visuelle (RFC-013)
  carnet.md          Le carnet de vigilances — ce qui peut mal tourner, et ce qu'on lui oppose
.github/workflows/   La CI : trempe du produit, tests, Atelier, style

dist/coupes/<harness>/<cible>/   Coupes forgées — généré, jamais suivi  (D9.1)
```

Vos harness vivent hors de ce dépôt : un repo git par harness, enregistré
auprès de votre instance (RFC-009 D9.1).
