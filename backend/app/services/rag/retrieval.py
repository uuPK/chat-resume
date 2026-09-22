import asyncio
import os
from llama_index.core import VectorStoreIndex

# 我们直接复用 ingestion.py 中写好的连接数据库和模型的函数，避免重复造轮子
from app.services.rag.ingestion import (
    build_embed_model,
    build_vector_store,
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBED_DIM,
    DEFAULT_EMBED_MODEL,
    DEFAULT_MILVUS_URI,
)

async def retrieve_interview_questions(query: str, limit: int = 5) -> str:
    """Search Milvus for interview questions related to the query."""
    if not is_rag_enabled():
        return ""

    embed_dim = int(os.getenv("RAG_EMBED_DIM", str(DEFAULT_EMBED_DIM)))
    embed_model = build_embed_model(
        model=os.getenv("RAG_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        embed_dim=embed_dim,
    )
    vector_store = build_vector_store(
        uri=os.getenv("RAG_MILVUS_URI", DEFAULT_MILVUS_URI),
        token=os.getenv("MILVUS_TOKEN", ""),
        collection_name=os.getenv("MILVUS_COLLECTION", DEFAULT_COLLECTION_NAME),
        embed_dim=embed_dim,
    )
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )
    retriever = index.as_retriever(similarity_top_k=limit)
    nodes = await asyncio.to_thread(retriever.retrieve, query)

    if not nodes:
        return ""

    return "\n\n---\n\n".join(node.text for node in nodes)


def is_rag_enabled() -> bool:
    """Return whether question-bank retrieval is enabled for this process."""
    return os.getenv("RAG_ENABLED", "false").strip().lower() not in {
        "false",
        "0",
        "no",
    }
