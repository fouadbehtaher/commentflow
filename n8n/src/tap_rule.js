//@@common
const ev = $('Split events').item.json;
const rule = PARSE_RULE($input.first().json);
return [{ json: { ...ev, rule_id: rule.id, dm_text: rule.dm_text } }];
