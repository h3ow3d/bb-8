from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_MAX_DOCS = 20
_MAX_DOC_CHARS = 4000


def load_docs(knowledge_dir: str) -> list[dict[str, str]]:
    """Load markdown files from the knowledge directory."""
    docs: list[dict[str, str]] = []
    path = Path(knowledge_dir)
    if not path.exists():
        logger.debug("Knowledge directory not found: %s", knowledge_dir)
        return docs
    for md_file in sorted(path.glob("*.md"))[:_MAX_DOCS]:
        try:
            content = md_file.read_text(encoding="utf-8")[:_MAX_DOC_CHARS]
            docs.append({"filename": md_file.name, "content": content})
        except Exception as exc:
            logger.warning("Failed to read knowledge file %s: %s", md_file, exc)
    return docs


def retrieve_relevant(docs: list[dict[str, str]], query: str, top_k: int = 3) -> list[dict[str, str]]:
    """Simple keyword-based retrieval of relevant docs."""
    if not docs or not query:
        return []

    query_words = set(query.lower().split())
    scored: list[tuple[int, dict[str, str]]] = []
    for doc in docs:
        text = (doc.get("filename", "") + " " + doc.get("content", "")).lower()
        score = sum(1 for word in query_words if word in text)
        if score > 0:
            scored.append((score, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]
