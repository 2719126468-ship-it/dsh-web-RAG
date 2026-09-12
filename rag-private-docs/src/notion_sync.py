"""Notion sync (optional).

Pulls pages from a Notion database, converts them to Markdown,
saves them under docs/notion/, and returns the list of files
so the indexer can pick them up.

Setup:
  1. Create a Notion integration at https://www.notion.so/my-integrations
  2. Share your target database with the integration
  3. Copy the integration secret to .env as NOTION_API_KEY=secret_xxx
  4. Copy the database id (from the URL) to .env as NOTION_DATABASE_ID=xxx
  5. Run: python src/notion_sync.py

Note: Requires the `notion-client` package (install separately if needed).
"""
import os
import sys
from pathlib import Path
from typing import List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTION_DIR = PROJECT_ROOT / "docs" / "notion"


def _to_markdown(block) -> str:
    """Convert a single Notion block to a Markdown line."""
    btype = block.get("type", "")
    if btype == "paragraph":
        text = "".join(
            t.get("plain_text", "") for t in block["paragraph"].get("rich_text", [])
        )
        return text
    if btype == "heading_1":
        text = "".join(t.get("plain_text", "") for t in block["heading_1"]["rich_text"])
        return f"# {text}"
    if btype == "heading_2":
        text = "".join(t.get("plain_text", "") for t in block["heading_2"]["rich_text"])
        return f"## {text}"
    if btype == "heading_3":
        text = "".join(t.get("plain_text", "") for t in block["heading_3"]["rich_text"])
        return f"### {text}"
    if btype == "bulleted_list_item":
        text = "".join(t.get("plain_text", "") for t in block["bulleted_list_item"]["rich_text"])
        return f"- {text}"
    if btype == "numbered_list_item":
        text = "".join(t.get("plain_text", "") for t in block["numbered_list_item"]["rich_text"])
        return f"1. {text}"
    if btype == "code":
        text = "".join(t.get("plain_text", "") for t in block["code"]["rich_text"])
        lang = block["code"].get("language", "")
        return f"```{lang}\n{text}\n```"
    if btype == "quote":
        text = "".join(t.get("plain_text", "") for t in block["quote"]["rich_text"])
        return f"> {text}"
    if btype == "to_do":
        text = "".join(t.get("plain_text", "") for t in block["to_do"]["rich_text"])
        checked = "x" if block["to_do"].get("checked") else " "
        return f"- [{checked}] {text}"
    if btype == "divider":
        return "---"
    return ""


def page_to_markdown(page: dict) -> str:
    """Convert a Notion page dict to a Markdown string."""
    title = "Untitled"
    if "properties" in page:
        for prop in page["properties"].values():
            if prop.get("type") == "title":
                title = "".join(
                    t.get("plain_text", "") for t in prop.get("title", [])
                )
                break
    blocks = page.get("_blocks", [])
    body = "\n\n".join(_to_markdown(b) for b in blocks if _to_markdown(b))
    return f"# {title}\n\n{body}\n"


def safe_filename(title: str) -> str:
    """Turn a page title into a safe filename."""
    keep = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return "".join(c if c in keep else "_" for c in title).strip()[:80] or "untitled"


def sync(api_key: str, database_id: str) -> List[Path]:
    """Sync all pages from a Notion database; return list of written files."""
    try:
        from notion_client import Client
    except ImportError:
        print("[error] notion-client not installed. Run:")
        print("  pip install notion-client")
        sys.exit(1)

    client = Client(auth=api_key)
    NOTION_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[info] Querying database {database_id}...")
    pages = []
    cursor = None
    while True:
        kwargs = {"database_id": database_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        pages.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
    print(f"[info] Found {len(pages)} pages")

    written = []
    for page in pages:
        page_id = page["id"]
        # Fetch blocks
        blocks = []
        cursor = None
        while True:
            kwargs = {"block_id": page_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor
            resp = client.blocks.children.list(**kwargs)
            blocks.extend(resp.get("results", []))
            if not resp.get("has_more"):
                break
            cursor = resp.get("next_cursor")
        page["_blocks"] = blocks

        md = page_to_markdown(page)
        title = "Untitled"
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = "".join(
                    t.get("plain_text", "") for t in prop.get("title", [])
                )
                break
        fname = safe_filename(title) + ".md"
        fpath = NOTION_DIR / fname
        fpath.write_text(md, encoding="utf-8")
        print(f"[info] wrote {fpath.relative_to(PROJECT_ROOT)}")
        written.append(fpath)
    return written


def main():
    api_key = os.getenv("NOTION_API_KEY")
    db_id = os.getenv("NOTION_DATABASE_ID")
    if not api_key or not db_id:
        print("=" * 60)
        print("Notion Sync - 配置缺失")
        print("=" * 60)
        print("\n请在 .env 中添加：")
        print("  NOTION_API_KEY=secret_xxxxxxxxxxxxxxxxxx")
        print("  NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxx")
        print("\n获取方式：")
        print("  1. 在 https://www.notion.so/my-integrations 创建集成")
        print('  2. 在目标数据库页面点 "..." -> Connections -> 添加你的集成')
        print("  3. 数据库 ID 在 URL 里：notion.so/<workspace>/<DB_ID>?v=...")
        print("\n依赖安装：pip install notion-client")
        sys.exit(0)
    written = sync(api_key, db_id)
    print(f"\n[done] synced {len(written)} pages to {NOTION_DIR}")
    print("Now run: python src/indexer.py  (or start watcher.py)")


if __name__ == "__main__":
    main()