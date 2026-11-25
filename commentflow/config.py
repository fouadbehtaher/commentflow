import os
from dataclasses import dataclass, field


@dataclass
class Config:
    graph_base: str = "https://graph.facebook.com/v21.0"
    page_id: str = ""
    ig_id: str = ""
    page_token: str = ""
    app_secret: str = ""
    verify_token: str = ""
    db_path: str = "commentflow.db"
    rules_file: str = "examples/rules.json"
    rules_source: str = "file"  # file | notion
    notion_token: str = ""
    notion_database_id: str = ""
    supabase_url: str = ""
    supabase_key: str = ""
    host: str = "127.0.0.1"
    port: int = 8080
    dry_run: bool = True

    @classmethod
    def from_env(cls):
        e = os.environ.get
        return cls(
            graph_base=e("GRAPH_BASE", cls.graph_base),
            page_id=e("FB_PAGE_ID", ""),
            ig_id=e("IG_ID", ""),
            page_token=e("PAGE_ACCESS_TOKEN", ""),
            app_secret=e("META_APP_SECRET", ""),
            verify_token=e("WEBHOOK_VERIFY_TOKEN", ""),
            db_path=e("DB_PATH", "commentflow.db"),
            rules_file=e("RULES_FILE", "examples/rules.json"),
            rules_source=e("RULES_SOURCE", "file"),
            notion_token=e("NOTION_TOKEN", ""),
            notion_database_id=e("NOTION_DATABASE_ID", ""),
            supabase_url=e("SUPABASE_URL", ""),
            supabase_key=e("SUPABASE_SERVICE_KEY", ""),
            host=e("HOST", "127.0.0.1"),
            port=int(e("PORT", "8080")),
            dry_run=e("DRY_RUN", "1") == "1",
        )
