"""用于覆盖 test_observability_setup.py 对应的回归测试。"""

import json
import logging
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from loguru import logger as loguru_logger

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.config import settings  # noqa: E402
from app.infra.langfuse_observer import LangfuseRunObserver  # noqa: E402
from app.infra.langfuse_setup import configure_langfuse  # noqa: E402
from app.infra.langsmith_observer import LangSmithRunObserver  # noqa: E402
from app.infra.langsmith_setup import configure_langsmith  # noqa: E402
from app.infra.logging_setup import JsonFormatter, configure_logging  # noqa: E402
from app.infra.request_context import log_context  # noqa: E402
from app.infra.sentry_setup import _before_send  # noqa: E402


class ObservabilitySetupTests(unittest.TestCase):
    def test_json_formatter_includes_correlation_fields(self):
        """用于验证jsonformatterincludescorrelationfields。"""
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=10,
            msg="hello observability",
            args=(),
            exc_info=None,
        )
        record.request_id = "req_123"
        record.session_id = "sess_123"
        record.tool_call_id = "tool_123"

        payload = json.loads(JsonFormatter().format(record))
        self.assertEqual(payload["message"], "hello observability")
        self.assertEqual(payload["request_id"], "req_123")
        self.assertEqual(payload["session_id"], "sess_123")
        self.assertEqual(payload["tool_call_id"], "tool_123")

    def test_loguru_json_sink_includes_context_and_redacts_sensitive_extra(self):
        """用于验证logurujsonsinkincludes上下文andredactssensitiveextra。"""
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "json"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            with log_context(
                request_id="req_loguru",
                session_id="sess_loguru",
                tool_call_id="tool_loguru",
            ):
                loguru_logger.bind(api_key="secret", answer=42).info("hello loguru")

        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        self.assertEqual(payload["message"], "hello loguru")
        self.assertEqual(payload["request_id"], "req_loguru")
        self.assertEqual(payload["session_id"], "sess_loguru")
        self.assertEqual(payload["tool_call_id"], "tool_loguru")
        self.assertEqual(payload["api_key"], "[REDACTED]")
        self.assertEqual(payload["answer"], 42)

    def test_standard_logging_is_intercepted_by_loguru(self):
        """用于验证standardloggingisinterceptedbyloguru。"""
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "json"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            with log_context(request_id="req_std"):
                logging.getLogger("test.std").info(
                    "hello stdlib",
                    extra={"session_id": "sess_extra", "safe_value": "ok"},
                )

        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        self.assertEqual(payload["message"], "hello stdlib")
        self.assertEqual(payload["logger"], "test.std")
        self.assertEqual(payload["request_id"], "req_std")
        self.assertEqual(payload["session_id"], "sess_extra")
        self.assertEqual(payload["safe_value"], "ok")

    def test_uvicorn_access_info_logging_is_suppressed(self):
        """用于验证uvicornaccessinfologgingissuppressed。"""
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "json"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            logging.getLogger("uvicorn.access").info(
                '127.0.0.1:52839 - "POST /api/ai/chat/stream HTTP/1.1" 200 OK'
            )

        self.assertEqual(stream.getvalue(), "")

    def test_uvicorn_error_info_logging_is_suppressed(self):
        """用于验证uvicorn错误infologgingissuppressed。"""
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "json"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            logging.getLogger("uvicorn.error").info("Application startup complete.")

        self.assertEqual(stream.getvalue(), "")

    def test_text_logging_does_not_emit_extra_blank_line(self):
        """用于验证textloggingdoesnotemitextrablankline。"""
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "text"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            logging.getLogger("test.text").info("single line")

        lines = stream.getvalue().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("INFO test.text", lines[0])
        self.assertNotIn("[req=", lines[0])
        self.assertNotIn(" ses=", lines[0])
        self.assertNotIn(" tool=", lines[0])
        self.assertTrue(lines[0].endswith("single line"))

    def test_text_logging_appends_agent_trace_fields(self):
        """用于验证textloggingappendsAgenttracefields。"""
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "text"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            logging.getLogger("app.runtime.pi_agent_runtime").info(
                "agent.trace.tool.requested",
                extra={
                    "agent_trace": True,
                    "request_id": "req_1234567890",
                    "session_id": "sess_1234567890",
                    "run_id": "run_trace_1234567890",
                    "tool_name": "update_bullet",
                    "tool_input": {
                        "text": "维护多个后台服务" * 20,
                        "api_key": "secret",
                    },
                },
            )

        line = stream.getvalue().strip()
        self.assertIn("INFO piagent", line)
        self.assertNotIn("[req=", line)
        self.assertNotIn(" ses=", line)
        self.assertNotIn(" tool=-]", line)
        self.assertIn("trace.tool.requested", line)
        self.assertIn(" | ", line)
        self.assertIn("run=run_trac", line)
        self.assertIn("tool=update_bullet", line)
        self.assertIn('"text":"维护多个后台服务维护多个后台服务', line)
        self.assertIn("...", line)
        self.assertIn('"api_key":"[REDACTED]"', line)

    def test_before_send_enriches_event_with_request_context(self):
        """用于验证beforesendenriches事件with请求上下文。"""
        with log_context(
            request_id="req_ctx",
            session_id="sess_ctx",
            tool_call_id="tool_ctx",
        ):
            event = _before_send({"message": "boom"}, {})

        assert event is not None
        self.assertEqual(event["tags"]["request_id"], "req_ctx")
        self.assertEqual(event["tags"]["session_id"], "sess_ctx")
        self.assertEqual(event["tags"]["tool_call_id"], "tool_ctx")
        self.assertEqual(event["extra"]["request_id"], "req_ctx")

    def test_configure_langfuse_is_disabled_without_credentials(self):
        """用于验证configurelangfuseisdisabledwithoutcredentials。"""
        with (
            patch("app.infra.langfuse_setup._langfuse_client", None),
            patch.object(settings, "LANGFUSE_PUBLIC_KEY", ""),
            patch.object(settings, "LANGFUSE_SECRET_KEY", ""),
        ):
            self.assertFalse(configure_langfuse())

    def test_configure_langsmith_is_disabled_without_credentials(self):
        """用于验证configureLangSmithisdisabledwithoutcredentials。"""
        with (
            patch("app.infra.langsmith_setup._langsmith_client", None),
            patch.object(settings, "LANGSMITH_TRACING", True),
            patch.object(settings, "LANGSMITH_API_KEY", ""),
        ):
            self.assertFalse(configure_langsmith())

    def test_configure_langsmith_sets_langchain_environment(self):
        """用于验证configureLangSmithsetslangchainenvironment。"""
        class FakeClient:
            def __init__(self, **kwargs):
                """用于处理init。"""
                self.kwargs = kwargs

        with (
            patch("app.infra.langsmith_setup._langsmith_client", None),
            patch("langsmith.Client", FakeClient),
            patch.object(settings, "LANGSMITH_TRACING", True),
            patch.object(settings, "LANGSMITH_API_KEY", "ls_test"),
            patch.object(settings, "LANGSMITH_ENDPOINT", "https://smith.test"),
            patch.object(settings, "LANGSMITH_PROJECT", "chat-resume-test"),
            patch.object(settings, "LANGSMITH_WORKSPACE_ID", ""),
            patch.dict("os.environ", {}, clear=True),
        ):
            self.assertTrue(configure_langsmith())

            import os

            self.assertEqual(os.environ["LANGSMITH_TRACING"], "true")
            self.assertEqual(os.environ["LANGCHAIN_TRACING_V2"], "true")
            self.assertEqual(os.environ["LANGSMITH_API_KEY"], "ls_test")
            self.assertEqual(os.environ["LANGCHAIN_API_KEY"], "ls_test")
            self.assertEqual(os.environ["LANGSMITH_PROJECT"], "chat-resume-test")
            self.assertEqual(os.environ["LANGCHAIN_PROJECT"], "chat-resume-test")

    def test_langfuse_observer_is_noop_when_client_missing(self):
        """用于验证langfuseobserverisnoopwhen客户端missing。"""
        with patch(
            "app.infra.langfuse_observer.get_langfuse_client", return_value=None
        ):
            observer = LangfuseRunObserver(
                run_id="run_test",
                agent_type="resume",
                run_kind="chat_stream",
                user_id=1,
                input_text="hello",
            )
            with observer:
                observer.on_runtime_event(
                    {"prompt_rendered": True, "system_prompt": "test"}
                )
                observer.finish("done")

    def test_langsmith_observer_is_noop_when_client_missing(self):
        """用于验证LangSmithobserverisnoopwhen客户端missing。"""
        with patch(
            "app.infra.langsmith_observer.get_langsmith_client", return_value=None
        ):
            observer = LangSmithRunObserver(
                run_id="run_test",
                agent_type="resume",
                run_kind="chat_stream",
                user_id=1,
                input_text="hello",
            )
            with observer:
                observer.on_runtime_event({"tool_pending": True})
                observer.finish("done")

    def test_langsmith_observer_mirrors_pi_agent_runtime_events(self):
        """用于验证LangSmithobservermirrorspiAgentruntime事件。"""
        calls = []

        class FakeClient:
            def create_run(self, **kwargs):
                """用于创建run。"""
                calls.append(("create", kwargs))

            def update_run(self, run_id, **kwargs):
                """用于处理updaterun。"""
                calls.append(("update", run_id, kwargs))

        with (
            patch(
                "app.infra.langsmith_observer.get_langsmith_client",
                return_value=FakeClient(),
            ),
            patch.object(settings, "LANGSMITH_PROJECT", "chat-resume-test"),
        ):
            observer = LangSmithRunObserver(
                run_id="12345678123456781234567812345678",
                agent_type="resume",
                run_kind="chat_stream",
                user_id=1,
                input_text="优化简历",
                metadata={"request_id": "req_test"},
            )
            with observer:
                observer.on_runtime_event(
                    {
                        "event_type": "prompt_rendered",
                        "prompt_rendered": True,
                        "system_prompt": "system",
                        "user_message_preview": "优化简历",
                    }
                )
                observer.on_runtime_event(
                    {
                        "event_type": "llm_request",
                        "llm_request": True,
                        "agent_name": "resume_agent",
                        "model": "moonshotai/kimi-k2.6",
                        "messages": [{"role": "user", "content": "优化简历"}],
                        "params": {"temperature": 0.4},
                        "tool_names": ["update_bullet"],
                    }
                )
                observer.on_runtime_event(
                    {
                        "event_type": "tool_pending",
                        "tool_pending": True,
                        "call_id": "call_1",
                        "tool_id": "update_bullet",
                        "tool_name": "优化要点",
                        "tool_input": {"text": "新内容"},
                        "diff_summary": "改动预览",
                    }
                )
                observer.on_runtime_event(
                    {
                        "event_type": "tool_confirmed",
                        "tool_confirmed": True,
                        "call_id": "call_1",
                        "tool_id": "update_bullet",
                        "tool_name": "优化要点",
                        "result": {"success": True},
                    }
                )
                observer.on_runtime_event(
                    {
                        "event_type": "llm_response",
                        "llm_response": True,
                        "model": "moonshotai/kimi-k2.6",
                        "response_content": "已完成",
                        "tool_call_count": 1,
                        "latency_ms": 123.0,
                    }
                )
                observer.finish("已完成", metadata={"event_count": 1})

        created_names = [
            call[1]["name"] for call in calls if call[0] == "create"
        ]
        self.assertIn("resume.chat_stream", created_names)
        self.assertIn("prompt.rendered", created_names)
        self.assertIn("model.moonshotai/kimi-k2.6", created_names)
        self.assertIn("tool.update_bullet", created_names)

        update_payloads = [
            call[2] for call in calls if call[0] == "update"
        ]
        self.assertTrue(
            any(payload.get("outputs", {}).get("response") == "已完成" for payload in update_payloads)
        )
        self.assertTrue(
            any(payload.get("outputs", {}).get("output") == "已完成" for payload in update_payloads)
        )
