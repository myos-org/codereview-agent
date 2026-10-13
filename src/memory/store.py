"""In-memory vector store for "Chat with Code" follow-ups.

Ephemeral on purpose: a portfolio deploy should hold nothing between
sessions, and an in-memory Chroma client costs nothing to run.
"""

from __future__ import annotations

import uuid


class DiffMemory:
    def __init__(self, collection: str = "pr-chunks"):
        import chromadb

        self._client = chromadb.EphemeralClient()
        self._col = self._client.get_or_create_collection(collection)

    def add(self, chunks: list[str], source: str) -> None:
        if not chunks:
            return
        self._col.add(
            documents=chunks,
            ids=[str(uuid.uuid4()) for _ in chunks],
            metadatas=[{"source": source} for _ in chunks],
        )

    def search(self, query: str, k: int = 4) -> list[str]:
        if self._col.count() == 0:
            return []
        res = self._col.query(query_texts=[query], n_results=k)
        return res["documents"][0] if res.get("documents") else []
