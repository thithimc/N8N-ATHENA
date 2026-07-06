# Ajout — « Secteur Entreprise » + « Groupe » (dont Ruptures) dans le Google Sheet

**Date :** 2026-07-06
**Workflow concerné :** `Board Data - Monday` (`9xpDRWaprRG4OwRl`)
**Sheet cible :** `Data CRM` — classeur `1gSD9MGJCedOWhM5N4FRko6NDs9wWbru8rXmMveHFjt8`

## Objectif

Faire remonter deux informations Monday, aujourd'hui absentes du Google Sheet :

1. **Secteur Entreprise** — la colonne *status* du board Élèves (labels `Grande Distri 🛒`,
   `Automobile 🚘`, `Restauration 🍔`…). ⚠️ À ne pas confondre avec **Secteur de prédilection**
   (`long_text_mksbdbc2`), qui est déjà récupérée mais elle aussi non écrite dans le sheet.
2. **Groupe** — le groupe Monday auquel appartient chaque contact. C'est cette info qui indique
   qu'un élève est dans le groupe **`Ruptures`** (mais aussi `Replacement 2èmes années`,
   `Nouveaux 2èmes années`, `BTS MCO`, etc. selon le board).

## Ce qu'a montré l'analyse

- Chaque nœud Code (`Eleves …`, `Leads …`, `Candidats …`) interroge un board Monday en GraphQL
  puis mappe les colonnes vers un objet plat. **Le nœud Google Sheets `Append or Update1` est en
  mode `autoMapInputData`** : il écrit uniquement les champs dont le **nom correspond à un en-tête
  de colonne existant** dans l'onglet `Data CRM`. Tout champ sans en-tête correspondant est ignoré.
- **`Secteur Entreprise`** = colonne `5089536606__color_mm1qxjge`, **identique sur les 9 boards
  Élèves**, **absente** des boards Leads et Candidats.
- **`Ruptures`** est un **groupe**, pas une colonne. Son `id` **varie selon le board**
  (`group_mkq39hn2`, `group_mm22zvyj`, `group_mm2hje6q`…), donc on récupère le **titre** du groupe
  via l'API (`group { id title }`) plutôt qu'un id figé.
- La requête GraphQL actuelle **ne récupère pas** le groupe (`group`) ni la colonne Secteur
  Entreprise.

> ⚠️ **Ne PAS reconstruire le workflow via l'API n8n.** Les credentials (Google Sheets OAuth)
> sont masqués (redacted) à la lecture : un rebuild les perdrait et casserait l'écriture du sheet.
> Éditer **uniquement** les nœuds Code concernés dans l'UI n8n, à la main.

---

## Étape 1 — Ajouter les 2 colonnes dans le Google Sheet

Dans le classeur `Data CRM`, onglet **`Data CRM`** (gid `105610334`), ajouter **2 en-têtes** de
colonne (dans la ligne d'en-tête, à la suite des colonnes existantes) :

```
secteur_entreprise
groupe
```

Faire de même dans l'onglet **`Supprimé`** (gid `684542426`) pour garder les deux onglets alignés
(le nœud `Append to Supprimés` est aussi en `autoMapInputData`).

> Le mode `autoMapInputData` lit les en-têtes à chaque exécution : dès que ces colonnes existent
> et que les nœuds Code produisent les champs `secteur_entreprise` / `groupe`, le mapping est
> automatique — **aucune modification du nœud Google Sheets n'est nécessaire.**

---

## Étape 2 — Récupérer le groupe dans TOUS les nœuds Code (23 nœuds)

Dans **chaque** nœud Code (`Eleves …`, `Leads …`, `Candidats …`), les **deux** requêtes GraphQL
contiennent ce fragment identique :

```
items { id name created_at column_values { id text value }
```

Le remplacer (dans les 2 requêtes : `items_page` **et** `next_items_page`) par :

```
items { id name created_at group { id title } column_values { id text value }
```

Puis, dans l'objet retourné (`return allItems.map(item => ({ json: { … } }))`), ajouter **une
ligne** — par exemple juste après `item_id: item.id,` :

```js
    groupe: item.group ? item.group.title : '',
```

Liste des 23 nœuds : `Eleves Lyon`, `Eleves Marseille`, `Eleves Montpellier`, `Eleves Perpignan`,
`Eleves Nice`, `Eleves IDF 77/`, `Eleves IDF 1`, `Eleves IDF  1`, `Eleves IDF 96`,
`Leads Lyon1`, `Leads Marseille1`, `Leads Montpellier1`, `Leads IDF 77/`, `Leads IDF 94/`,
`Leads Perpignan1`, `Leads Nice1`, `Candidats Lyon1`, `Candidats Marseille1`,
`Candidats Montpellier1`, `Candidats IDF 77/`, `Candidats IDF 94/`, `Candidats Perpignan1`,
`Candidats Nice1`.

> Si vous ne voulez le groupe **que** pour les élèves (seul cas où « Ruptures » existe), limitez
> l'ajout de la ligne `groupe` aux **9 nœuds `Eleves …`**. La colonne `groupe` sera alors vide pour
> les leads/candidats. L'ajout du fragment `group { id title }` à la requête est sans risque même
> là où on n'utilise pas le résultat.

---

## Étape 3 — Ajouter « Secteur Entreprise » dans les 9 nœuds Élèves uniquement

La colonne n'existe **que** sur les boards Élèves. Dans **chacun des 9 nœuds `Eleves …`**, ajouter
dans l'objet retourné **une ligne** (par ex. à côté de `secteur_predilection:`) :

```js
    secteur_entreprise: get(item.column_values, '5089536606__color_mm1qxjge'),
```

Ne rien ajouter côté Leads / Candidats (la colonne n'y existe pas).

---

## Exemple complet — nœud `Eleves Lyon` (résultat attendu)

Les 2 requêtes deviennent (fragment `group { id title }` ajouté) :

```js
let query = `{ boards(ids: ${boardId}) { items_page(limit: 500) { cursor items { id name created_at group { id title } column_values { id text value } } } } }`;
// …
query = `{ next_items_page(limit: 500, cursor: "${cursor}") { cursor items { id name created_at group { id title } column_values { id text value } } } }`;
```

Et l'objet mappé gagne 2 lignes :

```js
return allItems.map(item => ({
  json: {
    source_board: 'eleves',
    item_id: item.id,
    groupe: item.group ? item.group.title : '',                             // <-- AJOUT (groupe, dont Ruptures)
    zone: 'Lyon',
    nom: item.name,
    // … champs inchangés …
    secteur_predilection: get(item.column_values, 'long_text_mksbdbc2'),
    secteur_entreprise: get(item.column_values, '5089536606__color_mm1qxjge'), // <-- AJOUT (Secteur Entreprise)
    // … reste inchangé …
  }
}));
```

---

## Vérification

1. Ouvrir le workflow → « Execute Workflow » (ou attendre le trigger `Toutes les 30m`).
2. Sur un nœud `Eleves …`, contrôler dans la sortie que `groupe` (ex. `Ruptures`, `Elèves`) et
   `secteur_entreprise` (ex. `Restauration 🍔`) sont bien renseignés.
3. Dans l'onglet `Data CRM`, vérifier que les colonnes `secteur_entreprise` et `groupe` se
   remplissent (matching d'upsert inchangé : `item_id`).

## Récapitulatif des identifiants Monday utilisés

| Info | Type Monday | Identifiant | Portée |
|------|-------------|-------------|--------|
| Secteur Entreprise | colonne `status` | `5089536606__color_mm1qxjge` | 9 boards Élèves (identique) |
| Groupe (dont Ruptures) | `group { title }` | via API, titre du groupe | tous les boards |
| Secteur de prédilection *(déjà récupéré, non écrit)* | `long_text` | `long_text_mksbdbc2` (Élèves) | pour info |
