# Fix — Les leads passent direct en « Abandon ❌ »

**Date :** 2026-06-24
**Board concerné :** Leads - Perpignan ❄️ (`5090687714`) — et par extension les 9 boards campus (clones).
**Exemple :** Flavien JEROME (`olini@hotmail.fr`, source *Site - Brochure*, item `3018240555`).

## Symptôme

À leur création, les leads arrivent directement avec le **Statut du Lead = `Abandon ❌`**
au lieu de `Lead ❄️`.

## Cause racine

1. Le lead est créé par n8n (workflow **Leads Webflow**, ou **Nomad** pour Typeform).
   La mutation `create_item` écrit l'email, la formation, la source, le téléphone… **mais ne
   fixe jamais la colonne `Statut du Lead` (`statut8__1`).**
2. Comme la valeur n'est pas fournie, Monday applique la **valeur par défaut du groupe**.
   Sur le groupe « Leads contact » du board Perpignan, ce défaut est `Abandon ❌`.

Preuve (journal d'activité de l'item) : juste après la création, l'utilisateur système Monday
(`user_id = -4`, `action_record_uuid = null`) pose `Statut → Abandon ❌`, `Campus → Perpignan`,
`Qui → Thibaud`. Cette signature = **valeurs par défaut**, pas une automatisation
(aucune automatisation n'est active sur le board, vérifié).

## Correctif appliqué (côté n8n)

Forcer explicitement le statut `Lead ❄️` à la création, dans **chaque** nœud de construction
de payload. Une valeur explicite passée dans `create_item` **écrase** le défaut du groupe.

> ⚠️ Ne PAS reconstruire les workflows entiers via l'API n8n : les credentials (Monday/Slack)
> sont masqués (redacted) à la lecture et les triggers webhook seraient ré-enregistrés.
> Éditer **uniquement** le nœud Code concerné dans l'UI n8n.

### Workflow « Leads Webflow » (`fRKhyOxlbxd5Usy7`)

Dans chacun des **9 nœuds** `Build Monday - <Campus>`
(Marseille, Perpignan, Montpellier, Champs-sur-Marne, Villepinte, Evry, Villejuif, Lyon, Nice),
ajouter la ligne `statut8__1` dans l'objet `rawColumnValues` :

```js
const rawColumnValues = {
  "statut8__1": { "label": "Lead ❄️" },   // <-- AJOUT : force le statut à la création
  "e_mail__1": email ? { "text": email, "email": email } : null,
  "statut2__1": formation ? { "label": formation } : null,
  // ... le reste inchangé
};
```

> Ne PAS modifier `Build Monday - Newsletter` ni `Build Monday - B2B` (boards différents,
> sans colonne `statut8__1`).

### Workflow « Nomad » (`u7SAEmmql2dd7UpP`)

Dans le nœud Code `Parser les réponses`, à la suite des lignes `columnValues[...] = ...`,
ajouter :

```js
columnValues['statut8__1'] = { label: 'Lead ❄️' };
```

## Vérification

1. Soumettre un lead test (Webflow + Typeform Nomad).
2. Le nouvel item doit apparaître en `Statut du Lead = Lead ❄️`.
3. Contrôler le journal d'activité : plus de passage `→ Abandon ❌` à la création.

## Note — ajouts manuels

Cette correction couvre les leads créés par les automatisations. Les leads ajoutés
**manuellement** dans le groupe hériteront toujours du défaut `Abandon ❌`. Pour couvrir aussi
ce cas, changer la valeur par défaut du groupe dans l'UI Monday
(colonne *Statut du Lead* → clic droit / paramètres de colonne → valeur par défaut → `Lead ❄️`).
