# Chat Resume

AI 驱动的简历优化和模拟面试平台，帮助用户创建专业简历并提升面试技能。

## ✨ 主要功能

- 🤖 **AI 智能解析** - 自动提取和结构化简历内容
- 📝 **实时编辑预览** - 所见即所得的简历编辑体验
- 💡 **智能优化建议** - AI 助手提供个性化简历优化指导
- 🎯 **模拟面试训练** - 与 AI 面试官进行真实面试演练
- 📊 **面试评分分析** - 详细的面试表现反馈和改进建议
- 📄 **多格式导出** - 支持 PDF、Word 等多种格式导出

## 🏗️ 技术栈

### 后端

- **FastAPI** - 现代化的 Python Web 框架
- **SQLAlchemy** - 强大的 ORM 数据库操作
- **PostgreSQL** - 可靠的关系型数据库
- **Redis** - 高性能缓存和会话存储
- **Alembic** - 数据库版本管理

### 前端

- **Next.js 14** - React 全栈框架
- **TypeScript** - 类型安全的 JavaScript
- **Tailwind CSS** - 实用优先的 CSS 框架
- **Zustand** - 轻量级状态管理
- **Framer Motion** - 流畅的动画库

### AI 服务

- **OpenRouter** - 多模型 AI 服务集成
- **火山引擎** - 语音识别和合成服务
- **spaCy** - 自然语言处理

## 🚀 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+
- PostgreSQL 13+
- Redis 6+

### 安装步骤

1. **克隆项目**

```bash
git clone <repository-url>
cd chat-resume
```

2. **启动后端**

```bash
./start-backend.sh
```

3. **启动前端**

```bash
./start-frontend.sh
```

4. **访问应用**

- 前端地址: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 📁 项目结构

```
chat-resume/
├── backend/           # FastAPI后端服务
│   ├── app/
│   │   ├── api/      # API路由端点
│   │   ├── core/     # 核心配置和工具
│   │   ├── models/   # 数据库模型
│   │   ├── schemas/  # Pydantic数据模式
│   │   └── services/ # 业务逻辑服务
│   └── alembic/      # 数据库迁移文件
├── frontend/         # Next.js前端应用
│   ├── src/
│   │   ├── app/      # App Router页面
│   │   ├── components/ # React组件
│   │   └── lib/      # 工具函数和配置
└── docs/             # 项目文档
```

## 🔧 开发工具

项目使用以下工具确保代码质量：

- **Ruff** - Python 代码格式化和检查
- **ty** - Python 类型检查
- **ESLint** - JavaScript 代码检查

## 📄 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 🤝 贡献

欢迎提交 Issue 和 Pull Request 来改进项目！
