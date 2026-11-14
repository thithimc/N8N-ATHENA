"""Génère les workflows n8n (JSON importables) de plugkit-maison."""
import json, uuid, pathlib

OUT = pathlib.Path(__file__).parent  # régénérer les JSON : python _build_workflows.py
GRAPH = "https://graph.instagram.com/v23.0"
IG_CRED = {"httpHeaderAuth": {"id": "REMPLACER", "name": "Instagram Token (Bearer)"}}
MONDAY_CRED = {"mondayComApi": {"id": "REMPLACER", "name": "Monday account"}}


class WF:
    def __init__(self, name):
        self.name, self.nodes, self.conn, self.x = name, [], {}, 0

    def add(self, name, type_, version, params, pos, **extra):
        n = {"parameters": params, "id": str(uuid.uuid4()), "name": name,
             "type": type_, "typeVersion": version, "position": pos}
        n.update(extra)
        self.nodes.append(n)
        return name

    def link(self, a, b, kind="main", out=0):
        outs = self.conn.setdefault(a, {}).setdefault(kind, [])
        while len(outs) <= out:
            outs.append([])
        outs[out].append({"node": b, "type": kind, "index": 0})

    def save(self, fname):
        data = {"name": self.name, "nodes": self.nodes, "connections": self.conn,
                "settings": {"executionOrder": "v1"}, "pinData": {}}
        (OUT / fname).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def code(js):
    return {"jsCode": js.strip() + "\n"}


def http_json(url, body_expr="={{ JSON.stringify($json.body) }}", cred="ig", method="POST"):
    p = {"method": method, "url": url, "sendBody": True, "specifyBody": "json",
         "jsonBody": body_expr, "options": {}}
    if cred == "ig":
        p.update(authentication="genericCredentialType", genericAuthType="httpHeaderAuth")
    else:
        p.update(authentication="predefinedCredentialType", nodeCredentialType="mondayComApi")
    return p


# ---------------------------------------------------------------- 01 webhook
w = WF("PlugKit maison — 01 Instagram : mots-clés → DM + agent IA")

CONFIG_JS = r"""
// ============ CONFIG — à adapter ============
return [{ json: {
  VERIFY_TOKEN: 'choisis-un-secret-long',          // même valeur que dans l'app Meta
  RULES_BOARD_ID: 1234567890,                       // board Monday « Automations DM »
  LEADS_BOARD_ID: 5090687714,                       // board où créer les leads
  LEADS_GROUP_ID: 'topics',                         // id du groupe (ex. « Leads contact »)
  // Colonnes posées à la création du lead. Toujours forcer le statut,
  // sinon Monday applique le défaut du groupe (cf. FIX_leads_passent_en_abandon.md).
  LEAD_COLUMNS: { statut8__1: { label: 'Lead ❄️' } },
  PAUSE_BOT_HOURS: 12,                              // pause de l'IA quand un humain répond
  BRAND: 'Mon école',
  BRAND_CONTEXT: `Formations proposées, campus, dates de rentrée, prix, lien d'inscription : à compléter.`,
  SLACK_CHANNEL: '#leads-instagram',
}}];
"""

NORMALIZE_JS = r"""
// Transforme le payload Meta en événements simples + applique les règles mots-clés.
const cfg = $('Config').first().json;
const body = $('Webhook Meta (POST)').first().json.body || {};
const store = $getWorkflowStaticData('global');
store.done ??= {};      // commentaires / couples user+post déjà traités
store.sentMids ??= [];  // ids des messages envoyés par le bot
store.paused ??= {};    // senderId -> timestamp de fin de pause
const now = Date.now();

// ---- Règles depuis Monday (colonnes lues par leur TITRE) ----
const items = $json.data?.boards?.[0]?.items_page?.items ?? [];
const col = (it, title) => (it.column_values.find(c => c.column?.title === title)?.text ?? '').trim();
const norm = s => (s || '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
const rules = items.map(it => ({
  keywords: it.name.split(',').map(k => norm(k.trim())).filter(Boolean),
  message: col(it, 'Message DM'),
  link: col(it, 'Lien'),
  publicReplies: col(it, 'Réponse publique').split('|').map(s => s.trim()).filter(Boolean),
  mediaId: col(it, 'Post ciblé (ID)'),
  active: !['non', 'off', 'inactif'].includes(norm(col(it, 'Actif'))),
})).filter(r => r.active && r.keywords.length && r.message);

const match = (text, mediaId) => {
  const t = ' ' + norm(text).replace(/[^a-z0-9]+/g, ' ') + ' ';
  return rules.find(r => (!r.mediaId || r.mediaId === mediaId)
    && r.keywords.some(k => t.includes(' ' + k.replace(/[^a-z0-9]+/g, ' ').trim() + ' '))) || null;
};

const out = [];
for (const entry of body.entry ?? []) {
  const igId = entry.id;

  // ---- Commentaires ----
  for (const ch of entry.changes ?? []) {
    if (ch.field !== 'comments') continue;
    const v = ch.value || {};
    if (!v.id || v.from?.id === igId) continue;             // ignore nos propres commentaires
    const rule = match(v.text, v.media?.id);
    if (!rule) continue;
    const key = `${v.from?.id}:${v.media?.id}`;             // 1 DM par personne et par post
    if (store.done[v.id] || store.done[key]) continue;
    store.done[v.id] = store.done[key] = now;
    out.push({ kind: 'comment', igId, commentId: v.id, mediaId: v.media?.id,
      userId: v.from?.id, username: v.from?.username, text: v.text, rule });
  }

  // ---- Messages privés ----
  for (const m of entry.messaging ?? []) {
    const msg = m.message;
    if (!msg || msg.is_deleted) continue;
    if (msg.is_echo) {
      // Echo d'un message qui n'a pas été envoyé par le bot = un humain a pris la main.
      if (!store.sentMids.includes(msg.mid)) store.paused[m.recipient.id] = now + cfg.PAUSE_BOT_HOURS * 3600e3;
      continue;
    }
    if (m.sender.id === igId || !msg.text) continue;
    if ((store.paused[m.sender.id] ?? 0) > now) continue;   // conversation gérée par un humain
    if (store.done[msg.mid]) continue;                      // événement renvoyé par Meta
    store.done[msg.mid] = now;
    const rule = match(msg.text, null);
    out.push({ kind: rule ? 'dm_keyword' : 'dm_ai', igId, senderId: m.sender.id,
      text: msg.text, mid: msg.mid, rule });
  }
}

// ménage : on garde 30 jours d'historique
for (const [k, t] of Object.entries(store.done)) if (now - t > 30 * 864e5) delete store.done[k];
store.sentMids = store.sentMids.slice(-500);

return out.map(json => ({ json }));
"""

RULES_QUERY = ("={{ JSON.stringify({ query: `query { boards(ids: [${$json.RULES_BOARD_ID}]) "
               "{ items_page(limit: 200) { items { id name column_values { column { title } text } } } } }` }) }}")

RECORD_MID_JS = r"""
const store = $getWorkflowStaticData('global');
store.sentMids ??= [];
for (const it of $input.all()) if (it.json.message_id) store.sentMids.push(it.json.message_id);
return $input.all();
"""

# GET : vérification du webhook par Meta
w.add("Webhook Meta (GET)", "n8n-nodes-base.webhook", 2,
      {"path": "instagram", "responseMode": "responseNode", "options": {}}, [0, -300],
      webhookId=str(uuid.uuid4()))
w.add("Vérifier token", "n8n-nodes-base.code", 2, code(r"""
const q = $json.query || {};
const VERIFY_TOKEN = 'choisis-un-secret-long'; // identique au nœud Config
if (q['hub.mode'] !== 'subscribe' || q['hub.verify_token'] !== VERIFY_TOKEN) throw new Error('Token invalide');
return [{ json: { challenge: q['hub.challenge'] } }];
"""), [220, -300])
w.add("Répondre challenge", "n8n-nodes-base.respondToWebhook", 1.1,
      {"respondWith": "text", "responseBody": "={{ $json.challenge }}", "options": {}}, [440, -300])
w.link("Webhook Meta (GET)", "Vérifier token")
w.link("Vérifier token", "Répondre challenge")

# POST : événements
w.add("Webhook Meta (POST)", "n8n-nodes-base.webhook", 2,
      {"httpMethod": "POST", "path": "instagram", "options": {}}, [0, 0], webhookId=str(uuid.uuid4()))
w.add("Config", "n8n-nodes-base.code", 2, code(CONFIG_JS), [220, 0])
w.add("Charger règles (Monday)", "n8n-nodes-base.httpRequest", 4.2,
      http_json("https://api.monday.com/v2", RULES_QUERY, cred="monday"), [440, 0], credentials=MONDAY_CRED)
w.add("Normaliser + matcher", "n8n-nodes-base.code", 2, code(NORMALIZE_JS), [660, 0])
w.link("Webhook Meta (POST)", "Config")
w.link("Config", "Charger règles (Monday)")
w.link("Charger règles (Monday)", "Normaliser + matcher")

# --- Branche A : commentaire avec mot-clé ---
w.add("→ Commentaires", "n8n-nodes-base.code", 2, code(r"""
return $input.all().filter(i => i.json.kind === 'comment').map(i => {
  const r = i.json.rule;
  const text = [r.message.replace('{prenom}', i.json.username || ''), r.link].filter(Boolean).join('\n\n');
  return { json: { ...i.json, body: { recipient: { comment_id: i.json.commentId }, message: { text } } } };
});
"""), [900, -200])
w.add("DM privé (private reply)", "n8n-nodes-base.httpRequest", 4.2,
      http_json(f"={GRAPH}/{{{{ $json.igId }}}}/messages"), [1120, -200],
      credentials=IG_CRED, onError="continueRegularOutput")
w.add("Préparer réponse publique", "n8n-nodes-base.code", 2, code(r"""
return $('→ Commentaires').all().filter(i => i.json.rule.publicReplies.length).map(i => {
  const opts = i.json.rule.publicReplies;               // plusieurs variantes = moins « spam »
  const message = opts[Math.floor(Math.random() * opts.length)].replace('{prenom}', '@' + (i.json.username || ''));
  return { json: { commentId: i.json.commentId, body: { message } } };
});
"""), [1340, -200])
w.add("Répondre au commentaire", "n8n-nodes-base.httpRequest", 4.2,
      http_json(f"={GRAPH}/{{{{ $json.commentId }}}}/replies"), [1560, -200],
      credentials=IG_CRED, onError="continueRegularOutput")
w.add("Préparer lead (commentaire)", "n8n-nodes-base.code", 2, code(r"""
const cfg = $('Config').first().json;
return $('→ Commentaires').all().map(i => {
  const name = `@${i.json.username} — ${i.json.rule.keywords[0].toUpperCase()} (Instagram)`;
  const query = `mutation ($b: ID!, $g: String, $n: String!, $c: JSON) {
    create_item(board_id: $b, group_id: $g, item_name: $n, column_values: $c) { id } }`;
  return { json: { body: { query, variables: { b: cfg.LEADS_BOARD_ID, g: cfg.LEADS_GROUP_ID, n: name,
    c: JSON.stringify(cfg.LEAD_COLUMNS) } } } };
});
"""), [1780, -200])
w.add("Créer lead Monday", "n8n-nodes-base.httpRequest", 4.2,
      http_json("https://api.monday.com/v2", cred="monday"), [2000, -200],
      credentials=MONDAY_CRED, onError="continueRegularOutput")
for a, b in [("Normaliser + matcher", "→ Commentaires"), ("→ Commentaires", "DM privé (private reply)"),
             ("DM privé (private reply)", "Préparer réponse publique"),
             ("Préparer réponse publique", "Répondre au commentaire"),
             ("DM privé (private reply)", "Préparer lead (commentaire)"),
             ("Préparer lead (commentaire)", "Créer lead Monday")]:
    w.link(a, b)

# --- Branche B : DM contenant un mot-clé ---
w.add("→ DM mot-clé", "n8n-nodes-base.code", 2, code(r"""
return $input.all().filter(i => i.json.kind === 'dm_keyword').map(i => {
  const r = i.json.rule;
  return { json: { ...i.json, body: { recipient: { id: i.json.senderId },
    message: { text: [r.message.replace('{prenom}', ''), r.link].filter(Boolean).join('\n\n') } } } };
});
"""), [900, 0])
w.add("Envoyer DM (mot-clé)", "n8n-nodes-base.httpRequest", 4.2,
      http_json(f"={GRAPH}/{{{{ $json.igId }}}}/messages"), [1120, 0], credentials=IG_CRED)
w.add("Mémoriser envoi", "n8n-nodes-base.code", 2, code(RECORD_MID_JS), [1340, 0])
w.link("Normaliser + matcher", "→ DM mot-clé")
w.link("→ DM mot-clé", "Envoyer DM (mot-clé)")
w.link("Envoyer DM (mot-clé)", "Mémoriser envoi")

# --- Branche C : DM libre → agent IA ---
w.add("→ DM pour IA", "n8n-nodes-base.code", 2,
      code("return $input.all().filter(i => i.json.kind === 'dm_ai');"), [900, 250])
w.add("Agent IA", "@n8n/n8n-nodes-langchain.agent", 1.7, {
    "promptType": "define", "text": "={{ $json.text }}",
    "options": {"systemMessage": (
        "=Tu réponds aux messages privés Instagram de {{ $('Config').first().json.BRAND }}.\n"
        "Contexte (seule source de vérité) :\n{{ $('Config').first().json.BRAND_CONTEXT }}\n\n"
        "Règles :\n"
        "- Réponds en français, ton chaleureux, 2 à 4 phrases max, pas de markdown.\n"
        "- N'invente jamais un prix, une date ou une info absente du contexte : propose plutôt un échange avec l'équipe.\n"
        "- Objectif : qualifier (formation visée, ville/campus, niveau) puis demander email ou téléphone pour être recontacté.\n"
        "- Si la personne demande un humain, est mécontente, ou si tu ne sais pas : termine ta réponse par [HUMAIN].")}},
    [1120, 250])
w.add("Claude", "@n8n/n8n-nodes-langchain.lmChatAnthropic", 1.3, {
    "model": {"__rl": True, "value": "claude-sonnet-5-5", "mode": "id"},
    "options": {"maxTokensToSample": 400, "temperature": 0.4}}, [1040, 470],
    credentials={"anthropicApi": {"id": "REMPLACER", "name": "Anthropic account"}})
w.add("Mémoire conversation", "@n8n/n8n-nodes-langchain.memoryBufferWindow", 1.3, {
    "sessionIdType": "customKey", "sessionKey": "={{ 'ig-' + $('→ DM pour IA').item.json.senderId }}",
    "contextWindowLength": 12}, [1200, 470])
w.add("Préparer réponse IA", "n8n-nodes-base.code", 2, code(r"""
return $input.all().map((i, idx) => {
  const src = $('→ DM pour IA').all()[idx].json;
  const raw = String(i.json.output || '');
  const handoff = raw.includes('[HUMAIN]');
  const text = raw.replace('[HUMAIN]', '').trim().slice(0, 990) || "Merci pour ton message, quelqu'un de l'équipe te répond très vite !";
  return { json: { ...src, handoff, reply: text,
    body: { recipient: { id: src.senderId }, message: { text } } } };
});
"""), [1340, 250])
w.add("Envoyer DM (IA)", "n8n-nodes-base.httpRequest", 4.2,
      http_json(f"={GRAPH}/{{{{ $json.igId }}}}/messages"), [1560, 250], credentials=IG_CRED)
w.add("Mémoriser envoi IA", "n8n-nodes-base.code", 2, code(RECORD_MID_JS), [1780, 250])
w.add("Lead détecté ?", "n8n-nodes-base.code", 2, code(r"""
// Si la personne donne un email ou un téléphone → création du lead dans Monday.
const cfg = $('Config').first().json;
const out = [];
for (const i of $('Préparer réponse IA').all()) {
  const t = i.json.text;
  const email = t.match(/[\w.+-]+@[\w-]+\.[\w.-]+/)?.[0];
  const phone = t.match(/(?:\+33|0)\s?[1-9](?:[\s.-]?\d{2}){4}/)?.[0];
  if (!email && !phone) continue;
  const cols = { ...cfg.LEAD_COLUMNS };
  if (email) cols.e_mail__1 = { email, text: email };        // ids de colonnes du board Leads
  if (phone) cols.phone = { phone: phone.replace(/\D/g, ''), countryShortName: 'FR' };
  const query = `mutation ($b: ID!, $g: String, $n: String!, $c: JSON) {
    create_item(board_id: $b, group_id: $g, item_name: $n, column_values: $c, create_labels_if_missing: true) { id } }`;
  out.push({ json: { body: { query, variables: { b: cfg.LEADS_BOARD_ID, g: cfg.LEADS_GROUP_ID,
    n: `${email || phone} (DM Instagram)`, c: JSON.stringify(cols) } } } });
}
return out;
"""), [2000, 150])
w.add("Créer lead Monday (DM)", "n8n-nodes-base.httpRequest", 4.2,
      http_json("https://api.monday.com/v2", cred="monday"), [2220, 150],
      credentials=MONDAY_CRED, onError="continueRegularOutput")
w.add("Escalade humaine ?", "n8n-nodes-base.code", 2, code(r"""
const cfg = $('Config').first().json;
const store = $getWorkflowStaticData('global');
store.paused ??= {};
return $('Préparer réponse IA').all().filter(i => i.json.handoff).map(i => {
  store.paused[i.json.senderId] = Date.now() + cfg.PAUSE_BOT_HOURS * 3600e3; // l'IA se tait
  return { json: { text: `🙋 Un prospect Instagram demande un humain.\nMessage : « ${i.json.text} »\nRéponds-lui directement dans la boîte Instagram (l'IA est en pause ${cfg.PAUSE_BOT_HOURS} h pour lui).` } };
});
"""), [2000, 350])
w.add("Alerte Slack", "n8n-nodes-base.slack", 2.3, {
    "select": "channel",
    "channelId": {"__rl": True, "value": "={{ $('Config').first().json.SLACK_CHANNEL }}", "mode": "name"},
    "text": "={{ $json.text }}", "otherOptions": {}}, [2220, 350],
    credentials={"slackApi": {"id": "REMPLACER", "name": "Slack account"}}, onError="continueRegularOutput")
w.link("Normaliser + matcher", "→ DM pour IA")
w.link("→ DM pour IA", "Agent IA")
w.link("Claude", "Agent IA", kind="ai_languageModel")
w.link("Mémoire conversation", "Agent IA", kind="ai_memory")
w.link("Agent IA", "Préparer réponse IA")
w.link("Préparer réponse IA", "Envoyer DM (IA)")
w.link("Envoyer DM (IA)", "Mémoriser envoi IA")
w.link("Mémoriser envoi IA", "Lead détecté ?")
w.link("Lead détecté ?", "Créer lead Monday (DM)")
w.link("Mémoriser envoi IA", "Escalade humaine ?")
w.link("Escalade humaine ?", "Alerte Slack")
w.save("01_instagram_mots_cles_dm_ia.json")

# ---------------------------------------------------------------- 02 MCP
m = WF("PlugKit maison — 02 Serveur MCP Instagram (pour Claude / ChatGPT)")
m.add("MCP Server", "@n8n/n8n-nodes-langchain.mcpTrigger", 2,
      {"path": "plugkit-instagram", "authentication": "bearerAuth"}, [0, 0],
      webhookId=str(uuid.uuid4()),
      credentials={"httpBearerAuth": {"id": "REMPLACER", "name": "MCP PlugKit token"}})


def tool(name, desc, method, url, query=None, pos=(0, 0)):
    p = {"toolDescription": desc, "method": method, "url": url,
         "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth", "options": {}}
    if query:
        p["sendQuery"] = True
        p["queryParameters"] = {"parameters": [{"name": k, "value": v} for k, v in query]}
    m.add(name, "n8n-nodes-base.httpRequestTool", 4.2, p, list(pos), credentials=IG_CRED)
    m.link(name, "MCP Server", kind="ai_tool")


tool("ig_stats_compte", "Statistiques du compte Instagram sur les N derniers jours (max 30) : portée, vues, interactions, comptes engagés, abonnés gagnés.",
     "GET", f"{GRAPH}/me/insights", [
         ("metric", "reach,views,total_interactions,accounts_engaged,follows_and_unfollows"),
         ("metric_type", "total_value"), ("period", "day"),
         ("since", "={{ Math.floor(Date.now()/1000) - Math.min(30, $fromAI('jours', 'Nombre de jours à analyser (1-30)', 'number')) * 86400 }}"),
         ("until", "={{ Math.floor(Date.now()/1000) }}")], (-400, 250))
tool("ig_derniers_posts", "Liste les derniers posts/reels Instagram avec likes, commentaires, lien et date. Utile pour récupérer un media_id.",
     "GET", f"{GRAPH}/me/media", [
         ("fields", "id,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count"),
         ("limit", "={{ $fromAI('limite', 'Nombre de posts (1-50)', 'number') }}")], (-200, 250))
tool("ig_stats_post", "Statistiques détaillées d'un post ou reel (vues, portée, partages, enregistrements).",
     "GET", f"{GRAPH}/{{{{ $fromAI('media_id', 'ID du media Instagram', 'string') }}}}/insights", [
         ("metric", "views,reach,likes,comments,shares,saved,total_interactions")], (0, 250))
tool("ig_commentaires", "Liste les commentaires d'un post (id, texte, auteur, date).",
     "GET", f"{GRAPH}/{{{{ $fromAI('media_id', 'ID du media Instagram', 'string') }}}}/comments", [
         ("fields", "id,text,username,timestamp,replies{id,text,username}"), ("limit", "50")], (200, 250))
tool("ig_repondre_commentaire", "Publie une réponse publique sous un commentaire. Toujours montrer le texte à l'utilisateur et attendre sa validation avant d'appeler cet outil.",
     "POST", f"{GRAPH}/{{{{ $fromAI('comment_id', 'ID du commentaire', 'string') }}}}/replies", [
         ("message", "={{ $fromAI('message', 'Texte de la réponse', 'string') }}")], (400, 250))
m.save("02_mcp_server_instagram.json")

# ---------------------------------------------------------------- 03 rapport hebdo
r = WF("PlugKit maison — 03 Rapport hebdo Instagram → Slack")
r.add("Chaque lundi 9h", "n8n-nodes-base.scheduleTrigger", 1.2, {
    "rule": {"interval": [{"field": "weeks", "triggerAtDay": [1], "triggerAtHour": 9}]}}, [0, 0])
r.add("Stats compte (7 j)", "n8n-nodes-base.httpRequest", 4.2, {
    "url": f"{GRAPH}/me/insights", "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
    "sendQuery": True, "queryParameters": {"parameters": [
        {"name": "metric", "value": "reach,views,total_interactions,accounts_engaged,follows_and_unfollows"},
        {"name": "metric_type", "value": "total_value"}, {"name": "period", "value": "day"},
        {"name": "since", "value": "={{ Math.floor(Date.now()/1000) - 7*86400 }}"},
        {"name": "until", "value": "={{ Math.floor(Date.now()/1000) }}"}]}, "options": {}},
    [220, 0], credentials=IG_CRED)
r.add("Posts récents", "n8n-nodes-base.httpRequest", 4.2, {
    "url": f"{GRAPH}/me/media", "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
    "sendQuery": True, "queryParameters": {"parameters": [
        {"name": "fields", "value": "id,caption,media_product_type,permalink,timestamp,like_count,comments_count"},
        {"name": "limit", "value": "25"}]}, "options": {}}, [440, 0], credentials=IG_CRED)
r.add("Mettre en forme", "n8n-nodes-base.code", 2, code(r"""
const stats = $('Stats compte (7 j)').first().json.data ?? [];
const val = n => stats.find(s => s.name === n)?.total_value?.value ?? 'n/d';
const fu = stats.find(s => s.name === 'follows_and_unfollows')?.total_value?.breakdowns?.[0]?.results ?? [];
const weekAgo = Date.now() - 7 * 864e5;
const posts = ($json.data ?? []).filter(p => new Date(p.timestamp) > weekAgo)
  .sort((a, b) => (b.like_count + b.comments_count) - (a.like_count + a.comments_count));
const lines = posts.slice(0, 3).map((p, i) =>
  `${i + 1}. ${(p.caption || '(sans légende)').split('\n')[0].slice(0, 60)} — ❤️ ${p.like_count} 💬 ${p.comments_count} <${p.permalink}|voir>`);
const text = [
  '*📊 Instagram — 7 derniers jours*',
  `Portée : *${val('reach')}* · Vues : *${val('views')}* · Interactions : *${val('total_interactions')}*`,
  `Comptes engagés : *${val('accounts_engaged')}* · Abonnés : ${fu.map(r => `${r.dimension_values?.[0]}: ${r.value}`).join(' / ') || 'n/d'}`,
  `Posts publiés : *${posts.length}*`,
  lines.length ? '*Top posts :*\n' + lines.join('\n') : '',
].filter(Boolean).join('\n');
return [{ json: { text } }];
"""), [660, 0])
r.add("Envoyer Slack", "n8n-nodes-base.slack", 2.3, {
    "select": "channel", "channelId": {"__rl": True, "value": "#social", "mode": "name"},
    "text": "={{ $json.text }}", "otherOptions": {}}, [880, 0],
    credentials={"slackApi": {"id": "REMPLACER", "name": "Slack account"}})
for a, b in [("Chaque lundi 9h", "Stats compte (7 j)"), ("Stats compte (7 j)", "Posts récents"),
             ("Posts récents", "Mettre en forme"), ("Mettre en forme", "Envoyer Slack")]:
    r.link(a, b)
r.save("03_rapport_hebdo_slack.json")
print("ok")
