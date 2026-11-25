// Pick the rule for this comment. Rows come from the Notion query; permalink from Graph.
//@@common
const ev = $('Split events').item.json;
const permalink = ($('Media permalink').item.json.permalink) || '';
const rows = ($('Notion rules').first().json.results || []).map(PARSE_RULE).filter(r => r.active);
const code = SHORTCODE(permalink);
const rule = rows.find(r => {
  const hit = (r.media_id && r.media_id === ev.media_id) || (code && SHORTCODE(r.post_url) === code);
  return hit && (!r.keyword || ev.text.toLowerCase().includes(r.keyword.toLowerCase()));
});
if (!rule) return [];
const reply = rule.replies.length ? rule.replies[Math.floor(Math.random() * rule.replies.length)] : '';
const private_body = rule.require_follow ? FOLLOW_PROMPT(rule.id, true) : { text: rule.dm_text };
return [{ json: { ...ev, rule_id: rule.id, reply, private_body, require_follow: rule.require_follow } }];
