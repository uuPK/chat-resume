# 日志等级切换指南

## 支持的日志等级

- **DEBUG**: 最详细的日志信息，用于调试问题
- **INFO**: 一般信息，确认程序正常运行
- **WARNING**: 警告信息，表示可能的问题
- **ERROR**: 错误信息，程序遇到问题但能继续运行
- **CRITICAL**: 严重错误，程序无法继续运行

## 切换方法

### 方法一：使用环境变量（推荐）

1. **复制配置文件**:
   ```bash
   cp .env.example .env
   ```

2. **修改日志等级**:
   编辑 `.env` 文件：
   ```env
   LOG_LEVEL=DEBUG    # 开发调试时使用
   LOG_LEVEL=INFO     # 生产环境推荐
   LOG_LEVEL=WARNING  # 只显示警告和错误
   LOG_LEVEL=ERROR    # 只显示错误信息
   ```

3. **重启服务**:
   ```bash
   # 开发环境
   uvicorn app.main:app --reload

   # 生产环境
   # 根据你的部署方式重启服务
   ```

### 方法二：直接设置环境变量

```bash
# Linux/macOS
export LOG_LEVEL=DEBUG
uvicorn app.main:app --reload

# Windows (PowerShell)
$env:LOG_LEVEL="DEBUG"
uvicorn app.main:app --reload

# Windows (CMD)
set LOG_LEVEL=DEBUG
uvicorn app.main:app --reload
```

### 方法三：启动时指定

```bash
LOG_LEVEL=DEBUG uvicorn app.main:app --reload
```

## 不同等级的使用场景

### 开发调试
```env
LOG_LEVEL=DEBUG
```
- 显示所有日志，包括详细的调试信息
- 用于排查问题和开发新功能

### 测试环境
```env
LOG_LEVEL=INFO
```
- 显示一般信息和警告
- 保持日志简洁但信息充足

### 生产环境
```env
LOG_LEVEL=WARNING
# 或
LOG_LEVEL=ERROR
```
- 只显示重要的警告和错误
- 减少日志文件大小

## 日志等级过滤示例

假设有如下日志代码：
```python
logger.debug("这是调试信息")
logger.info("这是一般信息")
logger.warning("这是警告")
logger.error("这是错误")
```

不同等级的输出结果：

**DEBUG等级** (显示所有):
```
2025-01-02 14:30:15 - module - DEBUG - 这是调试信息
2025-01-02 14:30:15 - module - INFO - 这是一般信息
2025-01-02 14:30:15 - module - WARNING - 这是警告
2025-01-02 14:30:15 - module - ERROR - 这是错误
```

**INFO等级** (不显示DEBUG):
```
2025-01-02 14:30:15 - module - INFO - 这是一般信息
2025-01-02 14:30:15 - module - WARNING - 这是警告
2025-01-02 14:30:15 - module - ERROR - 这是错误
```

**WARNING等级** (只显示警告和错误):
```
2025-01-02 14:30:15 - module - WARNING - 这是警告
2025-01-02 14:30:15 - module - ERROR - 这是错误
```

## 生产环境配置建议

对于生产环境，建议：

1. **使用WARNING或ERROR等级**减少日志量
2. **配置日志轮转**避免日志文件过大
3. **将错误日志发送到监控系统**
4. **定期清理或归档日志文件**

## 查看当前日志等级

启动服务时会显示当前的日志配置：
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete.
```