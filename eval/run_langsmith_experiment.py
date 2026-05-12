"""Run the Resume Agent against the LangSmith evaluation dataset."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
if str(EVAL_DIR) not in sys.path:
    sys.path.insert(0, str(EVAL_DIR))

from langsmith import Client, aevaluate  # noqa: E402

from harness import build_agent, load_backend_env, run_agent_target  # noqa: E402

DEFAULT_DATASET = "chat-resume-resume-agent-eval"
DEFAULT_EXPERIMENT_PREFIX = "resume-agent"


def _filter_examples(
    client: Client,
    *,
    dataset_name: str,
    case_ids: list[str] | None,
    limit: int | None,
) -> Any:
    """用于按 case id 或数量限制筛选 LangSmith dataset examples。"""
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


def _make_target(agent):
    """用于构造 LangSmith aevaluate 消费的异步 target。"""

    async def target(inputs: dict[str, Any]) -> dict[str, Any]:
        result = await run_agent_target(agent, inputs)
        result.pop("runtime_events", None)
        return result

    return target


async def _run(args: argparse.Namespace) -> None:
    """用于执行 LangSmith experiment 并等待服务端结果生成。"""
    load_backend_env()
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
    results = await aevaluate(
        _make_target(build_agent()),
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
    """用于解析 CLI 参数并运行 LangSmith experiment。"""
    parser = argparse.ArgumentParser(description="Run Resume Agent LangSmith eval")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--experiment-prefix", default=DEFAULT_EXPERIMENT_PREFIX)
    parser.add_argument("--cases", help="逗号分隔的 case_id，例如 TC037,TC038")
    parser.add_argument("--limit", type=int, help="只运行前 N 条样本")
    args = parser.parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
