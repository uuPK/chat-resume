import os
from llama_index.core import VectorStoreIndex

# 我们直接复用 ingestion.py 中写好的连接数据库和模型的函数，避免重复造轮子
from app.services.rag.ingestion import (
    build_embed_model,
    build_vector_store,
    DEFAULT_TABLE_NAME,
    DEFAULT_EMBED_DIM,
    DEFAULT_EMBED_MODEL,
)
from app.infra.config import settings

async def retrieve_interview_questions(query: str, limit: int = 5) -> str:
    """
    根据查询词（如：前端开发 React），去向量数据库中检索最相关的面试题。
    """
    # 1. 准备大模型的 Embedding（向量化）模型，用于把你的查询词变成数学向量
    embed_model = build_embed_model(
        model=os.getenv("RAG_EMBED_MODEL", DEFAULT_EMBED_MODEL),
        embed_dim=int(os.getenv("RAG_EMBED_DIM", str(DEFAULT_EMBED_DIM))),
    )
    
    # 2. 连接到 PostgreSQL 的 pgvector 数据库表
    vector_store = build_vector_store(
        database_url=settings.DATABASE_URL,
        table_name=os.getenv("RAG_VECTOR_TABLE", DEFAULT_TABLE_NAME),
        embed_dim=int(os.getenv("RAG_EMBED_DIM", str(DEFAULT_EMBED_DIM))),
        hybrid_search=False, 
    )
    
    # 3. 使用 LlamaIndex 将向量数据库包装成一个可查询的索引
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=embed_model,
    )
    
    # 4. 把索引变成一个“检索器”，设置每次最多返回 limit（默认 5）个结果
    retriever = index.as_retriever(similarity_top_k=limit)
    
    # 5. 执行异步搜索！(aretrieve 会去数据库里比对向量相似度)
    nodes = await retriever.aretrieve(query)
    
    if not nodes:
        return ""
        
    # 6. 把检索到的所有题目的文本拼接成一个长字符串，用 --- 隔开
    retrieved_texts = []
    for node in nodes:
        retrieved_texts.append(node.text)
        
    return "\n\n---\n\n".join(retrieved_texts)