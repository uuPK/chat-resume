"""用于统计结构化面试主链路完成率和阶段性成功率。"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_PASSWORD = "password123"
DEFAULT_TIMEOUT_S = 20.0
DEFAULT_RUNS = 2
DEFAULT_POLL_INTERVAL_S = 0.5
DEFAULT_EVALUATION_POLLS = 20
BENCHMARK_RESUME_TITLE = "面试链路基准简历"

REPORT_REQUIRED_KEYS = (
    "dimensions",
    "recurring_issues",
    "next_training_plan",
    "resume_feedback",
)

DEFAULT_SCENARIOS = [
    {
        "name": "practice_stream",
        "mode": "practice",
        "request_hint": False,
        "answer": (
            "我最近负责一个求职工作台项目，主导了结构化简历编辑和"
            "面试链路设计，并把关键页面的交互延迟降到了可接受范围。"
        ),
    },
    {
        "name": "practice_stream_with_hint",
        "mode": "practice",
        "request_hint": True,
        "answer": (
            "我会先说明项目背景，再讲我负责的 Agent 编排、评测体系和"
            "端到端验证，最后补充性能指标和上线后的稳定性观察。"
        ),
    },
    {
        "name": "simulation_stream",
        "mode": "simulation",
        "request_hint": False,
        "answer": (
            "这个项目里我重点负责面试会话管理、流式回答和报告生成，"
            "核心目标是让用户能稳定完成一次从提问到复盘的完整练习。"
        ),
    },
]


def parse_args() -> argparse.Namespace:
    """用于解析脚本参数。"""
    parser = argparse.ArgumentParser(description="统计结构化面试主链路完成率")
    parser.add_argument("--api-url", default=DEFAULT_API_URL, help="后端 API 地址")
    parser.add_argument("--email", help="测速账号邮箱，不传则自动生成")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="测速账号密码")
    parser.add_argument(
        "--runs",
        type=int,
        default=DEFAULT_RUNS,
        help="每个默认场景重复执行次数",
    )
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=DEFAULT_TIMEOUT_S,
        help="单次 HTTP 请求超时秒数",
    )
    parser.add_argument(
        "--poll-interval-s",
        type=float,
        default=DEFAULT_POLL_INTERVAL_S,
        help="轮询评估结果时的等待秒数",
    )
    parser.add_argument(
        "--evaluation-polls",
        type=int,
        default=DEFAULT_EVALUATION_POLLS,
        help="练习模式下评估轮询次数",
    )
    parser.add_argument("--output", help="结果输出 JSON 文件路径")
    return parser.parse_args()


def api_url(base_url: str, path: str) -> str:
    """用于拼接 API 地址。"""
    return f"{base_url.rstrip('/')}{path}"


def build_seed_resume_content(email: str) -> dict[str, Any]:
    """用于准备可复用的基准简历结构。"""
    return {
        "job_application": {
            "target_company": "求职实验室",
            "target_title": "AI 应用工程师",
            "jd_text": "负责 AI 应用开发、Agent 编排、前后端联调与性能优化。",
            "strategy": "突出 Agent 编排、评测体系和工程化交付能力。",
        },
        "personal_info": {
            "name": "面试链路基准用户",
            "email": email,
            "phone": "13800000000",
            "position": "AI 应用工程师",
            "github": "https://github.com/example/interview-metrics",
        },
        "summary": {
            "text": "负责 AI 工作台、评测体系和端到端交付的全栈工程师。",
        },
        "education": [
            {
                "school": "指标大学",
                "major": "计算机科学与技术",
                "degree": "本科",
                "duration": "2017 - 2021",
            }
        ],
        "work_experience": [
            {
                "company": "实验求职科技",
                "position": "全栈工程师",
                "duration": "2022 - 至今",
                "highlights": [
                    {"text": "负责求职工作台、结构化简历编辑和面试系统。"},
                    {"text": "推动 SSE 流式链路稳定性优化，减少关键流程超时。"},
                ],
            }
        ],
        "projects": [
            {
                "name": "Chat Resume",
                "overview": "围绕简历优化和模拟面试的 AI 求职工作台。",
                "role": "负责人",
                "duration": "2024 - 至今",
                "highlights": [
                    {"text": "搭建 Resume Agent 工具调用和 diff 确认机制。"},
                    {"text": "为结构化面试链路增加报告生成与评测体系。"},
                ],
            }
        ],
        "skills": [
            {"category": "前端", "items": ["React", "Next.js", "TypeScript"]},
            {"category": "后端", "items": ["FastAPI", "SQLAlchemy", "PostgreSQL"]},
            {"category": "AI", "items": ["OpenRouter", "SSE", "Prompt Engineering"]},
        ],
    }


def scenario_payloads(runs: int) -> list[dict[str, Any]]:
    """用于把默认场景扩展成实际执行列表。"""
    payloads: list[dict[str, Any]] = []
    for repeat_index in range(max(1, runs)):
        for scenario in DEFAULT_SCENARIOS:
            payloads.append(
                {
                    **scenario,
                    "run_index": repeat_index + 1,
                    "display_name": f"{scenario['name']}#{repeat_index + 1}",
                }
            )
    return payloads


def ensure_user(client: httpx.Client, base_url: str, email: str, password: str) -> None:
    """用于确保基准账号存在并已登录。"""
    register_response = client.post(
        api_url(base_url, "/api/auth/register"),
        json={
            "email": email,
            "password": password,
            "full_name": "面试链路指标用户",
        },
    )
    if register_response.status_code not in {200, 400}:
        raise RuntimeError(
            f"注册失败: {register_response.status_code} {register_response.text}"
        )

    login_response = client.post(
        api_url(base_url, "/api/auth/login"),
        data={"username": email, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    login_response.raise_for_status()


def ensure_resume(client: httpx.Client, base_url: str, email: str) -> dict[str, Any]:
    """用于复用或创建基准简历。"""
    list_response = client.get(api_url(base_url, "/api/resumes/"))
    list_response.raise_for_status()
    resumes = list_response.json()
    if isinstance(resumes, list):
        for resume in resumes:
            if resume.get("title") == BENCHMARK_RESUME_TITLE:
                return resume

    create_response = client.post(
        api_url(base_url, "/api/resumes/"),
        json={
            "title": BENCHMARK_RESUME_TITLE,
            "content": build_seed_resume_content(email),
        },
    )
    create_response.raise_for_status()
    return create_response.json()


def validate_report_data(report_data: Any) -> bool:
    """用于判断报告字段是否达到可展示标准。"""
    if not isinstance(report_data, dict):
        return False
    return all(report_data.get(key) for key in REPORT_REQUIRED_KEYS)


def parse_sse_lines(response: httpx.Response) -> list[dict[str, Any]]:
    """用于解析面试流式回答的 SSE 事件。"""
    events: list[dict[str, Any]] = []
    for line in response.iter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = line[6:]
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


def build_step(
    *,
    success: bool,
    status_code: int | None = None,
    detail: str = "",
    data: Any = None,
    skipped: bool = False,
) -> dict[str, Any]:
    """用于统一构造阶段执行结果。"""
    return {
        "success": success,
        "statusCode": status_code,
        "detail": detail,
        "data": data,
        "skipped": skipped,
    }


def poll_for_evaluation(
    client: httpx.Client,
    base_url: str,
    session_id: int,
    *,
    poll_interval_s: float,
    evaluation_polls: int,
) -> dict[str, Any]:
    """用于在练习模式下等待评估结果落库。"""
    latest_session: dict[str, Any] | None = None
    for _ in range(max(1, evaluation_polls)):
        response = client.get(api_url(base_url, f"/api/interviews/{session_id}"))
        response.raise_for_status()
        latest_session = response.json().get("session")
        turns = (
            list(latest_session.get("turns", []))
            if isinstance(latest_session, dict)
            else []
        )
        answered_turns = [turn for turn in turns if turn.get("answer")]
        if answered_turns and answered_turns[-1].get("evaluation"):
            return build_step(
                success=True,
                status_code=response.status_code,
                detail="已检测到当前题评估结果。",
                data={"session": latest_session},
            )
        time.sleep(max(0.0, poll_interval_s))
    return build_step(
        success=False,
        status_code=200,
        detail="轮询结束后仍未拿到当前题评估结果。",
        data={"session": latest_session},
    )


def finalize_scenario(
    result: dict[str, Any], latest_session: dict[str, Any] | None
) -> dict[str, Any]:
    """用于根据阶段执行结果计算单场链路是否闭环。"""
    steps = result["steps"]
    chain_complete = all(
        steps.get(step_name, {}).get("success", False)
        for step_name in ("create", "start", "answer", "report")
    ) and steps.get("evaluation", {}).get("success", False)
    result["chainCompleted"] = chain_complete
    result["finalStatus"] = (
        latest_session.get("status") if isinstance(latest_session, dict) else None
    )
    result["reportReady"] = validate_report_data(
        latest_session.get("report_data") if isinstance(latest_session, dict) else None
    )
    return result


def run_single_scenario(
    client: httpx.Client,
    base_url: str,
    resume_id: int,
    scenario: dict[str, Any],
    *,
    poll_interval_s: float,
    evaluation_polls: int,
) -> dict[str, Any]:
    """用于执行一次完整面试链路并记录每个阶段。"""
    result: dict[str, Any] = {
        "name": scenario["name"],
        "displayName": scenario["display_name"],
        "runIndex": scenario["run_index"],
        "mode": scenario["mode"],
        "requestHint": scenario["request_hint"],
        "steps": {},
    }

    session_id: int | None = None
    latest_session: dict[str, Any] | None = None

    try:
        create_response = client.post(
            api_url(base_url, "/api/interviews/"),
            json={
                "resume_id": resume_id,
                "target_title": "AI 应用工程师",
                "target_company": "求职实验室",
                "jd_text": "负责 AI 应用开发、Agent 编排、前后端联调与性能优化。",
                "interview_type": "general",
                "difficulty": "medium",
                "language": "zh-CN",
                "mode": scenario["mode"],
            },
        )
        create_ok = create_response.status_code == 200
        create_data = create_response.json() if create_ok else None
        session_id = (
            create_data.get("session", {}).get("id")
            if isinstance(create_data, dict)
            else None
        )
        latest_session = (
            create_data.get("session") if isinstance(create_data, dict) else None
        )
        result["steps"]["create"] = build_step(
            success=create_ok and session_id is not None,
            status_code=create_response.status_code,
            detail="已创建面试 session。" if create_ok else create_response.text,
            data={"sessionId": session_id, "session": latest_session},
        )
        if not result["steps"]["create"]["success"]:
            return finalize_scenario(result, latest_session)

        start_response = client.post(
            api_url(base_url, f"/api/interviews/{session_id}/start")
        )
        start_ok = start_response.status_code == 200
        start_data = start_response.json() if start_ok else None
        latest_session = (
            start_data.get("session")
            if isinstance(start_data, dict)
            else latest_session
        )
        result["steps"]["start"] = build_step(
            success=start_ok,
            status_code=start_response.status_code,
            detail="已成功生成第一题。" if start_ok else start_response.text,
            data={"session": latest_session},
        )
        if not result["steps"]["start"]["success"]:
            return finalize_scenario(result, latest_session)

        if scenario["request_hint"]:
            hint_response = client.post(
                api_url(base_url, f"/api/interviews/{session_id}/hint")
            )
            hint_ok = hint_response.status_code == 200
            hint_data = hint_response.json() if hint_ok else None
            hint_items = (
                hint_data.get("hints", []) if isinstance(hint_data, dict) else []
            )
            result["steps"]["hint"] = build_step(
                success=hint_ok and bool(hint_items),
                status_code=hint_response.status_code,
                detail="已成功获取答题提示。" if hint_ok else hint_response.text,
                data={"hints": hint_items},
            )
        else:
            result["steps"]["hint"] = build_step(
                success=True,
                detail="当前场景未请求提示。",
                skipped=True,
            )

        with client.stream(
            "POST",
            api_url(base_url, f"/api/interviews/{session_id}/answer/stream"),
            json={"answer": scenario["answer"]},
        ) as answer_response:
            answer_ok = answer_response.status_code == 200
            events = parse_sse_lines(answer_response) if answer_ok else []
        done_event = next(
            (event for event in events if event.get("type") == "done"),
            None,
        )
        evaluation_event = next(
            (event for event in events if event.get("type") == "evaluation"),
            None,
        )
        latest_session = (
            done_event.get("session")
            if isinstance(done_event, dict)
            else latest_session
        )
        result["steps"]["answer"] = build_step(
            success=answer_ok and done_event is not None,
            status_code=200 if answer_ok else None,
            detail="流式回答完成并收到 done 事件。"
            if answer_ok and done_event is not None
            else "回答链路未拿到 done 事件。",
            data={"events": events, "session": latest_session},
        )
        if not result["steps"]["answer"]["success"]:
            return finalize_scenario(result, latest_session)

        if scenario["mode"] == "practice":
            if evaluation_event is not None:
                result["steps"]["evaluation"] = build_step(
                    success=True,
                    status_code=200,
                    detail="流式事件中已返回当前题评估。",
                    data={"evaluation": evaluation_event.get("evaluation", "")},
                )
            else:
                result["steps"]["evaluation"] = poll_for_evaluation(
                    client,
                    base_url,
                    session_id,
                    poll_interval_s=poll_interval_s,
                    evaluation_polls=evaluation_polls,
                )
                session_data = result["steps"]["evaluation"]["data"] or {}
                latest_session = session_data.get("session") or latest_session
        else:
            result["steps"]["evaluation"] = build_step(
                success=True,
                detail="simulation 模式不要求当前题评估。",
                skipped=True,
            )

        if (
            isinstance(latest_session, dict)
            and latest_session.get("status") == "completed"
            and validate_report_data(latest_session.get("report_data"))
        ):
            result["steps"]["end"] = build_step(
                success=True,
                detail="回答后 session 已自动完成，无需额外结束。",
                data={"session": latest_session},
                skipped=True,
            )
        else:
            end_response = client.post(
                api_url(base_url, f"/api/interviews/{session_id}/end")
            )
            end_ok = end_response.status_code == 200
            end_data = end_response.json() if end_ok else None
            latest_session = (
                end_data.get("session")
                if isinstance(end_data, dict)
                else latest_session
            )
            result["steps"]["end"] = build_step(
                success=end_ok,
                status_code=end_response.status_code,
                detail="已成功结束面试并生成报告。" if end_ok else end_response.text,
                data={"session": latest_session},
            )
            if not result["steps"]["end"]["success"]:
                return finalize_scenario(result, latest_session)

        report_response = client.get(
            api_url(base_url, f"/api/interviews/{session_id}/report")
        )
        report_ok = report_response.status_code == 200
        report_data = report_response.json() if report_ok else None
        latest_session = (
            report_data.get("session")
            if isinstance(report_data, dict)
            else latest_session
        )
        report_ready = validate_report_data(
            latest_session.get("report_data")
            if isinstance(latest_session, dict)
            else None
        )
        result["steps"]["report"] = build_step(
            success=report_ok and report_ready,
            status_code=report_response.status_code,
            detail="最终报告字段完整。"
            if report_ok and report_ready
            else "最终报告缺少关键字段或请求失败。",
            data={"session": latest_session},
        )
        return finalize_scenario(result, latest_session)
    except httpx.HTTPError as exc:
        result["steps"]["runtime_error"] = build_step(
            success=False,
            detail=str(exc),
        )
        return finalize_scenario(result, latest_session)


def summarize_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    """用于把逐场结果汇总成证据包可直接消费的统计结构。"""
    total_sessions = len(results)
    practice_sessions = [result for result in results if result["mode"] == "practice"]
    simulation_sessions = [
        result for result in results if result["mode"] == "simulation"
    ]

    def count_success(step_name: str) -> int:
        return sum(
            1 for result in results if result["steps"].get(step_name, {}).get("success")
        )

    hint_requested = sum(1 for result in results if result["requestHint"])
    hint_success = sum(
        1
        for result in results
        if result["requestHint"] and result["steps"].get("hint", {}).get("success")
    )
    end_attempted = sum(
        1
        for result in results
        if not result["steps"].get("end", {}).get("skipped", False)
    )
    end_success = sum(
        1
        for result in results
        if result["steps"].get("end", {}).get("success")
        and not result["steps"].get("end", {}).get("skipped", False)
    )
    evaluation_expected = len(practice_sessions)
    evaluation_ready = sum(
        1
        for result in practice_sessions
        if result["steps"].get("evaluation", {}).get("success")
    )
    report_success = sum(1 for result in results if result.get("reportReady"))
    chain_completion = sum(1 for result in results if result.get("chainCompleted"))

    def rate(numerator: int, denominator: int) -> float:
        if denominator <= 0:
            return 0.0
        return round((numerator / denominator) * 100, 1)

    create_success = count_success("create")
    start_success = count_success("start")
    answer_success = count_success("answer")

    return {
        "totalSessions": total_sessions,
        "practiceSessions": len(practice_sessions),
        "simulationSessions": len(simulation_sessions),
        "createSuccessCount": create_success,
        "createSuccessRate": rate(create_success, total_sessions),
        "startSuccessCount": start_success,
        "startSuccessRate": rate(start_success, total_sessions),
        "hintRequestedCount": hint_requested,
        "hintSuccessCount": hint_success,
        "hintSuccessRate": rate(hint_success, hint_requested),
        "answerSuccessCount": answer_success,
        "answerSuccessRate": rate(answer_success, total_sessions),
        "evaluationExpectedCount": evaluation_expected,
        "evaluationReadyCount": evaluation_ready,
        "evaluationReadyRate": rate(evaluation_ready, evaluation_expected),
        "endAttemptedCount": end_attempted,
        "endSuccessCount": end_success,
        "endSuccessRate": rate(end_success, end_attempted),
        "reportSuccessCount": report_success,
        "reportSuccessRate": rate(report_success, total_sessions),
        "chainCompletionCount": chain_completion,
        "chainCompletionRate": rate(chain_completion, total_sessions),
    }


def print_summary(summary: dict[str, Any]) -> None:
    """用于在终端打印关键统计结果。"""
    print("\n=== 面试链路指标 ===")
    print(
        f"- 创建成功率: {summary['createSuccessCount']}/{summary['totalSessions']} "
        f"({summary['createSuccessRate']:.1f}%)"
    )
    print(
        f"- 开始成功率: {summary['startSuccessCount']}/{summary['totalSessions']} "
        f"({summary['startSuccessRate']:.1f}%)"
    )
    print(
        f"- 回答成功率: {summary['answerSuccessCount']}/{summary['totalSessions']} "
        f"({summary['answerSuccessRate']:.1f}%)"
    )
    print(
        f"- 练习模式评估就绪率: "
        f"{summary['evaluationReadyCount']}/{summary['evaluationExpectedCount']} "
        f"({summary['evaluationReadyRate']:.1f}%)"
    )
    print(
        f"- 报告生成成功率: {summary['reportSuccessCount']}/{summary['totalSessions']} "
        f"({summary['reportSuccessRate']:.1f}%)"
    )
    print(
        f"- 面试链路完成率: "
        f"{summary['chainCompletionCount']}/{summary['totalSessions']} "
        f"({summary['chainCompletionRate']:.1f}%)"
    )


def main() -> None:
    """用于串起面试链路指标测量流程。"""
    args = parse_args()
    email = args.email or f"interview_metrics_{int(time.time())}@example.com"
    base_url = args.api_url.rstrip("/")
    scenarios = scenario_payloads(args.runs)

    with httpx.Client(
        base_url=base_url,
        timeout=args.timeout_s,
        follow_redirects=True,
    ) as client:
        ensure_user(client, base_url, email, args.password)
        resume = ensure_resume(client, base_url, email)
        resume_id = int(resume["id"])

        results = [
            run_single_scenario(
                client,
                base_url,
                resume_id,
                scenario,
                poll_interval_s=args.poll_interval_s,
                evaluation_polls=args.evaluation_polls,
            )
            for scenario in scenarios
        ]

    summary = summarize_results(results)
    print_summary(summary)

    output = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "config": {
            "apiUrl": base_url,
            "runs": args.runs,
            "timeoutSeconds": args.timeout_s,
            "pollIntervalSeconds": args.poll_interval_s,
            "evaluationPolls": args.evaluation_polls,
        },
        "benchmarkData": {
            "userEmail": email,
            "resumeId": resume_id,
            "resumeTitle": BENCHMARK_RESUME_TITLE,
            "scenarioCount": len(scenarios),
        },
        "summary": summary,
        "scenarioResults": results,
    }

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(output, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n完整 JSON 报告已写入: {output_path}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
