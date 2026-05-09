import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
TREND = ROOT_DIR / "eval" / "compare_trends.py"


def run_trend(baseline_path: Path, current_path: Path, output_path: Path):
    return subprocess.run(
        [
            sys.executable,
            str(TREND),
            "--baseline",
            str(baseline_path),
            "--current",
            str(current_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT_DIR / "backend",
        text=True,
        capture_output=True,
        check=False,
    )


def write_summary(path: Path, payload: dict):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_trend_comparison_reports_improvements_and_fixed_cases(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "trend.json"

    write_summary(
        baseline_path,
        {
            "metadata": {"generatedAt": "2026-05-01T00:00:00+00:00"},
            "summary": {
                "totalCases": 3,
                "okCases": 2,
                "passedCases": 1,
                "failedCases": 2,
                "keywordImprovement": 0.1,
                "failureTaxonomy": {
                    "tool_mismatch": {"count": 1, "caseIds": ["TC001"]},
                    "forbidden_content": {"count": 1, "caseIds": ["TC002"]},
                },
                "gateStatus": "fail",
            },
            "cases": [
                {
                    "id": "TC001",
                    "passed": False,
                    "expectations": {
                        "toolCalls": {"f1": 0.5},
                        "runtimeStability": {
                            "fallbackTriggered": True,
                            "passed": False,
                        },
                    },
                    "failures": [{"category": "tool_mismatch"}],
                },
                {
                    "id": "TC002",
                    "passed": False,
                    "expectations": {"toolCalls": {"f1": 1.0}},
                    "failures": [{"category": "forbidden_content"}],
                },
                {
                    "id": "TC003",
                    "passed": True,
                    "expectations": {"toolCalls": {"f1": 1.0}},
                },
            ],
        },
    )
    write_summary(
        current_path,
        {
            "metadata": {"generatedAt": "2026-05-09T00:00:00+00:00"},
            "summary": {
                "totalCases": 3,
                "okCases": 3,
                "passedCases": 2,
                "failedCases": 1,
                "keywordImprovement": 0.22,
                "failureTaxonomy": {
                    "forbidden_content": {"count": 1, "caseIds": ["TC002"]},
                },
                "gateStatus": "pass",
            },
            "cases": [
                {
                    "id": "TC001",
                    "passed": True,
                    "expectations": {
                        "toolCalls": {"f1": 1.0},
                        "runtimeStability": {
                            "fallbackTriggered": False,
                            "passed": True,
                        },
                    },
                },
                {
                    "id": "TC002",
                    "passed": False,
                    "expectations": {"toolCalls": {"f1": 1.0}},
                    "failures": [{"category": "forbidden_content"}],
                },
                {
                    "id": "TC003",
                    "passed": True,
                    "expectations": {"toolCalls": {"f1": 1.0}},
                },
            ],
        },
    )

    completed = run_trend(baseline_path, current_path, output_path)

    assert completed.returncode == 0, completed.stderr
    assert "成功率: 66.7% -> 100.0% (+33.3pp)" in completed.stdout
    assert "工具 F1: 0.833 -> 1.000 (+0.167)" in completed.stdout
    assert "关键词提升: 10.0% -> 22.0% (+12.0pp)" in completed.stdout
    assert "Fallback 率: 33.3% -> 0.0% (-33.3pp)" in completed.stdout
    assert "Gate: fail -> pass (improved)" in completed.stdout
    assert "修复失败: TC001" in completed.stdout
    assert "新增失败分类: 无" in completed.stdout
    assert "消失失败分类: tool_mismatch" in completed.stdout

    trend = json.loads(output_path.read_text(encoding="utf-8"))
    assert trend["metadata"]["inputs"] == {
        "baseline": str(baseline_path),
        "current": str(current_path),
    }
    assert trend["metrics"]["successRate"] == {
        "baseline": 0.667,
        "current": 1.0,
        "delta": 0.333,
        "direction": "improved",
    }
    assert trend["metrics"]["averageToolF1"] == {
        "baseline": 0.833,
        "current": 1.0,
        "delta": 0.167,
        "direction": "improved",
    }
    assert trend["metrics"]["keywordImprovement"] == {
        "baseline": 0.1,
        "current": 0.22,
        "delta": 0.12,
        "direction": "improved",
    }
    assert trend["metrics"]["fallbackRate"] == {
        "baseline": 0.333,
        "current": 0.0,
        "delta": -0.333,
        "direction": "improved",
    }
    assert trend["metrics"]["gateStatus"] == {
        "baseline": "fail",
        "current": "pass",
        "changed": True,
        "direction": "improved",
    }
    assert trend["cases"] == {
        "newlyFailed": [],
        "fixed": ["TC001"],
        "stillFailing": ["TC002"],
    }
    assert trend["failureTaxonomy"] == {
        "added": [],
        "removed": ["tool_mismatch"],
        "persisting": ["forbidden_content"],
    }


def test_trend_comparison_reports_regressions_and_case_set_changes(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "trend.json"

    write_summary(
        baseline_path,
        {
            "summary": {
                "totalCases": 3,
                "okCases": 3,
                "passedCases": 2,
                "failedCases": 1,
                "failureTaxonomy": {
                    "tool_mismatch": {"count": 1, "caseIds": ["TC002"]},
                },
                "gateStatus": "pass",
            },
            "cases": [
                {"id": "TC001", "passed": True},
                {
                    "id": "TC002",
                    "passed": False,
                    "failures": [{"category": "tool_mismatch"}],
                },
                {"id": "TC003", "passed": True},
            ],
        },
    )
    write_summary(
        current_path,
        {
            "summary": {
                "totalCases": 4,
                "okCases": 3,
                "passedCases": 2,
                "failedCases": 2,
                "failureTaxonomy": {
                    "tool_mismatch": {"count": 1, "caseIds": ["TC002"]},
                    "latency_or_fallback": {"count": 1, "caseIds": ["TC004"]},
                },
                "gateStatus": "fail",
            },
            "cases": [
                {"id": "TC001", "passed": True},
                {
                    "id": "TC002",
                    "passed": False,
                    "failures": [{"category": "tool_mismatch"}],
                },
                {"id": "TC003", "passed": True},
                {
                    "id": "TC004",
                    "passed": False,
                    "failures": [{"category": "latency_or_fallback"}],
                },
            ],
        },
    )

    completed = run_trend(baseline_path, current_path, output_path)

    assert completed.returncode == 0, completed.stderr
    trend = json.loads(output_path.read_text(encoding="utf-8"))
    assert trend["metrics"]["successRate"] == {
        "baseline": 1.0,
        "current": 0.75,
        "delta": -0.25,
        "direction": "regressed",
    }
    assert trend["metrics"]["gateStatus"] == {
        "baseline": "pass",
        "current": "fail",
        "changed": True,
        "direction": "regressed",
    }
    assert trend["cases"] == {
        "newlyFailed": ["TC004"],
        "fixed": [],
        "stillFailing": ["TC002"],
    }
    assert trend["failureTaxonomy"] == {
        "added": ["latency_or_fallback"],
        "removed": [],
        "persisting": ["tool_mismatch"],
    }


def test_trend_comparison_marks_missing_optional_metrics(tmp_path):
    baseline_path = tmp_path / "baseline.json"
    current_path = tmp_path / "current.json"
    output_path = tmp_path / "trend.json"

    write_summary(
        baseline_path,
        {
            "summary": {"totalCases": 1, "okCases": 1},
            "cases": [{"id": "TC001", "passed": True}],
        },
    )
    write_summary(
        current_path,
        {
            "summary": {"totalCases": 1, "okCases": 1},
            "cases": [{"id": "TC001", "passed": True}],
        },
    )

    completed = run_trend(baseline_path, current_path, output_path)

    assert completed.returncode == 0, completed.stderr
    assert "工具 F1: N/A -> N/A (N/A)" in completed.stdout
    assert "关键词提升: N/A -> N/A (N/A)" in completed.stdout
    assert "Fallback 率: N/A -> N/A (N/A)" in completed.stdout
    assert "Gate: N/A -> N/A (missing)" in completed.stdout

    metrics = json.loads(output_path.read_text(encoding="utf-8"))["metrics"]
    assert metrics["averageToolF1"] == {
        "baseline": None,
        "current": None,
        "delta": None,
        "direction": "missing",
    }
    assert metrics["keywordImprovement"] == {
        "baseline": None,
        "current": None,
        "delta": None,
        "direction": "missing",
    }
    assert metrics["fallbackRate"] == {
        "baseline": None,
        "current": None,
        "delta": None,
        "direction": "missing",
    }
    assert metrics["gateStatus"] == {
        "baseline": None,
        "current": None,
        "changed": False,
        "direction": "missing",
    }
