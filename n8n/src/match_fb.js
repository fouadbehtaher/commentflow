// Facebook has no documented follow check. A rule with require_follow is NOT sent (fails closed);
// the workflow logs it as blocked_require_follow and sends nothing.
//@@common
const ev = $('Split events').item.json;
const rows = ($input.first().json.results || []).map(PARSE_RULE).filter(r => r.active);
const rule = rows.find(r => r.media_id && (r.media_id === ev.media_id || ev.media_id.endsWith('_' + r.media_id))
  && (!r.keyword || ev.text.toLowerCase().includes(r.keyword.toLowerCase())));
if (!rule) return [];
const reply = rule.replies.length ? rule.replies[Math.floor(Math.random() * rule.replies.length)] : '';
return [{ json: { ...ev, rule_id: rule.id, reply, private_body: { text: rule.dm_text }, require_follow: rule.require_follow } }];
