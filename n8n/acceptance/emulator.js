// Minimal n8n workflow emulator. Runs the REAL generated workflow JSON (Code node JS, expressions,
// IF routing, HTTP node params, connections) and serves /webhook/<path> like n8n does.
// It is NOT n8n: use it when n8n cannot be installed (needs ~3GB RAM to install). Real n8n: run_acceptance.sh.
const http = require('http'), fs = require('fs'), path = require('path');
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
const wfs = process.argv.slice(2).map(f => JSON.parse(fs.readFileSync(f, 'utf8')));
const routes = {};
for (const wf of wfs) for (const n of wf.nodes)
  if (n.type === 'n8n-nodes-base.webhook') routes[n.parameters.httpMethod + ' ' + n.parameters.path] = { wf, node: n };

async function expr(s, ctx) {
  if (typeof s !== 'string' || !s.startsWith('=')) return s;
  s = s.slice(1);
  const run = (e) => new AsyncFunction('$json', '$env', '$', 'return (' + e + ')')(ctx.json, process.env, ctx.dollar);
  const m = /^\{\{([\s\S]*)\}\}$/.exec(s.trim());
  if (m && !/\}\}[\s\S]*\{\{/.test(m[1])) return await run(m[1]);
  let out = '', last = 0; const re = /\{\{([\s\S]*?)\}\}/g; let x;
  while ((x = re.exec(s))) { out += s.slice(last, x.index) + String(await run(x[1])); last = re.lastIndex; }
  return out + s.slice(last);
}

async function runFlow(wf, startNode, items, raw, respond) {
  const byName = Object.fromEntries(wf.nodes.map(n => [n.name, n]));
  const last = {};
  const dollar = (name) => ({ item: { json: (last[name] || {}) }, first: () => ({ json: last[name] || {} }) });
  async function exec(name, item) {
    const n = byName[name]; const t = n.type.split('.').pop(); const ctx = { json: item, dollar };
    let outs; // array of arrays of items per output
    if (t === 'webhook') outs = [[item]];
    else if (t === 'code') {
      const helpers = { getBinaryDataBuffer: async () => raw };
      const fn = new AsyncFunction('$input', '$', '$env', 'require', n.parameters.jsCode);
      const input = { first: () => ({ json: item, binary: { data: {} } }), all: () => [{ json: item }] };
      const r = await fn.call({ helpers }, input, dollar, process.env, require);
      outs = [(r || []).map(i => i.json)];
    } else if (t === 'set') {
      const o = n.parameters.includeOtherFields ? { ...item } : {};
      for (const a of n.parameters.assignments.assignments) o[a.name] = await expr(a.value, ctx);
      outs = [[o]];
    } else if (t === 'if') {
      const c = n.parameters.conditions.conditions[0];
      const v = await expr(c.leftValue, ctx);
      outs = v ? [[item], []] : [[], [item]];
    } else if (t === 'respondToWebhook') {
      respond && respond(Number(await expr(n.parameters.options.responseCode, ctx)), String(await expr(n.parameters.responseBody, ctx)));
      outs = [[item]];
    } else if (t === 'httpRequest') {
      const p = n.parameters; const h = { 'Content-Type': 'application/json' };
      for (const hp of (p.headerParameters || {}).parameters || []) h[hp.name] = await expr(hp.value, ctx);
      if (p.authentication === 'genericCredentialType') {   // Header Auth credential, supplied via CRED_MAP in tests
        const c = JSON.parse(process.env.CRED_MAP || '{}')[((n.credentials || {})[p.genericAuthType] || {}).name];
        if (!c) throw new Error('credential not provided for ' + n.name);
        h[c.name] = c.value;
      }
      const opts = { method: p.method, headers: h };
      if (p.sendBody) opts.body = JSON.stringify(await expr(p.jsonBody, ctx));
      try {
        const res = await fetch(await expr(p.url, ctx), opts);
        const txt = await res.text(); if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = txt ? JSON.parse(txt) : {};
        outs = [Array.isArray(data) ? data : [data]];
      } catch (e) {
        if (n.onError !== 'continueRegularOutput') throw e;
        outs = [[{ error: { message: String(e.message) } }]];
      }
    } else throw new Error('unsupported node ' + n.type);
    const conns = (wf.connections[name] || {}).main || [];
    for (let o = 0; o < conns.length; o++)
      for (const out of outs[o] || []) {
        last[name] = out;
        for (const c of conns[o]) await exec(c.node, out);
      }
  }
  for (const it of items) await exec(startNode, it);
}

http.createServer((req, res) => {
  const u = new URL(req.url, 'http://x'); const key = req.method + ' ' + u.pathname.replace(/^\/webhook\//, '');
  const route = routes[key];
  const chunks = []; req.on('data', c => chunks.push(c));
  req.on('end', async () => {
    if (!route) { res.writeHead(404); return res.end(); }
    let answered = false;
    const respond = (code, body) => { if (!answered) { answered = true; res.writeHead(code); res.end(body); } };
    const raw = Buffer.concat(chunks);
    let body = {}; try { body = JSON.parse(raw.toString() || '{}'); } catch (e) {}
    const query = Object.fromEntries(u.searchParams);
    try { await runFlow(route.wf, route.node.name, [{ headers: req.headers, query, body }], raw, respond); }
    catch (e) { console.error('flow error', e.message); respond(500, 'error'); }
    respond(200, '');
  });
}).listen(5679, '127.0.0.1', () => console.log('emulator on 5679'));
