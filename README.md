# Chat Resume 

AI驱动的简历优化和模拟面试平台，支持实时预览和智能内容分析。

## 功能特性

-  **AI智能简历解析** - 使用先进AI技术进行智能文本提取和结构化
-  **实时编辑预览** - 编辑时即时预览简历内容
-  **简历优化Agent** - 与AI助手实时交流优化简历
-  **面试官Agent** - 与面试官Agent进行模拟面试，打磨面试技巧

## 技术架构

### 前端
- **Next.js 14** - 带有App Router的React框架
- **React 18** - 现代React与hooks和suspense
- **TypeScript** - 类型安全开发
- **Tailwind CSS** - 实用优先的样式框架
- **Framer Motion** - 流畅的动画效果

### 后端
- **FastAPI** - 高性能Python web框架
- **SQLAlchemy** - 数据库ORM与关系映射
- **PostgreSQL** - 强大的关系型数据库
- **Redis** - 缓存和会话管理
- **Alembic** - 数据库迁移管理

### AI集成
- **OpenRouter API** - 支持多种大语言模型
- **Google Gemini** - 先进的语言理解能力
- **流式传输** - 实时AI响应
- **上下文记忆** - 多轮对话支持

### 文件处理
- **PDF支持** - 使用pdfplumber提取PDF简历文本
- **DOCX支持** - Microsoft Word文档处理



## 快速开始

### 环境要求
- Python 3.10+
- Node.js 18+
- PostgreSQL
- Redis

### 环境配置

1. **克隆仓库**
   ```bash
   git clone https://github.com/849261680/chat-resume.git
   cd chat-resume
   ```

2. **后端配置**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # Windows用户: venv\\Scripts\\activate
   pip install -r requirements.txt
   
   # 复制环境配置文件并编辑
   cp .env.example .env
   # 编辑.env文件，填入数据库和API凭据
   ```

3. **前端配置**
   ```bash
   cd frontend
   npm install
   
   # 复制环境配置文件并编辑
   cp .env.example .env.local
   # 编辑.env.local文件，填入API端点
   ```

### 环境变量

**后端 (.env)**
```env
DATABASE_URL=postgresql://username:password@localhost/chat_resume
REDIS_URL=redis://localhost:6379
SECRET_KEY=your-secret-key
OPENROUTER_API_KEY=your-openrouter-api-key
OPENROUTER_API_BASE=https://openrouter.ai/api/v1
OPENROUTER_MODEL=google/gemini-2.5-flash
```

**前端 (.env.local)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 运行应用

1. **启动后端**
   ```bash
   cd backend
   source venv/bin/activate
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **启动前端**
   ```bash
   cd frontend
   npm run dev
   ```

3. **访问应用**
   - 前端: http://localhost:3000
   - 后端API: http://localhost:8000
   - API文档: http://localhost:8000/docs

##  AI简历解析器

### 工作原理

1. **文件上传** - 支持PDF、DOCX和TXT格式
2. **文本提取** - 智能提取文本并保留结构
3. **AI处理** - 使用AI分析和结构化内容
4. **质量评估** - 计算完整性和准确性评分
5. **实时预览** - 即时显示解析结果

### 支持的内容类型

- 个人信息（姓名、联系方式、社交链接）
- 教育背景（学校、学位、日期）
- 工作经验（公司、职位、描述）
- 技术技能（按类型分类）
- 项目经验（技术栈、角色、成就）
- 成就和认证

##  AI聊天功能

### 核心特性

- **实时对话** - 与AI助手进行流式对话
- **上下文记忆** - 记住整个对话历史
- **专业建议** - 基于简历内容提供针对性优化建议
- **多轮交互** - 支持深入的多轮对话优化

### 使用场景

- 简历内容优化建议
- 职业发展咨询
- 技能提升建议
- 面试准备指导

## 开发

### 项目结构

```
chat-resume/
├── backend/                 # FastAPI后端
│   ├── app/
│   │   ├── api/            # API路由
│   │   ├── core/           # 配置文件
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic模式
│   │   └── services/       # 业务逻辑
│   ├── alembic/            # 数据库迁移
│   └── requirements.txt
├── frontend/               # Next.js前端
│   ├── src/
│   │   ├── app/           # App Router页面
│   │   ├── components/    # React组件
│   │   └── lib/           # 工具库
│   └── package.json
└── README.md
```

### 数据库迁移

```bash
cd backend
# 创建新迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head
```

### 测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm test
```

## 部署

### Railway.app（推荐）

1. **连接GitHub仓库**
   - 将仓库链接到Railway
   - 在Railway控制台设置环境变量

2. **后端部署**
   - Railway会自动检测Procfile
   - 设置`RAILWAY_SERVICE_TYPE=backend`

3. **前端部署**
   - 单独部署前端或使用Vercel
   - 在环境变量中更新API URL

### Docker部署

```bash
# 使用Docker Compose构建和运行
docker-compose up --build
```







