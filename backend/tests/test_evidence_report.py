import json
import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
EVIDENCE_REPORT = ROOT_DIR / "eval" / "build_evidence_report.py"


def run_evidence_report(args: list[str]):
    return subprocess.run(
        [sys.executable, str(EVIDENCE_REPORT), *args],
        cwd=ROOT_DIR / "backend",
        text=True,
        capture_output=True,
        check=False,
    )


def test_evidence_report_consumes_eval_analysis_with_interview_metrics(tmp_path):
    eval_analysis_path = tmp_path / "eval_analysis.json"
    interview_report_path = tmp_path / "interview_metrics.json"
    output_json_path = tmp_path / "evidence_summary.json"
    output_md_path = tmp_path / "evidence_summary.md"

    eval_analysis_path.write_text(
        json.dumps(
            {
                "summary": {
                    "totalCases": 3,
                    "okCases": 3,
                    "errorCases": 0,
                    "passedCases": 2,
                    "failedCases": 1,
                    "failureTaxonomy": {
                        "tool_mismatch": {
                            "count": 1,
                            "caseIds": ["TC002"],
                        }
                    },
                },
                "gateSummary": {
                    "passed": False,
                    "gates": [
                        {
                            "name": "successRate",
                            "threshold": 1.0,
                            "actual": 1.0,
                            "passed": True,
                            "evidence": [],
                        },
                        {
                            "name": "averageToolF1",
                            "threshold": 1.0,
                            "actual": 0.667,
                            "passed": False,
                            "evidence": [{"caseId": "TC002", "f1": 0.0}],
                        },
                    ],
                },
                "cases": [
                    {
                        "id": "TC001",
                        "status": "ok",
                        "elapsedSeconds": 1.0,
                        "passed": True,
                        "toolCalls": ["update_highlight"],
                        "expectations": {
                            "toolCalls": {
                                "f1": 1.0,
                                "passed": True,
                            }
                        },
                    },
                    {
                        "id": "TC002",
                        "status": "ok",
                        "elapsedSeconds": 2.0,
                        "passed": False,
                        "toolCalls": ["read_resume"],
                        "expectations": {
                            "toolCalls": {
                                "f1": 0.0,
                                "passed": False,
                            }
                        },
                        "failures": [
                            {
                                "category": "tool_mismatch",
                                "evidence": ["unexpected read_resume"],
                            }
                        ],
                    },
                    {
                        "id": "TC003",
                        "status": "ok",
                        "elapsedSeconds": 3.0,
                        "passed": True,
                        "toolCalls": [],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    interview_report_path.write_text(
        json.dumps(
            {
                "summary": {
                    "totalSessions": 2,
                    "practiceSessions": 1,
                    "simulationSessions": 1,
                    "createSuccessRate": 100.0,
                    "startSuccessRate": 100.0,
                    "answerSuccessRate": 100.0,
                    "evaluationReadyRate": 100.0,
                    "reportSuccessRate": 50.0,
                    "chainCompletionCount": 1,
                    "chainCompletionRate": 50.0,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_evidence_report(
        [
            "--eval-analysis",
            str(eval_analysis_path),
            "--interview-report",
            str(interview_report_path),
            "--output-json",
            str(output_json_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(output_json_path.read_text(encoding="utf-8"))
    assert summary["sources"] == ["eval_analysis.json", "interview-metrics.json"]
    assert summary["eval"]["totalCases"] == 3
    assert summary["eval"]["successRate"] == 100.0
    assert summary["eval"]["toolCorrectness"]["averageF1"] == 0.5
    assert summary["eval"]["gate"] == {
        "passed": False,
        "failedGates": ["averageToolF1"],
    }
    assert summary["eval"]["failureTaxonomy"] == [
        {"category": "tool_mismatch", "count": 1, "caseIds": ["TC002"]}
    ]
    assert summary["interview"]["reportSuccessRate"] == 50.0

    markdown = output_md_path.read_text(encoding="utf-8")
    assert "Gate 状态：fail" in markdown
    assert "失败分类：tool_mismatch 1 个 case（TC002）" in markdown
    assert "面试报告生成成功率 | 50.0%" in markdown


def test_evidence_report_handles_eval_analysis_missing_optional_fields(tmp_path):
    eval_analysis_path = tmp_path / "eval_analysis.json"
    output_json_path = tmp_path / "evidence_summary.json"
    output_md_path = tmp_path / "evidence_summary.md"

    eval_analysis_path.write_text(
        json.dumps(
            {
                "summary": {
                    "totalCases": 1,
                    "okCases": 1,
                    "errorCases": 0,
                    "passedCases": 1,
                    "failedCases": 0,
                },
                "cases": [
                    {
                        "id": "TC001",
                        "status": "ok",
                        "passed": True,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_evidence_report(
        [
            "--eval-analysis",
            str(eval_analysis_path),
            "--output-json",
            str(output_json_path),
            "--output-md",
            str(output_md_path),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(output_json_path.read_text(encoding="utf-8"))
    assert summary["eval"]["totalCases"] == 1
    assert summary["eval"]["gate"] == {"passed": False, "failedGates": []}
    assert summary["eval"]["failureTaxonomy"] == []
    markdown = output_md_path.read_text(encoding="utf-8")
    assert "Resume Agent 离线评测覆盖 1 条用例" in markdown


def test_evidence_report_keeps_legacy_eval_scores_input_compatible(tmp_path):
    eval_scores_path = tmp_path / "eval_scores.json"
    output_json_path = tmp_path / "evidence_summary.json"

    eval_scores_path.write_text(
        json.dumps(
            {
                "scored": [
                    {
                        "id": "TC001",
                        "status": "ok",
                        "elapsed_s": 1.0,
                        "fallback_triggered": False,
                        "case": {
                            "resume_file": "resume_junior.json",
                            "jd_file": "jd_backend.json",
                        },
                        "scores": {
                            "keyword_improvement": {
                                "skipped": False,
                                "delta": 0.2,
                            },
                            "tool_correctness": {
                                "score": 1.0,
                            },
                            "decision_rule": {
                                "skipped": False,
                                "score": 1.0,
                            },
                            "llm_judge": {
                                "skipped": True,
                                "reason": "disabled",
                            },
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_evidence_report(
        [
            "--eval-scores",
            str(eval_scores_path),
            "--output-json",
            str(output_json_path),
        ]
    )

    assert completed.returncode == 0, completed.stderr
    summary = json.loads(output_json_path.read_text(encoding="utf-8"))
    assert summary["sources"] == ["eval_scores.json"]
    assert summary["eval"]["successRate"] == 100.0
    assert summary["eval"]["toolCorrectness"]["averageF1"] == 1.0
