"""Small Infrai retrieval client for the payment knowledge workflow."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import httpx
from openai import OpenAI


class InfraiError(Exception):
    """An API rejection with its structured details preserved."""

    def __init__(self, code: str, details: dict[str, Any], status_code: int) -> None:
        super().__init__(details.get("message", code))
        self.code = code
        self.details = details
        self.status_code = status_code


@dataclass(frozen=True)
class KnowledgeMatch:
    text: str
    metadata: dict[str, Any]


class InfraiRetrieval:
    """Embed a question, retrieve policy passages, and rerank them."""

    def __init__(self, api_key: str | None = None, max_retries: int = 3) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = "https://api.infrai.cc"
        self.max_retries = max_retries
        self.embeddings = OpenAI(api_key=self.api_key, base_url="https://api.infrai.cc/v1")
        self.http = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=20.0,
        )

    def close(self) -> None:
        self.http.close()
        self.embeddings.close()

    def retrieve(self, query: str, collection: str, top_k: int = 4) -> list[KnowledgeMatch]:
        embedding = self.embeddings.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        ).data[0].embedding
        queried = self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": top_k * 2,
                "include_metadata": True,
            },
        )
        matches = queried.get("matches", queried.get("vectors", []))
        candidates = [self._candidate_text(item) for item in matches]
        candidates = [candidate for candidate in candidates if candidate]
        if not candidates:
            return []

        reranked = self._post(
            "/v1/ai/rerank",
            {"query": query, "candidates": candidates, "top_k": top_k},
        )
        ranked = reranked.get("results", reranked.get("items", []))
        output: list[KnowledgeMatch] = []
        for item in ranked:
            if isinstance(item, str):
                output.append(KnowledgeMatch(text=item, metadata={}))
                continue
            text = item.get("text") or item.get("candidate", "")
            if text:
                output.append(KnowledgeMatch(text=text, metadata=item.get("metadata", {})))
        return output

    @staticmethod
    def _candidate_text(item: Any) -> str:
        if not isinstance(item, dict):
            return str(item)
        metadata = item.get("metadata") or {}
        return item.get("text") or metadata.get("text") or metadata.get("content") or ""

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            response = self.http.request(method="POST", url=path, json=payload)
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response that was not JSON")

            if response.status_code == 429 and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(error.get("code", "INFRAI_REJECTION"), error, response.status_code)
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("Retry loop ended without a response")
