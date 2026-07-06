# Fix — Mauvaise « zone » pour les Élèves 91 (Evry) et 93 (Villepinte)

**Date :** 2026-07-06
**Workflow :** `Board Data - Monday` (`9xpDRWaprRG4OwRl`)
**Exemple :** Anouar RAMMACH (`anouar.rammach1@gmail.com`, item `2785376720`, board **Elèves 93**) —
apparaissait en `zone = IDF 77/93` dans le Data CRM alors que son Campus Monday = **Athena 93**
(donc *Villepinte*).

## Cause racine

Pour les boards IDF, la `zone` est calculée dans le nœud Code à partir de la colonne **Campus**
du board :

```js
zone: (() => {
  const c = get(item.column_values, '<ID_COLONNE_CAMPUS>');
  if (c === 'Athena 93') return 'Villepinte';
  // …
  return 'IDF 77/93';  // fallback si la colonne est vide / non trouvée
})()
```

Or **l'id de la colonne Campus est différent sur chaque board** (les boards sont des clones, mais
la colonne Campus a été recréée avec un id propre). Deux nœuds lisaient l'id d'un **autre** board :
`get()` ne trouvait donc pas la colonne, renvoyait `''`, et la `zone` retombait sur le fallback.

| Nœud | Board | Colonne Campus **réelle** | Lisait (faux) |
|------|-------|---------------------------|---------------|
| `Eleves IDF  1` | Elèves 91 (`5094936373`) | `color_mm2k2c12` | `color_mm1pcwz8` *(id du board Elèves 94)* |
| `Eleves IDF 96` | Elèves 93 (`5094929625`) | `color_mm2k9bkk` | `color_mm05kvfj` *(id du board Elèves 77)* |

Vérifié sur Monday : les 34 élèves du board 91 sont tous `Athena 91`, les 51 du board 93 tous
`Athena 93`. Une fois le bon id lu, le mapping existant donne `Athena 91 → Evry` et
`Athena 93 → Villepinte`.

> Les autres nœuds IDF étaient déjà corrects : `Eleves IDF 77/` (`color_mm05kvfj`),
> `Eleves IDF 1` (`color_mm1pcwz8`), `Candidats IDF 77/` (`color_mm05y9ps`),
> `Candidats IDF 94/` (`color_mm05bjyz`), `Leads IDF 77/` (`color_mkzz6m73`),
> `Leads IDF 94/` (`color_mkzzsdp1`).

## Correctif

Dans chacun des 2 nœuds, remplacer l'id de colonne Campus (2 occurrences : la fonction `zone`
**et** la ligne `campus: get(...)`) :

- **`Eleves IDF  1`** : `color_mm1pcwz8` → `color_mm2k2c12`
- **`Eleves IDF 96`** : `color_mm05kvfj` → `color_mm2k9bkk`

⚠️ Remplacement **ciblé nœud par nœud** : ne PAS faire un rechercher/remplacer global, car
`color_mm1pcwz8` reste correct dans `Eleves IDF 1` et `color_mm05kvfj` dans `Eleves IDF 77/`.

## Vérification

Après correction, exécuter le nœud `Eleves IDF 96` seul : les élèves du board 93 doivent sortir
avec `zone = Villepinte` (et `campus = Athena 93`). Idem `Eleves IDF  1` → `zone = Evry`.
Le dédoublonnage privilégie déjà une vraie ville face au fallback `IDF 77/93`/`IDF 94/91`.
