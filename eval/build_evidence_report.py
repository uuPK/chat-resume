"""用于把评测结果整理成面向求职展示的指标摘要。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    """用于读取并解析单个 JSON 文件。"""
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def mean(values: list[float]) -> float:
    """用于计算一组数值的平均值。"""
    return sum(values) / len(values) if values else 0.0


def percentile(values: list[float], p: int) -> float:
    """用于计算简单百分位数，保持和性能脚本同样的口径。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(
        len(ordered) - 1,
        max(0, ((p * len(ordered) + 99) // 100) - 1),
    )
    return ordered[index]


def percent(numerator: int, denominator: int) -> float:
    """用于把计数转换为百分比。"""
    if denominator <= 0:
        return 0.0
    return (numerator / denominator) * 100


def format_percent(value: float, digits: int = 1) -> str:
    """用于格式化百分比展示值。"""
    return f"{value:.{digits}f}%"


def format_signed_percent_points(delta_ratio: float) -> str:
    """用于把覆盖率增量格式化成百分点。"""
    return f"{delta_ratio * 100:+.1f} 个百分点"


def format_seconds(value: float) -> str:
    """用于统一格式化秒级耗时。"""
    return f"{value:.2f} s"


def format_milliseconds(value: float) -> str:
    """用于统一格式化毫秒级耗时。"""
    return f"{value:.1f} ms"


def summarize_eval(eval_scores: dict[str, Any]) -> dict[str, Any]:
    """用于汇总 Resume Agent 离线评测结果。"""
    scored = eval_scores.get("scored", [])
    total_cases = len(scored)
    ok_results = [result for result in scored if result.get("status") == "ok"]
    ok_count = len(ok_results)

    elapsed_values = [
        float(result.get("elapsed_s", 0.0))
        for result in ok_results
        if result.get("elapsed_s") is not None
    ]
    fallback_count = sum(1 for result in ok_results if result.get("fallback_triggered"))

    keyword_scores = [
        result["scores"]["keyword_improvement"]
        for result in ok_results
        if not result["scores"]["keyword_improvement"].get("skipped")
    ]
    keyword_deltas = [float(item.get("delta", 0.0)) for item in keyword_scores]
    keyword_improved_count = sum(1 for delta in keyword_deltas if delta > 0)

    tool_scores = [
        float(result["scores"]["tool_correctness"].get("score", 0.0))
        for result in ok_results
    ]
    tool_exact_match_count = sum(1 for score in tool_scores if score >= 1.0)

    judge_scores = [
        result["scores"]["llm_judge"]["scores"]
        for result in ok_results
        if not result["scores"]["llm_judge"].get("skipped")
        and "scores" in result["scores"]["llm_judge"]
    ]
    judge_overall = [float(item.get("overall", 0.0)) for item in judge_scores]
    instruction_scores = [
        float(item.get("instruction_follow", {}).get("score", 0.0))
        for item in judge_scores
    ]
    quality_scores = [
        float(item.get("quality", {}).get("score", 0.0)) for item in judge_scores
    ]
    hallucination_scores = [
        float(item.get("no_hallucination", {}).get("score", 0.0))
        for item in judge_scores
    ]

    decision_scores = [
        result["scores"]["decision_rule"]
        for result in ok_results
        if not result["scores"]["decision_rule"].get("skipped")
    ]
    decision_values = [float(item.get("score", 0.0)) for item in decision_scores]
    decision_passed_count = sum(1 for score in decision_values if score >= 1.0)

    unique_resume_files = sorted(
        {
            str(result.get("case", {}).get("resume_file", "")).strip()
            for result in scored
            if result.get("case", {}).get("resume_file")
        }
    )
    unique_jd_files = sorted(
        {
            str(result.get("case", {}).get("jd_file", "")).strip()
            for result in scored
            if result.get("case", {}).get("jd_file")
        }
    )

    return {
        "totalCases": total_cases,
        "okCases": ok_count,
        "successRate": percent(ok_count, total_cases),
        "averageLatencySeconds": mean(elapsed_values),
        "p95LatencySeconds": percentile(elapsed_values, 95),
        "fallbackCount": fallback_count,
        "fallbackRate": percent(fallback_count, ok_count),
        "coverage": {
            "resumeFixtures": len(unique_resume_files),
            "jdFixtures": len(unique_jd_files),
        },
        "keywordImprovement": {
            "caseCount": len(keyword_scores),
            "averageDeltaRatio": mean(keyword_deltas),
            "improvedCount": keyword_improved_count,
            "improvedRate": percent(keyword_improved_count, len(keyword_scores)),
        },
        "toolCorrectness": {
            "caseCount": len(tool_scores),
            "averageF1": mean(tool_scores),
            "exactMatchCount": tool_exact_match_count,
            "exactMatchRate": percent(tool_exact_match_count, len(tool_scores)),
        },
        "llmJudge": {
            "caseCount": len(judge_scores),
            "averageOverall": mean(judge_overall),
            "averageInstructionFollow": mean(instruction_scores),
            "averageQuality": mean(quality_scores),
            "averageNoHallucination": mean(hallucination_scores),
        },
        "decisionRule": {
            "caseCount": len(decision_scores),
            "averageScore": mean(decision_values),
            "passedCount": decision_passed_count,
            "passedRate": percent(decision_passed_count, len(decision_scores)),
        },
    }


def summarize_eval_analysis(eval_analysis: dict[str, Any]) -> dict[str, Any]:
    """用于汇总新版确定性 eval analysis 输出。"""
    summary = eval_analysis.get("summary", {})
    cases = eval_analysis.get("cases", [])
    total_cases = int(summary.get("totalCases", len(cases)))
    ok_cases = int(summary.get("okCases", 0))
    elapsed_values = [
        float(case.get("elapsedSeconds", 0.0))
        for case in cases
        if case.get("elapsedSeconds") is not None
    ]
    tool_scores = [
        float(case["expectations"]["toolCalls"].get("f1", 0.0))
        for case in cases
        if case.get("expectations", {}).get("toolCalls")
    ]
    tool_exact_match_count = sum(1 for score in tool_scores if score >= 1.0)
    decision_scores = [
        case["expectations"]["decisionRule"]
        for case in cases
        if case.get("expectations", {}).get("decisionRule")
    ]
    decision_passed_count = sum(
        1 for score in decision_scores if score.get("passed")
    )
    fallback_count = sum(
        1
        for case in cases
        if case.get("expectations", {})
        .get("runtimeStability", {})
        .get("fallbackTriggered")
    )
    taxonomy = summary.get("failureTaxonomy", {})
    failure_taxonomy = [
        {
            "category": category,
            "count": int(item.get("count", 0)),
            "caseIds": [str(case_id) for case_id in item.get("caseIds", [])],
        }
        for category, item in taxonomy.items()
    ]
    gate_summary = eval_analysis.get("gateSummary", {})
    gates = gate_summary.get("gates", [])
    failed_gates = [
        str(gate.get("name"))
        for gate in gates
        if gate.get("passed") is False
    ]

    return {
        "totalCases": total_cases,
        "okCases": ok_cases,
        "successRate": percent(ok_cases, total_cases),
        "averageLatencySeconds": mean(elapsed_values),
        "p95LatencySeconds": percentile(elapsed_values, 95),
        "fallbackCount": fallback_count,
        "fallbackRate": percent(fallback_count, total_cases),
        "coverage": {
            "resumeFixtures": 0,
            "jdFixtures": 0,
        },
        "keywordImprovement": {
            "caseCount": 0,
            "averageDeltaRatio": 0.0,
            "improvedCount": 0,
            "improvedRate": 0.0,
        },
        "toolCorrectness": {
            "caseCount": len(tool_scores),
            "averageF1": mean(tool_scores),
            "exactMatchCount": tool_exact_match_count,
            "exactMatchRate": percent(tool_exact_match_count, len(tool_scores)),
        },
        "llmJudge": {
            "caseCount": 0,
            "averageOverall": 0.0,
            "averageInstructionFollow": 0.0,
            "averageQuality": 0.0,
            "averageNoHallucination": 0.0,
        },
        "decisionRule": {
            "caseCount": len(decision_scores),
            "averageScore": percent(decision_passed_count, len(decision_scores)) / 100,
            "passedCount": decision_passed_count,
            "passedRate": percent(decision_passed_count, len(decision_scores)),
        },
        "gate": {
            "passed": bool(gate_summary.get("passed", False)),
            "failedGates": failed_gates,
        },
        "failureTaxonomy": failure_taxonomy,
    }


def summarize_perf(perf_report: dict[str, Any]) -> dict[str, Any]:
    """用于汇总生产模式性能测速结果。"""
    api_results = perf_report.get("apiResults", [])
    browser_results = perf_report.get("browserResults", [])

    all_api_samples = [
        float(sample)
        for result in api_results
        for sample in result.get("samplesMs", [])
    ]
    all_browser_samples = [
        float(sample.get("wallMs", 0.0))
        for result in browser_results
        for sample in result.get("samples", [])
    ]

    api_probes = [
        {
            "name": result.get("name", "Unnamed API"),
            "avgMs": float(result.get("summary", {}).get("avgMs", 0.0)),
            "p95Ms": float(result.get("summary", {}).get("p95Ms", 0.0)),
            "maxMs": float(result.get("summary", {}).get("maxMs", 0.0)),
        }
        for result in api_results
    ]
    browser_routes = [
        {
            "name": result.get("name", "Unnamed Route"),
            "path": result.get("path", ""),
            "avgMs": float(result.get("summary", {}).get("avgMs", 0.0)),
            "p95Ms": float(result.get("summary", {}).get("p95Ms", 0.0)),
            "maxMs": float(result.get("summary", {}).get("maxMs", 0.0)),
        }
        for result in browser_results
    ]

    slowest_route = max(browser_routes, key=lambda item: item["avgMs"], default=None)
    editor_route = next(
        (route for route in browser_routes if route["name"] == "简历编辑页"),
        None,
    )

    return {
        "runs": int(perf_report.get("config", {}).get("runs", 0)),
        "apiProbeCount": len(api_probes),
        "browserRouteCount": len(browser_routes),
        "averageApiMs": mean(all_api_samples),
        "p95ApiMs": percentile(all_api_samples, 95),
        "averageBrowserMs": mean(all_browser_samples),
        "p95BrowserMs": percentile(all_browser_samples, 95),
        "apiProbes": api_probes,
        "browserRoutes": browser_routes,
        "slowestRoute": slowest_route,
        "editorRoute": editor_route,
    }


def summarize_manual_metrics(manual_metrics: dict[str, Any]) -> list[dict[str, str]]:
    """用于读取手工补充指标，先承接面试链路等未自动化指标。"""
    metrics = manual_metrics.get("metrics", [])
    normalized: list[dict[str, str]] = []
    for metric in metrics:
        normalized.append(
            {
                "label": str(metric.get("label", "")).strip(),
                "value": str(metric.get("value", "")).strip(),
                "description": str(metric.get("description", "")).strip(),
            }
        )
    return [metric for metric in normalized if metric["label"] and metric["value"]]


def summarize_interview_metrics(interview_report: dict[str, Any]) -> dict[str, Any]:
    """用于读取结构化面试链路指标脚本的输出。"""
    summary = interview_report.get("summary", {})
    return {
        "totalSessions": int(summary.get("totalSessions", 0)),
        "practiceSessions": int(summary.get("practiceSessions", 0)),
        "simulationSessions": int(summary.get("simulationSessions", 0)),
        "createSuccessRate": float(summary.get("createSuccessRate", 0.0)),
        "startSuccessRate": float(summary.get("startSuccessRate", 0.0)),
        "answerSuccessRate": float(summary.get("answerSuccessRate", 0.0)),
        "evaluationReadyRate": float(summary.get("evaluationReadyRate", 0.0)),
        "reportSuccessRate": float(summary.get("reportSuccessRate", 0.0)),
        "chainCompletionCount": int(summary.get("chainCompletionCount", 0)),
        "chainCompletionRate": float(summary.get("chainCompletionRate", 0.0)),
    }


def build_resume_bullets(summary: dict[str, Any]) -> list[str]:
    """用于生成可以直接复用到简历或面试里的项目表述。"""
    bullets: list[str] = []
    eval_summary = summary.get("eval")
    perf_summary = summary.get("perf")
    interview_summary = summary.get("interview")

    if eval_summary:
        keyword_delta = format_signed_percent_points(
            eval_summary["keywordImprovement"]["averageDeltaRatio"]
        )
        decision_rate = format_percent(eval_summary["decisionRule"]["passedRate"])
        bullets.append(
            "为 Resume Agent 构建离线评测集，覆盖 "
            f"{eval_summary['totalCases']} 条用例，成功率 "
            f"{format_percent(eval_summary['successRate'])}，"
            f"平均将 JD 关键词覆盖率提升 {keyword_delta}。"
        )
        bullets.append(
            "为结构化工具调用建立质量约束，平均工具调用正确性 "
            f"F1 {eval_summary['toolCorrectness']['averageF1']:.3f}，"
            f"optimize-first 决策规则通过率 {decision_rate}。"
        )

    if perf_summary:
        editor_route = perf_summary.get("editorRoute")
        editor_note = ""
        if editor_route:
            editor_note = (
                "，其中简历编辑页平均打开耗时 "
                f"{format_milliseconds(editor_route['avgMs'])}"
            )
        bullets.append(
            "为求职工作台建立生产模式测速链路，API 探针 P95 "
            f"{format_milliseconds(perf_summary['p95ApiMs'])}，"
            f"页面导航平均耗时 {format_milliseconds(perf_summary['averageBrowserMs'])}"
            f"{editor_note}。"
        )

    if interview_summary:
        bullets.append(
            "为结构化面试模块建立端到端链路回放，覆盖 "
            f"{interview_summary['totalSessions']} 次 session，"
            f"面试链路完成率 "
            f"{format_percent(interview_summary['chainCompletionRate'])}，"
            f"报告生成成功率 "
            f"{format_percent(interview_summary['reportSuccessRate'])}。"
        )

    return bullets


def build_markdown(summary: dict[str, Any]) -> str:
    """用于把结构化摘要渲染成面向求职展示的 Markdown。"""
    lines: list[str] = []
    eval_summary = summary.get("eval")
    perf_summary = summary.get("perf")
    interview_summary = summary.get("interview")
    manual_metrics = summary.get("manualMetrics", [])

    lines.append("# Agent Metrics Summary")
    lines.append("")
    lines.append(
        f"生成时间：{summary['generatedAt']}  |  "
        f"数据源：{', '.join(summary['sources']) if summary['sources'] else '未提供'}"
    )
    lines.append("")

    lines.append("## 快速结论")
    lines.append("")
    if eval_summary:
        keyword_delta = format_signed_percent_points(
            eval_summary["keywordImprovement"]["averageDeltaRatio"]
        )
        decision_rate = format_percent(eval_summary["decisionRule"]["passedRate"])
        gate = eval_summary.get("gate")
        if gate:
            gate_status = "pass" if gate.get("passed") else "fail"
            lines.append(f"- Gate 状态：{gate_status}。")
        for failure in eval_summary.get("failureTaxonomy", []):
            case_ids = "、".join(failure["caseIds"])
            lines.append(
                "- 失败分类："
                f"{failure['category']} {failure['count']} 个 case"
                f"（{case_ids}）。"
            )
        lines.append(
            "- Resume Agent 离线评测覆盖 "
            f"{eval_summary['totalCases']} 条用例，成功 "
            f"{eval_summary['okCases']}/{eval_summary['totalCases']} "
            f"({format_percent(eval_summary['successRate'])})。"
        )
        lines.append(
            "- 含 JD 用例的关键词覆盖率平均提升 "
            f"{keyword_delta}，"
            f"{eval_summary['keywordImprovement']['improvedCount']}/"
            f"{eval_summary['keywordImprovement']['caseCount']} 条用例出现提升。"
        )
        lines.append(
            "- 工具调用正确性平均 F1 为 "
            f"{eval_summary['toolCorrectness']['averageF1']:.3f}，"
            f"决策规则通过率 {decision_rate}。"
        )
    if perf_summary:
        lines.append(
            "- 生产模式 API 探针平均耗时 "
            f"{format_milliseconds(perf_summary['averageApiMs'])}，"
            f"P95 为 {format_milliseconds(perf_summary['p95ApiMs'])}。"
        )
        lines.append(
            "- 页面导航平均耗时 "
            f"{format_milliseconds(perf_summary['averageBrowserMs'])}，"
            f"P95 为 {format_milliseconds(perf_summary['p95BrowserMs'])}。"
        )
    if interview_summary:
        lines.append(
            "- 结构化面试链路共回放 "
            f"{interview_summary['totalSessions']} 次，"
            f"端到端完成率 "
            f"{format_percent(interview_summary['chainCompletionRate'])}，"
            f"报告生成成功率 "
            f"{format_percent(interview_summary['reportSuccessRate'])}。"
        )
    for metric in manual_metrics:
        lines.append(f"- {metric['label']}：{metric['value']}。{metric['description']}")
    lines.append("")

    lines.append("## 核心指标")
    lines.append("")
    lines.append("| 指标 | 数值 | 说明 |")
    lines.append("| --- | --- | --- |")
    if eval_summary:
        keyword_delta = format_signed_percent_points(
            eval_summary["keywordImprovement"]["averageDeltaRatio"]
        )
        lines.append(
            "| Agent 修改成功率 | "
            f"{eval_summary['okCases']}/{eval_summary['totalCases']} "
            f"({format_percent(eval_summary['successRate'])}) | "
            "离线评测用例中成功执行并返回结果的比例 |"
        )
        lines.append(
            f"| JD 匹配度提升 | {keyword_delta} | 修改前后 JD 关键词覆盖率的平均增量 |"
        )
        lines.append(
            "| 工具调用正确性 | "
            f"{eval_summary['toolCorrectness']['averageF1']:.3f} F1 | "
            "期望工具集与实际调用集的匹配程度 |"
        )
        if eval_summary["llmJudge"]["caseCount"] > 0:
            lines.append(
                "| LLM Judge 综合评分 | "
                f"{eval_summary['llmJudge']['averageOverall']:.2f} / 5 | "
                "基于指令遵循、内容质量、无幻觉的质量评分 |"
            )
        lines.append(
            "| Agent 平均响应时间 | "
            f"{format_seconds(eval_summary['averageLatencySeconds'])} | "
            "离线评测用例的平均完成耗时 |"
        )
    if perf_summary:
        lines.append(
            "| API P95 响应 | "
            f"{format_milliseconds(perf_summary['p95ApiMs'])} | "
            "生产模式 API 探针的 95 分位耗时 |"
        )
        lines.append(
            "| 页面导航平均耗时 | "
            f"{format_milliseconds(perf_summary['averageBrowserMs'])} | "
            "生产模式浏览器真实导航耗时均值 |"
        )
        if perf_summary["editorRoute"]:
            lines.append(
                "| 简历编辑页平均打开耗时 | "
                f"{format_milliseconds(perf_summary['editorRoute']['avgMs'])} | "
                "核心工作台页面的平均导航耗时 |"
            )
    if interview_summary:
        lines.append(
            "| 面试链路完成率 | "
            f"{interview_summary['chainCompletionCount']}/"
            f"{interview_summary['totalSessions']} "
            f"({format_percent(interview_summary['chainCompletionRate'])}) | "
            "从创建 session 到拿到最终 report 的端到端成功率 |"
        )
        lines.append(
            "| 面试报告生成成功率 | "
            f"{format_percent(interview_summary['reportSuccessRate'])} | "
            "最终报告包含关键字段的比例 |"
        )
    for metric in manual_metrics:
        lines.append(
            f"| {metric['label']} | {metric['value']} | {metric['description']} |"
        )
    lines.append("")

    lines.append("## 可直接复用的项目表述")
    lines.append("")
    for bullet in build_resume_bullets(summary):
        lines.append(f"- {bullet}")
    lines.append("")

    if eval_summary:
        lines.append("## Agent 质量细分")
        lines.append("")
        lines.append(
            "- 覆盖样本："
            f"{eval_summary['coverage']['resumeFixtures']} 份简历样本，"
            f"{eval_summary['coverage']['jdFixtures']} 份 JD 样本。"
        )
        lines.append(
            "- 关键词提升："
            f"{eval_summary['keywordImprovement']['improvedCount']}/"
            f"{eval_summary['keywordImprovement']['caseCount']} 条用例有提升。"
        )
        lines.append(
            "- 工具精确命中："
            f"{eval_summary['toolCorrectness']['exactMatchCount']}/"
            f"{eval_summary['toolCorrectness']['caseCount']} 条用例 F1 = 1.0。"
        )
        lines.append(
            "- 回退触发率："
            f"{format_percent(eval_summary['fallbackRate'])}，"
            f"平均完成耗时 {format_seconds(eval_summary['averageLatencySeconds'])}，"
            f"P95 {format_seconds(eval_summary['p95LatencySeconds'])}。"
        )
        if eval_summary.get("gate"):
            failed_gates = eval_summary["gate"].get("failedGates", [])
            lines.append(
                "- Gate："
                f"{'pass' if eval_summary['gate'].get('passed') else 'fail'}，"
                f"失败项 {', '.join(failed_gates) if failed_gates else '无'}。"
            )
        if eval_summary.get("failureTaxonomy"):
            failure_text = "；".join(
                f"{failure['category']}={failure['count']}"
                for failure in eval_summary["failureTaxonomy"]
            )
            lines.append(f"- 失败分类概览：{failure_text}。")
        if eval_summary["llmJudge"]["caseCount"] > 0:
            lines.append(
                "- LLM Judge："
                f"指令遵循 "
                f"{eval_summary['llmJudge']['averageInstructionFollow']:.2f}/5，"
                f"内容质量 {eval_summary['llmJudge']['averageQuality']:.2f}/5，"
                f"无幻觉 {eval_summary['llmJudge']['averageNoHallucination']:.2f}/5。"
            )
        lines.append("")

    if perf_summary:
        lines.append("## 性能测量细分")
        lines.append("")
        lines.append(
            "- API 探针数量："
            f"{perf_summary['apiProbeCount']}，浏览器路由数量："
            f"{perf_summary['browserRouteCount']}。"
        )
        if perf_summary["slowestRoute"]:
            lines.append(
                "- 最慢页面："
                f"{perf_summary['slowestRoute']['name']}，"
                f"平均 {format_milliseconds(perf_summary['slowestRoute']['avgMs'])}。"
            )
        lines.append("")
        lines.append("| 页面 / 接口 | Avg | P95 | Max |")
        lines.append("| --- | --- | --- | --- |")
        for item in perf_summary["apiProbes"]:
            lines.append(
                f"| {item['name']} | {format_milliseconds(item['avgMs'])} | "
                f"{format_milliseconds(item['p95Ms'])} | "
                f"{format_milliseconds(item['maxMs'])} |"
            )
        for item in perf_summary["browserRoutes"]:
            lines.append(
                f"| {item['name']} | {format_milliseconds(item['avgMs'])} | "
                f"{format_milliseconds(item['p95Ms'])} | "
                f"{format_milliseconds(item['maxMs'])} |"
            )
        lines.append("")

    if interview_summary:
        lines.append("## 面试链路细分")
        lines.append("")
        lines.append(
            f"- 创建成功率：{format_percent(interview_summary['createSuccessRate'])}。"
        )
        lines.append(
            f"- 开始成功率：{format_percent(interview_summary['startSuccessRate'])}。"
        )
        lines.append(
            f"- 回答成功率：{format_percent(interview_summary['answerSuccessRate'])}。"
        )
        lines.append(
            "- 练习模式评估就绪率："
            f"{format_percent(interview_summary['evaluationReadyRate'])}。"
        )
        lines.append(
            "- 面试链路完成率："
            f"{format_percent(interview_summary['chainCompletionRate'])}。"
        )
        lines.append("")

    lines.append("## 说明")
    lines.append("")
    lines.append("- `JD 匹配度提升` 来自 `eval/score.py` 的关键词覆盖率增量。")
    lines.append("- `工具调用正确性` 来自预期工具集与实际调用集的 F1。")
    lines.append("- `面试链路完成率` 来自 interviews API 的端到端链路回放统计。")
    lines.append(
        "- `manual metrics` 用于承接面试复训率、"
        "线上转化率等尚未完全自动化的业务指标。"
    )
    lines.append("")

    return "\n".join(lines).strip() + "\n"


def build_summary(
    eval_scores: dict[str, Any] | None,
    perf_report: dict[str, Any] | None,
    interview_report: dict[str, Any] | None,
    manual_metrics: dict[str, Any] | None,
    eval_analysis: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """用于汇总所有输入源，生成统一摘要结构。"""
    sources: list[str] = []
    summary: dict[str, Any] = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
        "eval": None,
        "perf": None,
        "interview": None,
        "manualMetrics": [],
    }

    if eval_analysis is not None:
        summary["eval"] = summarize_eval_analysis(eval_analysis)
        sources.append("eval_analysis.json")
    elif eval_scores is not None:
        summary["eval"] = summarize_eval(eval_scores)
        sources.append("eval_scores.json")
    if perf_report is not None:
        summary["perf"] = summarize_perf(perf_report)
        sources.append("perf-report.json")
    if interview_report is not None:
        summary["interview"] = summarize_interview_metrics(interview_report)
        sources.append("interview-metrics.json")
    if manual_metrics is not None:
        summary["manualMetrics"] = summarize_manual_metrics(manual_metrics)
        if summary["manualMetrics"]:
            sources.append("manual_metrics.json")

    return summary


def parse_args() -> argparse.Namespace:
    """用于解析命令行参数。"""
    parser = argparse.ArgumentParser(
        description="把 Agent 评测结果整理成求职证据包摘要"
    )
    parser.add_argument("--eval-scores", help="eval/score.py 生成的评分文件路径")
    parser.add_argument(
        "--eval-analysis",
        help="eval/analyze_results.py 生成的分析文件路径",
    )
    parser.add_argument(
        "--perf-report",
        help="measure-production.mjs 生成的性能报告路径",
    )
    parser.add_argument(
        "--interview-report",
        help="measure_interview_pipeline.py 生成的面试链路报告路径",
    )
    parser.add_argument("--manual-metrics", help="手工补充指标 JSON 文件路径")
    parser.add_argument(
        "--output-md",
        help="Markdown 输出文件路径；不传则打印到标准输出",
    )
    parser.add_argument("--output-json", help="结构化 JSON 摘要输出路径")
    return parser.parse_args()


def main() -> None:
    """用于串起评测摘要生成流程。"""
    args = parse_args()

    if not any(
        (
            args.eval_scores,
            args.eval_analysis,
            args.perf_report,
            args.interview_report,
            args.manual_metrics,
        )
    ):
        raise SystemExit(
            "至少需要提供一个输入：--eval-scores / --perf-report / "
            "--eval-analysis / "
            "--interview-report / "
            "--manual-metrics"
        )

    eval_scores = load_json(Path(args.eval_scores)) if args.eval_scores else None
    eval_analysis = (
        load_json(Path(args.eval_analysis)) if args.eval_analysis else None
    )
    perf_report = load_json(Path(args.perf_report)) if args.perf_report else None
    interview_report = (
        load_json(Path(args.interview_report)) if args.interview_report else None
    )
    manual_metrics = (
        load_json(Path(args.manual_metrics)) if args.manual_metrics else None
    )

    summary = build_summary(
        eval_scores=eval_scores,
        perf_report=perf_report,
        interview_report=interview_report,
        manual_metrics=manual_metrics,
        eval_analysis=eval_analysis,
    )
    markdown = build_markdown(summary)

    if args.output_md:
        output_md_path = Path(args.output_md)
        output_md_path.parent.mkdir(parents=True, exist_ok=True)
        output_md_path.write_text(markdown, encoding="utf-8")
        print(f"Markdown 摘要已写入: {output_md_path}")
    else:
        print(markdown)

    if args.output_json:
        output_json_path = Path(args.output_json)
        output_json_path.parent.mkdir(parents=True, exist_ok=True)
        output_json_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"JSON 摘要已写入: {output_json_path}")


if __name__ == "__main__":
    main()
