"""Tests for the Milvus question bank and Zhipu Embedding-3 integration."""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace

import pytest

from app.services.rag import ingestion
from app.services.rag.retrieval import retrieve_interview_questions


class _FakeEmbeddingsApi:
    """Record Embedding-3 calls and return deliberately unordered results."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        """Return stable vectors for the requested dimension."""
        self.calls.append(kwargs)
        dimensions = int(kwargs["dimensions"])
        inputs = list(kwargs["input"])
        data = [
            SimpleNamespace(index=index, embedding=[float(index)] * dimensions)
            for index in reversed(range(len(inputs)))
        ]
        return SimpleNamespace(data=data)


class _FakeZhipuClient:
    """Provide the embeddings resource used by ZhipuEmbedding."""

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.embeddings = _FakeEmbeddingsApi()


class _WrongDimensionEmbedding:
    """Return a stable vector with the wrong configured dimension."""

    def get_text_embedding(self, text: str) -> list[float]:
        """Return a 256-dimensional vector."""
        del text
        return [0.0] * 256


def test_build_embed_model_requires_zhipu_key(monkeypatch) -> None:
    """Reject startup when no dedicated Zhipu key is configured."""
    monkeypatch.delenv("RAG_EMBED_API_KEY", raising=False)
    monkeypatch.delenv("ZHIPUAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="RAG_EMBED_API_KEY"):
        ingestion.build_embed_model(model="embedding-3", embed_dim=1024)


def test_zhipu_embedding_uses_model_dimension_and_response_order(monkeypatch) -> None:
    """Send explicit Embedding-3 settings and restore API response order."""
    monkeypatch.setattr(ingestion, "ZhipuAiClient", _FakeZhipuClient)
    model = ingestion.ZhipuEmbedding(
        model_name="embedding-3",
        dimensions=512,
        api_key="test-key",
        embed_batch_size=64,
    )

    vectors = model._get_text_embeddings(["first", "second"])

    assert len(vectors) == 2
    assert vectors[0][0] == 0.0
    assert vectors[1][0] == 1.0
    assert len(vectors[0]) == 512
    assert model._client.embeddings.calls == [
        {
            "model": "embedding-3",
            "input": ["first", "second"],
            "dimensions": 512,
        }
    ]


def test_validate_embedding_dimension_rejects_mismatch() -> None:
    """Reject a collection configuration that differs from API output."""
    fake_model = _WrongDimensionEmbedding()

    with pytest.raises(ValueError, match="configured 1024, API returned 256"):
        ingestion.validate_embedding_dimension(fake_model, 1024)


def test_build_vector_store_configures_milvus_lite(monkeypatch, tmp_path) -> None:
    """Create the local Milvus directory and pass stable collection settings."""
    captured: dict[str, object] = {}

    def fake_vector_store(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(ingestion, "MilvusVectorStore", fake_vector_store)
    uri = str(tmp_path / "milvus" / "question-bank.db")

    ingestion.build_vector_store(
        uri=uri,
        token="",
        collection_name="question_bank_vectors",
        embed_dim=1024,
        overwrite=True,
    )

    assert (tmp_path / "milvus").is_dir()
    assert captured == {
        "uri": uri,
        "collection_name": "question_bank_vectors",
        "dim": 1024,
        "overwrite": True,
        "similarity_metric": "COSINE",
    }


def test_parse_args_uses_project_specific_milvus_uri(monkeypatch, tmp_path) -> None:
    """Avoid PyMilvus' reserved MILVUS_URI variable for Milvus Lite paths."""
    expected_uri = str(tmp_path / "question-bank.db")
    monkeypatch.setenv("MILVUS_URI", "http://reserved-by-pymilvus:19530")
    monkeypatch.setenv("RAG_MILVUS_URI", expected_uri)
    monkeypatch.setattr(sys, "argv", ["ingestion", "--dry-run"])

    args = ingestion.parse_args()

    assert args.milvus_uri == expected_uri


def test_retrieval_returns_empty_when_rag_is_disabled(monkeypatch) -> None:
    """Avoid API and database calls when deployment explicitly disables RAG."""
    monkeypatch.setenv("RAG_ENABLED", "false")

    assert asyncio.run(retrieve_interview_questions("React")) == ""
