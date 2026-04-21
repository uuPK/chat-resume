# 文档索引

本索引用来给人和智能体提供最小可用的仓库地图，目的是先定位信息，再深入具体文档。

## 阅读顺序

1. `../AGENTS.md`：任务执行协议和标准验证入口
2. `../ARCHITECTURE.md`：分层、职责和主数据流
3. 对应领域文档：产品、架构、执行计划、参考资料

## 目录说明

### 架构

- `../ARCHITECTURE.md`：全局架构地图和依赖规则
- `architecture/index.md`：架构文档入口
- `architecture/project-structure.md`：项目目录和关键入口速览
- `architecture/current-test-report.md`：测试覆盖和当前验证现状

### 产品

- `product/index.md`：产品文档入口
- `product/chat-resume-product-improvement-plan.md`：当前产品改进方向

### 执行计划

- `exec-plans/README.md`：执行计划的写法和生命周期
- `exec-plans/active/`：进行中的任务计划
- `exec-plans/completed/`：已完成任务归档

### 参考资料

- `references/README.md`：参考资料入口
- `references/openai-llms.txt`：OpenAI / Codex 协作参考
- `references/uv-llms.txt`：`uv` 使用约定参考

## 维护规则

- 新文档优先放到明确目录，不要继续堆在 `docs/` 根目录
- 根目录文档只保留高频入口和已有历史文档
- 文档更新时，优先补索引和交叉链接，避免孤立页面
