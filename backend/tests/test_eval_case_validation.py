import json
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT_DIR / "eval" / "validate_cases.py"


def write_fixture(fixtures_dir: Path, filename: str) -> None:
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    (fixtures_dir / filename).write_text("{}", encoding="utf-8")


def run_validator(cases_path: Path, fixtures_dir: Path):
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--cases",
            str(cases_path),
            "--fixtures-dir",
            str(fixtures_dir),
        ],
        cwd=ROOT_DIR / "backend",
        text=True,
        capture_output=True,
        check=False,
    )


def test_validator_accepts_valid_cases(tmp_path):
    fixtures_dir = tmp_path / "cases"
    write_fixture(fixtures_dir, "resume.json")
    write_fixture(fixtures_dir, "jd.json")
    cases_path = tmp_path / "test_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "desc": "合法用例",
                    "resume_file": "resume.json",
                    "jd_file": "jd.json",
                    "user_message": "请优化简历",
                    "expected_tool_calls": ["update_bullet"],
                    "must_contain_keywords": ["微服务"],
                    "forbidden_content": ["虚构"],
                    "expected_decision": "execute",
                    "forbidden_reply_substrings": ["是否确认"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_validator(cases_path, fixtures_dir)

    assert completed.returncode == 0, completed.stderr
    assert "校验通过: 1 条用例" in completed.stdout


def test_validator_rejects_duplicate_and_blank_case_ids(tmp_path):
    fixtures_dir = tmp_path / "cases"
    write_fixture(fixtures_dir, "resume.json")
    cases_path = tmp_path / "test_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "resume_file": "resume.json",
                    "jd_file": None,
                    "user_message": "请优化简历",
                },
                {
                    "id": "TC001",
                    "resume_file": "resume.json",
                    "jd_file": None,
                    "user_message": "请优化简历",
                },
                {
                    "id": "",
                    "resume_file": "resume.json",
                    "jd_file": None,
                    "user_message": "请优化简历",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_validator(cases_path, fixtures_dir)

    assert completed.returncode == 1
    assert "[1].id duplicate: TC001 already used by [0].id" in completed.stdout
    assert "[2].id must be a non-empty string" in completed.stdout


def test_validator_rejects_missing_fixture_references(tmp_path):
    fixtures_dir = tmp_path / "cases"
    write_fixture(fixtures_dir, "resume.json")
    cases_path = tmp_path / "test_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "resume_file": "missing_resume.json",
                    "jd_file": "missing_jd.json",
                    "user_message": "请优化简历",
                },
                {
                    "id": "TC002",
                    "resume_file": "resume.json",
                    "jd_file": None,
                    "user_message": "没有 JD 也合法",
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_validator(cases_path, fixtures_dir)

    assert completed.returncode == 1
    assert "[0].resume_file fixture not found: missing_resume.json" in completed.stdout
    assert "[0].jd_file fixture not found: missing_jd.json" in completed.stdout
    assert "[1].jd_file" not in completed.stdout


def test_validator_rejects_expectation_field_type_errors(tmp_path):
    fixtures_dir = tmp_path / "cases"
    write_fixture(fixtures_dir, "resume.json")
    cases_path = tmp_path / "test_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "resume_file": "resume.json",
                    "jd_file": None,
                    "user_message": "请优化简历",
                    "must_contain_keywords": "微服务",
                    "forbidden_content": ["虚构", 123],
                    "expected_tool_calls": [None],
                    "required_reply_substrings_any": "目标岗位",
                    "forbidden_reply_substrings": ["是否确认", False],
                    "max_question_marks": "1",
                    "expect_refusal": "yes",
                    "expect_moderate_refusal": 0,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_validator(cases_path, fixtures_dir)

    assert completed.returncode == 1
    assert "[0].must_contain_keywords must be a list of strings" in completed.stdout
    assert "[0].forbidden_content[1] must be a string" in completed.stdout
    assert "[0].expected_tool_calls[0] must be a string" in completed.stdout
    assert (
        "[0].required_reply_substrings_any must be a list of strings"
        in completed.stdout
    )
    assert "[0].forbidden_reply_substrings[1] must be a string" in completed.stdout
    assert "[0].max_question_marks must be an integer" in completed.stdout
    assert "[0].expect_refusal must be a boolean" in completed.stdout
    assert "[0].expect_moderate_refusal must be a boolean" in completed.stdout


def test_validator_rejects_invalid_expected_decision_enum(tmp_path):
    fixtures_dir = tmp_path / "cases"
    write_fixture(fixtures_dir, "resume.json")
    cases_path = tmp_path / "test_cases.json"
    cases_path.write_text(
        json.dumps(
            [
                {
                    "id": "TC001",
                    "resume_file": "resume.json",
                    "jd_file": None,
                    "user_message": "请优化简历",
                    "expected_decision": "ask_user",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    completed = run_validator(cases_path, fixtures_dir)

    assert completed.returncode == 1
    assert (
        "[0].expected_decision must be one of: clarify, execute"
        in completed.stdout
    )
