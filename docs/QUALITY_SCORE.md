# 质量评分

本文档记录项目质量评分维度和检查结果。

## 评分维度

- 功能正确性
- 回归风险
- 测试覆盖
- 用户体验
- 可维护性
- 可观测性

## 当前状态

待补充最新质量检查结果。

## 验证命令

```bash
cd backend && uv run --extra dev python -m pytest tests
cd frontend && npm run type-check && npm run build
```
