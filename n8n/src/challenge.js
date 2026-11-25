const q = $input.first().json.query || {};
const good = q['hub.mode'] === 'subscribe' && $env.WEBHOOK_VERIFY_TOKEN && q['hub.verify_token'] === $env.WEBHOOK_VERIFY_TOKEN;
return [{ json: { ok: !!good, challenge: good ? String(q['hub.challenge'] || '') : 'forbidden' } }];
