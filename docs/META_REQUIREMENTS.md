# Meta requirements (checked against Meta's docs, Nov 2026)

- Private reply to a comment: `POST /<PAGE_ID>/messages` with `recipient.comment_id`. One message per comment, within 7 days. It lands in Inbox if the commenter follows the account, otherwise in Requests. Needs Advanced Access, `instagram_manage_comments` and `pages_messaging`, and a Page token from someone with the MESSAGING task on the linked Page. Standard Access only works for people with a role on the app.
  https://developers.facebook.com/docs/messenger-platform/instagram/features/private-replies
- Webhooks: the app must be Live. Advanced Access for `comments`; Meta's webhook page lists Business Verification as required for the access tiers.
  https://developers.facebook.com/documentation/instagram-platform/webhooks.md
- Follow check: the User Profile API returns `is_user_follow_business` for an IGSID, but only after the person has messaged the account or tapped a button. A comment alone is not consent. This is why the follow gate is a tap-to-confirm button, not a silent check at comment time.
  https://developers.facebook.com/docs/messenger-platform/instagram/features/user-profile/
- Until app review passes, test only with accounts that have a role on your app (admin, developer, tester).

## Costs
Meta API: no charge. Supabase Free: $0, 500 MB, paused after 1 week of inactivity (https://supabase.com/pricing). Notion API: free, 180 requests/min on non-Business plans (https://developers.notion.com/skill.md). Hosting: needs a public HTTPS URL; local run needs a tunnel; a small VPS is the only paid item.
