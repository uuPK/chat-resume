# 前端说明

本文档记录前端应用结构、状态管理、API 约定和页面实现规范。

## 技术栈

- Next.js App Router
- React
- TypeScript
- npm

## 关键目录

- `frontend/src/app/`：页面、布局和路由。
- `frontend/src/components/`：可复用组件和业务组件。
- `frontend/src/lib/`：API 客户端、状态和工具函数。
- `frontend/src/types/`：共享类型定义。

## 验证命令

```bash
cd frontend
npm run type-check
npm run build
```

## 待补充

- API 错误处理约定
- 登录态处理
- 关键页面验收标准
- Playwright e2e 覆盖范围
