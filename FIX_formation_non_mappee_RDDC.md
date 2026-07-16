# Fix — Lead non créé dans Monday (formation « Responsable du Développement Commercial »)

**Date :** 2026-07-16
**Workflow :** Leads Webflow (`fRKhyOxlbxd5Usy7`)
**Exécution en cause :** [`311916`](https://n8n.srv1390592.hstgr.cloud/workflow/fRKhyOxlbxd5Usy7/executions/311916) (2026-07-15)
**Exemple :** Meriem Lahcene (`meriemlahcene8@gmail.com`, campus Champs-sur-Marne).

## Symptôme

Le lead **n'apparaît pas dans Monday** alors que l'exécution n8n est en statut *success*
et que la notification Slack est bien partie.

## Cause racine

L'exécution ne s'arrête pas parce que le nœud HTTP `Monday - <Campus>` renvoie un HTTP 200
**même quand Monday rejette la mutation** (l'erreur est dans le corps JSON `errors[]`, pas
dans le code HTTP). L'échec passe donc inaperçu.

Erreur renvoyée par Monday sur `create_item` :

```
This status label doesn't exist, possible statuses are:
{0: BTS NDRC, 1: BTS MCO, 2: BTS GPME, 3: BTS MCO 2, 4: BTS NDRC 2,
 5: A renseigner ❌, 6: BTS GPME 2, 7: MASTER MA, 8: BACHELOR RDA,
 9: MASTER MA 2, 10: TITRE PRO COMMERCE, 17: BACHELOR RDDC}
column_id: statut2__1 (Formation) — column_validation_error_code: missingLabel
```

La colonne **Formation** (`statut2__1`) est une colonne *statut* : elle n'accepte que les labels
existants. Le workflow a tenté d'y écrire `"Responsable du Développement Commercial"`, qui
**n'existe pas** → Monday rejette **tout l'item** (rien n'est créé).

### Pourquoi le mapping n'a pas fonctionné

Le nœud **`Normalize Payload`** contient déjà une fonction `normalizeFormation()`, mais elle
ne gérait que le libellé **avec** préfixe :

```js
if (formation === "Bachelor Responsable du Développement Commercial") return "BACHELOR RDDC";
```

Or le formulaire Webflow « Admission » a envoyé la valeur **sans** le préfixe « Bachelor » :
`"Responsable du Développement Commercial"`. Aucune règle ne matchait → la valeur brute était
transmise telle quelle à Monday → `missingLabel`.

## Correctif (à appliquer dans l'UI n8n)

> ⚠️ Ne PAS reconstruire le workflow entier via l'API n8n : les credentials (Monday/Slack) sont
> masqués (redacted) à la lecture et les triggers webhook seraient ré-enregistrés.
> Éditer **uniquement** le nœud Code `Normalize Payload` dans l'UI n8n.

Remplacer la fonction `normalizeFormation()` par une version **tolérante aux variantes** de
libellé (avec ou sans préfixe « Bachelor », casse, etc.) :

```js
// --- Mapping formation (Webflow -> labels Monday, tolérant aux variantes) ---
function normalizeFormation(formation) {
  const raw = (formation || "").trim();
  if (!raw) return "";
  const lower = raw.toLowerCase();

  // Mappings explicites conservés
  if (raw === "Bachelor Responsable du Développement Commercial") return "BACHELOR RDDC";
  if (raw === "MBA Manager d'affaires") return "MASTER MA";
  if (raw === "BACHELOR RDC") return "BACHELOR RDDC";

  // Règles universelles : matchent quelle que soit la variante envoyée par Webflow
  if (lower.includes("responsable du développement commercial")) return "BACHELOR RDDC";
  if (lower.includes("manager d'affaires") || lower.includes("manager d’affaires")) return "MASTER MA";

  return raw;
}
```

Le reste du nœud est inchangé (`formationNormalisee: normalizeFormation(data.formation)`).

## Rattrapage effectué

Le lead manquant a été recréé manuellement dans Monday le 2026-07-16 :

- Board **Leads 77/93 ❄️** (`5090671033`), groupe *Leads* (`group_mm2dd159`)
- Item **Meriem Lahcene** — [`3085958978`](https://athena-bs.monday.com/boards/5090671033/pulses/3085958978)
- Formation `BACHELOR RDDC`, Campus `Athena 77`, Source `Site - Contact`,
  Statut du Lead `Lead ❄️`.

## Vérification

1. Soumettre un lead test « Admission » avec formation *Responsable du Développement Commercial*.
2. Contrôler dans `Normalize Payload` que `formationNormalisee = "BACHELOR RDDC"`.
3. Vérifier que l'item est bien créé dans Monday (colonne Formation renseignée, pas d'erreur
   `missingLabel` dans la sortie du nœud `Monday - <Campus>`).

## Amélioration recommandée (hors scope de ce correctif)

Le vrai angle mort : un rejet Monday (`errors[]` dans un HTTP 200) **ne fait pas échouer**
l'exécution. Pour éviter que de futurs leads disparaissent silencieusement, ajouter après chaque
nœud `Monday - <Campus>` un contrôle qui déclenche une alerte (ou fait échouer le nœud) si
`{{ $json.errors }}` est non vide — idéalement en réutilisant le canal Slack déjà en place.
