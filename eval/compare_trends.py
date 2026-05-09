"""Compare two deterministic eval analysis summaries."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def round_metric(value: float) -> float:
    return round(value, 3)


def ratio(numerator: Any, denominator: Any) -> float | None:
    denominator_value = int(denominator or 0)
    if denominator_value <= 0:
        return None
    return round_metric(float(numerator or 0) / denominator_value)


def direction_for_delta(
    delta: float | None,
    *,
    lower_is_better: bool = False,
) -> str:
    if delta is None or delta == 0:
        return "unchanged"
    improved = delta < 0 if lower_is_better else delta > 0
    return "improved" if improved else "regressed"


def compare_numeric(
    baseline: float | None,
    current: float | None,
    *,
    lower_is_better: bool = False,
) -> dict[str, Any]:
    if baseline is None or current is None:
        return {
            "baseline": baseline,
            "current": current,
            "delta": None,
            "direction": "missing",
        }
    delta = round_metric(current - baseline)
    return {
        "baseline": baseline,
        "current": current,
        "delta": delta,
        "direction": direction_for_delta(delta, lower_is_better=lower_is_better),
    }


def case_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(case.get("id")): case
        for case in payload.get("cases", [])
        if isinstance(case, dict) and case.get("id") is not None
    }


def failed_case_ids(payload: dict[str, Any]) -> set[str]:
    return {
        case_id
        for case_id, case in case_by_id(payload).items()
        if not bool(case.get("passed"))
    }


def average_tool_f1(payload: dict[str, Any]) -> float | None:
    values = []
    for case in case_by_id(payload).values():
        tool_score = case.get("expectations", {}).get("toolCalls")
        if isinstance(tool_score, dict) and tool_score.get("f1") is not None:
            values.append(float(tool_score["f1"]))
    if not values:
        return None
    return round_metric(sum(values) / len(values))


def fallback_rate(payload: dict[str, Any]) -> float | None:
    cases = list(case_by_id(payload).values())
    if not cases:
        return None
    fallback_count = 0
    has_runtime_signal = False
    for case in cases:
        runtime = case.get("expectations", {}).get("runtimeStability")
        if not isinstance(runtime, dict):
            continue
        has_runtime_signal = True
        if runtime.get("fallbackTriggered"):
            fallback_count += 1
    if not has_runtime_signal:
        return None
    return round_metric(fallback_count / len(cases))


def keyword_improvement(payload: dict[str, Any]) -> float | None:
    summary = payload.get("summary", {})
    if summary.get("keywordImprovement") is not None:
        return round_metric(float(summary["keywordImprovement"]))
    return None


def gate_status(payload: dict[str, Any]) -> str | None:
    summary = payload.get("summary", {})
    value = summary.get("gateStatus")
    if isinstance(value, str):
        return value
    gate = summary.get("gate")
    if isinstance(gate, dict) and isinstance(gate.get("status"), str):
        return gate["status"]
    return None


def compare_gate_status(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    baseline_status = gate_status(baseline)
    current_status = gate_status(current)
    direction = "unchanged"
    if baseline_status == "fail" and current_status == "pass":
        direction = "improved"
    elif baseline_status == "pass" and current_status == "fail":
        direction = "regressed"
    elif baseline_status is None or current_status is None:
        direction = "missing"
    return {
        "baseline": baseline_status,
        "current": current_status,
        "changed": baseline_status != current_status,
        "direction": direction,
    }


def compare_cases(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, list[str]]:
    baseline_failed = failed_case_ids(baseline)
    current_failed = failed_case_ids(current)
    return {
        "newlyFailed": sorted(current_failed - baseline_failed),
        "fixed": sorted(baseline_failed - current_failed),
        "stillFailing": sorted(baseline_failed & current_failed),
    }


def taxonomy_categories(payload: dict[str, Any]) -> set[str]:
    taxonomy = payload.get("summary", {}).get("failureTaxonomy", {})
    if not isinstance(taxonomy, dict):
        return set()
    return {str(category) for category in taxonomy}


def compare_taxonomy(
    baseline: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, list[str]]:
    baseline_categories = taxonomy_categories(baseline)
    current_categories = taxonomy_categories(current)
    return {
        "added": sorted(current_categories - baseline_categories),
        "removed": sorted(baseline_categories - current_categories),
        "persisting": sorted(baseline_categories & current_categories),
    }


def build_comparison(
    baseline: dict[str, Any],
    current: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    baseline_summary = baseline.get("summary", {})
    current_summary = current.get("summary", {})
    metrics = {
        "successRate": compare_numeric(
            ratio(baseline_summary.get("okCases"), baseline_summary.get("totalCases")),
            ratio(current_summary.get("okCases"), current_summary.get("totalCases")),
        ),
        "averageToolF1": compare_numeric(
            average_tool_f1(baseline),
            average_tool_f1(current),
        ),
        "keywordImprovement": compare_numeric(
            keyword_improvement(baseline),
            keyword_improvement(current),
        ),
        "fallbackRate": compare_numeric(
            fallback_rate(baseline),
            fallback_rate(current),
            lower_is_better=True,
        ),
        "gateStatus": compare_gate_status(baseline, current),
    }
    return {
        "metadata": {
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "inputs": {
                "baseline": str(Path(args.baseline)),
                "current": str(Path(args.current)),
            },
            "baselineGeneratedAt": baseline.get("metadata", {}).get("generatedAt"),
            "currentGeneratedAt": current.get("metadata", {}).get("generatedAt"),
        },
        "metrics": metrics,
        "cases": compare_cases(baseline, current),
        "failureTaxonomy": compare_taxonomy(baseline, current),
    }


def format_percent(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:.1f}%"


def format_delta_pp(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value * 100:+.1f}pp"


def format_decimal(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:.3f}"


def format_delta_decimal(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{value:+.3f}"


def format_list(values: list[str]) -> str:
    return ", ".join(values) if values else "无"


def print_summary(comparison: dict[str, Any]) -> None:
    success = comparison["metrics"]["successRate"]
    print(
        "成功率: "
        f"{format_percent(success['baseline'])} -> "
        f"{format_percent(success['current'])} "
        f"({format_delta_pp(success['delta'])})"
    )
    tool_f1 = comparison["metrics"]["averageToolF1"]
    print(
        "工具 F1: "
        f"{format_decimal(tool_f1['baseline'])} -> "
        f"{format_decimal(tool_f1['current'])} "
        f"({format_delta_decimal(tool_f1['delta'])})"
    )
    keyword = comparison["metrics"]["keywordImprovement"]
    print(
        "关键词提升: "
        f"{format_percent(keyword['baseline'])} -> "
        f"{format_percent(keyword['current'])} "
        f"({format_delta_pp(keyword['delta'])})"
    )
    fallback = comparison["metrics"]["fallbackRate"]
    print(
        "Fallback 率: "
        f"{format_percent(fallback['baseline'])} -> "
        f"{format_percent(fallback['current'])} "
        f"({format_delta_pp(fallback['delta'])})"
    )
    gate = comparison["metrics"]["gateStatus"]
    print(
        "Gate: "
        f"{gate['baseline'] or 'N/A'} -> {gate['current'] or 'N/A'} "
        f"({gate['direction']})"
    )
    cases = comparison["cases"]
    print(f"新增失败: {format_list(cases['newlyFailed'])}")
    print(f"修复失败: {format_list(cases['fixed'])}")
    print(f"仍失败: {format_list(cases['stillFailing'])}")
    taxonomy = comparison["failureTaxonomy"]
    print(f"新增失败分类: {format_list(taxonomy['added'])}")
    print(f"消失失败分类: {format_list(taxonomy['removed'])}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two eval summaries")
    parser.add_argument("--baseline", required=True, help="Baseline analysis JSON")
    parser.add_argument("--current", required=True, help="Current analysis JSON")
    parser.add_argument("--output", required=True, help="Trend output JSON")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison = build_comparison(
        load_json(Path(args.baseline)),
        load_json(Path(args.current)),
        args,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print_summary(comparison)


if __name__ == "__main__":
    main()
