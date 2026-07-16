# Fix — Un lead Diploméo arrive plusieurs fois sur Slack (doublons)

**Date :** 2026-07-16
**Workflow concerné :** `Diploméo` (`ygWgOINNqiNCUaZN`)
**Exemple :** Abdillah Mohamed ASMAHANE (`yetinayeti41@gmail.com`) — 2 messages Slack
identiques à ~5 min d'écart (13 h 23 puis 13 h 28) sur le canal Nice.

## Symptôme

Le même lead Diploméo génère **plusieurs messages Slack identiques** (et autant d'items
Monday), à quelques minutes d'intervalle.

## Cause racine

Le workflow est une chaîne linéaire **sans aucune protection anti-doublon** :

```
1. Webhook (?id=…) → 2. Auth JWT → 3. Récupère lead → 4. Transformation + Routage
→ 5. Établissement reconnu ? → 6. Monday → Slack → 7. Réponse OK
```

**Chaque appel du webhook = 1 message Slack + 1 item Monday, sans condition.**

Le webhook est appelé plusieurs fois pour un même lead parce que :

1. **Relance du fournisseur (cause la plus probable).** La réponse `200 OK` n'est renvoyée
   qu'à la toute fin (nœud 7), soit **après** 4 appels externes en série
   (Auth JWT + récupération du lead + Monday + Slack). Si ça dépasse le délai d'attente de
   GetMyLeads/HelloWork, la livraison est considérée échouée et le lead est **renvoyé**.
   L'écart régulier de ~5 min est typique d'un **calendrier de relance**.
2. Le fournisseur peut aussi re-pousser légitimement le même lead.

Dans les deux cas, l'absence de dédup fait qu'on notifie à chaque réception.

## Application — 2 options

**Option A (rapide) : ré-importer le JSON déjà patché.**
Un fichier `Diplomeo_dedup.json` prêt à l'emploi a été généré (fourni séparément, **non
versionné dans git car il contient des secrets** : mot de passe HelloWork + token Monday).
Il reprend le workflow à l'identique (mêmes ids, mêmes credentials Slack/Gmail) + les 4
changements ci-dessous. Dans n8n : ouvrir le workflow *Diploméo* → menu « ⋯ » →
**Import from File** → sélectionner le JSON → **Save**. Vérifier ensuite que les nœuds
Slack et Gmail affichent bien leurs credentials, puis réactiver le workflow si besoin.

**Option B : appliquer les 4 changements à la main** dans l'UI (détail ci-dessous).

## Correctif — garde anti-doublon (détail des 4 changements)

Principe : mémoriser les leads déjà **traités avec succès** (clé = `leadId` **et** email,
fenêtre 24 h) dans la *static data* du workflow. Un lead déjà vu reçoit quand même un
`200 OK` (ce qui **coupe les relances**) mais **ne déclenche ni Slack ni Monday**.

> ⚠️ Ne PAS reconstruire le workflow via l'API n8n (credentials Slack/Gmail masqués,
> webhook ré-enregistré). Appliquer ces changements **dans l'UI n8n**.

### Étape 1 — Nœud « 4. Transformation + Routage » (Code) : contrôle en lecture seule

Juste **avant** le `return { json: { ... } }` final, insérer ce bloc :

```js
// === DEDUP (lecture seule) : le lead a-t-il déjà été traité récemment ? ===
const dedupStore = $getWorkflowStaticData('global');
if (!dedupStore.seenLeads) dedupStore.seenLeads = {};
const DEDUP_WINDOW_MS = 24 * 60 * 60 * 1000; // fenêtre glissante : 24h
const nowTs = Date.now();
// purge des entrées de plus de 24h
for (const k of Object.keys(dedupStore.seenLeads)) {
  if (nowTs - dedupStore.seenLeads[k] > DEDUP_WINDOW_MS) delete dedupStore.seenLeads[k];
}
const dedupKeyId = 'id:' + String(lead.Id || lead.id || '');
const dedupKeyEmail = email ? 'em:' + email.toLowerCase() : null;
const isDuplicate = !!dedupStore.seenLeads[dedupKeyId]
  || (dedupKeyEmail ? !!dedupStore.seenLeads[dedupKeyEmail] : false);
```

Puis, dans l'objet retourné, **ajouter 3 champs** (`isDuplicate`, `dedupKeyId`,
`dedupKeyEmail`) :

```js
return { json: { itemName, boardId: dest?.boardId || null, groupId: dest?.groupId || null,
  columnValues: columnValues, leadId: lead.Id || lead.id,
  schoolName: schoolName || 'Inconnue', destinationFound: !!dest,
  slackChannel, slackMessage,
  isDuplicate, dedupKeyId, dedupKeyEmail } };   // <-- AJOUT
```

> Le nœud ne fait que **lire** l'historique ici. On ne marque le lead comme « traité »
> qu'à l'étape 4, une fois Monday + Slack réussis — ainsi un lead dont le traitement
> échoue n'est jamais perdu (une relance le retraitera).

### Étape 2 — Nouveau nœud « 0. Doublon ? » (IF), juste après le nœud 4

- Type : **IF** (`n8n-nodes-base.if`)
- Condition (booléen) : valeur `{{ $json.isDuplicate }}` → opérateur **is true**
- **Rebrancher** : sortie du nœud 4 → ce nœud IF (au lieu d'aller directement au nœud 5).
  - Sortie **true** (doublon) → nouveau nœud « Réponse - Doublon ignoré » (étape 3)
  - Sortie **false** (nouveau lead) → « 5. Établissement reconnu ? » (branchement existant)

### Étape 3 — Nouveau nœud « Réponse - Doublon ignoré » (Respond to Webhook)

- Type : **Respond to Webhook** (`n8n-nodes-base.respondToWebhook`)
- Respond With : **JSON**, Response Code : **200**
- Response Body :

```
={{ JSON.stringify({ status: 'duplicate_ignored', leadId: $('4. Transformation + Routage').item.json.leadId }) }}
```

> C'est ce `200` qui indique au fournisseur « bien reçu » et **stoppe les relances**.

### Étape 4 — Nouveau nœud « Marquer lead traité » (Code), entre Slack et « 7. Réponse OK »

Insérer un nœud **Code** (`runOnceForEachItem` ou mode par défaut) sur le chemin succès :
`Send a message` (Slack) → **Marquer lead traité** → `7. Réponse OK`.

```js
// === DEDUP (écriture) : marquer le lead comme traité, APRÈS succès Monday + Slack ===
const dedupStore = $getWorkflowStaticData('global');
if (!dedupStore.seenLeads) dedupStore.seenLeads = {};
const nowTs = Date.now();
const idKey = $('4. Transformation + Routage').item.json.dedupKeyId;
const emKey = $('4. Transformation + Routage').item.json.dedupKeyEmail;
if (idKey) dedupStore.seenLeads[idKey] = nowTs;
if (emKey) dedupStore.seenLeads[emKey] = nowTs;
return $input.all();
```

> Rebrancher : `Send a message` → `Marquer lead traité` → `7. Réponse OK`.

### Schéma final

```
4. Transformation + Routage
   → 0. Doublon ?
        ├─ true  → Réponse - Doublon ignoré (200, rien d'autre)
        └─ false → 5. Établissement reconnu ?
                     ├─ true  → 6. Monday → Slack → Marquer lead traité → 7. Réponse OK
                     └─ false → 7b. Alerte établissement inconnu → Gmail
```

## Vérification

1. Réémettre 2 fois le webhook avec le **même `?id=`** (ou attendre une relance réelle).
2. 1er passage : item Monday créé + message Slack envoyé + `200` renvoyé.
3. 2e passage (< 24h) : **aucun** nouveau message Slack, **aucun** nouvel item Monday,
   réponse `{"status":"duplicate_ignored", ...}` en `200`.
4. Contrôler que les leads « établissement inconnu » et les vrais nouveaux leads passent
   toujours normalement.

## Notes

- **Portée de la dédup :** couvre le chemin succès (Monday + Slack). La branche
  « établissement inconnu » (`7b` + Gmail) n'est volontairement pas dédupliquée ici ;
  si elle génère aussi des doublons d'e-mails, on pourra l'ajouter sur le même principe.
- **Fenêtre 24 h :** un lead réellement re-soumis après 24 h sera de nouveau notifié
  (comportement voulu). Ajuster `DEDUP_WINDOW_MS` si besoin.
- **Complément recommandé (cause n°1) :** pour réduire les relances à la source, répondre
  au webhook **immédiatement** après réception plutôt qu'en fin de chaîne. La dédup
  ci-dessus protège de toute façon dans tous les cas.
- La *static data* est propre à ce workflow ; elle est réinitialisée si le workflow est
  ré-importé/dupliqué (sans impact fonctionnel : au pire un lead re-notifié une fois).
```