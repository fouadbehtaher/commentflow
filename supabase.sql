create table if not exists events (
  id bigint generated always as identity primary key,
  created_at timestamptz default now(),
  kind text not null,
  comment_id text, igsid text, username text, rule_id text, detail text
);
alter table events enable row level security;  -- the service key bypasses RLS; nothing else can read it

-- used by the n8n workflows (dedupe key + event log)
create table if not exists comments (
  comment_id text primary key,
  created_at timestamptz default now(),
  igsid text, username text, rule_id text
);
alter table comments enable row level security;
