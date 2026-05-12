## 项目概述
一个AGENT驱动的简历优化和模拟面试网站

## 本地可观测性栈
- 启动命令：在项目根目录运行 `docker compose -f docker-compose.observability.yml up -d`
- 后端建议启动方式：`LOG_FORMAT=json AGENT_TRACE_LOG_ENABLED=true OTEL_TRACES_ENABLED=true ./backend.sh`
- Grafana：`http://localhost:13001`，用于查看日志、指标和 trace，可视化入口。
- Prometheus：`http://localhost:19090`，采集后端 `/metrics`，用于 PromQL 指标查询。
- Loki：`http://localhost:13100`，存储后端 JSON 日志，只提供 API；根路径 404 属于正常现象，健康检查用 `/ready`。
- Promtail：采集 `backend/logs/backend.log` 并推送到 Loki，通常不直接访问。
- Tempo：`http://localhost:13200`，存储 OpenTelemetry trace，主要通过 Grafana 查看。
- OTel Collector：`http://localhost:14318/v1/traces`，接收后端 OTLP trace 并转发到 Tempo。
- 后端指标端点：`http://localhost:8000/metrics`
- Agent 可调用只读查询工具：`query_logs_logql` 查询 Loki 日志，`query_metrics_promql` 查询 Prometheus 指标。
- 常用 PromQL：`sum(rate(chat_resume_http_requests_total[5m]))`
- 常用 LogQL：`{app="chat-resume", service="backend"} |= "agent.trace.tool.executed"`
- 端口使用独立高位端口，避免和其他本地观测栈冲突；不要改回 `3100`、`9090`、`3200`、`4318`、`3000`，除非先确认端口空闲。

# 开发规则

- 测试驱动开发，在构建功能时，先打造一个微小的、端到端的功能切片，寻求反馈，然后在此基础上逐步扩展。 曳光弹的概念源自《程序员修炼之道》。在构建系统时，你希望编写能尽快获得反馈的代码。曳光弹是贯穿系统所有层的小功能切片，让你能尽早测试和验证方法。这有助于识别潜在问题，并确保在投入大量开发时间之前，整体架构是稳健的。

- 永远不要破坏已有接口。新版本必须向后兼容，已有行为不得改变。

- 回归是最严重的错误。新改动引入的问题必须立即修复，不得拖延。

- 每次改动只做一件事。一个提交解决一个问题，不混入无关修改。

- 提交说明必须解释为什么，而不只是做了什么。"修复 bug"不是合格的说明，"防止 X 条件下 Y 崩溃"才是。

- 代码嵌套不能超过3层

- 每一个模块和函数都要写一个简短的注释来注明其功能

- 没有临时代码。进入系统的代码就是永久代码，不存在"以后再清理"。

- 写简单易读的代码，复杂代码是错误的代码。如果需要大段注释才能解释一段逻辑，说明这段逻辑需要重写。

- 先做正确，再做优化。不要在未确认瓶颈前优化性能，但一旦确认必须认真对待。

- uv管理虚拟环境

- 不要用RUFF,BLACK,LINT
