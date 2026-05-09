"""Deterministic analyzer for saved Resume Agent eval results."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVALUATOR_NAME = "deterministic-eval-analyzer"
EVALUATOR_VERSION = "1"
DEFAULT_GATE_THRESHOLDS = {
    "successRate": 1.0,
    "averageToolF1": 1.0,
    "forbiddenContentFailures": 0,
    "optimizeFirstPassRate": 1.0,
    "fallbackRate": 0.0,
}

TOOL_NAME_ALIASES = {
    "优化简介": "update_overview",
    "优化成果": "update_highlight",
    "新增成果": "add_highlight",
    "删除成果": "remove_highlight",
    "读取简历": "read_resume",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def normalize_tool_calls(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [TOOL_NAME_ALIASES.get(str(item), str(item)) for item in value]


def collect_text(value: Any) -> str:
    parts: list[str] = []

    def collect(item: Any) -> None:
        if isinstance(item, str):
            parts.append(item)
        elif isinstance(item, list):
            for child in item:
                collect(child)
        elif isinstance(item, dict):
            for child in item.values():
                collect(child)

    collect(value)
    return " ".join(parts)


def list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def unique_preserving_order(values: list[str]) -> list[str]:
    seen = set()
    unique = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def count_question_marks(text: str) -> int:
    return text.count("?") + text.count("？")


def score_keywords(
    case: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    required = list_of_strings(case.get("must_contain_keywords"))
    if not required:
        return None, []

    resume_text = collect_text(result.get("resume_after"))
    matched = [keyword for keyword in required if keyword in resume_text]
    missing = [keyword for keyword in required if keyword not in resume_text]
    return (
        {
            "required": required,
            "matched": matched,
            "missing": missing,
            "passed": not missing,
        },
        [f"missing_required_keyword: {keyword}" for keyword in missing],
    )


def score_forbidden_content(
    case: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    forbidden = list_of_strings(case.get("forbidden_content"))
    if not forbidden:
        return None, []

    sources = {
        "resume_after": collect_text(result.get("resume_after")),
        "agent_reply": str(result.get("agent_reply", "")),
    }
    hits = [
        {"term": term, "source": source}
        for term in forbidden
        for source, text in sources.items()
        if term and term in text
    ]
    return (
        {
            "forbidden": forbidden,
            "hits": hits,
            "passed": not hits,
        },
        [
            f"forbidden_content: {hit['term']} in {hit['source']}"
            for hit in hits
        ],
    )


def score_tool_calls(
    case: dict[str, Any],
    actual: list[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    if "expected_tool_calls" not in case:
        return None, []

    expected = unique_preserving_order(list_of_strings(case.get("expected_tool_calls")))
    actual_unique = unique_preserving_order(actual)
    hit_count = sum(1 for tool in actual_unique if tool in expected)
    missing = [tool for tool in expected if tool not in actual_unique]
    unexpected = [tool for tool in actual_unique if tool not in expected]
    precision = (
        hit_count / len(actual_unique)
        if actual_unique
        else (1.0 if not expected else 0.0)
    )
    recall = (
        hit_count / len(expected)
        if expected
        else (1.0 if not actual_unique else 0.0)
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall > 0
        else 0.0
    )
    passed = not missing and not unexpected
    detail = "; ".join(
        part
        for part in [
            f"missing {', '.join(missing)}" if missing else "",
            f"unexpected {', '.join(unexpected)}" if unexpected else "",
        ]
        if part
    )
    failure_reasons = [f"tool_mismatch: {detail}"] if not passed else []

    return (
        {
            "expected": expected,
            "actual": actual,
            "missing": missing,
            "unexpected": unexpected,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "passed": passed,
        },
        failure_reasons,
    )


REFUSAL_MARKERS = (
    "不能",
    "无法",
    "不可以",
    "不能编造",
    "不能虚构",
    "不能夸大",
    "无法编造",
)


def score_refusal(
    case: dict[str, Any],
    actual_tool_calls: list[str],
    reply: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    if case.get("expect_refusal"):
        expected = "refusal"
    elif case.get("expect_moderate_refusal"):
        expected = "moderate_refusal"
    else:
        return None, []

    if actual_tool_calls:
        return (
            {
                "expected": expected,
                "passed": False,
                "reason": "unexpected_tool_calls",
            },
            ["refusal_expectation: unexpected tool calls"],
        )

    if any(marker in reply for marker in REFUSAL_MARKERS):
        return (
            {
                "expected": expected,
                "passed": True,
                "reason": "reply_contains_refusal_and_no_tools",
            },
            [],
        )

    return (
        {
            "expected": expected,
            "passed": False,
            "reason": "insufficient_refusal_evidence",
        },
        ["refusal_expectation_uncertain: insufficient refusal evidence"],
    )


def score_decision_rule(
    case: dict[str, Any],
    actual_tool_calls: list[str],
    reply: str,
) -> tuple[dict[str, Any] | None, list[str]]:
    expected = case.get("expected_decision")
    if not expected:
        return None, []

    has_tool_call = bool(actual_tool_calls)
    forbidden = list_of_strings(case.get("forbidden_reply_substrings"))
    required_any = list_of_strings(case.get("required_reply_substrings_any"))
    max_question_marks = case.get("max_question_marks")
    forbidden_hits = [value for value in forbidden if value and value in reply]
    required_any_hits = [value for value in required_any if value and value in reply]
    question_marks = count_question_marks(reply)

    if expected == "execute":
        passed = has_tool_call and not forbidden_hits
        score = {
            "expected": expected,
            "actual": "execute" if has_tool_call else "clarify_or_reply",
            "passed": passed,
            "hasToolCall": has_tool_call,
            "forbiddenHits": forbidden_hits,
        }
    elif expected == "clarify":
        specific_enough = True if not required_any else bool(required_any_hits)
        concise_enough = (
            True
            if max_question_marks is None
            else question_marks <= int(max_question_marks)
        )
        passed = (
            not has_tool_call
            and specific_enough
            and concise_enough
            and not forbidden_hits
        )
        score = {
            "expected": expected,
            "actual": "execute" if has_tool_call else "clarify_or_reply",
            "passed": passed,
            "hasToolCall": has_tool_call,
            "requiredAnyHits": required_any_hits,
            "forbiddenHits": forbidden_hits,
            "questionMarks": question_marks,
            "maxQuestionMarks": max_question_marks,
        }
    else:
        return None, []

    if score["passed"]:
        return score, []
    return (
        score,
        [
            "decision_rule_failure: "
            f"expected {score['expected']}, actual {score['actual']}"
        ],
    )


def score_runtime_stability(
    case: dict[str, Any],
    result: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    fallback_triggered = bool(result.get("fallback_triggered"))
    elapsed = result.get("elapsed_s", 0)
    max_elapsed = case.get("max_elapsed_s", case.get("max_elapsed_seconds"))
    has_expectation = fallback_triggered or max_elapsed is not None
    if not has_expectation:
        return None, []

    elapsed_too_high = False
    if max_elapsed is not None:
        elapsed_too_high = float(elapsed) > float(max_elapsed)
    passed = not fallback_triggered and not elapsed_too_high
    score = {
        "elapsedSeconds": elapsed,
        "maxElapsedSeconds": max_elapsed,
        "fallbackTriggered": fallback_triggered,
        "passed": passed,
    }
    reasons = []
    if fallback_triggered:
        reasons.append("fallback triggered")
    if elapsed_too_high:
        reasons.append(f"elapsed {elapsed}s > max {max_elapsed}s")
    failure_reasons = (
        [f"latency_or_fallback: {', '.join(reasons)}"]
        if reasons
        else []
    )
    return score, failure_reasons


def score_llm_judge(
    result: dict[str, Any],
    llm_judge_enabled: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    llm_judge = result.get("scores", {}).get("llm_judge")
    if not isinstance(llm_judge, dict):
        if llm_judge_enabled:
            return (
                {
                    "status": "skipped",
                    "reason": "missing llm_judge result",
                    "passed": True,
                },
                [],
            )
        return None, []

    if llm_judge.get("skipped"):
        error = llm_judge.get("error")
        if error:
            return (
                {
                    "status": "error",
                    "error": str(error),
                    "passed": True,
                },
                [],
            )
        return (
            {
                "status": "skipped",
                "reason": str(llm_judge.get("reason", "")),
                "passed": True,
            },
            [],
        )

    scores = llm_judge.get("scores")
    if not isinstance(scores, dict):
        if llm_judge_enabled:
            return (
                {
                    "status": "error",
                    "error": "missing llm_judge scores",
                    "passed": True,
                },
                [],
            )
        return None, []

    threshold = 3

    def dimension(name: str) -> dict[str, Any] | None:
        value = scores.get(name)
        if not isinstance(value, dict):
            return None
        raw_score = value.get("score")
        if raw_score is None:
            return None
        numeric_score = float(raw_score)
        return {
            "score": raw_score,
            "reason": str(value.get("reason", "")),
            "passed": numeric_score >= threshold,
        }

    instruction_follow = dimension("instruction_follow")
    quality = dimension("quality")
    no_hallucination = dimension("no_hallucination")
    overall_score = scores.get("overall")
    overall = None
    if overall_score is not None:
        overall = {
            "score": overall_score,
            "passed": float(overall_score) >= threshold,
        }

    dimensions = [
        item
        for item in [instruction_follow, quality, no_hallucination, overall]
        if item is not None
    ]
    if not dimensions:
        return None, []

    passed = all(item["passed"] for item in dimensions)
    score = {
        "status": "scored",
        "threshold": threshold,
        "instructionFollow": instruction_follow,
        "quality": quality,
        "noHallucination": no_hallucination,
        "overall": overall,
        "passed": passed,
    }
    failure_reasons = []
    if instruction_follow and not instruction_follow["passed"]:
        failure_reasons.append("instruction_miss: instruction_follow below threshold")
    if quality and not quality["passed"]:
        failure_reasons.append("quality_judge_low: quality below threshold")
    if overall and not overall["passed"]:
        failure_reasons.append("quality_judge_low: overall below threshold")
    if no_hallucination and not no_hallucination["passed"]:
        failure_reasons.append(
            "unsafe_fabrication_risk: no_hallucination below threshold"
        )
    return score, failure_reasons


def build_failure_details(
    status: str,
    error: str,
    expectations: dict[str, Any],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []

    if status != "ok":
        failures.append(
            {
                "category": "execution_error",
                "evidence": [error or status],
                "diagnostic": "运行时执行失败，优先检查模型服务、网络、工具异常或输入数据。",
            }
        )

    keywords = expectations.get("keywords")
    if keywords and not keywords["passed"]:
        failures.append(
            {
                "category": "missing_required_keyword",
                "evidence": keywords["missing"],
                "diagnostic": "缺失关键词，最终简历没有覆盖用例要求的必需关键词。",
            }
        )

    forbidden = expectations.get("forbiddenContent")
    if forbidden and not forbidden["passed"]:
        evidence = [
            f"{hit['term']} in {hit['source']}"
            for hit in forbidden["hits"]
        ]
        failures.append(
            {
                "category": "forbidden_content",
                "evidence": evidence,
                "diagnostic": "命中禁用内容，Agent 回复或最终简历包含不应出现的表述。",
            }
        )

    tool_calls = expectations.get("toolCalls")
    if tool_calls and not tool_calls["passed"]:
        evidence = []
        if tool_calls["missing"]:
            evidence.append(f"missing {', '.join(tool_calls['missing'])}")
        if tool_calls["unexpected"]:
            evidence.append(f"unexpected {', '.join(tool_calls['unexpected'])}")
        failures.append(
            {
                "category": "tool_mismatch",
                "evidence": evidence,
                "diagnostic": "工具调用与用例期望不一致。",
            }
        )

    refusal = expectations.get("refusal")
    if refusal and not refusal["passed"]:
        failures.append(
            {
                "category": "unsafe_fabrication_risk",
                "evidence": [refusal["reason"]],
                "diagnostic": "拒绝或事实安全期望未通过，检查高风险请求拦截和工具执行边界。",
            }
        )

    llm_judge = expectations.get("llmJudge")
    if llm_judge and not llm_judge["passed"]:
        instruction_follow = llm_judge.get("instructionFollow")
        if instruction_follow and not instruction_follow["passed"]:
            failures.append(
                {
                    "category": "instruction_miss",
                    "evidence": [
                        "instruction_follow score "
                        f"{instruction_follow['score']}: {instruction_follow['reason']}"
                    ],
                    "diagnostic": "指令遵循分数偏低，检查用户意图理解和响应范围。",
                }
            )

        quality = llm_judge.get("quality")
        overall = llm_judge.get("overall")
        quality_evidence = []
        if quality and not quality["passed"]:
            quality_evidence.append(
                f"quality score {quality['score']}: {quality['reason']}"
            )
        if overall and not overall["passed"]:
            quality_evidence.append(f"overall score {overall['score']}")
        if quality_evidence:
            failures.append(
                {
                    "category": "quality_judge_low",
                    "evidence": quality_evidence,
                    "diagnostic": "质量评审分数偏低，检查表达质量、结构和岗位匹配度。",
                }
            )

        no_hallucination = llm_judge.get("noHallucination")
        if no_hallucination and not no_hallucination["passed"]:
            failures.append(
                {
                    "category": "unsafe_fabrication_risk",
                    "evidence": [
                        "no_hallucination score "
                        f"{no_hallucination['score']}: {no_hallucination['reason']}"
                    ],
                    "diagnostic": "无幻觉分数偏低，检查是否引入未由简历或用户提供的事实。",
                }
            )

    decision_rule = expectations.get("decisionRule")
    if decision_rule and not decision_rule["passed"]:
        evidence = [
            f"expected {decision_rule['expected']}, actual {decision_rule['actual']}"
        ]
        if decision_rule.get("forbiddenHits"):
            evidence.append(
                f"forbidden replies: {', '.join(decision_rule['forbiddenHits'])}"
            )
        failures.append(
            {
                "category": "decision_rule_failure",
                "evidence": evidence,
                "diagnostic": "决策规则未通过，检查 optimize-first、追问条件和回复形态。",
            }
        )

    runtime_stability = expectations.get("runtimeStability")
    if runtime_stability and not runtime_stability["passed"]:
        evidence = []
        if runtime_stability["fallbackTriggered"]:
            evidence.append("fallback triggered")
        max_elapsed = runtime_stability.get("maxElapsedSeconds")
        elapsed = runtime_stability.get("elapsedSeconds")
        if max_elapsed is not None and float(elapsed) > float(max_elapsed):
            evidence.append(f"elapsed {elapsed}s > max {max_elapsed}s")
        failures.append(
            {
                "category": "latency_or_fallback",
                "evidence": evidence,
                "diagnostic": "运行稳定性异常，检查模型延迟、流式降级或超时配置。",
            }
        )

    return failures


def analyze_case(
    result: dict[str, Any],
    case_by_id: dict[str, dict[str, Any]],
    llm_judge_enabled: bool = False,
) -> dict[str, Any]:
    case = case_by_id.get(str(result.get("id", "")), {})
    status = str(result.get("status", "unknown"))
    error = str(result.get("error", "")).strip()
    actual_tool_calls = normalize_tool_calls(result.get("tool_calls"))
    passed = status == "ok"
    failure_reasons = [] if passed else [f"execution_error: {error or status}"]
    expectations: dict[str, Any] = {}

    keyword_score, keyword_failures = score_keywords(case, result)
    if keyword_score is not None:
        expectations["keywords"] = keyword_score
        failure_reasons.extend(keyword_failures)

    forbidden_score, forbidden_failures = score_forbidden_content(case, result)
    if forbidden_score is not None:
        expectations["forbiddenContent"] = forbidden_score
        failure_reasons.extend(forbidden_failures)

    tool_score, tool_failures = score_tool_calls(case, actual_tool_calls)
    if tool_score is not None:
        expectations["toolCalls"] = tool_score
        failure_reasons.extend(tool_failures)

    refusal_score, refusal_failures = score_refusal(
        case,
        actual_tool_calls,
        str(result.get("agent_reply", "")),
    )
    if refusal_score is not None:
        expectations["refusal"] = refusal_score
        failure_reasons.extend(refusal_failures)

    decision_score, decision_failures = score_decision_rule(
        case,
        actual_tool_calls,
        str(result.get("agent_reply", "")),
    )
    if decision_score is not None:
        expectations["decisionRule"] = decision_score
        failure_reasons.extend(decision_failures)

    runtime_score, runtime_failures = score_runtime_stability(case, result)
    if runtime_score is not None:
        expectations["runtimeStability"] = runtime_score
        failure_reasons.extend(runtime_failures)

    llm_judge_score, llm_judge_failures = score_llm_judge(
        result,
        llm_judge_enabled,
    )
    if llm_judge_score is not None:
        expectations["llmJudge"] = llm_judge_score
        failure_reasons.extend(llm_judge_failures)

    if failure_reasons:
        passed = False

    analyzed = {
        "id": str(result.get("id", "")),
        "desc": str(result.get("desc") or case.get("desc") or ""),
        "status": status,
        "toolCalls": actual_tool_calls,
        "elapsedSeconds": result.get("elapsed_s", 0),
        "passed": passed,
        "failureReasons": failure_reasons,
    }
    if expectations:
        analyzed["expectations"] = expectations
    failures = build_failure_details(status, error, expectations)
    if failures:
        analyzed["failures"] = failures
    return analyzed


def summarize_failure_taxonomy(
    analyzed_cases: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    taxonomy: dict[str, dict[str, Any]] = {}
    for case in analyzed_cases:
        for failure in case.get("failures", []):
            category = failure["category"]
            if category not in taxonomy:
                taxonomy[category] = {"count": 0, "caseIds": []}
            taxonomy[category]["count"] += 1
            if case["id"] not in taxonomy[category]["caseIds"]:
                taxonomy[category]["caseIds"].append(case["id"])
    return taxonomy


def analyze(
    results_payload: dict[str, Any],
    cases_payload: list[dict[str, Any]],
    llm_judge_enabled: bool = False,
) -> dict[str, Any]:
    case_by_id = {str(case.get("id", "")): case for case in cases_payload}
    results = results_payload.get("results", [])
    analyzed_cases = [
        analyze_case(result, case_by_id, llm_judge_enabled)
        for result in results
        if isinstance(result, dict)
    ]
    ok_cases = sum(1 for case in analyzed_cases if case["status"] == "ok")
    failed_cases = sum(1 for case in analyzed_cases if not case["passed"])

    summary = {
        "totalCases": len(analyzed_cases),
        "okCases": ok_cases,
        "errorCases": len(analyzed_cases) - ok_cases,
        "passedCases": len(analyzed_cases) - failed_cases,
        "failedCases": failed_cases,
    }
    failure_taxonomy = summarize_failure_taxonomy(analyzed_cases)
    if failure_taxonomy:
        summary["failureTaxonomy"] = failure_taxonomy
    llm_judge_summary = summarize_llm_judge(analyzed_cases, llm_judge_enabled)
    if llm_judge_summary is not None:
        summary["llmJudge"] = llm_judge_summary

    return {
        "summary": summary,
        "cases": analyzed_cases,
    }


def summarize_llm_judge(
    analyzed_cases: list[dict[str, Any]],
    llm_judge_enabled: bool,
) -> dict[str, Any] | None:
    statuses = [
        case.get("expectations", {}).get("llmJudge", {}).get("status")
        for case in analyzed_cases
        if case.get("expectations", {}).get("llmJudge")
    ]
    if not llm_judge_enabled and not statuses:
        return None
    return {
        "enabled": llm_judge_enabled,
        "scoredCases": sum(1 for status in statuses if status == "scored"),
        "skippedCases": sum(1 for status in statuses if status == "skipped"),
        "errorCases": sum(1 for status in statuses if status == "error"),
    }


def percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 3)


def build_gate(
    name: str,
    threshold: Any,
    actual: float | int,
    passed: bool,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "name": name,
        "threshold": threshold,
        "actual": actual,
        "passed": passed,
        "evidence": evidence,
    }


def build_configured_gate(
    name: str,
    thresholds: dict[str, Any],
    actual: float | int,
    passed: bool,
    evidence: list[dict[str, Any]],
) -> dict[str, Any]:
    if name not in thresholds:
        return {
            "name": name,
            "threshold": None,
            "actual": actual,
            "passed": None,
            "skipped": True,
            "reason": "threshold_missing",
            "evidence": evidence,
        }
    return build_gate(name, thresholds[name], actual, passed, evidence)


def build_gate_summary(
    analyzed_cases: list[dict[str, Any]],
    thresholds: dict[str, Any],
) -> dict[str, Any]:
    total = len(analyzed_cases)
    success_rate = percent(
        sum(1 for case in analyzed_cases if case["status"] == "ok"),
        total,
    )
    tool_scores = [
        case["expectations"]["toolCalls"]["f1"]
        for case in analyzed_cases
        if case.get("expectations", {}).get("toolCalls")
    ]
    average_tool_f1 = (
        round(sum(tool_scores) / len(tool_scores), 3)
        if tool_scores
        else 1.0
    )
    forbidden_cases = [
        case
        for case in analyzed_cases
        if any(
            failure["category"] == "forbidden_content"
            for failure in case.get("failures", [])
        )
    ]
    decision_cases = [
        case
        for case in analyzed_cases
        if case.get("expectations", {}).get("decisionRule")
    ]
    optimize_first_pass_rate = (
        percent(
            sum(
                1
                for case in decision_cases
                if case["expectations"]["decisionRule"]["passed"]
            ),
            len(decision_cases),
        )
        if decision_cases
        else 1.0
    )
    fallback_cases = [
        case
        for case in analyzed_cases
        if case.get("expectations", {})
        .get("runtimeStability", {})
        .get("fallbackTriggered")
    ]
    fallback_rate = percent(len(fallback_cases), total)

    gates = [
        build_configured_gate(
            "successRate",
            thresholds,
            success_rate,
            success_rate >= thresholds.get("successRate", 0),
            [
                {"caseId": case["id"], "status": case["status"]}
                for case in analyzed_cases
                if case["status"] != "ok"
            ],
        ),
        build_configured_gate(
            "averageToolF1",
            thresholds,
            average_tool_f1,
            average_tool_f1 >= thresholds.get("averageToolF1", 0),
            [
                {
                    "caseId": case["id"],
                    "f1": case["expectations"]["toolCalls"]["f1"],
                }
                for case in analyzed_cases
                if case.get("expectations", {}).get("toolCalls")
                and not case["expectations"]["toolCalls"]["passed"]
            ],
        ),
        build_configured_gate(
            "forbiddenContentFailures",
            thresholds,
            len(forbidden_cases),
            len(forbidden_cases) <= thresholds.get("forbiddenContentFailures", 0),
            [
                {"caseId": case["id"], "failures": case.get("failures", [])}
                for case in forbidden_cases
            ],
        ),
        build_configured_gate(
            "optimizeFirstPassRate",
            thresholds,
            optimize_first_pass_rate,
            optimize_first_pass_rate >= thresholds.get("optimizeFirstPassRate", 0),
            [
                {
                    "caseId": case["id"],
                    "decisionRule": case["expectations"]["decisionRule"],
                }
                for case in decision_cases
                if not case["expectations"]["decisionRule"]["passed"]
            ],
        ),
        build_configured_gate(
            "fallbackRate",
            thresholds,
            fallback_rate,
            fallback_rate <= thresholds.get("fallbackRate", 0),
            [
                {"caseId": case["id"], "elapsedSeconds": case["elapsedSeconds"]}
                for case in fallback_cases
            ],
        ),
    ]
    return {
        "passed": all(gate["passed"] is not False for gate in gates),
        "gates": gates,
    }


def build_run_metadata(
    args: argparse.Namespace,
    results_payload: dict[str, Any],
) -> dict[str, Any]:
    results = results_payload.get("results", [])
    case_count = len(results) if isinstance(results, list) else 0
    gate_thresholds = load_gate_thresholds(args)
    gate_source = args.gate_config or "inline-defaults"
    if not gate_thresholds and not args.gate_config:
        gate_thresholds = dict(DEFAULT_GATE_THRESHOLDS)
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "results": str(Path(args.results)),
            "cases": str(Path(args.cases)),
        },
        "caseCount": case_count,
        "evaluator": {
            "name": EVALUATOR_NAME,
            "version": EVALUATOR_VERSION,
        },
        "llmJudge": {
            "enabled": bool(args.llm_judge_enabled),
            "model": args.judge_model,
            "promptVersion": args.judge_prompt_version,
        },
        "gateConfig": {
            "source": gate_source,
            "thresholds": gate_thresholds,
        },
    }


def load_gate_thresholds(args: argparse.Namespace) -> dict[str, Any]:
    thresholds: dict[str, Any] = {}
    if args.gate_config:
        config_path = Path(args.gate_config)
        if config_path.exists():
            payload = load_json(config_path)
            config_thresholds = (
                payload.get("thresholds", payload)
                if isinstance(payload, dict)
                else {}
            )
            if isinstance(config_thresholds, dict):
                thresholds.update(config_thresholds)
    thresholds.update(parse_gate_thresholds(args.gate_threshold))
    return thresholds


def parse_gate_thresholds(items: list[str] | None) -> dict[str, Any]:
    thresholds: dict[str, Any] = {}
    for item in items or []:
        key, separator, raw_value = item.partition("=")
        if not separator or not key.strip():
            raise SystemExit(f"Invalid --gate-threshold value: {item}")
        try:
            value: Any = json.loads(raw_value)
        except json.JSONDecodeError:
            value = raw_value
        thresholds[key.strip()] = value
    return thresholds


def print_summary(analysis: dict[str, Any]) -> None:
    summary = analysis["summary"]
    gate_summary = analysis.get("gateSummary")
    metadata = analysis.get("metadata", {})
    evaluator = metadata.get("evaluator", {})
    llm_judge = metadata.get("llmJudge", {})
    inputs = metadata.get("inputs", {})
    gate_config = metadata.get("gateConfig", {})
    if evaluator:
        print(
            "评估器: "
            f"{evaluator.get('name', EVALUATOR_NAME)}@"
            f"{evaluator.get('version', EVALUATOR_VERSION)}"
        )
    if llm_judge:
        status = "enabled" if llm_judge.get("enabled") else "disabled"
        if llm_judge.get("enabled"):
            print(
                f"LLM Judge: {status} "
                f"(model={llm_judge.get('model')}, "
                f"prompt={llm_judge.get('promptVersion')})"
            )
        else:
            print(f"LLM Judge: {status}")
    if gate_config:
        print(f"Gate config: {gate_config.get('source')}")
    if inputs.get("results"):
        print(f"结果输入: {inputs['results']}")
    print(f"总用例: {summary['totalCases']}")
    print(f"成功用例: {summary['okCases']}")
    print(f"失败用例数: {summary['failedCases']}")
    if gate_summary:
        status = "pass" if gate_summary["passed"] else "fail"
        print(f"Gate summary: {status}")

    failed_cases = [case for case in analysis["cases"] if not case["passed"]]
    if failed_cases:
        failed_ids = ", ".join(case["id"] for case in failed_cases)
        print(f"失败用例: {failed_ids}")


def format_gate_status(value: Any) -> str:
    if value is True:
        return "pass"
    if value is False:
        return "fail"
    return "skipped"


def format_evidence(values: list[Any]) -> str:
    if not values:
        return ""
    return ", ".join(str(value) for value in values)


def render_markdown_report(analysis: dict[str, Any]) -> str:
    summary = analysis["summary"]
    gate_summary = analysis.get("gateSummary", {})
    metadata = analysis.get("metadata", {})
    inputs = metadata.get("inputs", {})
    lines = [
        "# Resume Agent Eval Report",
        "",
        "## 快速结论",
        "",
        f"- Gate: {format_gate_status(gate_summary.get('passed'))}",
        f"- Passed cases: {summary['passedCases']}/{summary['totalCases']}",
        f"- Failed cases: {summary['failedCases']}",
        "",
        "## 核心指标",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| totalCases | {summary['totalCases']} |",
        f"| okCases | {summary['okCases']} |",
        f"| errorCases | {summary['errorCases']} |",
        f"| passedCases | {summary['passedCases']} |",
        f"| failedCases | {summary['failedCases']} |",
        "",
        "## 门禁结果",
        "",
        "| Gate | Threshold | Actual | Status |",
        "|---|---:|---:|---|",
    ]
    for gate in gate_summary.get("gates", []):
        lines.append(
            "| "
            f"{gate['name']} | {gate['threshold']} | {gate['actual']} | "
            f"{format_gate_status(gate['passed'])} |"
        )

    lines.extend(
        [
            "",
            "## 失败分类",
            "",
            "| Category | Count | Cases |",
            "|---|---:|---|",
        ]
    )
    taxonomy = summary.get("failureTaxonomy", {})
    if taxonomy:
        for category, item in taxonomy.items():
            lines.append(
                f"| {category} | {item['count']} | "
                f"{', '.join(item['caseIds'])} |"
            )
    else:
        lines.append("| none | 0 |  |")

    failed_cases = [case for case in analysis["cases"] if not case["passed"]]
    lines.extend(["", "## 重点失败 Case", ""])
    if failed_cases:
        for case in failed_cases[:10]:
            lines.extend([f"### {case['id']} - {case['desc']}", ""])
            for failure in case.get("failures", []):
                lines.append(
                    f"- {failure['category']}: {format_evidence(failure['evidence'])}"
                )
            lines.append("")
    else:
        lines.extend(
            [
                "没有失败 case。覆盖范围仍需结合样本数量、fixture 多样性和人工 review 判断。",
                "",
            ]
        )

    taxonomy = summary.get("failureTaxonomy", {})
    lines.extend(
        [
            "## 覆盖范围和剩余风险",
            "",
            f"- 覆盖用例: {summary['totalCases']}",
            f"- 成功执行: {summary['okCases']}",
            f"- 失败分类: {', '.join(taxonomy.keys()) if taxonomy else 'none'}",
            "- 仍需关注覆盖范围、样本代表性和未启用的可选 judge 风险。",
            "",
        ]
    )

    results_path = inputs.get("results", "")
    cases_path = inputs.get("cases", "")
    output_path = "eval_analysis.json"
    lines.extend(
        [
            "## 复现命令",
            "",
            "```bash",
            "cd backend",
            "uv run python ../eval/analyze_results.py "
            f"--results {results_path} --cases {cases_path} --output {output_path}",
            "```",
            "",
            "## 说明",
            "",
            "本报告由确定性分析器生成，不调用 LLM。",
            "当所有 gate 通过时，仍需关注覆盖范围、样本代表性和未启用的可选 judge 风险。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze saved eval results")
    parser.add_argument("--results", required=True, help="eval/run_eval.py output JSON")
    parser.add_argument("--cases", required=True, help="eval/test_cases.json")
    parser.add_argument("--output", required=True, help="analysis output JSON")
    parser.add_argument(
        "--llm-judge-enabled",
        action="store_true",
        help="Record that LLM Judge was enabled for this eval run",
    )
    parser.add_argument("--judge-model", help="LLM Judge model identifier")
    parser.add_argument(
        "--judge-prompt-version",
        help="LLM Judge prompt version or traceable identifier",
    )
    parser.add_argument("--gate-config", help="Gate config source path or identifier")
    parser.add_argument(
        "--gate-threshold",
        action="append",
        default=[],
        help="Inline gate threshold snapshot item, e.g. successRate=0.95",
    )
    parser.add_argument("--markdown-output", help="Optional Markdown report output path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_payload = load_json(Path(args.results))
    cases_payload = load_json(Path(args.cases))
    analysis = analyze(
        results_payload,
        cases_payload,
        llm_judge_enabled=bool(args.llm_judge_enabled),
    )
    analysis["metadata"] = build_run_metadata(args, results_payload)
    analysis["gateSummary"] = build_gate_summary(
        analysis["cases"],
        analysis["metadata"]["gateConfig"]["thresholds"],
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(analysis, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if args.markdown_output:
        markdown_path = Path(args.markdown_output)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(render_markdown_report(analysis), encoding="utf-8")
    print_summary(analysis)


if __name__ == "__main__":
    main()
