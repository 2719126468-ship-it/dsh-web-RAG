"""Parent-Child chunking: small chunks for retrieval, large for context.

Idea (Anthropic 2024 best practice):
  - Split each document into big PARENT chunks (1500 chars, full context)
  - Split each parent into small CHILD chunks (200 chars, precise match)
  - Embed and index CHILD chunks (better precision)
  - On retrieval: find matching children, return their PARENT context to LLM

Why this works:
  Small child chunks match user queries more precisely (higher precision).
  But LLM needs the full surrounding context to write good answers.
  So we trade a bit of "what does the chunk say" precision for "where in the doc" precision,
  while still giving the LLM enough context to reason.

Storage in Qdrant:
  - Each child has metadata.parent_id (integer)
  - Each child has metadata.parent_text (the full parent block)
  - Each child has metadata.parent_source, metadata.parent_start_line
"""
import uuid
from typing import List, Tuple, Dict, Any
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


CHILD_SIZE = 200
CHILD_OVERLAP = 30
PARENT_SIZE = 1500
PARENT_OVERLAP = 100


def build_parent_child(docs: List[Document]) -> Tuple[List[Document], Dict[str, Document]]:
    """Given a list of documents (one per page or per file),
    return (child_chunks, parents_by_id).

    child_chunks are the ones to embed; parents_by_id maps parent_id to the parent Document.
    """
    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=PARENT_SIZE,
        chunk_overlap=PARENT_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHILD_SIZE,
        chunk_overlap=CHILD_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
    )

    all_parents: Dict[str, Document] = {}
    all_children: List[Document] = []

    for doc in docs:
        # Preserve pdf_metadata docs as special self-contained children.
        # These come from parse_pdf() with chunk_role=pdf_metadata and contain
        # Title/Author/etc. from the PDF metadata. They should NOT be re-split
        # through the parent-child pipeline (which would overwrite chunk_role).
        if doc.metadata.get("chunk_role") == "pdf_metadata":
            parent_id = str(uuid.uuid4())[:12]
            doc.metadata["parent_id"] = parent_id
            doc.metadata["parent_text"] = doc.page_content  # self-contained, no separate parent
            all_parents[parent_id] = doc
            all_children.append(doc)
            continue

        # Step 1: split into parents
        parents = parent_splitter.split_documents([doc])
        for parent in parents:
            parent_id = str(uuid.uuid4())[:12]
            parent.metadata["parent_id"] = parent_id
            parent.metadata["chunk_role"] = "parent"
            all_parents[parent_id] = parent

            # Step 2: split each parent into children
            children = child_splitter.split_documents([parent])
            for child in children:
                child.metadata["parent_id"] = parent_id
                child.metadata["parent_text"] = parent.page_content
                child.metadata["parent_source"] = parent.metadata.get("source", "")
                child.metadata["parent_start_line"] = parent.metadata.get("start_line", 0)
                child.metadata["chunk_role"] = "child"
                all_children.append(child)

    return all_children, all_parents


def get_parent_for_child(child: Document, parents: Dict[str, Document]) -> Document:
    """Return the parent Document for a child, falling back to the child itself."""
    pid = child.metadata.get("parent_id")
    if pid and pid in parents:
        return parents[pid]
    return child


if __name__ == "__main__":
    # Self-test: take a sample doc and show what gets generated
    sample = Document(
        page_content=("LangChain 是一个用于开发大语言模型应用的框架。" * 20),
        metadata={"source": "test.md"},
    )
    children, parents = build_parent_child([sample])
    print(f"Generated {len(parents)} parents and {len(children)} children")
    print("First parent length:", len(list(parents.values())[0].page_content))
    print("First child length:", len(children[0].page_content))
    print("First child parent_id:", children[0].metadata["parent_id"])