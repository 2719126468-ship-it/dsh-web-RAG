"""Generate a synthetic two-column academic PDF for testing.

Run:
  python example_lessons/make_test_pdf.py
Outputs: docs/papers/test-two-column-paper.pdf
"""
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
)
from reportlab.lib import colors


OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "papers" / "test-two-column-paper.pdf"


TITLE = "A Synthetic Study on Vector Retrieval Quality"
AUTHORS = "Anonymous Authors"
ABSTRACT = ("We present a synthetic paper used to test PDF parsing for a Retrieval-Augmented "
             "Generation (RAG) system. The paper is laid out in two columns like a typical NeurIPS submission. "
             "We include sections, tables, and references to exercise the parser.")

SECTIONS = [
    ("1. Introduction", [
        "Vector retrieval has become a key building block of modern AI systems.",
        "Common approaches include BM25 keyword search and dense embedding similarity.",
        "Hybrid retrieval combines both signals via reciprocal rank fusion.",
    ]),
    ("2. Method", [
        "We split documents into chunks of roughly 500 characters.",
        "Each chunk is embedded with the BGE-small-zh model.",
        "Retrieved chunks are re-ranked by a cross-encoder.",
        "The final top-K chunks are passed to a large language model as context.",
    ]),
    ("3. Experiment", [
        "We evaluate on 8 questions across 6 documents.",
        "Hit@1 measures whether the first result is the correct document.",
        "Context precision measures how many of the top-K results are relevant.",
        "Context recall measures whether all the required keywords were retrieved.",
    ]),
    ("4. Results", [
        "Hit@1 reaches 1.0 on the simple test set, indicating perfect top-1 ranking.",
        "Context recall also reaches 1.0, meaning no keyword is missed.",
        "Context precision is 0.825 because some retrieved chunks cover adjacent content.",
    ]),
    ("5. Discussion", [
        "A two-column layout typically defeats simple text extractors.",
        "Our parser uses x-coordinate clustering to detect columns and reads in proper order.",
        "Tables are preserved as markdown to keep them queryable.",
    ]),
    ("6. Conclusion", [
        "We showed that a small set of techniques yields a working RAG pipeline.",
        "Future work could explore parent-child chunking and contextual retrieval.",
    ]),
]

TABLE_DATA = [
    ["Model", "Hit@1", "Precision", "Recall"],
    ["Baseline", "0.50", "0.40", "0.60"],
    ["+ BM25", "0.75", "0.60", "0.80"],
    ["+ Rerank", "0.90", "0.75", "0.95"],
    ["+ Contextual", "1.00", "0.83", "1.00"],
]


def build_pdf():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("title", parent=styles["Title"], fontSize=18, alignment=1)
    author_style = ParagraphStyle("author", parent=styles["Normal"], fontSize=11, alignment=1, textColor=colors.grey)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=13, spaceBefore=8, spaceAfter=4)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=9, leading=11)
    abstract_style = ParagraphStyle("abs", parent=body, leftIndent=12, rightIndent=12, fontSize=8, textColor=colors.dimgrey)

    story = []
    story.append(Paragraph(TITLE, title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph(AUTHORS, author_style))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Abstract", h2))
    story.append(Paragraph(ABSTRACT, abstract_style))
    story.append(Spacer(1, 12))

    left_chunks = []
    right_chunks = []
    for sec_title, sec_paras in SECTIONS[:3]:
        block = [Paragraph("<b>" + sec_title + "</b>", h2)]
        for p in sec_paras:
            block.append(Paragraph(p, body))
            block.append(Spacer(1, 4))
        left_chunks.append(block)
    for sec_title, sec_paras in SECTIONS[3:]:
        block = [Paragraph("<b>" + sec_title + "</b>", h2)]
        for p in sec_paras:
            block.append(Paragraph(p, body))
            block.append(Spacer(1, 4))
        right_chunks.append(block)

    while len(left_chunks) < len(right_chunks):
        left_chunks.append([])
    while len(right_chunks) < len(left_chunks):
        right_chunks.append([])

    rows = []
    for L, R in zip(left_chunks, right_chunks):
        rows.append([L, R])
    tbl = Table(rows, colWidths=[3.5 * inch, 3.5 * inch])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 14))

    story.append(PageBreak())
    story.append(Paragraph("<b>Table 1. Retrieval Quality Metrics</b>", h2))
    story.append(Spacer(1, 6))
    t = Table(TABLE_DATA, colWidths=[2.0 * inch, 1.3 * inch, 1.3 * inch, 1.3 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
    ]))
    story.append(t)

    doc.build(story)
    print("Wrote " + str(OUTPUT))


if __name__ == "__main__":
    build_pdf()