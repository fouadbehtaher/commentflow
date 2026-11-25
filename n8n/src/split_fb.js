// Flatten Facebook Page "feed" webhook into new-comment events.
const body = $input.first().json.body || {};
const page = $env.FB_PAGE_ID || '';
const out = [];
for (const entry of body.entry || []) {
  for (const ch of entry.changes || []) {
    const v = ch.value || {};
    if (ch.field !== 'feed' || v.item !== 'comment' || v.verb !== 'add') continue;
    const from = v.from || {};
    if (!v.comment_id || from.id === page) continue;
    out.push({ json: { kind: 'comment', comment_id: v.comment_id, text: v.message || '', igsid: from.id || '', username: from.name || '', media_id: v.post_id || '' } });
  }
}
return out;
