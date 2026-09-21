# Milvus 与智谱 Embedding-3 部署说明

## 当前方案

面试题 RAG 使用以下链路：

1. 智谱 `embedding-3` 把题库和检索词转换为 1024 维向量。
2. Milvus Lite 把向量持久化到 `/app/data/milvus/question_bank.db`。
3. 用户打开实时面试 WebSocket 时，后端按目标岗位和简历摘要检索最相关的 5 道题。
4. 检索结果写入 LangGraph 面试官的系统提示词，供技术面试官和 HR 面试官选题与追问。

线上服务器只有约 1.7 GiB 内存，因此使用 Milvus Lite。它与 Milvus Standalone 使用同一套 PyMilvus API；业务增长后可以把 `MILVUS_URI` 改为独立 Milvus 服务地址。

## 环境变量

在服务器 `/www/wwwroot/chat-resume/.env.server` 中配置：

```dotenv
RAG_ENABLED=true
RAG_EMBED_API_KEY=智谱_API_Key
```

Compose 已固定以下非敏感设置：

```dotenv
RAG_EMBED_MODEL=embedding-3
RAG_EMBED_DIM=1024
MILVUS_URI=/app/data/milvus/question_bank.db
MILVUS_COLLECTION=question_bank_vectors
```

不要把 `.env.server` 或 API Key 提交到 Git。

## 首次导入

后端容器启动后执行：

```bash
docker compose --env-file .env.server -f compose.server.yml exec backend \
  python -m app.services.rag.ingestion --reset
```

命令会先检查智谱返回的向量维度，再将 `backend/data/question_bank/*.jsonl` 导入 Milvus。`--reset` 会重建题库集合，适合首次部署或全量更新题库。

仅验证题库文件而不调用智谱、也不写入 Milvus：

```bash
docker compose --env-file .env.server -f compose.server.yml exec backend \
  python -m app.services.rag.ingestion --dry-run
```

## 更新与备份

- 更新题库后重新执行带 `--reset` 的导入命令。
- `milvus_data` Docker volume 保存 Milvus Lite 数据，重建后端容器不会丢失向量。
- 备份时同时备份 PostgreSQL 和 `milvus_data` volume。
- 修改模型或维度后必须重新导入；同一集合不能混用不同维度的向量。

## 官方资料

- [智谱 Embedding-3](https://docs.bigmodel.cn/cn/guide/models/embedding/embedding-3)
- [Milvus Lite 快速开始](https://milvus.io/docs/quickstart.md)
- [Milvus 与 LlamaIndex 集成](https://milvus.io/docs/integrate_with_llamaindex.md)
