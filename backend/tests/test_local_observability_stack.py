"""用于覆盖 test_local_observability_stack.py 对应的回归测试。"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.executor import ResumeToolExecutor  # noqa: E402
from app.infra.prometheus_metrics import (  # noqa: E402
    record_http_request,
    render_metrics,
    reset_metrics_for_tests,
)
from app.services.observability import ObservabilityQueryService  # noqa: E402
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA  # noqa: E402


class LocalObservabilityStackTests(unittest.TestCase):
    def tearDown(self):
        """用于清理测试后置状态。"""
        reset_metrics_for_tests()

    def test_metrics_renderer_exports_http_and_db_metrics(self):
        """用于验证指标rendererexportshttpand数据库指标。"""
        record_http_request(
            method="get",
            path="/health",
            status=200,
            duration_seconds=0.042,
            db_query_count=2,
            db_query_duration_seconds=0.011,
        )

        output = render_metrics()

        self.assertIn("chat_resume_http_requests_total", output)
        self.assertIn('method="GET",path="/health",status="200"', output)
        self.assertIn("chat_resume_http_request_duration_seconds_bucket", output)
        self.assertIn(
            'chat_resume_http_request_duration_seconds_bucket{method="GET",path="/health",le="0.05"} 1',
            output,
        )
        self.assertIn(
            'chat_resume_http_request_duration_seconds_bucket{method="GET",path="/health",le="+Inf"} 1',
            output,
        )
        self.assertIn('chat_resume_db_queries_total{path="/health"} 2', output)
        self.assertIn(
            'chat_resume_db_query_duration_seconds_total{path="/health"} 0.011000',
            output,
        )

    def test_promql_service_calls_prometheus_query_api(self):
        """用于验证promqlservicecallsprometheusqueryAPI。"""
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """用于处理handler。"""
            seen["path"] = request.url.path
            seen["query"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "resultType": "vector",
                        "result": [{"metric": {"job": "backend"}, "value": [1, "1"]}],
                    },
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        service = ObservabilityQueryService(
            prometheus_base_url="http://prometheus.test",
            client=client,
        )

        result = service.query_promql("up", time="1710000000")

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "prometheus")
        self.assertEqual(seen["path"], "/api/v1/query")
        self.assertEqual(seen["query"]["query"], "up")
        self.assertEqual(seen["query"]["time"], "1710000000")

    def test_logql_service_calls_loki_query_range_api(self):
        """用于验证logqlservicecallslokiqueryrangeAPI。"""
        seen = {}

        def handler(request: httpx.Request) -> httpx.Response:
            """用于处理handler。"""
            seen["path"] = request.url.path
            seen["query"] = dict(request.url.params)
            return httpx.Response(
                200,
                json={
                    "status": "success",
                    "data": {
                        "resultType": "streams",
                        "result": [
                            {
                                "stream": {"service": "backend"},
                                "values": [["1710000000000000000", "hello"]],
                            }
                        ],
                    },
                },
            )

        client = httpx.Client(transport=httpx.MockTransport(handler))
        service = ObservabilityQueryService(
            loki_base_url="http://loki.test",
            client=client,
        )

        result = service.query_logql(
            '{service="backend"}',
            limit=5,
            start="1710000000000000000",
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["source"], "loki")
        self.assertEqual(seen["path"], "/loki/api/v1/query_range")
        self.assertEqual(seen["query"]["query"], '{service="backend"}')
        self.assertEqual(seen["query"]["limit"], "5")
        self.assertEqual(seen["query"]["direction"], "backward")
        self.assertEqual(seen["query"]["start"], "1710000000000000000")

    def test_resume_agent_exposes_readonly_observability_tools(self):
        """用于验证简历Agentexposesreadonly可观测性tools。"""
        schema_names = {
            item["function"]["name"]
            for item in RESUME_TOOLS_SCHEMA
            if item.get("type") == "function"
        }

        self.assertIn("query_logs_logql", schema_names)
        self.assertIn("query_metrics_promql", schema_names)
        self.assertIn(
            "query_logs_logql",
            ResumeAgent().definition.auto_execute_tool_names,
        )
        self.assertIn(
            "query_metrics_promql",
            ResumeAgent().definition.auto_execute_tool_names,
        )

    def test_resume_tool_executor_dispatches_promql_tool(self):
        """用于验证简历toolexecutordispatchespromqltool。"""
        class FakeService:
            def query_promql(self, query, *, time=None):
                """用于处理querypromql。"""
                return {
                    "success": True,
                    "source": "prometheus",
                    "query": query,
                    "result_type": "vector",
                    "results": [],
                }

        with patch(
            "app.tools.observability.query_tools.ObservabilityQueryService",
            return_value=FakeService(),
        ):
            result = ResumeToolExecutor().execute(
                tool_name="query_metrics_promql",
                tool_input={"query": "up"},
                context={"resume_content": {}},
            )

        self.assertEqual(result["tool_name"], "查询指标")
        self.assertEqual(result["result"]["source"], "prometheus")
        self.assertTrue(result["result"]["success"])


if __name__ == "__main__":
    unittest.main()
