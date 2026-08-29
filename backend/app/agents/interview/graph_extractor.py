from typing import List
from pydantic import BaseModel, Field
import networkx as nx
from langchain_core.prompts import ChatPromptTemplate
from app.agents.interview.llm import get_deepseek_llm

class Relation(BaseModel):
    source: str = Field(description="主体的名称，如候选人姓名、技术栈名称、项目名称等")
    target: str = Field(description="客体的名称，如某项具体技术、业务难点、业务收益等")
    relation_type: str = Field(description="主体和客体之间的关系，例如：精通、开发了、使用、解决、提升了")

class GraphExtraction(BaseModel):
    relations: List[Relation] = Field(description="从文本中提取的实体关系三元组列表")

def extract_knowledge_graph(resume_text: str) -> nx.Graph:
    """
    使用 deepseek-v4-pro 离线分析简历，萃取知识图谱，并返回 NetworkX 图对象。
    """
    # 抽取图谱需要强推理能力，因此选用 deepseek-v4-pro
    llm = get_deepseek_llm(model_name="deepseek-v4-pro")

    # 强制大模型输出结构化的 GraphExtraction JSON
    structured_llm = llm.with_structured_output(GraphExtraction)

    prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一个资深的技术招聘专家和知识图谱工程师。
请从以下候选人的简历文本中提取出核心的知识图谱关系三元组。
要求提炼出候选人的技术栈、核心项目、负责的模块、解决的技术难点以及业务结果。
请以精准的 [实体] -> [关系] -> [实体] 的形式输出。
例如：[候选人] -> 开发了 -> [高并发电商系统]；[高并发电商系统] -> 使用 -> [Redis]；[Redis] -> 解决了 -> [缓存击穿问题]。"""),
        ("user", "简历文本：\n\n{resume_text}")
    ])

    chain = prompt | structured_llm
    extraction: GraphExtraction = chain.invoke({"resume_text": resume_text})

    # 将提取到的结构化三元组转换为 NetworkX 图
    G = nx.Graph()
    for rel in extraction.relations:
        G.add_edge(rel.source, rel.target, relation=rel.relation_type)

    return G

def get_graph_subgraph(G: nx.Graph, query_entity: str, depth: int = 1) -> str:
    """
    根据给定的实体（如“Redis”），从图谱中查询其关联的上下文节点。
    这是 GraphRAG 的核心查询工具逻辑。
    """
    if query_entity not in G:
        return f"知识图谱中未找到实体 '{query_entity}' 的相关记录。"

    # 获取指定深度的自我中心网络 (Ego Graph)
    subgraph = nx.ego_graph(G, query_entity, radius=depth)

    results = []
    for u, v, data in subgraph.edges(data=True):
        relation = data.get("relation", "关联")
        results.append(f"[{u}] --({relation})--> [{v}]")

    return "\n".join(results)
