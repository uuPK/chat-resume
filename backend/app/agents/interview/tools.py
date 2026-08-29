from langchain_core.tools import tool
import networkx as nx
from typing import Optional

# 假设我们在初始化 Agent 时，把萃取好的简历知识图谱注入到全局变量或传递进来
# 这里为了演示，我们提供一个依赖注入的占位符
_GLOBAL_RESUME_GRAPH: Optional[nx.Graph] = None

def set_global_graph(g: nx.Graph):
    global _GLOBAL_RESUME_GRAPH
    _GLOBAL_RESUME_GRAPH = g

@tool
def query_graph_rag(entity_name: str) -> str:
    """
    当需要深入挖掘候选人简历中某个技术点或项目的细节时调用此工具。
    输入一个实体名称（如 'React', '高并发', '某项目名称'），返回该实体在候选人知识图谱中的关联信息。
    """
    from app.agents.interview.graph_extractor import get_graph_subgraph

    if _GLOBAL_RESUME_GRAPH is None:
        return "知识图谱尚未初始化。"

    # 获取一跳和二跳关系，给大模型提供足够上下文
    return get_graph_subgraph(_GLOBAL_RESUME_GRAPH, entity_name, depth=2)


import asyncio
from app.services.rag.retrieval import retrieve_interview_questions

@tool
def search_question_bank(query: str) -> str:
    """
    【核心专业知识库检索工具】
    当你作为技术面试官，需要针对候选人的技术栈（如 "React 性能优化", "Redis 分布式锁"）
    寻找高难度、专业的标准面试题和考核点时，请调用此工具。
    它会连接后端的 pgvector 向量数据库，为您提供业界标准的八股文和标准答案参考。
    """
    try:
        # 因为原有的检索器是异步函数，在同步工具中我们需要用 run_coroutine_threadsafe 或 asyncio.run 包装
        # （假设当前外层图运行在异步/同步环境，这里做了防御性调用）
        try:
            loop = asyncio.get_running_loop()
            import nest_asyncio
            nest_asyncio.apply()
        except RuntimeError:
            pass

        result = asyncio.run(retrieve_interview_questions(query, limit=3))
        if not result:
            return f"向量题库中未找到关于 '{query}' 的相关专业面试题。"
        return f"[向量题库检索结果]：\n{result}"
    except Exception as e:
        return f"查询向量题库失败: {str(e)}"
