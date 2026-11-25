//@@common
const t = $('Tap rule').item.json;
const follows = !!$input.first().json.is_user_follow_business;
return [{ json: { igsid: t.igsid, rule_id: t.rule_id, follows,
  dm: follows ? { text: t.dm_text } : FOLLOW_PROMPT(t.rule_id, false),
  log_kind: follows ? 'dm_sent' : 'follow_missing' } }];
