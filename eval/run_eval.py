"""
Agent 评测执行器

用法：
    cd backend
    uv run python ../eval/run_eval.py [--cases TC001,TC002] [--output results.json]

依赖：
    - 需要设置 ANTHROPIC_API_KEY 环境变量
    - 从 backend/ 目录运行（以便 import app.*）
"""

import asyncio
import json
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# 将 backend 加入 sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
EVAL_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.definitions.resume_agent import ResumeAgent  # noqa: E402
from app.agents.runtime.agent_runtime import AgentRuntime  # noqa: E402
from app.services.llm.chat_service import ChatService  # noqa: E402


def load_cases(filter_ids: list[str] | None = None) -> list[dict]:
    cases_path = EVAL_DIR / "test_cases.json"
    with open(cases_path) as f:
        cases = json.load(f)
    if filter_ids:
        cases = [c for c in cases if c["id"] in filter_ids]
    return cases


def load_resume(filename: str) -> dict:
    path = EVAL_DIR / "cases" / filename
    with open(path) as f:
        return json.load(f)


def load_jd(filename: str) -> dict | None:
    if not filename:
        return None
    path = EVAL_DIR / "cases" / filename
    with open(path) as f:
        return json.load(f)


def build_agent() -> ResumeAgent:
    """构建使用真实 LLM 的 Agent。"""
    chat_service = ChatService()
    agent = ResumeAgent()
    agent.runtime = AgentRuntime(chat_service=chat_service)
    return agent


def build_message_with_jd(user_message: str, jd: dict | None) -> str:
    """将 JD 信息追加到用户消息中。"""
    if not jd:
        return user_message
    jd_text = f"\n\n【目标岗位JD】\n职位：{jd['title']}\n{jd['description']}"
    return user_message + jd_text


async def run_single_case(agent: ResumeAgent, case: dict) -> dict:
    """运行单个测试用例，返回原始结果。"""
    resume = load_resume(case["resume_file"])
    jd = load_jd(case.get("jd_file"))
    message = build_message_with_jd(case["user_message"], jd)

    start = time.time()
    try:
        result = await agent.optimize(
            user_message=message,
            resume_content=resume,
        )
        elapsed = round(time.time() - start, 2)
        return {
            "id": case["id"],
            "desc": case["desc"],
            "status": "ok",
            "elapsed_s": elapsed,
            "agent_reply": result["content"],
            "tool_calls": [tc.get("name", tc.get("tool", "")) if isinstance(tc, dict) else str(tc)
                           for tc in (result.get("tool_calls") or [])],
            "resume_before": load_resume(case["resume_file"]),
            "resume_after": result.get("resume_content", {}),
            "case": case,
        }
    except Exception as e:
        elapsed = round(time.time() - start, 2)
        return {
            "id": case["id"],
            "desc": case["desc"],
            "status": "error",
            "elapsed_s": elapsed,
            "error": str(e),
            "agent_reply": "",
            "tool_calls": [],
            "resume_before": {},
            "resume_after": {},
            "case": case,
        }


async def run_all(filter_ids: list[str] | None = None) -> list[dict]:
    cases = load_cases(filter_ids)
    agent = build_agent()
    results = []

    print(f"\n{'='*60}")
    print(f"共 {len(cases)} 个测试用例")
    print(f"{'='*60}\n")

    for i, case in enumerate(cases, 1):
        print(f"[{i}/{len(cases)}] {case['id']} - {case['desc']}")
        result = await run_single_case(agent, case)
        results.append(result)

        if result["status"] == "ok":
            tools_str = ", ".join(result["tool_calls"]) or "（无工具调用）"
            print(f"  ✓ {result['elapsed_s']}s | 工具: {tools_str}")
            print(f"  回复: {result['agent_reply'][:100]}...")
        else:
            print(f"  ✗ 错误: {result['error']}")
        print()

    return results


def save_results(results: list[dict], output_path: str):
    output = {
        "run_at": datetime.now().isoformat(),
        "total": len(results),
        "ok": sum(1 for r in results if r["status"] == "ok"),
        "error": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Agent 评测执行器")
    parser.add_argument("--cases", help="逗号分隔的用例ID，如 TC001,TC002（默认全部）")
    parser.add_argument("--output", default="eval_results.json", help="结果输出文件路径")
    args = parser.parse_args()

    filter_ids = [x.strip() for x in args.cases.split(",")] if args.cases else None

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("错误: 未设置 ANTHROPIC_API_KEY 环境变量")
        sys.exit(1)

    results = asyncio.run(run_all(filter_ids))
    save_results(results, args.output)

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n完成: {ok}/{len(results)} 成功")


if __name__ == "__main__":
    main()
