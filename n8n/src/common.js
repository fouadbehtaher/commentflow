// Shared helpers are inlined into each Code node by build.py (n8n Code nodes cannot import local files).
const NOTION_TXT = (p) => !p ? '' : ((p.title || p.rich_text || []).map(x => x.plain_text || '').join(''));
const PARSE_RULE = (page) => {
  const p = page.properties || {};
  return {
    id: page.id,
    media_id: NOTION_TXT(p['Media ID']).trim(),
    post_url: (p['Post URL'] && p['Post URL'].url) || '',
    keyword: NOTION_TXT(p['Keyword']).trim(),
    replies: [1, 2, 3].map(i => NOTION_TXT(p['Reply ' + i]).trim()).filter(Boolean),
    dm_text: NOTION_TXT(p['DM']),
    require_follow: !!(p['Require follow'] && p['Require follow'].checkbox),
    active: p['Active'] ? !!p['Active'].checkbox : true,
  };
};
const SHORTCODE = (u) => { const m = /\/(?:p|reel|reels|tv)\/([^\/?#]+)/.exec(u || ''); return m ? m[1] : ''; };
const FOLLOW_PROMPT = (rule_id, first) => ({
  text: first ? 'Thanks for commenting! Follow this account first, then tap the button and I will send it.'
              : 'I cannot see the follow yet. Follow the account, wait a few seconds, then tap again.',
  quick_replies: [{ content_type: 'text', title: 'I followed', payload: 'CF_FOLLOWED:' + rule_id }],
});
