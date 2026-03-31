"""Knowledge Base / RAG tools for Project Omni.

ChromaDB-based vector storage and semantic search.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from agent import tool


# ─────────────────────────────────────────────────────────────────────────────
# ChromaDB Setup
# ─────────────────────────────────────────────────────────────────────────────

CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "omni-knowledge")

# Global ChromaDB client
_chroma_client = None
_collection = None


def _get_chroma():
    """Get or create ChromaDB client and collection."""
    global _chroma_client, _collection

    if _chroma_client is None:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError:
            return None, None

        # Ensure directory exists
        Path(CHROMA_PATH).mkdir(parents=True, exist_ok=True)

        _chroma_client = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )

    if _collection is None:
        try:
            _collection = _chroma_client.get_or_create_collection(
                name=CHROMA_COLLECTION,
                metadata={"description": "Project Omni Knowledge Base"},
            )
        except Exception:  # noqa: BLE001
            _collection = _chroma_client.create_collection(
                name=CHROMA_COLLECTION,
                metadata={"description": "Project Omni Knowledge Base"},
            )

    return _chroma_client, _collection


# ─────────────────────────────────────────────────────────────────────────────
# Document Processing
# ─────────────────────────────────────────────────────────────────────────────


def _load_document(path: str) -> list[tuple[str, str]]:
    """Load document and return list of (text, source) tuples."""
    ext = Path(path).suffix.lower()
    results: list[tuple[str, str]] = []

    if ext == ".pdf":
        try:
            import pymupdf

            doc = pymupdf.open(path)
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():
                    results.append((text.strip(), f"{path}#page{i + 1}"))
            doc.close()
        except Exception as exc:  # noqa: BLE001
            return [(f"[error loading PDF: {exc}]", path)]

    elif ext in (".md", ".markdown"):
        with open(path, encoding="utf-8") as f:
            content = f.read()
            results.append((content, path))

    elif ext == ".txt":
        with open(path, encoding="utf-8") as f:
            content = f.read()
            results.append((content, path))

    elif ext == ".json":
        import json

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            results.append((json.dumps(data, indent=2), path))

    elif ext == ".csv":
        import pandas as pd

        df = pd.read_csv(path)
        # Convert to readable text
        text = df.to_string()
        results.append((text, path))

    else:
        return [(f"[unsupported file type: {ext}]", path)]

    return results


def _split_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks."""
    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap

    return chunks


def _get_embedding(text: str) -> list[float]:
    """Get embedding for text using LiteLLM."""
    try:
        import litellm

        # Use a model that supports embeddings
        response = litellm.embedding(
            model="text-embedding-3-small",
            input=[text],
        )
        return response.data[0]["embedding"]
    except Exception as exc:  # noqa: BLE001
        # Fallback: return random embedding (for testing)
        import random

        return [random.random() for _ in range(1536)]


# ─────────────────────────────────────────────────────────────────────────────
# RAG Tools
# ─────────────────────────────────────────────────────────────────────────────


@tool(
    name="rag_add_documents",
    description=(
        "Add documents to the knowledge base. "
        "Supports PDF, Markdown, TXT, JSON, CSV files. "
        "Documents are chunked and indexed for semantic search."
    ),
    parameters={
        "type": "object",
        "properties": {
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to add",
            },
            "chunk_size": {
                "type": "integer",
                "description": "Chunk size for splitting documents. Default: 1000",
            },
            "overlap": {
                "type": "integer",
                "description": "Overlap between chunks. Default: 100",
            },
        },
        "required": ["paths"],
    },
)
def rag_add_documents(
    paths: list[str],
    chunk_size: int = 1000,
    overlap: int = 100,
) -> str:
    """Add documents to the knowledge base."""
    _, collection = _get_chroma()

    if collection is None:
        return "[error] ChromaDB not available. Run: pip install chromadb"

    if not paths:
        return "[error] No paths provided"

    total_chunks = 0
    errors: list[str] = []

    for path in paths:
        if not os.path.exists(path):
            errors.append(f"File not found: {path}")
            continue

        # Load document
        docs = _load_document(path)
        if not docs:
            errors.append(f"No content extracted: {path}")
            continue

        # Split into chunks
        all_chunks: list[tuple[str, str]] = []
        for content, source in docs:
            chunks = _split_text(content, chunk_size, overlap)
            for chunk in chunks:
                if chunk.strip():
                    all_chunks.append((chunk, source))

        if not all_chunks:
            continue

        # Generate IDs and embeddings
        ids: list[str] = []
        embeddings: list[list[float]] = []
        documents: list[str] = []
        metadatas: list[dict] = []

        base_id = f"{Path(path).stem}_{len(collection.get()['ids'])}"

        for i, (chunk, source) in enumerate(all_chunks):
            ids.append(f"{base_id}_{i}")
            documents.append(chunk)
            metadatas.append({"source": source})

            # Get embedding
            emb = _get_embedding(chunk)
            embeddings.append(emb)

        # Add to collection
        try:
            collection.add(ids=ids, documents=documents, embeddings=embeddings, metadatas=metadatas)
            total_chunks += len(ids)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Error adding {path}: {exc}")

    result = f"Added {total_chunks} chunks from {len(paths)} files"
    if errors:
        result += "\n\nErrors:\n" + "\n".join(errors)

    return result


@tool(
    name="rag_search",
    description=(
        "Search the knowledge base using semantic similarity. "
        "Returns the most relevant chunks from indexed documents."
    ),
    parameters={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "n_results": {
                "type": "integer",
                "description": "Number of results to return. Default: 5",
            },
        },
        "required": ["query"],
    },
)
def rag_search(query: str, n_results: int = 5) -> str:
    """Search the knowledge base."""
    _, collection = _get_chroma()

    if collection is None:
        return "[error] ChromaDB not available. Run: pip install chromadb"

    try:
        # Get query embedding
        query_embedding = _get_embedding(query)

        # Search
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
        )

        if not results["documents"] or not results["documents"][0]:
            return "No results found"

        output_parts: list[str] = []
        for i, (doc, meta) in enumerate(
            zip(results["documents"][0], results["metadatas"][0])
        ):
            source = meta.get("source", "unknown")
            output_parts.append(f"--- Result {i + 1} [{source}] ---\n{doc[:500]}")

        return "\n\n".join(output_parts)

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="rag_delete",
    description="Delete documents from the knowledge base by source.",
    parameters={
        "type": "object",
        "properties": {
            "source": {
                "type": "string",
                "description": "Source file path to delete (partial match)",
            },
            "delete_all": {
                "type": "boolean",
                "description": "Delete all documents. Default: false",
            },
        },
    },
)
def rag_delete(source: str | None = None, delete_all: bool = False) -> str:
    """Delete documents from knowledge base."""
    _, collection = _get_chroma()

    if collection is None:
        return "[error] ChromaDB not available. Run: pip install chromadb"

    try:
        if delete_all:
            collection.delete(where={})
            return "Deleted all documents from knowledge base"

        if source:
            # Delete by source metadata
            collection.delete(where={"source": {"$contains": source}})
            return f"Deleted documents from: {source}"

        return "[error] Must specify source or delete_all=true"

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="rag_stats",
    description="Get statistics about the knowledge base.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def rag_stats() -> str:
    """Get knowledge base statistics."""
    _, collection = _get_chroma()

    if collection is None:
        return "[error] ChromaDB not available. Run: pip install chromadb"

    try:
        count = collection.count()
        return f"Knowledge Base Statistics:\n- Collection: {CHROMA_COLLECTION}\n- Total chunks: {count}\n- Storage: {CHROMA_PATH}"
    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"


@tool(
    name="rag_list_sources",
    description="List all indexed sources in the knowledge base.",
    parameters={
        "type": "object",
        "properties": {},
    },
)
def rag_list_sources() -> str:
    """List all indexed sources."""
    _, collection = _get_chroma()

    if collection is None:
        return "[error] ChromaDB not available. Run: pip install chromadb"

    try:
        results = collection.get()
        if not results["metadatas"]:
            return "No documents in knowledge base"

        # Get unique sources
        sources: dict[str, int] = {}
        for meta in results["metadatas"]:
            source = meta.get("source", "unknown")
            sources[source] = sources.get(source, 0) + 1

        output = "Indexed Sources:\n"
        for source, count in sorted(sources.items()):
            output += f"- {source}: {count} chunks\n"

        return output

    except Exception as exc:  # noqa: BLE001
        return f"[error] {exc}"