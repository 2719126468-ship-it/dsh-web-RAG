"""Incremental indexer: only re-embed changed files.

Hashes each file, compares to a manifest, and only runs
embedding + ingestion on new or modified files. Deleted files
are removed from the vector store.
"""
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Tuple

from langchain_community.document_loaders import TextLoader, Docx2txtLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http import models  # Qdrant HTTP models for vector params etc.

from config import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
QDRANT_PATH = PROJECT_ROOT / config.QDRANT_PATH.lstrip("./")
MANIFEST_PATH = QDRANT_PATH / "_manifest.json"


def file_hash(path: Path) -> str:
    """SHA-256 of file content. Small files only — md/text are fine."""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def load_manifest() -> Dict[str, str]:
    """Map: relative file path -> sha256 hash."""
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(manifest: Dict[str, str]) -> None:
    QDRANT_PATH.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def scan_files() -> Dict[str, Path]:
    """Walk docs/ and return {relative_path: absolute_path} for supported files."""
    suffixes = ["*.md", "*.txt", "*.pdf", "*.docx"]
    found = {}
    for suf in suffixes:
        for p in DOCS_DIR.rglob(suf):
            rel = str(p.relative_to(PROJECT_ROOT)).replace(chr(92), "/")
            found[rel] = p
    return found


def diff_files(
    current: Dict[str, Path], manifest: Dict[str, str]
) -> Tuple[List[Path], List[str], List[Path]]:
    """Return (new_or_changed, deleted, all_to_ingest).

    - new_or_changed: files whose hash differs or are not in manifest
    - deleted: paths that were in manifest but no longer exist
    - all_to_ingest: same as new_or_changed (alias for clarity)
    """
    new_or_changed: List[Path] = []
    deleted: List[str] = []

    # Check for changes
    for rel, p in current.items():
        h = file_hash(p)
        if manifest.get(rel) != h:
            new_or_changed.append(p)

    # Check for deletions
    for rel in list(manifest.keys()):
        if rel not in current:
            deleted.append(rel)

    return new_or_changed, deleted, new_or_changed


def load_file(path: Path) -> List:
    """Load a single file as a list of Documents."""
    suf = path.suffix.lower()
    if suf in (".md", ".txt"):
        loader = TextLoader(str(path), encoding="utf-8")
    elif suf == ".pdf":
        from pdf_parser import parse_pdf
        return parse_pdf(path)
    elif suf == ".docx":
        loader = Docx2txtLoader(str(path))
    else:
        return []
    try:
        return loader.load()
    except Exception as e:
        print(f"[warn] Failed to load {path}: {e}")
        return []


def split_documents(docs, child_size=None, child_overlap=None):
    """Parent-aware splitter: returns list of (parent_doc, child_chunks).

    For simplicity, here we use a single-level splitter;
    the small-enough chunks are good for retrieval AND context.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_size or config.CHUNK_SIZE,
        chunk_overlap=child_overlap or config.CHUNK_OVERLAP,
        separators=["\n\n", "\n", "。", "！", "？", ". ", " ", ""],
    )
    return splitter.split_documents(docs)


def remove_deleted_from_store(client: QdrantClient, deleted: List[str]) -> int:
    """Delete points whose source metadata matches a deleted file path."""
    n = 0
    for rel in deleted:
        # Match by source path which ends with the relative path
        # Qdrant payload filter: source contains the relative path
        rel_escaped = rel.replace(chr(92), "/")
        flt = {"must": [{"key": "metadata.source", "match": {"text": rel_escaped}}]}
        try:
            res = client.delete(
                collection_name=config.COLLECTION_NAME,
                points_selector=flt,
            )
            n += 1
        except Exception as e:
            print(f"[warn] Could not delete points for {rel}: {e}")
    return n


class IncrementalIndexer:
    def __init__(self):
        print("[info] Loading embedding model...")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=config.EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        QDRANT_PATH.mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(QDRANT_PATH))
        # Make sure collection exists (with correct vector size 512 for BGE)
        if not self.client.collection_exists(config.COLLECTION_NAME):
            print(f"[info] Creating collection {config.COLLECTION_NAME}")
            self.client.create_collection(
                collection_name=config.COLLECTION_NAME,
                vectors_config=models.VectorParams(
                    size=512, distance=models.Distance.COSINE
                ),
            )
            self.store = None
        else:
            self.store = QdrantVectorStore(
                client=self.client,
                collection_name=config.COLLECTION_NAME,
                embedding=self.embeddings,
            )
        self.manifest = load_manifest()
        self.parents_by_id = {}  # Populated when USE_PARENT_CHILD=true

    def reindex(self, force: bool = False) -> dict:
        """Run an incremental reindex pass."""
        import shutil
        import gc
        import time as _time_module
        start = _time_module.time()
        current = scan_files()
        manifest = {} if force else dict(self.manifest)

        new_or_changed, deleted, to_ingest = diff_files(current, manifest)
        print(f"[info] Files: {len(current)} total, {len(new_or_changed)} changed, {len(deleted)} deleted")

        # When force=True, delete the entire qdrant_data directory and recreate from
        # scratch. This avoids SQLite lock issues that make delete_collection unreliable
        # when other QdrantClient instances are active. Note: all existing points are lost.
        # Strategy: close current client, delete dir, create fresh client.
        if force:
            # Close current client to release SQLite file handles
            del self.client
            del self.store
            self.client = None
            self.store = None
            gc.collect()  # Ensure Python GC releases handles
            if QDRANT_PATH.exists():
                try:
                    shutil.rmtree(QDRANT_PATH)
                    print(f"[info] Force reindex: removed {QDRANT_PATH}, will rebuild from scratch")
                except PermissionError:
                    # Windows: SQLite lock may persist briefly after process exit
                    # Try again after a short delay
                    _time_module.sleep(0.5)
                    try:
                        shutil.rmtree(QDRANT_PATH)
                        print(f"[info] Force reindex: removed {QDRANT_PATH} (after retry)")
                    except PermissionError:
                        print(f"[warn] Could not delete {QDRANT_PATH} - another process may hold a lock")
                        print(f"[warn] Trying to continue with existing collection...")
            QDRANT_PATH.mkdir(parents=True, exist_ok=True)
            # Recreate client and collection fresh
            self.client = QdrantClient(path=str(QDRANT_PATH))
            self.client.create_collection(
                collection_name=config.COLLECTION_NAME,
                vectors_config=models.VectorParams(size=512, distance=models.Distance.COSINE),
            )
            self.store = None
            self.manifest = {}  # Clear manifest since we're rebuilding
            print("[info] Collection recreated")

        # Handle deletions first (frees up collection space)
        if deleted:
            print(f"[info] Removing {len(deleted)} deleted files from store...")
            n = remove_deleted_from_store(self.client, deleted)
            for d in deleted:
                manifest.pop(d, None)
            print(f"[info] Removed vectors for {n} deleted files")

        # Handle new/changed files
        if to_ingest:
            print(f"[info] Loading & splitting {len(to_ingest)} files...")
            all_chunks = []
            use_pc = os.getenv("USE_PARENT_CHILD", "false").lower() == "true"
            if use_pc:
                from parent_child_splitter import build_parent_child
                self.parents_by_id = {}
            for p in to_ingest:
                docs = load_file(p)
                if not docs:
                    continue
                rel = str(p.relative_to(PROJECT_ROOT)).replace(chr(92), "/")
                if use_pc:
                    children, parents = build_parent_child(docs)
                    for c in children:
                        c.metadata["source"] = rel
                    all_chunks.extend(children)
                    self.parents_by_id.update(parents)
                else:
                    chunks = split_documents(docs)
                    for c in chunks:
                        c.metadata["source"] = rel
                    all_chunks.extend(chunks)
                # Update manifest with current hash
                manifest[rel] = file_hash(p)
            chunk_word = "child chunks" if use_pc else "chunks"
            print(f"[info] Produced {len(all_chunks)} {chunk_word}")

            # Optional: Contextual Retrieval (Anthropic 2024)
            if os.getenv("USE_CONTEXTUAL", "false").lower() == "true":
                api_key = os.getenv("DEEPSEEK_API_KEY", "")
                if api_key and not api_key.startswith("sk-xxxxxxx"):
                    try:
                        from contextualizer import Contextualizer
                        ctx_engine = Contextualizer(batch_size=5)
                        print(f"[info] Adding LLM-generated context to {len(all_chunks)} chunks...")
                        all_chunks = ctx_engine.contextualize(all_chunks)
                        print("[info] Contextualization done")
                    except Exception as e:
                        print(f"[warn] Contextualization failed, continuing without: {e}")
                else:
                    print("[info] DEEPSEEK_API_KEY not set; skipping contextual retrieval")

            if all_chunks:
                print(f"[info] Embedding and upserting...")
                embed_start = time.time()
                if self.store is None:
                    # Collection already created in __init__; build the store and add
                    self.store = QdrantVectorStore(
                        client=self.client,
                        collection_name=config.COLLECTION_NAME,
                        embedding=self.embeddings,
                    )
                self.store.add_documents(all_chunks)
                print(f"[info] Embedding took {time.time() - embed_start:.1f}s")

        save_manifest(manifest)
        elapsed = _time_module.time() - start
        summary = {
            "total_files": len(current),
            "new_or_changed": len(new_or_changed),
            "deleted": len(deleted),
            "chunks_added": len(all_chunks) if to_ingest else 0,
            "elapsed_seconds": round(elapsed, 2),
        }
        print(f"[done] {summary}")
        return summary


def main(force: bool = False):
    indexer = IncrementalIndexer()
    return indexer.reindex(force=force)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Reindex everything from scratch")
    args = parser.parse_args()
    main(force=args.force)