import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
SCORER = ROOT_DIR / "eval" / "score.py"


def run_scorer(input_path: Path, output_path: Path, extra_args: list[str] | None = None):
    return subprocess.run(
        [
            sys.executable,
            str(SCORER),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            *(extra_args or []),
        ],
        cwd=ROOT_DIR / "backend",
        text=True,
        capture_output=True,
        check=False,
    )


def test_scorer_disables_llm_judge_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    input_path = tmp_path / "eval_results.json"
    output_path = tmp_path / "eval_scores.json"
    input_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "id": "TC001",
                        "desc": "默认快速评分",
                        "status": "ok",
                        "agent_reply": "已完成优化。",
                        "tool_calls": [],
                        "resume_before": {},
                        "resume_after": {},
                        "case": {
                            "id": "TC001",
                            "desc": "默认快速评分",
                            "expected_tool_calls": [],
                        },
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_scorer(input_path, output_path)

    assert completed.returncode == 0, completed.stderr
    scored = json.loads(output_path.read_text(encoding="utf-8"))["scored"]
    assert scored[0]["scores"]["llm_judge"] == {
        "skipped": True,
        "reason": "disabled",
    }
