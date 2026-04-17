"""
Agent 评测执行器

用法：
    cd backend
    uv run python ../eval/run_eval.py [--cases TC001,TC002] [--output results.json]

依赖：
    - 需要设置 OPENROUTER_API_KEY 环境变量
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

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.runtime.loop import AgentRuntime  # noqa: E402
from app.schemas.resume import dump_resume_content_for_frontend  # noqa: E402
from app.services.llm.chat_service import ChatService  # noqa: E402


def _normalize_legacy_highlights(items: list[dict] | None) -> list[dict]:
    """兼容旧样本里的 string highlights，转成当前 schema 可接受的对象结构。"""
    normalized = []
    for item in items or []:
        if not isinstance(item, dict):
            normalized.append(item)
            continue
        next_item = dict(item)
        highlights = next_item.get("highlights")
        if isinstance(highlights, list) and highlights and all(
            isinstance(highlight, str) for highlight in highlights
        ):
            next_item["highlights"] = [
                {"text": str(highlight).strip()}
                for highlight in highlights
                if str(highlight).strip()
            ]
        normalized.append(next_item)
    return normalized


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
        resume = json.load(f)
    if isinstance(resume, dict):
        for section in ("education", "work_experience", "projects"):
            if isinstance(resume.get(section), list):
                resume[section] = _normalize_legacy_highlights(resume.get(section))
    return dump_resume_content_for_frontend(resume)


def load_jd(filename: str) -> dict | None:
    if not filename:
        return None
    path = EVAL_DIR / "cases" / filename
    with open(path) as f:
        return json.load(f)


def inject_job_application(resume: dict, jd: dict | None) -> dict:
    """将 JD 结构化注入到 resume_content.job_application，便于 prompt 直接使用。"""
    if not jd or not isinstance(resume, dict):
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
    resume = inject_job_application(resume, jd)
    message = build_message_with_jd(case["user_message"], jd)
    runtime_events: list[dict] = []

    start = time.time()
    try:
        runtime_result = await agent.runtime.run(
            agent=agent.definition,
            user_message=message,
            context={
                "resume_content": resume,
                "allowed_sections": None,
            },
            event_callback=lambda event: runtime_events.append(dict(event)),
        )
        elapsed = round(time.time() - start, 2)
        fallback_triggered = any(
            event.get("event_type") == "llm_response"
            and event.get("finish_reason") == "stream_fallback"
            for event in runtime_events
        )
        return {
            "id": case["id"],
            "desc": case["desc"],
            "status": "ok",
            "elapsed_s": elapsed,
            "agent_reply": runtime_result["content"],
            "tool_calls": [
                tc.get("name", tc.get("tool", "")) if isinstance(tc, dict) else str(tc)
                for tc in (runtime_result.get("tool_calls") or [])
            ],
            "fallback_triggered": fallback_triggered,
            "resume_before": inject_job_application(load_resume(case["resume_file"]), jd),
            "resume_after": runtime_result.get("context", {}).get("resume_content", {}),
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
            "fallback_triggered": False,
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
            fallback_note = " | fallback" if result.get("fallback_triggered") else ""
            print(f"  ✓ {result['elapsed_s']}s | 工具: {tools_str}{fallback_note}")
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

    if not os.environ.get("OPENROUTER_API_KEY"):
        print("错误: 未设置 OPENROUTER_API_KEY 环境变量")
        sys.exit(1)

    results = asyncio.run(run_all(filter_ids))
    save_results(results, args.output)

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n完成: {ok}/{len(results)} 成功")


if __name__ == "__main__":
    main()
