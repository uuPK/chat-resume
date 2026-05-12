"""Run the Resume Agent against the LangSmith evaluation dataset."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
EVAL_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from langsmith import Client, aevaluate  # noqa: E402

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.schemas.resume import dump_resume_content_for_frontend  # noqa: E402

DEFAULT_DATASET = "chat-resume-resume-agent-eval"
DEFAULT_EXPERIMENT_PREFIX = "resume-agent"


def _load_backend_env() -> None:
    """Load backend/.env values when the shell did not export them."""
    env_path = BACKEND_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        os.environ.setdefault(key, value.strip().strip('"').strip("'"))


def _build_agent() -> ResumeAgent:
    """Create the real Resume Agent with the current LLM service."""
    return ResumeAgent()


def _normalize_legacy_highlights(items: Any) -> list[Any]:
    """Convert old string highlights into the current object shape."""
    if not isinstance(items, list):
        return []
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        next_item = dict(item)
        highlights = next_item.get("highlights")
        if isinstance(highlights, list) and all(
            isinstance(highlight, str) for highlight in highlights
        ):
            next_item["highlights"] = [
                {"text": str(highlight).strip()}
                for highlight in highlights
                if str(highlight).strip()
            ]
        normalized.append(next_item)
    return normalized


def _normalize_resume(resume: Any) -> dict[str, Any]:
    """Normalize dataset resume inputs to the app's frontend resume schema."""
    if not isinstance(resume, dict):
        return {}
    next_resume = dict(resume)
    for section in ("education", "work_experience", "projects"):
        if isinstance(next_resume.get(section), list):
            next_resume[section] = _normalize_legacy_highlights(next_resume[section])
    return dump_resume_content_for_frontend(next_resume)


def _inject_job_application(resume: dict[str, Any], jd: dict[str, Any] | None) -> dict[str, Any]:
    """Attach JD data to the resume content for prompt rendering."""
    if jd is None:
        return resume
    next_resume = dict(resume)
    current = next_resume.get("job_application")
    job_application = dict(current) if isinstance(current, dict) else {}
    job_application.update(
        {
            "target_title": str(jd.get("title", "") or ""),
            "target_company": str(jd.get("company", "") or ""),
            "jd_text": str(jd.get("description", "") or ""),
        }
    )
    next_resume["job_application"] = job_application
    return next_resume


def _build_message_with_jd(user_message: str, jd: dict[str, Any] | None) -> str:
    """Append JD text to the user message for eval compatibility."""
    if jd is None:
        return user_message
    jd_text = f"\n\n【目标岗位JD】\n职位：{jd.get('title', '')}\n{jd.get('description', '')}"
    return user_message + jd_text


def _tool_names(tool_calls: Any) -> list[str]:
    """Extract tool names from runtime tool-call records."""
    if not isinstance(tool_calls, list):
        return []
    names: list[str] = []
    for item in tool_calls:
        if isinstance(item, dict):
            name = item.get("name") or item.get("tool") or item.get("tool_name")
        else:
            name = item
        if name:
            names.append(str(name))
    return names


def _infer_decision(reply: str, tool_calls: list[str]) -> str:
    """Infer a coarse decision label for optimize-first eval cases."""
    if tool_calls:
        return "execute"
    if "?" in reply or "？" in reply:
        return "clarify"
    return "respond"


def _filter_examples(
    client: Client,
    *,
    dataset_name: str,
    case_ids: list[str] | None,
    limit: int | None,
) -> Any:
    """Return either the full dataset name or a filtered example list."""
    if not case_ids and limit is None:
        return dataset_name
    examples = list(client.list_examples(dataset_name=dataset_name, limit=1000))
    if case_ids:
        selected = set(case_ids)
        examples = [
            example
            for example in examples
            if isinstance(example.inputs, dict)
            and str(example.inputs.get("case_id", "")) in selected
        ]
    if limit is not None:
        examples = examples[:limit]
    return examples


def _make_target(agent: ResumeAgent):
    """Build the async target function consumed by LangSmith aevaluate."""

    async def target(inputs: dict[str, Any]) -> dict[str, Any]:
        resume = _normalize_resume(inputs.get("resume"))
        jd = inputs.get("jd") if isinstance(inputs.get("jd"), dict) else None
        resume = _inject_job_application(resume, jd)
        message = _build_message_with_jd(str(inputs.get("user_message", "")), jd)
        runtime_events: list[dict[str, Any]] = []
        started_at = time.time()
        result = await agent.runtime.run(
            agent=agent.definition,
            user_message=message,
            context={"resume_content": resume, "allowed_sections": None},
            event_callback=lambda event: runtime_events.append(dict(event)),
        )
        elapsed_s = round(time.time() - started_at, 2)
        reply = str(result.get("content", ""))
        tool_calls = _tool_names(result.get("tool_calls"))
        context = result.get("context")
        resume_after = context.get("resume_content", {}) if isinstance(context, dict) else {}
        return {
            "case_id": inputs.get("case_id"),
            "agent_reply": reply,
            "tool_calls": tool_calls,
            "decision": _infer_decision(reply, tool_calls),
            "elapsed_s": elapsed_s,
            "resume_after": resume_after,
        }

    return target


async def _run(args: argparse.Namespace) -> None:
    """Execute the LangSmith experiment and wait for completion."""
    _load_backend_env()
    if not os.environ.get("OPENROUTER_API_KEY"):
        raise SystemExit("缺少 OPENROUTER_API_KEY，无法运行真实 Agent eval")
    if not os.environ.get("LANGSMITH_API_KEY"):
        raise SystemExit("缺少 LANGSMITH_API_KEY，无法写入 LangSmith experiment")

    client = Client()
    case_ids = [case.strip() for case in args.cases.split(",")] if args.cases else None
    data = _filter_examples(
        client,
        dataset_name=args.dataset,
        case_ids=case_ids,
        limit=args.limit,
    )
    agent = _build_agent()
    results = await aevaluate(
        _make_target(agent),
        data=data,
        experiment_prefix=args.experiment_prefix,
        description="Resume Agent LangSmith evaluation run from local chat-resume checkout.",
        metadata={"agent": "resume_agent", "source": "eval/run_langsmith_experiment.py"},
        max_concurrency=0,
        client=client,
        blocking=True,
    )
    print(f"Experiment: {results.experiment_name}")
    print(f"View in LangSmith: {results.url}")


def main() -> None:
    """Parse CLI arguments and run a LangSmith experiment."""
    parser = argparse.ArgumentParser(description="Run Resume Agent LangSmith experiment")
    parser.add_argument("--dataset", default=DEFAULT_DATASET, help="LangSmith dataset name")
    parser.add_argument(
        "--experiment-prefix",
        default=DEFAULT_EXPERIMENT_PREFIX,
        help="Experiment name prefix",
    )
    parser.add_argument("--cases", help="Comma-separated case ids, for example TC037,TC038")
    parser.add_argument("--limit", type=int, help="Run only the first N matching examples")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
