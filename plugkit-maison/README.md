# PlugKit maison — l'IA qui fait grandir nos réseaux, sur notre stack

Équivalent auto-hébergé de [PlugKit](https://www.plugkit.co/fr/) (49–97 €/mois), construit
sur ce qu'on utilise déjà : **n8n + Monday + Slack**, plus **Postiz** (open source) pour la
publication multi-réseaux.

| Fonction PlugKit | Ici | Fichier |
|---|---|---|
| Commentaire « GUIDE » → DM automatique (remplace ManyChat) | Règles éditables dans un board Monday, DM privé + réponse publique + **lead créé dans Monday** | `workflows/01_instagram_mots_cles_dm_ia.json` |
| L'IA répond aux DM | Agent Claude qui qualifie le prospect, capte email/téléphone → lead Monday, **escalade Slack** si besoin, se met en pause quand un humain répond | `workflows/01_…` (même workflow) |
| Piloter depuis Claude/ChatGPT (MCP) | Serveur MCP n8n : stats compte, stats d'un post, derniers posts, commentaires, répondre | `workflows/02_mcp_server_instagram.json` |
| Stats tous réseaux | Rapport Slack chaque lundi 9 h (Instagram) + analytics Postiz (tous réseaux) | `workflows/03_rapport_hebdo_slack.json` |
| Publier / programmer partout | **Postiz** : 28+ réseaux (Instagram, TikTok, LinkedIn, YouTube, Facebook, X…), calendrier, MCP | voir §4 |
| Rushs → reels gratuitement dans Claude Code | Script local : coupe des silences, sous-titres mot par mot (Whisper), accroche, 9:16 | `reels/make_reel.py` + skill `/reel` |

```
 Instagram ──webhook──▶ n8n 01 ──▶ DM / réponse publique (Graph API)
                          │  ├──▶ Monday : règles mots-clés (lecture) + leads (création)
                          │  └──▶ Slack : « un humain est demandé »
 Claude / ChatGPT ──MCP──▶ n8n 02 (stats, commentaires)      ──MCP──▶ Postiz (publier, programmer, stats)
 Claude Code ──/reel──▶ make_reel.py ──▶ postiz upload + posts:create
```

**Coût** : Claude API (quelques € / mois pour quelques centaines de DM) + hébergement Postiz
si auto-hébergé (ou abonnement Postiz Cloud). Le reste tourne sur notre n8n.

---

## 1. Board Monday « Automations DM » (les règles mots-clés)

Créer un board avec ces colonnes (le workflow les lit **par leur titre**, l'orthographe compte) :

| Colonne | Type | Contenu |
|---|---|---|
| *Nom de l'élément* | — | Mot(s)-clé(s), séparés par des virgules : `GUIDE, brochure` (casse et accents ignorés, mot entier) |
| `Message DM` | Texte long | Le message envoyé en privé. `{prenom}` = pseudo Instagram |
| `Lien` | Texte | URL ajoutée à la fin du DM (brochure, inscription, Calendly…) |
| `Réponse publique` | Texte | Variantes séparées par `\|` : `Envoyé en DM {prenom} 😉 \| Check tes messages !` (vide = pas de réponse publique) |
| `Post ciblé (ID)` | Texte | Optionnel : ID du post Instagram ; vide = règle valable sur tous les posts |
| `Actif` | Statut | `Oui` / `Non` |

L'équipe ajoute ou coupe une campagne directement dans Monday, sans toucher à n8n
(et Claude peut aussi le faire via le connecteur Monday).

## 2. App Meta (Instagram API)

1. Le compte Instagram doit être **professionnel** (Business ou Créateur).
2. Sur [developers.facebook.com](https://developers.facebook.com/apps) : *Créer une app* →
   type **Business** → ajouter le produit **Instagram** → *API setup with Instagram login*.
3. *Generate access token* pour le compte → on obtient un **token longue durée (60 jours)**.
   À renouveler avant expiration :
   `GET https://graph.instagram.com/refresh_access_token?grant_type=ig_refresh_token&access_token=…`
   (facile à mettre dans un petit workflow n8n mensuel).
4. *Configure webhooks* :
   - Callback URL : `https://<notre-n8n>/webhook/instagram`
   - Verify token : la même valeur que `VERIFY_TOKEN` (nœuds **Config** et **Vérifier token**)
   - S'abonner aux champs **`comments`** et **`messages`**.
5. Dans l'app Instagram du compte : *Paramètres → Confidentialité → Messages →
   Outils connectés* → autoriser l'accès aux messages.
6. Permissions : `instagram_business_basic`, `instagram_business_manage_messages`,
   `instagram_business_manage_comments`. En **mode développement**, seuls les comptes ayant un
   rôle sur l'app déclenchent les webhooks → parfait pour tester. Pour le public :
   **App Review** de Meta + vérification de l'entreprise (compter quelques jours).

> Règles Meta à connaître : 1 seul DM « private reply » par commentaire (moins de 7 jours) ;
> ensuite la conversation est ouverte 24 h après chaque message du prospect. Ne pas envoyer
> de messages non sollicités. Le workflow envoie 1 DM max par personne et par post.

## 3. Importer les workflows n8n

*Workflows → Import from file* pour chacun des 3 JSON, puis :

| Credential à créer | Type n8n | Valeur |
|---|---|---|
| `Instagram Token (Bearer)` | Header Auth | Name `Authorization`, Value `Bearer <token Instagram>` |
| `Monday account` | Monday.com API | (existant) |
| `Anthropic account` | Anthropic | clé API Claude |
| `Slack account` | Slack | (existant) |
| `MCP PlugKit token` | Bearer Auth | un secret long aléatoire |

**Workflow 01** — ouvrir le nœud **Config** et remplir : `VERIFY_TOKEN`, `RULES_BOARD_ID`,
`LEADS_BOARD_ID`, `LEADS_GROUP_ID`, `BRAND`, et surtout **`BRAND_CONTEXT`** (formations, campus,
dates, prix, liens : c'est la seule source de vérité de l'IA, elle n'invente rien en dehors).
`LEAD_COLUMNS` force `statut8__1 = Lead ❄️` à la création (cf. `../FIX_leads_passent_en_abandon.md`).
Dans **Lead détecté ?**, vérifier les ids des colonnes email/téléphone du board Leads.
Puis **activer** le workflow (le dédoublonnage et la pause IA utilisent les données
statiques, qui ne sont persistées qu'en exécution de production).

**Workflow 02 (MCP)** — activer, puis connecter le client :
- Claude Code :
  ```bash
  claude mcp add --transport http plugkit https://<notre-n8n>/mcp/plugkit-instagram --header "Authorization: Bearer <secret>"
  ```
- Claude.ai / ChatGPT : *Connecteurs → Ajouter un connecteur personnalisé* avec l'URL MCP
  (si le client ne gère pas d'en-tête, mettre l'authentification du nœud sur *None* et utiliser
  un `path` long et secret).

Exemples ensuite : « Quels sont mes 5 reels qui ont le mieux marché ce mois-ci ? »,
« Montre-moi les commentaires du dernier post et propose des réponses ».

**Workflow 03** — choisir le canal Slack dans **Envoyer Slack**, activer.

## 4. Publication multi-réseaux : Postiz

[Postiz](https://github.com/gitroomhq/postiz-app) (open source) fait le calendrier, la
programmation et les stats sur 28+ réseaux, et expose une API publique **et un serveur MCP**.

1. Auto-héberger (Docker) ou utiliser Postiz Cloud ; connecter les comptes (Instagram, TikTok,
   LinkedIn, YouTube…).
2. *Réglages → API publique* : récupérer la clé API et l'URL MCP, l'ajouter comme connecteur
   dans Claude / ChatGPT → « programme ce reel jeudi 18 h sur Insta et TikTok ».
3. En ligne de commande (utilisé par le skill `/reel`) :
   ```bash
   npm install -g postiz
   ```
   ```bash
   export POSTIZ_API_KEY=...
   ```
   ```bash
   postiz posts:create -c "Légende" -m "$(postiz upload reel.mp4 | jq -r .path)" -s "2026-11-20T17:00:00Z" -i "<id-instagram>"
   ```

## 5. Rushs → reels (`reels/make_reel.py`)

```bash
pip install -r reels/requirements.txt
```
```bash
python3 reels/make_reel.py rush1.mp4 rush2.mov -o reel.mp4 --fond crop --accroche "3 erreurs en prépa" --srt
```

1. assemble les rushs ; 2. **coupe les silences** ; 3. transcrit en local avec Whisper
(gratuit, aucune donnée envoyée) ; 4. incruste des **sous-titres mot par mot** (mot prononcé
surligné) et le titre d'accroche ; 5. sort un MP4 **1080×1920**, son normalisé pour les réseaux.
`--fond flou` garde toute l'image (vidéo horizontale) sur fond flouté. `--srt` exporte les
sous-titres (`.ass`) pour corriger un nom propre puis relancer.

Dans **Claude Code**, ouvert sur ce repo : taper `/reel` (ou « fais-moi un reel avec ces rushs »).
Claude monte la vidéo, vérifie le rendu, propose une légende avec le bon mot-clé, puis
programme le reel via Postiz après confirmation.

## Limites / à faire ensuite

- Facebook Messenger / commentaires Facebook : même logique (webhook `page`), à ajouter si besoin.
- Les commentaires TikTok / LinkedIn n'ont pas d'API d'auto-DM ouverte comme Instagram.
- Sécurité : vérifier la signature `X-Hub-Signature-256` de Meta (nécessite le corps brut du
  webhook + le secret de l'app).
- `workflows/_build_workflows.py` régénère les 3 JSON (modifier le script plutôt que les JSON).
