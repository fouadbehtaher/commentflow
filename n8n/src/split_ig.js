// Flatten Instagram webhook payload into comment and button-tap events.
const body = $input.first().json.body || {};
const ig = $env.IG_ID || '';
const out = [];
for (const entry of body.entry || []) {
  for (const ch of entry.changes || []) {
    if (ch.field !== 'comments') continue;
    const v = ch.value || {};
    const from = v.from || {};
    if (!v.id || from.id === ig) continue;           // ignore own comments (loop guard)
    out.push({ json: { kind: 'comment', comment_id: v.id, text: v.text || '', igsid: from.id || '', username: from.username || '', media_id: (v.media || {}).id || '' } });
  }
  for (const ev of entry.messaging || []) {
    const igsid = (ev.sender || {}).id || '';
    if (igsid === ig) continue;
    const payload = (((ev.message || {}).quick_reply || {}).payload) || ((ev.postback || {}).payload) || '';
    if (payload.startsWith('CF_FOLLOWED:')) out.push({ json: { kind: 'tap', igsid, rule_id: payload.slice(12) } });
  }
}
return out;
