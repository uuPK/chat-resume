"""用于提供 run_resume_agent_smoke.py 脚本入口。"""

import argparse
import asyncio
import json
import sys
from copy import deepcopy
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.agents.resume.agent import ResumeAgent  # noqa: E402


def build_sample_resume() -> dict:
    """用于构建示例简历。"""
    return {
        "personal_info": {"name": "张三", "position": "后端开发"},
        "summary": {"text": "3年 Python 后端开发经验"},
        "work_experience": [
            {
                "id": "work_1",
                "company": "某科技公司",
                "position": "Python 开发工程师",
                "summary": "负责内部系统开发",
                "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
            }
        ],
        "projects": [],
        "skills": [],
        "education": [],
        "languages": [],
    }


def resume_changed(before: dict, after: dict) -> bool:
    """用于判断 smoke 运行是否实际改动了任意简历字段。"""
    return before != after


async def run_once(agent: ResumeAgent, prompt: str) -> dict:
    """用于运行单次运行。"""
    resume = build_sample_resume()
    before_resume = deepcopy(resume)
    started = perf_counter()
    result = await agent.optimize(prompt, resume, [])
    elapsed = perf_counter() - started
    return {
        "elapsed_seconds": round(elapsed, 2),
        "content": result["content"],
        "tool_calls": result["tool_calls"],
        "mutated_resume": resume,
        "tool_call_count": len(result["tool_calls"]),
        "changed": resume_changed(before_resume, resume),
    }


async def main() -> int:
    """用于执行脚本入口流程。"""
    parser = argparse.ArgumentParser(
        description="Run an end-to-end smoke test for ResumeAgent via OpenRouter."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of repeated runs for success-rate measurement.",
    )
    parser.add_argument(
        "--prompt",
        default="请直接优化我的工作经历，让它更像高级后端工程师简历",
        help="Optimization prompt sent to ResumeAgent.",
    )
    args = parser.parse_args()

    agent = ResumeAgent()
    results = []

    for run_index in range(args.runs):
        try:
            result = await run_once(agent, args.prompt)
            result["run"] = run_index + 1
            result["ok"] = True
            results.append(result)
        except Exception as exc:
            results.append(
                {
                    "run": run_index + 1,
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )

    success_count = sum(1 for item in results if item["ok"])
    mutated_count = sum(1 for item in results if item.get("changed"))

    output = {
        "runs": args.runs,
        "success_count": success_count,
        "success_rate": round(success_count / max(args.runs, 1), 2),
        "mutated_count": mutated_count,
        "mutation_rate": round(mutated_count / max(args.runs, 1), 2),
        "results": results,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if success_count == args.runs else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
