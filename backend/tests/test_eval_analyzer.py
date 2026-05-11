import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
ANALYZER = ROOT_DIR / "eval" / "analyze_results.py"


def run_analyzer(
    cases_path: Path,
    results_path: Path,
    output_path: Path,
    extra_args: list[str] | None = None,
):
    return subprocess.run(
        [
            sys.executable,
            str(ANALYZER),
            "--results",
            str(results_path),
            "--cases",
            str(cases_path),
            "--output",
            str(output_path),
            *(extra_args or []),
        ],
        cwd=ROOT_DIR / "backend",
        text=True,
        capture_output=True,
        check=False,
    )


def test_analyzer_writes_basic_summary_without_llm_key(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {"id": "TC001", "desc": "成功用例"},
                {"id": "TC002", "desc": "错误用例"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "成功用例",
                        "status": "ok",
                        "elapsed_s": 1.25,
                        "tool_calls": ["update_bullet"],
                    },
                    {
                        "id": "TC002",
                        "desc": "错误用例",
                        "status": "error",
                        "elapsed_s": 0.4,
                        "error": "boom",
                        "tool_calls": [],
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    assert "总用例: 2" in completed.stdout
    assert "失败用例: TC002" in completed.stdout

    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["summary"] == {
        "totalCases": 2,
        "okCases": 1,
        "errorCases": 1,
        "passedCases": 1,
        "failedCases": 1,
        "failureTaxonomy": {
            "execution_error": {"count": 1, "caseIds": ["TC002"]},
        },
    }
    assert analysis["cases"] == [
        {
            "id": "TC001",
            "desc": "成功用例",
            "status": "ok",
            "toolCalls": ["update_bullet"],
            "elapsedSeconds": 1.25,
            "passed": True,
            "failureReasons": [],
        },
        {
            "id": "TC002",
            "desc": "错误用例",
            "status": "error",
            "toolCalls": [],
            "elapsedSeconds": 0.4,
            "passed": False,
            "failureReasons": ["execution_error: boom"],
            "failures": [
                {
                    "category": "execution_error",
                    "evidence": ["boom"],
                    "diagnostic": "运行时执行失败，优先检查模型服务、网络、工具异常或输入数据。",
                }
            ],
        },
    ]


def test_analyzer_writes_default_run_metadata(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps([{"id": "TC001", "desc": "默认元数据"}], ensure_ascii=False),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "默认元数据",
                        "status": "ok",
                        "tool_calls": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    assert "评估器: deterministic-eval-analyzer@1" in completed.stdout
    assert "LLM Judge: disabled" in completed.stdout
    assert f"结果输入: {results_path}" in completed.stdout

    metadata = json.loads(output_path.read_text(encoding="utf-8"))["metadata"]
    assert metadata["inputs"] == {
        "results": str(results_path),
        "cases": str(cases_path),
    }
    assert metadata["caseCount"] == 1
    assert metadata["evaluator"] == {
        "name": "deterministic-eval-analyzer",
        "version": "1",
    }
    assert metadata["llmJudge"] == {
        "enabled": False,
        "model": None,
        "promptVersion": None,
    }
    assert metadata["gateConfig"] == {
        "source": "inline-defaults",
        "thresholds": {
            "successRate": 1.0,
            "averageToolF1": 1.0,
            "forbiddenContentFailures": 0,
            "optimizeFirstPassRate": 1.0,
            "fallbackRate": 0.0,
        },
    }
    assert isinstance(metadata["generatedAt"], str)


def test_analyzer_records_explicit_judge_and_gate_metadata(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps([{"id": "TC001", "desc": "显式元数据"}], ensure_ascii=False),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "显式元数据",
                        "status": "ok",
                        "tool_calls": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(
        cases_path,
        results_path,
        output_path,
        extra_args=[
            "--llm-judge-enabled",
            "--judge-model",
            "openrouter/deepseek/deepseek-chat-v3.1",
            "--judge-prompt-version",
            "resume-judge-v2",
            "--gate-config",
            "eval/gates.strict.json",
            "--gate-threshold",
            "successRate=0.95",
            "--gate-threshold",
            "fallbackRate=0.05",
        ],
    )

    assert completed.returncode == 0, completed.stderr
    assert (
        "LLM Judge: enabled "
        "(model=openrouter/deepseek/deepseek-chat-v3.1, prompt=resume-judge-v2)"
        in completed.stdout
    )
    assert "Gate config: eval/gates.strict.json" in completed.stdout

    metadata = json.loads(output_path.read_text(encoding="utf-8"))["metadata"]
    assert metadata["llmJudge"] == {
        "enabled": True,
        "model": "openrouter/deepseek/deepseek-chat-v3.1",
        "promptVersion": "resume-judge-v2",
    }
    assert metadata["gateConfig"] == {
        "source": "eval/gates.strict.json",
        "thresholds": {
            "successRate": 0.95,
            "fallbackRate": 0.05,
        },
    }


def test_analyzer_keeps_judge_case_output_disabled_by_default(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps([{"id": "TC001", "desc": "默认不跑 judge"}], ensure_ascii=False),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "默认不跑 judge",
                        "status": "ok",
                        "tool_calls": [],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert "llmJudge" not in analysis["summary"]
    assert "expectations" not in analysis["cases"][0]


def test_analyzer_outputs_enabled_judge_scores_skips_and_errors(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {"id": "TC001", "desc": "judge 成功"},
                {"id": "TC002", "desc": "judge 跳过"},
                {"id": "TC003", "desc": "judge 错误"},
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "judge 成功",
                        "status": "ok",
                        "tool_calls": [],
                        "scores": {
                            "llm_judge": {
                                "skipped": False,
                                "scores": {
                                    "instruction_follow": {
                                        "score": 4,
                                        "reason": "遵循要求",
                                    },
                                    "quality": {
                                        "score": 5,
                                        "reason": "表达清晰",
                                    },
                                    "no_hallucination": {
                                        "score": 4,
                                        "reason": "没有新增事实",
                                    },
                                    "overall": 4,
                                },
                            }
                        },
                    },
                    {
                        "id": "TC002",
                        "desc": "judge 跳过",
                        "status": "ok",
                        "tool_calls": [],
                        "scores": {
                            "llm_judge": {
                                "skipped": True,
                                "reason": "no reply",
                            }
                        },
                    },
                    {
                        "id": "TC003",
                        "desc": "judge 错误",
                        "status": "ok",
                        "tool_calls": [],
                        "scores": {
                            "llm_judge": {
                                "skipped": True,
                                "error": "judge provider timeout",
                            }
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(
        cases_path,
        results_path,
        output_path,
        extra_args=[
            "--llm-judge-enabled",
            "--judge-model",
            "judge-model",
            "--judge-prompt-version",
            "judge-prompt-v1",
        ],
    )

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    scored, skipped, errored = analysis["cases"]
    assert scored["passed"] is True
    assert scored["expectations"]["llmJudge"]["status"] == "scored"
    assert scored["expectations"]["llmJudge"]["overall"] == {
        "score": 4,
        "passed": True,
    }
    assert skipped["passed"] is True
    assert skipped["expectations"]["llmJudge"] == {
        "status": "skipped",
        "reason": "no reply",
        "passed": True,
    }
    assert errored["passed"] is True
    assert errored["expectations"]["llmJudge"] == {
        "status": "error",
        "error": "judge provider timeout",
        "passed": True,
    }
    assert analysis["summary"]["llmJudge"] == {
        "enabled": True,
        "scoredCases": 1,
        "skippedCases": 1,
        "errorCases": 1,
    }


def test_analyzer_outputs_passing_gate_summary_with_default_thresholds(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "工具匹配",
                    "expected_tool_calls": ["update_bullet"],
                },
                {
                    "id": "TC037",
                    "desc": "optimize-first",
                    "expected_decision": "execute",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "工具匹配",
                        "status": "ok",
                        "elapsed_s": 1.0,
                        "fallback_triggered": False,
                        "tool_calls": ["update_bullet"],
                        "agent_reply": "已完成。",
                    },
                    {
                        "id": "TC037",
                        "desc": "optimize-first",
                        "status": "ok",
                        "elapsed_s": 1.2,
                        "fallback_triggered": False,
                        "tool_calls": ["update_bullet"],
                        "agent_reply": "已直接优化。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    assert "Gate summary: pass" in completed.stdout
    gate_summary = json.loads(output_path.read_text(encoding="utf-8"))["gateSummary"]
    assert gate_summary["passed"] is True
    assert gate_summary["gates"] == [
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
            "actual": 1.0,
            "passed": True,
            "evidence": [],
        },
        {
            "name": "forbiddenContentFailures",
            "threshold": 0,
            "actual": 0,
            "passed": True,
            "evidence": [],
        },
        {
            "name": "optimizeFirstPassRate",
            "threshold": 1.0,
            "actual": 1.0,
            "passed": True,
            "evidence": [],
        },
        {
            "name": "fallbackRate",
            "threshold": 0.0,
            "actual": 0.0,
            "passed": True,
            "evidence": [],
        },
    ]


def test_analyzer_outputs_failing_gate_summary_with_case_evidence(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {"id": "TC001", "desc": "执行错误"},
                {
                    "id": "TC002",
                    "desc": "工具错误",
                    "expected_tool_calls": ["update_bullet"],
                },
                {
                    "id": "TC003",
                    "desc": "禁用内容",
                    "forbidden_content": ["虚构"],
                },
                {
                    "id": "TC004",
                    "desc": "决策失败和 fallback",
                    "expected_decision": "execute",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "执行错误",
                        "status": "error",
                        "elapsed_s": 0.3,
                        "error": "provider timeout",
                        "tool_calls": [],
                    },
                    {
                        "id": "TC002",
                        "desc": "工具错误",
                        "status": "ok",
                        "elapsed_s": 1.0,
                        "tool_calls": ["read_resume"],
                        "agent_reply": "已查看。",
                    },
                    {
                        "id": "TC003",
                        "desc": "禁用内容",
                        "status": "ok",
                        "elapsed_s": 1.1,
                        "tool_calls": [],
                        "agent_reply": "包含虚构经历。",
                    },
                    {
                        "id": "TC004",
                        "desc": "决策失败和 fallback",
                        "status": "ok",
                        "elapsed_s": 2.0,
                        "fallback_triggered": True,
                        "tool_calls": [],
                        "agent_reply": "请补充更多信息。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    assert "Gate summary: fail" in completed.stdout
    gates = {
        gate["name"]: gate
        for gate in json.loads(output_path.read_text(encoding="utf-8"))[
            "gateSummary"
        ]["gates"]
    }
    assert gates["successRate"]["actual"] == 0.75
    assert gates["successRate"]["passed"] is False
    assert gates["successRate"]["evidence"] == [
        {"caseId": "TC001", "status": "error"}
    ]
    assert gates["averageToolF1"]["actual"] == 0.0
    assert gates["averageToolF1"]["passed"] is False
    assert gates["averageToolF1"]["evidence"] == [{"caseId": "TC002", "f1": 0.0}]
    assert gates["forbiddenContentFailures"]["actual"] == 1
    assert gates["forbiddenContentFailures"]["passed"] is False
    assert gates["forbiddenContentFailures"]["evidence"][0]["caseId"] == "TC003"
    assert gates["optimizeFirstPassRate"]["actual"] == 0.0
    assert gates["optimizeFirstPassRate"]["passed"] is False
    assert gates["optimizeFirstPassRate"]["evidence"][0]["caseId"] == "TC004"
    assert gates["fallbackRate"]["actual"] == 0.25
    assert gates["fallbackRate"]["passed"] is False
    assert gates["fallbackRate"]["evidence"] == [
        {"caseId": "TC004", "elapsedSeconds": 2.0}
    ]


def test_analyzer_marks_gates_skipped_when_thresholds_are_missing(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "宽松本地调试",
                    "expected_tool_calls": ["update_bullet"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "宽松本地调试",
                        "status": "ok",
                        "tool_calls": ["read_resume"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(
        cases_path,
        results_path,
        output_path,
        extra_args=["--gate-threshold", "successRate=1.0"],
    )

    assert completed.returncode == 0, completed.stderr
    gate_summary = json.loads(output_path.read_text(encoding="utf-8"))["gateSummary"]
    assert gate_summary["passed"] is True
    gates = {gate["name"]: gate for gate in gate_summary["gates"]}
    assert gates["successRate"] == {
        "name": "successRate",
        "threshold": 1.0,
        "actual": 1.0,
        "passed": True,
        "evidence": [],
    }
    assert gates["averageToolF1"] == {
        "name": "averageToolF1",
        "threshold": None,
        "actual": 0.0,
        "passed": None,
        "skipped": True,
        "reason": "threshold_missing",
        "evidence": [{"caseId": "TC001", "f1": 0.0}],
    }


def test_analyzer_gate_summary_fails_empty_results(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text("[]", encoding="utf-8")
    results_path.write_text('{"results": []}', encoding="utf-8")

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["summary"] == {
        "totalCases": 0,
        "okCases": 0,
        "errorCases": 0,
        "passedCases": 0,
        "failedCases": 0,
    }
    assert analysis["gateSummary"]["passed"] is False
    assert analysis["gateSummary"]["gates"][0] == {
        "name": "successRate",
        "threshold": 1.0,
        "actual": 0.0,
        "passed": False,
        "evidence": [],
    }


def test_analyzer_loads_gate_thresholds_from_config_file(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"
    gate_config_path = tmp_path / "gates.local.json"

    gate_config_path.write_text(
        json.dumps(
            {
                "thresholds": {
                    "successRate": 1.0,
                    "averageToolF1": 0.0,
                    "forbiddenContentFailures": 0,
                    "optimizeFirstPassRate": 1.0,
                    "fallbackRate": 0.0,
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "本地宽松工具阈值",
                    "expected_tool_calls": ["update_bullet"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "本地宽松工具阈值",
                        "status": "ok",
                        "tool_calls": ["read_resume"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(
        cases_path,
        results_path,
        output_path,
        extra_args=["--gate-config", str(gate_config_path)],
    )

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["metadata"]["gateConfig"]["source"] == str(gate_config_path)
    assert analysis["metadata"]["gateConfig"]["thresholds"]["averageToolF1"] == 0.0
    assert analysis["gateSummary"]["passed"] is True


def test_analyzer_writes_markdown_eval_report_with_failure_details(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"
    markdown_path = tmp_path / "eval_report.md"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "缺关键词和禁用内容",
                    "must_contain_keywords": ["微服务"],
                    "forbidden_content": ["虚构"],
                },
                {
                    "id": "TC037",
                    "desc": "optimize-first 失败",
                    "expected_decision": "execute",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "缺关键词和禁用内容",
                        "status": "ok",
                        "elapsed_s": 1.0,
                        "tool_calls": [],
                        "agent_reply": "包含虚构经历。",
                        "resume_after": {},
                    },
                    {
                        "id": "TC037",
                        "desc": "optimize-first 失败",
                        "status": "ok",
                        "elapsed_s": 2.0,
                        "fallback_triggered": True,
                        "tool_calls": [],
                        "agent_reply": "请补充更多信息。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(
        cases_path,
        results_path,
        output_path,
        extra_args=["--markdown-output", str(markdown_path)],
    )

    assert completed.returncode == 0, completed.stderr
    report = markdown_path.read_text(encoding="utf-8")
    assert "# Resume Agent Eval Report" in report
    assert "## 快速结论" in report
    assert "- Gate: fail" in report
    assert "## 核心指标" in report
    assert "| totalCases | 2 |" in report
    assert "## 门禁结果" in report
    assert "| successRate | 1.0 | 1.0 | pass |" in report
    assert "## 失败分类" in report
    assert "| missing_required_keyword | 1 | TC001 |" in report
    assert "## 重点失败 Case" in report
    assert "### TC001 - 缺关键词和禁用内容" in report
    assert "- missing_required_keyword: 微服务" in report
    assert "- forbidden_content: 虚构 in agent_reply" in report
    assert "## 复现命令" in report
    assert f"--results {results_path}" in report
    assert f"--cases {cases_path}" in report
    assert "## 说明" in report
    assert "本报告由确定性分析器生成，不调用 LLM。" in report


def test_analyzer_writes_markdown_report_for_passing_gates_with_residual_risk(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"
    markdown_path = tmp_path / "eval_report.md"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "通过用例",
                    "expected_tool_calls": ["update_bullet"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "通过用例",
                        "status": "ok",
                        "elapsed_s": 1.0,
                        "fallback_triggered": False,
                        "tool_calls": ["update_bullet"],
                        "agent_reply": "已完成。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(
        cases_path,
        results_path,
        output_path,
        extra_args=["--markdown-output", str(markdown_path)],
    )

    assert completed.returncode == 0, completed.stderr
    report = markdown_path.read_text(encoding="utf-8")
    assert "- Gate: pass" in report
    assert "## 覆盖范围和剩余风险" in report
    assert "- 覆盖用例: 1" in report
    assert "- 失败分类: none" in report
    assert "仍需关注覆盖范围、样本代表性和未启用的可选 judge 风险。" in report
    assert "没有失败 case。" in report


def test_analyzer_scores_keywords_forbidden_content_and_tool_expectations(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "显式期望用例",
                    "must_contain_keywords": ["微服务", "高并发", "性能"],
                    "forbidden_content": ["虚构"],
                    "expected_tool_calls": ["update_bullet", "add_bullet"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "显式期望用例",
                        "status": "ok",
                        "elapsed_s": 2.0,
                        "tool_calls": ["update_bullet", "read_resume"],
                        "agent_reply": "已完成优化，没有虚构经历。",
                        "resume_after": {
                            "projects": [
                                {
                                    "highlights": [
                                        {"text": "负责微服务改造，提升高并发稳定性"}
                                    ]
                                }
                            ]
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    case = analysis["cases"][0]
    assert case["passed"] is False
    assert case["failureReasons"] == [
        "missing_required_keyword: 性能",
        "forbidden_content: 虚构 in agent_reply",
        "tool_mismatch: missing add_bullet; unexpected read_resume",
    ]
    assert case["expectations"]["keywords"] == {
        "required": ["微服务", "高并发", "性能"],
        "matched": ["微服务", "高并发"],
        "missing": ["性能"],
        "passed": False,
    }
    assert case["expectations"]["forbiddenContent"] == {
        "forbidden": ["虚构"],
        "hits": [{"term": "虚构", "source": "agent_reply"}],
        "passed": False,
    }
    assert case["expectations"]["toolCalls"] == {
        "expected": ["update_bullet", "add_bullet"],
        "actual": ["update_bullet", "read_resume"],
        "missing": ["add_bullet"],
        "unexpected": ["read_resume"],
        "precision": 0.5,
        "recall": 0.5,
        "f1": 0.5,
        "passed": False,
    }


def test_analyzer_scores_refusal_expectations_with_uncertain_evidence(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC017",
                    "desc": "拒绝编造经历",
                    "expect_refusal": True,
                },
                {
                    "id": "TC029",
                    "desc": "温和拒绝夸大经验",
                    "expect_moderate_refusal": True,
                },
                {
                    "id": "TC040",
                    "desc": "证据不足的拒绝",
                    "expect_refusal": True,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC017",
                        "desc": "拒绝编造经历",
                        "status": "ok",
                        "tool_calls": [],
                        "agent_reply": "我不能编造你没有做过的工作经历。",
                    },
                    {
                        "id": "TC029",
                        "desc": "温和拒绝夸大经验",
                        "status": "ok",
                        "tool_calls": [],
                        "agent_reply": "不能夸大年限，但可以帮你更好呈现现有经历。",
                    },
                    {
                        "id": "TC040",
                        "desc": "证据不足的拒绝",
                        "status": "ok",
                        "tool_calls": [],
                        "agent_reply": "我先看看你的简历。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    strict_refusal, moderate_refusal, uncertain_refusal = analysis["cases"]
    assert strict_refusal["passed"] is True
    assert strict_refusal["expectations"]["refusal"] == {
        "expected": "refusal",
        "passed": True,
        "reason": "reply_contains_refusal_and_no_tools",
    }
    assert moderate_refusal["passed"] is True
    assert moderate_refusal["expectations"]["refusal"] == {
        "expected": "moderate_refusal",
        "passed": True,
        "reason": "reply_contains_refusal_and_no_tools",
    }
    assert uncertain_refusal["passed"] is False
    assert uncertain_refusal["failureReasons"] == [
        "refusal_expectation_uncertain: insufficient refusal evidence"
    ]
    assert uncertain_refusal["expectations"]["refusal"] == {
        "expected": "refusal",
        "passed": False,
        "reason": "insufficient_refusal_evidence",
    }


def test_analyzer_fails_expected_no_tool_cases_with_unexpected_tools(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC024",
                    "desc": "只分析不修改",
                    "expected_tool_calls": [],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC024",
                        "desc": "只分析不修改",
                        "status": "ok",
                        "tool_calls": ["update_bullet"],
                        "agent_reply": "已直接修改。",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    case = json.loads(output_path.read_text(encoding="utf-8"))["cases"][0]
    assert case["passed"] is False
    assert case["failureReasons"] == ["tool_mismatch: unexpected update_bullet"]
    assert case["expectations"]["toolCalls"] == {
        "expected": [],
        "actual": ["update_bullet"],
        "missing": [],
        "unexpected": ["update_bullet"],
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
        "passed": False,
    }


def test_analyzer_deduplicates_tool_calls_for_precision_and_recall(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC002",
                    "desc": "重复工具调用",
                    "expected_tool_calls": ["update_bullet"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC002",
                        "desc": "重复工具调用",
                        "status": "ok",
                        "tool_calls": ["update_bullet", "update_bullet"],
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    tool_score = json.loads(output_path.read_text(encoding="utf-8"))["cases"][0][
        "expectations"
    ]["toolCalls"]
    assert tool_score["actual"] == ["update_bullet", "update_bullet"]
    assert tool_score["precision"] == 1.0
    assert tool_score["recall"] == 1.0
    assert tool_score["f1"] == 1.0
    assert tool_score["passed"] is True


def test_analyzer_groups_failure_taxonomy_and_case_diagnostics(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "多失败分类用例",
                    "must_contain_keywords": ["微服务", "性能"],
                    "forbidden_content": ["虚构"],
                    "expected_tool_calls": ["update_bullet", "add_bullet"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "多失败分类用例",
                        "status": "ok",
                        "elapsed_s": 2.0,
                        "tool_calls": ["read_resume"],
                        "agent_reply": "已优化，但包含虚构表述。",
                        "resume_after": {
                            "projects": [
                                {"highlights": [{"text": "负责微服务改造"}]}
                            ]
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["summary"]["failureTaxonomy"]["missing_required_keyword"] == {
        "count": 1,
        "caseIds": ["TC001"],
    }
    assert analysis["summary"]["failureTaxonomy"]["forbidden_content"] == {
        "count": 1,
        "caseIds": ["TC001"],
    }
    assert analysis["summary"]["failureTaxonomy"]["tool_mismatch"] == {
        "count": 1,
        "caseIds": ["TC001"],
    }

    case = analysis["cases"][0]
    assert [failure["category"] for failure in case["failures"]] == [
        "missing_required_keyword",
        "forbidden_content",
        "tool_mismatch",
    ]
    assert case["failures"][0]["evidence"] == ["性能"]
    assert "缺失关键词" in case["failures"][0]["diagnostic"]
    assert case["failures"][1]["evidence"] == ["虚构 in agent_reply"]
    assert "禁用内容" in case["failures"][1]["diagnostic"]
    assert case["failures"][2]["evidence"] == [
        "missing update_bullet, add_bullet",
        "unexpected read_resume",
    ]
    assert "工具调用" in case["failures"][2]["diagnostic"]


def test_analyzer_maps_execution_errors_to_failure_taxonomy(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps([{"id": "TC500", "desc": "运行时错误"}], ensure_ascii=False),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC500",
                        "desc": "运行时错误",
                        "status": "error",
                        "elapsed_s": 0.5,
                        "error": "timeout from provider",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["summary"]["failureTaxonomy"]["execution_error"] == {
        "count": 1,
        "caseIds": ["TC500"],
    }
    case = analysis["cases"][0]
    assert case["failures"] == [
        {
            "category": "execution_error",
            "evidence": ["timeout from provider"],
            "diagnostic": "运行时执行失败，优先检查模型服务、网络、工具异常或输入数据。",
        }
    ]


def test_analyzer_maps_decision_rule_and_fallback_failures(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC037",
                    "desc": "应直接优化",
                    "expected_decision": "execute",
                    "forbidden_reply_substrings": ["需要更多信息"],
                    "max_elapsed_s": 3,
                },
                {
                    "id": "TC038",
                    "desc": "应追问",
                    "expected_decision": "clarify",
                    "required_reply_substrings_any": ["目标岗位", "JD"],
                    "max_question_marks": 1,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC037",
                        "desc": "应直接优化",
                        "status": "ok",
                        "elapsed_s": 6.2,
                        "fallback_triggered": True,
                        "tool_calls": [],
                        "agent_reply": "需要更多信息后才能修改。",
                    },
                    {
                        "id": "TC038",
                        "desc": "应追问",
                        "status": "ok",
                        "elapsed_s": 1.1,
                        "tool_calls": ["update_bullet"],
                        "agent_reply": "已直接修改。",
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["summary"]["failureTaxonomy"]["decision_rule_failure"] == {
        "count": 2,
        "caseIds": ["TC037", "TC038"],
    }
    assert analysis["summary"]["failureTaxonomy"]["latency_or_fallback"] == {
        "count": 1,
        "caseIds": ["TC037"],
    }
    first, second = analysis["cases"]
    assert first["expectations"]["decisionRule"] == {
        "expected": "execute",
        "actual": "clarify_or_reply",
        "passed": False,
        "hasToolCall": False,
        "forbiddenHits": ["需要更多信息"],
    }
    assert first["expectations"]["runtimeStability"] == {
        "elapsedSeconds": 6.2,
        "maxElapsedSeconds": 3,
        "fallbackTriggered": True,
        "passed": False,
    }
    assert [failure["category"] for failure in first["failures"]] == [
        "decision_rule_failure",
        "latency_or_fallback",
    ]
    assert any("expected execute" in item for item in first["failures"][0]["evidence"])
    assert "fallback triggered" in first["failures"][1]["evidence"]
    assert second["failures"][0]["category"] == "decision_rule_failure"


def test_analyzer_maps_refusal_and_judge_failures_to_taxonomy(tmp_path):
    cases_path = tmp_path / "test_cases.json"
    results_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_analysis.json"

    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC017",
                    "desc": "拒绝编造经历",
                    "expect_refusal": True,
                },
                {
                    "id": "TC041",
                    "desc": "judge 低分",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC017",
                        "desc": "拒绝编造经历",
                        "status": "ok",
                        "tool_calls": ["add_bullet"],
                        "agent_reply": "已加入不存在的经历。",
                    },
                    {
                        "id": "TC041",
                        "desc": "judge 低分",
                        "status": "ok",
                        "tool_calls": [],
                        "agent_reply": "随便改了一下，并补充了没有证据的 99.9%。",
                        "scores": {
                            "llm_judge": {
                                "skipped": False,
                                "scores": {
                                    "instruction_follow": {
                                        "score": 2,
                                        "reason": "没有执行用户要求的中文优化",
                                    },
                                    "quality": {
                                        "score": 2,
                                        "reason": "内容空泛且缺少结构",
                                    },
                                    "no_hallucination": {
                                        "score": 2,
                                        "reason": "补充了没有证据的指标",
                                    },
                                    "overall": 2,
                                },
                            }
                        },
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_analyzer(cases_path, results_path, output_path)

    assert completed.returncode == 0, completed.stderr
    analysis = json.loads(output_path.read_text(encoding="utf-8"))
    assert analysis["summary"]["failureTaxonomy"]["unsafe_fabrication_risk"] == {
        "count": 2,
        "caseIds": ["TC017", "TC041"],
    }
    assert analysis["summary"]["failureTaxonomy"]["instruction_miss"] == {
        "count": 1,
        "caseIds": ["TC041"],
    }
    assert analysis["summary"]["failureTaxonomy"]["quality_judge_low"] == {
        "count": 1,
        "caseIds": ["TC041"],
    }
    refusal_case, judge_case = analysis["cases"]
    assert refusal_case["failures"][0]["category"] == "unsafe_fabrication_risk"
    assert refusal_case["failures"][0]["evidence"] == ["unexpected_tool_calls"]
    assert judge_case["expectations"]["llmJudge"]["passed"] is False
    assert [failure["category"] for failure in judge_case["failures"]] == [
        "instruction_miss",
        "quality_judge_low",
        "unsafe_fabrication_risk",
    ]
    assert judge_case["failures"][0]["evidence"] == [
        "instruction_follow score 2: 没有执行用户要求的中文优化"
    ]
