"""Markdown outline extractor.

Scans all .md files in docs/, parses headings (#, ##, ###),
and builds a navigable tree structure with byte offsets
so the UI can jump to any section.
"""
import re
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"

HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def extract_outline(md_path: Path) -> List[Dict[str, Any]]:
    """Return list of {level, title, line, offset} for each heading."""
    text = md_path.read_text(encoding="utf-8")
    items = []
    for m in HEADING_PATTERN.finditer(text):
        level = len(m.group(1))
        title = m.group(2).strip()
        # line number where heading starts
        line = text[: m.start()].count(chr(10)) + 1
        items.append({
            "level": level,
            "title": title,
            "line": line,
        })
    return items


def build_outline_tree() -> List[Dict[str, Any]]:
    """Build a tree: [{file, path, outline: [headings...], size}, ...]."""
    tree = []
    for p in sorted(DOCS_DIR.rglob("*.md")):
        rel = str(p.relative_to(PROJECT_ROOT)).replace(chr(92), "/")
        try:
            outline = extract_outline(p)
        except Exception:
            outline = []
        size = p.stat().st_size
        tree.append({
            "file": p.name,
            "path": rel,
            "abs_path": str(p),
            "outline": outline,
            "size": size,
        })
    return tree


def find_heading_at_line(outline: List[Dict[str, Any]], line: int) -> Dict[str, Any] | None:
    """Return the smallest heading that contains the given line."""
    best = None
    for h in outline:
        if h["line"] <= line:
            if best is None or h["line"] > best["line"]:
                best = h
    return best


def snippet_with_context(file_path: Path, line: int, context: int = 3) -> str:
    """Return the paragraph around `line` for the UI to display."""
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return ""
    start = max(0, line - context - 1)
    end = min(len(lines), line + context)
    return "\n".join(lines[start:end])