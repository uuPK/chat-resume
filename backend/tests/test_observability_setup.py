import json
import logging
import sys
import unittest
import warnings
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
from app.infra.warnings_setup import suppress_noisy_dependency_warnings  # noqa: E402


class ObservabilitySetupTests(unittest.TestCase):
    def test_langgraph_allowed_objects_warning_is_suppressed(self):
        with warnings.catch_warnings(record=True) as caught:
            suppress_noisy_dependency_warnings()
            warnings.warn_explicit(
                (
                    "The default value of `allowed_objects` will change in a future "
                    "version. Pass an explicit value to suppress this warning."
                ),
                Warning,
                filename="encrypted.py",
                lineno=5,
                module="langgraph.checkpoint.serde.encrypted",
            )

        self.assertEqual(caught, [])

    def test_json_formatter_includes_correlation_fields(self):
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

    def test_uvicorn_access_logging_is_intercepted_by_loguru(self):
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

        payload = json.loads(stream.getvalue().strip().splitlines()[-1])
        self.assertEqual(payload["logger"], "uvicorn.access")
        self.assertEqual(
            payload["message"],
            '127.0.0.1:52839 - "POST /api/ai/chat/stream HTTP/1.1" 200 OK',
        )

    def test_text_logging_does_not_emit_extra_blank_line(self):
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
        self.assertIn("[req=- ses=- tool=-]", lines[0])
        self.assertTrue(lines[0].endswith("single line"))

    def test_text_logging_appends_agent_trace_fields(self):
        stream = StringIO()
        with (
            patch("sys.stderr", stream),
            patch.object(settings, "LOG_FORMAT", "text"),
            patch.object(settings, "LOG_LEVEL", "INFO"),
        ):
            configure_logging()
            logging.getLogger("app.runtime.deepagents_runtime").info(
                "agent.trace.tool.requested",
                extra={
                    "agent_trace": True,
                    "request_id": "req_1234567890",
                    "session_id": "sess_1234567890",
                    "run_id": "run_trace_1234567890",
                    "tool_name": "update_highlight",
                    "tool_input": {
                        "text": "维护多个后台服务" * 20,
                        "api_key": "secret",
                    },
                },
            )

        line = stream.getvalue().strip()
        self.assertIn("INFO deepagent", line)
        self.assertIn("[req=req_12 ses=sess_1 tool=-]", line)
        self.assertIn("trace.tool.requested", line)
        self.assertIn(" | ", line)
        self.assertIn("run=run_trac", line)
        self.assertIn("tool=update_highlight", line)
        self.assertIn('"text":"维护多个后台服务维护多个后台服务', line)
        self.assertIn("...", line)
        self.assertIn('"api_key":"[REDACTED]"', line)

    def test_before_send_enriches_event_with_request_context(self):
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
        with (
            patch("app.infra.langfuse_setup._langfuse_client", None),
            patch.object(settings, "LANGFUSE_PUBLIC_KEY", ""),
            patch.object(settings, "LANGFUSE_SECRET_KEY", ""),
        ):
            self.assertFalse(configure_langfuse())

    def test_configure_langsmith_is_disabled_without_credentials(self):
        with (
            patch("app.infra.langsmith_setup._langsmith_client", None),
            patch.object(settings, "LANGSMITH_TRACING", True),
            patch.object(settings, "LANGSMITH_API_KEY", ""),
        ):
            self.assertFalse(configure_langsmith())

    def test_configure_langsmith_sets_langchain_environment(self):
        class FakeClient:
            def __init__(self, **kwargs):
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

    def test_langsmith_observer_scopes_native_deepagents_tracing(self):
        calls = []

        class FakeTraceContext:
            def __enter__(self):
                calls.append(("enter", None))

            def __exit__(self, exc_type, exc, tb):
                calls.append(("exit", exc_type))

        def fake_tracing_context(**kwargs):
            calls.append(("context", kwargs))
            return FakeTraceContext()

        fake_client = object()
        with (
            patch(
                "app.infra.langsmith_observer.get_langsmith_client",
                return_value=fake_client,
            ),
            patch("langsmith.tracing_context", fake_tracing_context),
            patch.object(settings, "LANGSMITH_PROJECT", "chat-resume-test"),
        ):
            observer = LangSmithRunObserver(
                run_id="run_test",
                agent_type="resume",
                run_kind="chat_stream",
                user_id=1,
                input_text="hello",
                metadata={"request_id": "req_test"},
            )
            with observer:
                observer.on_runtime_event({"tool_pending": True})
                observer.finish("done")

        context_call = next(item for item in calls if item[0] == "context")[1]
        self.assertEqual(context_call["project_name"], "chat-resume-test")
        self.assertTrue(context_call["enabled"])
        self.assertIs(context_call["client"], fake_client)
        self.assertIn("agent:resume", context_call["tags"])
        self.assertEqual(context_call["metadata"]["run_id"], "run_test")
        self.assertEqual(context_call["metadata"]["request_id"], "req_test")
        self.assertIn(("enter", None), calls)
        self.assertIn(("exit", None), calls)
