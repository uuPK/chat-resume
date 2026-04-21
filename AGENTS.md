# AGENTS.md

本文件是 Codex 在本仓库内执行任务时的唯一入口说明，目的是让智能体先找到地图，再深入具体文档。

## 1. 先读哪些文件

收到任务后，默认按以下顺序读取：

1. 本文件 `AGENTS.md`
2. 架构地图 `ARCHITECTURE.md`
3. 文档索引 `docs/index.md`
4. 与任务直接相关的入口文件和执行计划

如果任务只涉及某一层，只继续读取对应文档，不要一次性加载整个仓库说明。

## 2. 任务执行协议

每次任务都要先明确以下四项：

- 目标：这次具体要完成什么
- 非目标：这次明确不做什么
- 约束：必须遵守的实现和协作要求
- 验证：如何证明任务已经完成

如果需求存在关键歧义，并且错误假设会导致返工或破坏行为，需要先向用户确认。

## 3. 仓库级约束

- Python 依赖和虚拟环境统一使用 `uv`
- 新增或修改的 Python 模块和函数，需要补一句简短中文注释说明为什么存在
- 修复缺陷时，优先先写能复现问题的测试，再修复到通过
- 不要跳过验证；实现完成后必须运行与改动范围匹配的检查

## 4. 标准验证命令

按改动范围选择最小充分验证：

- 后端测试：`cd backend && uv run pytest`
- 后端静态检查：`cd backend && uv run ruff check .`
- 后端类型检查：`cd backend && uv run mypy app`
- 前端 Lint：`cd frontend && npm run lint`
- 前端类型检查：`cd frontend && npm run type-check`
- 前端构建：`cd frontend && npm run build`
- 前端 E2E：`cd frontend && npm run e2e`

如果任务是多步骤改造，每完成一个里程碑就先跑一次与该步对应的验证。

## 5. 文档地图

把 `AGENTS.md` 当目录，不要把细节长期堆在这里。

- 架构总览：`ARCHITECTURE.md`
- 文档总索引：`docs/index.md`
- 执行计划说明：`docs/exec-plans/README.md`
- 产品相关文档：`docs/product/`
- 架构相关文档：`docs/architecture/`
- 参考资料：`docs/references/`

现有可复用文档入口：

- 项目结构：`docs/architecture/project-structure.md`
- 产品改进：`docs/product/chat-resume-product-improvement-plan.md`
- 测试现状：`docs/architecture/current-test-report.md`

## 6. 执行计划规则

满足以下任一条件时，先创建或更新执行计划：

- 任务预计超过 30 分钟
- 涉及前后端联动或跨模块改造
- 需要分阶段验证
- 需要中断后恢复上下文

执行计划放在：

- 进行中：`docs/exec-plans/active/`
- 已完成：`docs/exec-plans/completed/`

计划至少包含：

1. 背景与目标
2. 非目标
3. 分步骤计划，每步附 `verify`
4. 决策日志
5. 当前状态 / 下一步


