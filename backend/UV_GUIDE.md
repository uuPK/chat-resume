# UV 使用指南

## 快速开始

### 1. 创建虚拟环境

```bash
uv venv
```

### 2. 激活虚拟环境

```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. 安装依赖

#### 方法 A：使用 requirements.txt（推荐）

```bash
uv pip install -r requirements.txt
```

#### 方法 B：使用 pyproject.toml

```bash
uv sync
```

#### 方法 C：直接运行（无需激活）

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 常用命令

### 包管理

```bash
# 安装包
uv pip install package_name

# 卸载包
uv pip uninstall package_name

# 查看已安装的包
uv pip list

# 更新包
uv pip install --upgrade package_name
```

### 虚拟环境管理

```bash
# 创建新环境
uv venv my-env

# 删除环境
rm -rf .venv

# 查看Python版本
uv python --version
```

## 故障排除

如果遇到 `uv sync` 错误，请使用：

```bash
uv pip install -r requirements.txt
```

## 项目结构

```
backend/
├── app/           # 应用代码
├── .venv/         # 虚拟环境（自动忽略）
├── requirements.txt
├── pyproject.toml
└── UV_GUIDE.md    # 本文件
```
