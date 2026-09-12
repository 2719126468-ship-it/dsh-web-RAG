"""PDF parser: smarter than PyPDFLoader.

Handles:
  - Single-column and two-column layouts (most common in academic papers)
  - Tables (preserved as pipe-delimited text)
  - Page numbers / running headers (stripped)
  - Hyphenated line breaks (joined)

Why not just PyPDFLoader?
  It reads page by page, left to right. On a two-column paper that means
  it reads "left column page 1" then "right column page 1" -- which is
  a wrong reading order for humans. pdfplumber gives us per-character
  coordinates so we can detect columns and read them in proper order.
"""
import re
from pathlib import Path
from typing import List, Dict, Any

import pdfplumber
from langchain_core.documents import Document


HEADER_FOOTER_PATTERN = re.compile(r"^\s*\d+\s*$|^\s*page\s*\d+|^\s*\d+\s*/\s*\d+\s*$", re.IGNORECASE)


def _is_likely_two_column(page) -> bool:
    """Heuristic: detect two-column layout by looking at x-coordinate clustering."""
    words = page.extract_words()
    if len(words) < 30:
        return False  # too few words, skip
    # Get x0 (left edge) of each word
    xs = sorted(w["x0"] for w in words)
    mid_x = page.width / 2
    left = sum(1 for x in xs if x < mid_x - 20)
    right = sum(1 for x in xs if x > mid_x + 20)
    # If both columns have many words, likely two-column
    return left > 15 and right > 15 and abs(left - right) / max(left, right) < 0.6


def _extract_column_text(page, x_min: float, x_max: float) -> str:
    """Extract text from a horizontal slice of the page (one column)."""
    cropped = page.crop((x_min, 0, x_max, page.height))
    text = cropped.extract_text() or ""
    return text


def _clean_text(text: str) -> str:
    """Join hyphenated line breaks, drop running headers/footers."""
    lines_out = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if HEADER_FOOTER_PATTERN.match(stripped):
            continue
        # Rejoin hyphenated words: "atten-\ntion" -> "attention"
        if lines_out and lines_out[-1].endswith("-"):
            lines_out[-1] = lines_out[-1][:-1] + stripped
        else:
            lines_out.append(stripped)
    return "\n".join(lines_out)


def _extract_tables(page) -> str:
    """Extract tables as pipe-delimited Markdown."""
    try:
        tables = page.extract_tables() or []
    except Exception:
        return ""
    md_chunks = []
    for tbl in tables:
        if not tbl or not tbl[0]:
            continue
        # Convert to markdown: first row is header
        header = [str(c) if c else "" for c in tbl[0]]
        md_chunks.append("| " + " | ".join(header) + " |")
        md_chunks.append("| " + " | ".join(["---"] * len(header)) + " |")
        for row in tbl[1:]:
            cells = [str(c) if c else "" for c in row]
            md_chunks.append("| " + " | ".join(cells) + " |")
    return "\n".join(md_chunks)


def _extract_header_band(page, fraction: float = 0.18) -> str:
    """Extract the top header band of a page as a single full-width strip.

    Why: in two-column papers the title/author row often spans both columns.
    If we extract columns independently, the title gets cut at the column
    boundary (e.g. "V" in left col, "ector Retrieval Quality" in right).
    Using the top band as one strip preserves the full title.

    fraction=0.18 covers the title + author + abstract header on most papers.
    """
    band_height = page.height * fraction
    band = page.crop((0, 0, page.width, band_height))
    return band.extract_text() or ""


def _extract_body_columns(page, mid_x: float) -> str:
    """Extract the body of a two-column page (below the header band).

    Returns left + right columns concatenated, in reading order.
    """
    body_top = page.height * 0.18
    left = page.crop((0, body_top, mid_x - 10, page.height))
    right = page.crop((mid_x + 10, body_top, page.width, page.height))
    left_text = (left.extract_text() or "").strip()
    right_text = (right.extract_text() or "").strip()
    return left_text + "\n\n" + right_text


def _make_metadata_doc(pdf_path: Path, meta: Dict[str, Any]) -> Document:
    """Build a Document from PDF metadata (Title, Author, Subject, Keywords).

    Some PDFs (especially scanned ones) have unreliable body text, but the
    metadata is usually clean. Injecting it as a small chunk is a cheap
    safety net for queries like "who wrote this paper" or "what is this about".
    """
    if not meta:
        return None
    fields = []
    title = meta.get("Title", "").strip()
    author = meta.get("Author", "").strip()
    subject = meta.get("Subject", "").strip()
    keywords = meta.get("Keywords", "").strip()
    creator = meta.get("Creator", "").strip()
    if title and title.lower() not in ("(anonymous)", "(unspecified)", ""):
        fields.append(f"Title: {title}")
    if author and author.lower() not in ("(anonymous)", "(unspecified)", ""):
        fields.append(f"Author(s): {author}")
    if subject and subject.lower() not in ("(unspecified)", ""):
        fields.append(f"Subject: {subject}")
    if keywords and keywords.lower() not in ("(unspecified)", ""):
        fields.append(f"Keywords: {keywords}")
    if not fields:
        return None
    body = "PDF Metadata:\n" + "\n".join(fields)
    return Document(
        page_content=body,
        metadata={
            "source": str(pdf_path),
            "page": 0,
            "chunk_role": "pdf_metadata",
        },
    )


def parse_pdf(pdf_path: Path) -> List[Document]:
    """Parse a PDF into a list of Documents.

    Returns one Document per page, plus optionally one Document containing
    the PDF metadata (Title, Author, etc.) for queries that target the
    document as a whole.

    Layout handling:
      - Single-column pages: full-page extract
      - Two-column pages: top band as full-width strip (keeps title intact),
        body as left + right column concatenation
    """
    docs = []
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            total = len(pdf.pages)

            # Optional metadata doc first
            meta_doc = _make_metadata_doc(pdf_path, pdf.metadata or {})
            if meta_doc is not None:
                docs.append(meta_doc)

            for i, page in enumerate(pdf.pages):
                two_col = _is_likely_two_column(page)
                layout = "two-column" if two_col else "single-column"

                if two_col:
                    header = _extract_header_band(page)
                    body = _extract_body_columns(page, page.width / 2)
                    page_text = (header.strip() + "\n\n" + body.strip()).strip()
                else:
                    page_text = page.extract_text() or ""

                # Extract tables (single-column only to keep order)
                tables_md = _extract_tables(page)
                if tables_md:
                    page_text = page_text + "\n\n[Tables]\n" + tables_md

                cleaned = _clean_text(page_text)
                if not cleaned.strip():
                    continue

                docs.append(Document(
                    page_content=cleaned,
                    metadata={
                        "source": str(pdf_path),
                        "page": i + 1,
                        "total_pages": total,
                        "layout": layout,
                    },
                ))
    except Exception as e:
        print(f"[warn] PDF parse failed for {pdf_path}: {e}")
    return docs


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path-to-pdf>")
        sys.exit(1)
    p = Path(sys.argv[1])
    docs = parse_pdf(p)
    print(f"Parsed {len(docs)} pages from {p.name}\n")
    for d in docs[:2]:
        print(f"--- Page {d.metadata['page']} ({d.metadata['layout']}) ---")
        print(d.page_content[:500])
        print()