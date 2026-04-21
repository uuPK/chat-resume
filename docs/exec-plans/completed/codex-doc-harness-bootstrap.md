# Codex 文档协作骨架搭建

## 背景

仓库已有 `AGENTS.md`、`CLAUDE.md` 和若干散落在 `docs/` 根目录的文档，但还没有形成面向智能体执行的稳定文档导航结构。

## 目标

把协作文档整理成“入口协议 + 架构地图 + 文档索引 + 执行计划目录 + 参考资料”的最小可用骨架。

## 非目标

- 不重写现有产品和测试文档正文
- 不大规模迁移历史文档
- 不改动业务代码和测试逻辑

## 步骤

1. 盘点现有协作文档和 `docs/` 内容 -> verify: `find docs -maxdepth 3 -type f | sort`
2. 收敛 `AGENTS.md` 和 `CLAUDE.md` 的职责边界 -> verify: 手动检查两者是否仍然存在规则重复
3. 新增 `docs/index.md`、`docs/exec-plans/`、`docs/references/` 骨架 -> verify: `find docs -maxdepth 3 -type f | sort`
4. 写入本次执行计划归档，作为后续任务样例 -> verify: 手动检查目录中是否存在 completed plan

## 决策日志

- 保留 `CLAUDE.md`，但只做兼容入口说明，避免直接删除带来外部工具断链
- 历史文档先通过索引挂载，不立即迁移目录，降低一次性整理成本
- 参考资料只补高频的 `OpenAI / Codex` 和 `uv`，先满足当前仓库最常见协作场景

## 当前状态

已完成。

## 下一步

- 继续把新增领域文档收敛到 `docs/product/`、`docs/architecture/` 等子目录
- 为后续中大型任务默认创建 `docs/exec-plans/active/*.md`
