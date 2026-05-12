# 本地可观测性

本地堆栈覆盖三类信号：

- 日志：`backend/logs/backend.log` 由 Promtail 采集到 Loki。
- 指标：后端 `/metrics` 由 Prometheus 抓取。
- 追踪：后端 OTLP trace 发送到 OTel Collector，再转发到 Tempo。

## 启动

在项目根目录启动可观测性服务：

```bash
docker compose -f docker-compose.observability.yml up -d
```

启动后端时建议开启 JSON 日志和 agent trace：

```bash
LOG_FORMAT=json AGENT_TRACE_LOG_ENABLED=true OTEL_TRACES_ENABLED=true ./backend.sh
```

Grafana 入口：

```text
http://localhost:13001
```

## Agent 查询

简历 Agent 现在有两个只读工具：

- `query_logs_logql`：查询 Loki，默认地址 `LOKI_BASE_URL=http://localhost:13100`
- `query_metrics_promql`：查询 Prometheus，默认地址 `PROMETHEUS_BASE_URL=http://localhost:19090`

可直接让 Agent 询问：

```text
用 PromQL 看最近 5 分钟后端请求量
```

等价查询：

```promql
sum(rate(chat_resume_http_requests_total[5m]))
```

也可以让 Agent 查日志：

```text
用 LogQL 找最近的 agent.trace.tool.executed 日志
```

等价查询：

```logql
{app="chat-resume", service="backend"} |= "agent.trace.tool.executed"
```

## 常用端点

- Prometheus: `http://localhost:19090`
- Loki: `http://localhost:13100`
- Tempo: `http://localhost:13200`
- OTel HTTP receiver: `http://localhost:14318/v1/traces`
- 后端指标: `http://localhost:8000/metrics`

## 验证

确认 Prometheus 能看到后端：

```bash
curl "http://localhost:19090/api/v1/query?query=up%7Bjob%3D%22chat-resume-backend%22%7D"
```

确认 Loki 能查到后端日志：

```bash
curl -G "http://localhost:13100/loki/api/v1/query_range" \
  --data-urlencode 'query={app="chat-resume", service="backend"}' \
  --data-urlencode 'limit=5'
```

确认后端本身暴露指标：

```bash
curl http://localhost:8000/metrics
```
