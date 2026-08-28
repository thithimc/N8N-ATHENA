# Migration Zapier → n8n — « Demande de fournitures »

**Date :** 2026-08-28
**Source :** Zap Zapier (Typeform → Gmail)
**Cible :** workflow n8n [`workflows/demande-fournitures.json`](workflows/demande-fournitures.json)

## Ce que faisait le Zap

| Étape | Appli | Détail |
|-------|-------|--------|
| 1. Déclencheur | **Typeform** | *New Entry* sur le formulaire **« Demande de fournitures »** |
| 2. Action | **Gmail** | *Send Email* — récapitulatif envoyé à Julie |

E-mail envoyé :

- **To :** `julie@athena-bs.fr`
- **From :** `thibaud@athena-bs.fr` — **From Name :** `TIBO`
- **Body type :** `plain`
- **Sujet :** `Demande de fournitures - {campus}`
- **Corps :**

  ```
  Hello Julie,

  {demandeur} a fait une demande pour le campus de {campus}.

  Il faut acheter :
  - {qté} ordinateur(s)
  - {qté} double(s) écran(s)
  - {qté} souris
  - {qté} clavier(s)
  - {qté} casque(s)
  - {qté} Chaise(s)

  Remarques supplémentaires :
  {remarques}

  Bonne journée.
  ```

## Le workflow n8n

Trois nœuds :

```
Typeform - Nouvelle demande  →  Construire l'e-mail (Code)  →  Gmail - Envoyer à Julie
```

1. **Typeform - Nouvelle demande** (`typeformTrigger`) — déclenché à chaque nouvelle réponse.
   Configuré avec `simplifyAnswers = false` et `onlyAnswers = false` pour recevoir la
   charge utile **brute** (voir le point clé ci-dessous).
2. **Construire l'e-mail** (`code`) — reconstruit le sujet et le corps à l'identique du Zap.
3. **Gmail - Envoyer à Julie** (`gmail`, opération *send*) — envoie l'e-mail en texte brut,
   nom d'expéditeur `TIBO`.

## Point clé — 6 questions au titre identique + réponses brutes obligatoires

Le formulaire pose **6 fois** la même question « Combien d'unité(s) souhaitez-vous
commander ? » (une par produit), chacune précédée d'une question « Avez-vous besoin
de X ? ». Dans Zapier chaque champ garde une clé distincte ; dans n8n l'option
« Simplify Answers » **écrase** les clés de même titre et on perd 5 quantités sur 6
(symptôme observé : **e-mail entièrement vide**).

➡️ Deux conditions pour que ça marche :

1. **Dans le nœud Typeform Trigger : `Simplify Answers = OFF` et `Only Answers = OFF`.**
   (Vérifier dans l'UI après import — un booléen d'import ne « prend » pas toujours.)
   Le nœud Code lève une erreur explicite si les réponses brutes sont absentes.
2. Le nœud Code rattache chaque quantité au produit via la question
   **« Avez-vous besoin de… » qui la précède** (et non par ordre d'index). Il matche
   par **mot-clé** dans l'intitulé (`ordinateur`, `écran`/`ecran`, `souris`, `clavier`,
   `casque`, `chaise`) — tolérant aux accents et apostrophes — et gère les **sauts
   logiques Typeform** (si « Non » saute la question « Combien », la quantité vaut 0
   sans décaler les autres produits).

| Question « Avez-vous besoin de… » | Produit dans le mail |
|-----------------------------------|----------------------|
| ordinateur(s) | ordinateur(s) |
| double(s) écran(s) | double(s) écran(s) |
| souris | souris |
| clavier(s) | clavier(s) |
| casque(s) | casque(s) |
| chaise(s) | Chaise(s) |

> ⚠️ Si un **nouveau produit** est ajouté au formulaire, ajouter une ligne au tableau
> `produits` dans le nœud Code (label + mot-clé de détection).

## Décision — le « 0 » du Zap d'origine

Dans le Zap, chaque ligne était `- 0 {quantité} …`, ce qui produit un **`0` littéral
en trop** devant la valeur (ex. `- 0 3 ordinateur(s)`). C'est presque certainement une
coquille d'origine. Le workflow n8n affiche directement la **quantité** (`- 3
ordinateur(s)`), et retombe sur `0` si le champ est vide (`- 0 souris`).
Pour reproduire strictement l'ancien comportement, remettre `- 0 ${...}` dans le nœud
Code.

## À faire après import dans n8n

1. **Importer** `workflows/demande-fournitures.json` (menu *Import from File*).
2. **Typeform** : sélectionner le credential Typeform et choisir le formulaire
   « Demande de fournitures » (le champ `formId` est un placeholder à remplacer).
3. **Gmail** : sélectionner le credential OAuth2 du compte **`thibaud@athena-bs.fr`**
   (c'est ce compte qui définit le « From » ; le nom d'expéditeur `TIBO` est déjà réglé
   dans les options du nœud).
4. **Régler le nœud Typeform** : `Simplify Answers = OFF`, `Only Answers = OFF`
   (indispensable — voir « Point clé » ci-dessus). Le nœud Code matche les questions
   par mot-clé, donc aucun intitulé n'est à recopier ; il faut seulement que les
   libellés du formulaire contiennent bien `campus`, `demandeur`, et les mots-clés
   produits (`ordinateur`, `écran`, `souris`, `clavier`, `casque`, `chaise`).
5. **Tester** avec une réponse réelle, puis **activer** le workflow.

> Les `id`/`name` de credentials dans le JSON sont des placeholders (`REMPLACER`) :
> n8n demandera de re-sélectionner les credentials à l'import, rien de sensible n'est
> stocké dans le fichier.
