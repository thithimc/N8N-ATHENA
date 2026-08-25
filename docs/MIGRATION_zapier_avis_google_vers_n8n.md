# Migration Zapier → n8n : « Avis Google - Champs-sur-Marne »

Zap d'origine :

| Étape | Zapier | Équivalent n8n |
|---|---|---|
| 1. Déclencheur | Google Business Profile — *New Review* (Athena Business School - Champs sur Marne) | Nœud **Google Business Profile Trigger** (événement *Review Added*, polling) |
| 2. Action | Slack — *Send Channel Message* | Nœud **Slack** (Message → Send) |

Un workflow prêt à importer est fourni : [`workflows/avis-google-champs-sur-marne.json`](../workflows/avis-google-champs-sur-marne.json).

---

## Étape 0 — Prérequis côté Google (le point le plus important)

> ⚠️ **Le bouton « Sign in with Google » de n8n Cloud ne fonctionne pas pour ce
> nœud** : les API Business Profile sont à accès restreint et l'application OAuth
> partagée de n8n n'y a pas accès — toutes les requêtes échouent alors en 404/403
> (« Could not load list »), y compris la liste des comptes. Il faut
> obligatoirement votre propre Client ID/Secret issu de votre propre projet
> Google Cloud, comme décrit ci-dessous.

Dans Zapier, la connexion Google Business Profile utilise l'application OAuth de
Zapier. Dans n8n, il faut **votre propre projet Google Cloud** :

1. Créer (ou réutiliser) un projet sur [console.cloud.google.com](https://console.cloud.google.com).
2. Activer les API **My Business Business Information API**, **My Business
   Account Management API** et **Google My Business API** (la « legacy » v4,
   utilisée pour lire les avis).
3. ⚠️ Les API Business Profile ont un **quota par défaut de 0** : il faut demander
   l'accès à Google via le [formulaire d'accès aux API Business Profile](https://developers.google.com/my-business/content/prereqs#request-access).
   La validation prend en général quelques jours. Faites cette demande en premier,
   c'est le seul délai incompressible de la migration.
4. Créer un identifiant **OAuth 2.0** (type « Application Web ») et y ajouter l'URL
   de redirection fournie par n8n lors de la création du credential.

## Étape 1 — Créer les credentials dans n8n

1. **Google Business Profile OAuth2** : n8n → *Credentials* → *Add credential* →
   « Google Business Profile OAuth2 API ». Renseigner Client ID / Client Secret du
   projet Google Cloud, puis se connecter avec le compte Google propriétaire de la
   fiche (Thibaud MASSON CHEVALERAUD).
2. **Slack OAuth2** : « Slack OAuth2 API » (ou un token de bot Slack). Autoriser le
   workspace, puis **inviter le bot dans le canal cible** (`/invite @nom-du-bot`),
   sinon l'envoi échouera.

## Étape 2 — Importer le workflow

1. n8n → *Workflows* → *Import from file* → choisir
   `workflows/avis-google-champs-sur-marne.json`.
2. Ouvrir le nœud **Nouvel avis Google** :
   - sélectionner le credential Google créé à l'étape 1 ;
   - choisir *Account* : « Thibaud MASSON CHEVALERAUD » ;
   - choisir *Location* : « Athena Business School - Champs sur Marne » ;
   - régler la fréquence de polling (*Poll Times*) — toutes les heures est un bon
     point de départ (voir « Différences avec Zapier » ci-dessous).
3. Ouvrir le nœud **Envoyer message Slack** :
   - sélectionner le credential Slack ;
   - choisir le canal cible (le JSON contient `#avis-google` en exemple —
     mettez le canal réellement utilisé par votre Zap) ;
   - adapter le texte du message si besoin (il reproduit un format classique :
     note en étoiles, auteur, date, commentaire).

## Étape 3 — Tester puis activer

1. Cliquer sur *Execute workflow* (ou *Fetch Test Event* sur le trigger) pour
   récupérer un avis existant et vérifier le message Slack.
2. Activer le workflow (toggle **Active** en haut à droite).
3. Dans Zapier : laisser les deux tourner en parallèle 1 à 2 jours pour valider,
   puis **désactiver le Zap** (sinon vous aurez des doublons dans Slack).

## Différences avec Zapier à connaître

- **Polling, pas de webhook** : comme Zapier, le trigger n8n interroge l'API à
  intervalle régulier. Chaque interrogation consomme du quota Google Business
  Profile (quota assez bas par défaut) : éviter un polling toutes les minutes ;
  toutes les 30–60 min suffit largement pour des avis.
- **Déduplication** : le trigger n8n mémorise les avis déjà vus, comme Zapier.
  Au premier lancement après activation, il ne renvoie pas tout l'historique.
- **Champs disponibles** : `reviewer.displayName`, `starRating` (`ONE`…`FIVE`),
  `comment`, `createTime`, `updateTime`, `name` (ID de l'avis). La note arrive en
  toutes lettres anglaises, d'où la table de conversion en étoiles dans le nœud
  Slack.
- **Multi-campus** : pour dupliquer sur un autre établissement (autre « Location »),
  dupliquer le workflow et changer simplement la Location et le canal Slack — ou
  utiliser un seul workflow avec plusieurs triggers.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| `429` / `quota exceeded` sur le trigger | Accès API Business Profile pas encore accordé par Google, ou polling trop fréquent |
| `channel_not_found` / `not_in_channel` côté Slack | Bot non invité dans le canal |
| Aucun avis remonté | Mauvais Account/Location sélectionné, ou aucun nouvel avis depuis l'activation (le trigger ne rejoue pas l'historique) |
