// Verify X-Hub-Signature-256 on the raw body, then flatten the payload into events.
const crypto = require('crypto');
const item = $input.first();
const headers = item.json.headers || {};
const sig = headers['x-hub-signature-256'] || '';
const secret = $env.META_APP_SECRET || '';
let raw;
if (item.binary && item.binary.data) {
  raw = await this.helpers.getBinaryDataBuffer(0, 'data');
} else {
  raw = Buffer.from(JSON.stringify(item.json.body || {}));
}
const mac = 'sha256=' + crypto.createHmac('sha256', secret).update(raw).digest('hex');
const a = Buffer.from(mac), b = Buffer.from(sig);
const ok = !!secret && a.length === b.length && crypto.timingSafeEqual(a, b);
let body = {};
try { body = JSON.parse(raw.toString('utf8')); } catch (e) { return [{ json: { ok: false } }]; }
if (!ok) return [{ json: { ok: false } }];
return [{ json: { ok: true, body } }];
