"""Import interview question JSONL files into a pgvector-backed LlamaIndex index."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from llama_index.core import Document, StorageContext, VectorStoreIndex
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.vector_stores.postgres import PGVectorStore
from sqlalchemy import create_engine, text

from app.infra.config import settings

BACKEND_DIR = Path(__file__).resolve().parents[3]
DEFAULT_QUESTION_BANK_DIR = BACKEND_DIR / "data" / "question_bank"
DEFAULT_TABLE_NAME = "question_bank_vectors"
DEFAULT_EMBED_MODEL = "text-embedding-3-small"
DEFAULT_EMBED_DIM = 1536
SAFE_TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main() -> None:
    """Run the question bank ingestion command."""
    args = parse_args()
    documents = load_question_bank_documents(args.source_dir)
    print(f"Loaded {len(documents)} question documents from {args.source_dir}")
    print_summary(documents)
    if args.dry_run:
        print("Dry run only. No embeddings were created and nothing was written.")
        return

    ensure_postgres_url(settings.DATABASE_URL)
    ensure_vector_extension(settings.DATABASE_URL)
    if args.reset:
        drop_vector_table(settings.DATABASE_URL, args.table_name)

    vector_store = build_vector_store(
        database_url=settings.DATABASE_URL,
        table_name=args.table_name,
        embed_dim=args.embed_dim,
        hybrid_search=args.hybrid,
    )
    embed_model = build_embed_model(
        model=args.embed_model,
        embed_dim=args.embed_dim,
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        show_progress=True,
    )
    print(
        "Ingestion completed. "
        f"Vector table: public.data_{args.table_name}"
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
        "--table-name",
        default=os.getenv("RAG_VECTOR_TABLE", DEFAULT_TABLE_NAME),
        help="LlamaIndex pgvector table name without the data_ prefix.",
    )
    parser.add_argument(
        "--embed-model",
        default=os.getenv("RAG_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        help="OpenAI-compatible embedding model name.",
    )
    parser.add_argument(
        "--embed-dim",
        type=int,
        default=int(os.getenv("RAG_EMBED_DIM", str(DEFAULT_EMBED_DIM))),
        help="Embedding dimension. Must match the embedding model output.",
    )
    parser.add_argument(
        "--hybrid",
        action="store_true",
        help="Enable LlamaIndex PostgreSQL hybrid vector/text search table setup.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop the existing vector table before importing documents.",
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


def build_vector_store(
    *,
    database_url: str,
    table_name: str,
    embed_dim: int,
    hybrid_search: bool,
) -> PGVectorStore:
    """Create the LlamaIndex PGVectorStore used by the question bank."""
    validate_table_name(table_name)
    return PGVectorStore.from_params(
        connection_string=database_url,
        table_name=table_name,
        embed_dim=embed_dim,
        hybrid_search=hybrid_search,
        text_search_config="simple",
        use_jsonb=True,
        indexed_metadata_keys={
            ("question_id", "text"),
            ("type", "text"),
            ("skill", "text"),
            ("difficulty", "text"),
        },
    )


def build_embed_model(*, model: str, embed_dim: int) -> OpenAIEmbedding:
    """Create the OpenAI-compatible embedding model for question vectors."""
    api_key = os.getenv("RAG_EMBED_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "Set OPENAI_API_KEY or RAG_EMBED_API_KEY before running ingestion."
        )
    api_base = os.getenv("RAG_EMBED_API_BASE") or os.getenv("OPENAI_API_BASE") or None
    return OpenAIEmbedding(
        model=model,
        dimensions=embed_dim,
        api_key=api_key,
        api_base=api_base,
        embed_batch_size=32,
    )


def ensure_postgres_url(database_url: str) -> None:
    """Reject non-PostgreSQL database URLs for pgvector ingestion."""
    if database_url.startswith(("postgresql://", "postgresql+psycopg2://")):
        return
    raise ValueError(
        "RAG ingestion requires PostgreSQL. "
        f"Current DATABASE_URL is {database_url!r}."
    )


def ensure_vector_extension(database_url: str) -> None:
    """Ensure the pgvector extension exists in the target database."""
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    engine.dispose()


def drop_vector_table(database_url: str, table_name: str) -> None:
    """Drop the LlamaIndex vector table for repeatable local imports."""
    validate_table_name(table_name)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text(f'DROP TABLE IF EXISTS public."data_{table_name}"'))
    engine.dispose()
    print(f"Dropped vector table if it existed: public.data_{table_name}")


def validate_table_name(table_name: str) -> None:
    """Validate table names before using them in SQL identifiers."""
    if SAFE_TABLE_NAME_RE.fullmatch(table_name):
        return
    raise ValueError(f"Unsafe table name: {table_name!r}")


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
