# OfferMaster 安装指南

## 环境要求

- Docker Desktop
- Python 3.11+
- uv
- Node.js 20+
- npm

## 一键安装并启动

在项目一级目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1
```

已安装过依赖时可快速启动：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-dev.ps1 -SkipInstall
```

启动完成后访问：

```text
前端：http://127.0.0.1:3000
后端：http://127.0.0.1:8001
健康检查：http://127.0.0.1:8001/health
```

## 数据库

数据库运行在 Docker 中，Docker 本身不需要放进项目文件夹，只需要电脑已安装 Docker Desktop。

默认连接信息：

```text
容器名：offermaster-postgres
数据库：chat_resume
用户：chat_resume
密码：chat_resume_password
宿主机端口：5433
连接地址：postgresql://chat_resume:chat_resume_password@localhost:5433/chat_resume
```

数据库表结构由启动脚本自动执行 Alembic 迁移创建。换电脑运行时会自动创建同样的表结构；业务数据不会自动带过去，如需迁移数据，先在旧电脑导出，再在新电脑导入。

导出：

```powershell
docker exec offermaster-postgres pg_dump -U chat_resume -d chat_resume -Fc -f /tmp/offermaster.dump
docker cp offermaster-postgres:/tmp/offermaster.dump .\offermaster.dump
```

导入：

```powershell
docker cp .\offermaster.dump offermaster-postgres:/tmp/offermaster.dump
docker exec offermaster-postgres pg_restore -U chat_resume -d chat_resume --clean --if-exists /tmp/offermaster.dump
```
