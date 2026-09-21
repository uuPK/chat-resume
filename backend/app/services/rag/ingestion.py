"""Import interview question JSONL files into a Milvus-backed index."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Protocol

from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.vector_stores.milvus import MilvusVectorStore
from pydantic import Field, PrivateAttr
from dotenv import load_dotenv
from zai import ZhipuAiClient

load_dotenv()

BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_QUESTION_BANK_DIR = BACKEND_DIR / "data" / "question_bank"
DEFAULT_COLLECTION_NAME = "question_bank_vectors"
DEFAULT_EMBED_MODEL = "embedding-3"
DEFAULT_EMBED_DIM = 1024
DEFAULT_MILVUS_URI = str(BACKEND_DIR / "data" / "milvus" / "question_bank.db")


def main() -> None:
    """Run the question bank ingestion command."""
    args = parse_args()
    documents = load_question_bank_documents(args.source_dir)
    print(f"Loaded {len(documents)} question documents from {args.source_dir}")
    print_summary(documents)
    if args.dry_run:
        print("Dry run only. No embeddings were created and nothing was written.")
        return

    vector_store = build_vector_store(
        uri=args.milvus_uri,
        token=args.milvus_token,
        collection_name=args.collection_name,
        embed_dim=args.embed_dim,
        overwrite=args.reset,
    )
    embed_model = build_embed_model(
        model=args.embed_model,
        embed_dim=args.embed_dim,
    )
    validate_embedding_dimension(embed_model, args.embed_dim)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )
    print(
        "Ingestion completed. "
        f"Milvus collection: {args.collection_name}; documents: {len(documents)}"
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the ingestion command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=DEFAULT_QUESTION_BANK_DIR,
        help="Directory containing question bank .jsonl files.",
    )
    parser.add_argument(
        "--collection-name",
        default=os.getenv("MILVUS_COLLECTION", DEFAULT_COLLECTION_NAME),
        help="Milvus collection used for interview question vectors.",
    )
    parser.add_argument(
        "--milvus-uri",
        default=os.getenv("MILVUS_URI", DEFAULT_MILVUS_URI),
        help="Milvus server URI or a local Milvus Lite database file.",
    )
    parser.add_argument(
        "--milvus-token",
        default=os.getenv("MILVUS_TOKEN", ""),
        help="Optional Milvus or Zilliz authentication token.",
    )
    parser.add_argument(
        "--embed-model",
        default=os.getenv("RAG_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        help="Zhipu embedding model name.",
    )
    parser.add_argument(
        "--embed-dim",
        type=int,
        default=int(os.getenv("RAG_EMBED_DIM", str(DEFAULT_EMBED_DIM))),
        help="Embedding dimension. Must match the embedding model output.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Replace the existing Milvus collection before importing documents.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate JSONL files without creating embeddings or writing to DB.",
    )
    return parser.parse_args()


def load_question_bank_documents(source_dir: Path) -> list[Document]:
    """Load all JSONL question items and convert them to LlamaIndex documents."""
    if not source_dir.exists():
        raise FileNotFoundError(f"Question bank directory not found: {source_dir}")
    documents: list[Document] = []
    for path in sorted(source_dir.glob("*.jsonl")):
        documents.extend(load_jsonl_documents(path))
    if not documents:
        raise ValueError(f"No question documents found in {source_dir}")
    return documents


def load_jsonl_documents(path: Path) -> list[Document]:
    """Load one JSONL file and convert each line to a document."""
    documents: list[Document] = []
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            item = parse_question_item(path, line_number, line)
            documents.append(question_item_to_document(item, path.name))
    return documents


def parse_question_item(path: Path, line_number: int, line: str) -> dict[str, Any]:
    """Parse and validate a single JSONL question item."""
    item = json.loads(line)
    if not isinstance(item, dict):
        raise ValueError(f"{path}:{line_number} must be a JSON object")
    required = {"id", "type", "skill", "difficulty", "question"}
    missing = sorted(key for key in required if not item.get(key))
    if missing:
        raise ValueError(f"{path}:{line_number} missing required keys: {missing}")
    return item


def question_item_to_document(item: dict[str, Any], source_file: str) -> Document:
    """Convert one question item to a searchable LlamaIndex document."""
    question_id = str(item["id"])
    metadata = {
        "question_id": question_id,
        "source_file": source_file,
        "type": str(item["type"]),
        "skill": str(item["skill"]),
        "difficulty": str(item["difficulty"]),
        "tags": string_list(item.get("tags")),
    }
    return Document(
        id_=question_id,
        text=render_question_text(item),
        metadata=metadata,
    )


def render_question_text(item: dict[str, Any]) -> str:
    """Render a question item as retrieval-friendly text."""
    sections = [
        ("Question", str(item.get("question") or "")),
        ("Skill", str(item.get("skill") or "")),
        ("Difficulty", str(item.get("difficulty") or "")),
        ("Expected points", join_list(item.get("expected_points"))),
        ("Followups", join_list(item.get("followups"))),
        ("Rubric", str(item.get("rubric") or "")),
        ("Tags", join_list(item.get("tags"))),
    ]
    return "\n".join(f"{title}: {value}" for title, value in sections if value)


class ZhipuEmbedding(BaseEmbedding):
    """Expose Zhipu Embedding-3 through the LlamaIndex embedding interface."""

    dimensions: int = Field(default=DEFAULT_EMBED_DIM, ge=256, le=2048)
    api_key: str = Field(exclude=True)
    _client: Any = PrivateAttr()

    def model_post_init(self, __context: Any) -> None:
        """Create the official Zhipu client after Pydantic validates the config."""
        self._client = ZhipuAiClient(api_key=self.api_key)

    def _get_query_embedding(self, query: str) -> list[float]:
        """Create one query vector."""
        return self._get_text_embedding(query)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        """Create one query vector without blocking the event loop."""
        import asyncio

        return await asyncio.to_thread(self._get_query_embedding, query)

    def _get_text_embedding(self, text: str) -> list[float]:
        """Create one document vector."""
        return self._request_embeddings([text])[0]

    def _get_text_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Create document vectors in batches supported by Embedding-3."""
        return self._request_embeddings(texts)

    def _request_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Call the official Zhipu embeddings API and preserve response order."""
        response = self._client.embeddings.create(
            model=self.model_name,
            input=texts,
            dimensions=self.dimensions,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]


def build_vector_store(
    *,
    uri: str,
    token: str,
    collection_name: str,
    embed_dim: int,
    overwrite: bool = False,
) -> MilvusVectorStore:
    """Create the Milvus vector store used by the interview question bank."""
    prepare_local_milvus_path(uri)
    options: dict[str, Any] = {
        "uri": uri,
        "collection_name": collection_name,
        "dim": embed_dim,
        "overwrite": overwrite,
        "similarity_metric": "COSINE",
    }
    if token:
        options["token"] = token
    return MilvusVectorStore(**options)


def build_embed_model(*, model: str, embed_dim: int) -> ZhipuEmbedding:
    """Create the configured Zhipu Embedding-3 client."""
    api_key = os.getenv("RAG_EMBED_API_KEY") or os.getenv("ZHIPUAI_API_KEY")
    if not api_key:
        raise ValueError("Set RAG_EMBED_API_KEY or ZHIPUAI_API_KEY for Embedding-3.")
    return ZhipuEmbedding(
        model_name=model,
        dimensions=embed_dim,
        api_key=api_key,
        embed_batch_size=64,
    )


class EmbeddingProbe(Protocol):
    """Small interface needed by the dimension preflight check."""

    def get_text_embedding(self, text: str) -> list[float]: ...


def validate_embedding_dimension(embed_model: EmbeddingProbe, expected: int) -> None:
    """Fail before ingestion when the API response dimension is misconfigured."""
    actual = len(embed_model.get_text_embedding("面试题向量维度检查"))
    if actual != expected:
        raise ValueError(
            f"Embedding dimension mismatch: configured {expected}, API returned {actual}."
        )


def prepare_local_milvus_path(uri: str) -> None:
    """Create the parent directory when Milvus Lite uses a local database file."""
    if "://" in uri:
        return
    Path(uri).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)


def print_summary(documents: list[Document]) -> None:
    """Print a compact ingestion summary grouped by skill."""
    counts: dict[str, int] = {}
    for document in documents:
        skill = str(document.metadata.get("skill") or "unknown")
        counts[skill] = counts.get(skill, 0) + 1
    for skill, count in sorted(counts.items()):
        print(f"- {skill}: {count}")


def join_list(value: Any) -> str:
    """Join a JSON list into readable text for retrieval."""
    return "; ".join(string_list(value))


def string_list(value: Any) -> list[str]:
    """Normalize any JSON value into a list of non-empty strings."""
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


if __name__ == "__main__":
    main()
