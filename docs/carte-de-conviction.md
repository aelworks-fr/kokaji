# Carte de conviction — le repo produit

Ce que ce repo prouve, avec la trace de la preuve. Une conviction sans
sabotage est une opinion : chaque vérificateur d'ici a été **vu refuser**
(RFC-007 §7) avant d'être tenu pour acquis.

## A — Le clone étranger (nominal)

`git clone` + `docker compose up` sur une machine neutre ⇒ instance vide
fonctionnelle. **Fait sur le poste de naissance** (voir C, boot de
référence) ; à rejouer sur une machine qui n'a jamais vu Kokaji — la coche
restera ouverte jusque-là.

## B — La première instance (nominal)

Le repo historique s'enregistre comme harness de cette instance et ses kata
se forgent sans modification du produit. **À venir** : demande le geste
d'enregistrement (RFC-007 §3), qui n'existe pas encore.

## C — Les sabotages de la trempe du produit

Faits le 13 septembre 2026, sur une branche jetable, supprimée depuis.
Chaque vérificateur a refusé, sortie 1, et le vert est revenu une fois le
sabotage retiré.

```
— sabotage : un faux corpus/CAS-9999/fiche.md → le lint contenu refuse
✗ contenu : un ha dans le produit — corpus/CAS-9999/fiche.md
✗ contenu : fichier de pratique — corpus/CAS-9999/fiche.md
code de sortie : 1

— sabotage : git add -f dist/coupes/test.txt → le check coupe refuse
✗ coupe : dist/ est suivi par git — dist/coupes/test.txt 
code de sortie : 1

— sabotage : « mode guidé » dans forge/README.md → le lint vocabulaire refuse
✗ vocabulaire : terme interdit dans forge/README.md
code de sortie : 1

— sabotage : un fetch vers un domaine tiers → le test de souveraineté refuse
✗ souveraineté : destination réseau en dur dans qg/sonde.js
code de sortie : 1

```

Un cinquième refus n'était pas prévu : le premier passage du sabotage 1 a
fait rougir le lint vocabulaire sur `trempe/exemptions.txt` — ses propres
justifications citent ce qu'elles exemptent. Le fichier s'exempte
désormais lui-même, et ce refus-là a payé sa place : un vérificateur qui
crie faux apprend à être ignoré.

## Boot de référence

Fait le 13 septembre 2026, depuis une copie des seuls fichiers versionnés de
`dojo/` et le `.env.example` tel quel (ports décalés pour cohabiter avec une
instance existante — le seul écart). Un détail de vraisemblance : le poste a
redémarré pendant l'exercice, et le kit est revenu seul, `restart:
unless-stopped` faisant son travail.

```
— coche 1 · la passerelle répond
$ curl -s http://127.0.0.1:14000/health/liveliness
"I'm alive!"
— coche 2 · le chat s'ouvre
$ curl -s -o /dev/null -w "HTTP %{http_code}" http://127.0.0.1:13000/
HTTP 200
— coche 3 · le modèle configuré figure dans la liste
$ curl -s http://127.0.0.1:14000/v1/models -H "Authorization: Bearer …"
['demo/moteur']
```

Réserve honnête : ce poste avait déjà vu les images Docker. Le clone
étranger (section A) reste à jouer sur une machine vraiment neutre.
