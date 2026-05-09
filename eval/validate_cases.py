"""Validate eval test case definitions.

Usage:
    cd backend
    uv run python ../eval/validate_cases.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

EVAL_DIR = Path(__file__).resolve().parent
DECISION_VALUES = ("clarify", "execute")
STRING_LIST_FIELDS = (
    "must_contain_keywords",
    "forbidden_content",
    "expected_tool_calls",
    "required_reply_substrings_any",
    "forbidden_reply_substrings",
)
BOOLEAN_FIELDS = ("expect_refusal", "expect_moderate_refusal")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def validate_string_list(
    case: dict[str, Any],
    index: int,
    field: str,
) -> list[str]:
    if field not in case:
        return []

    value = case[field]
    if not isinstance(value, list):
        return [f"[{index}].{field} must be a list of strings"]

    errors = []
    for item_index, item in enumerate(value):
        if not isinstance(item, str):
            errors.append(f"[{index}].{field}[{item_index}] must be a string")
    return errors


def validate_cases(cases: Any, fixtures_dir: Path) -> list[str]:
    if not isinstance(cases, list):
        return ["root must be a list of case objects"]

    errors: list[str] = []
    seen_ids: dict[str, int] = {}
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"[{index}] must be an object")
            continue

        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id.strip():
            errors.append(f"[{index}].id must be a non-empty string")
        elif case_id in seen_ids:
            errors.append(
                f"[{index}].id duplicate: {case_id} already used by "
                f"[{seen_ids[case_id]}].id"
            )
        else:
            seen_ids[case_id] = index

        resume_file = case.get("resume_file")
        if isinstance(resume_file, str) and resume_file:
            if not (fixtures_dir / resume_file).is_file():
                errors.append(f"[{index}].resume_file fixture not found: {resume_file}")

        jd_file = case.get("jd_file")
        if isinstance(jd_file, str) and jd_file:
            if not (fixtures_dir / jd_file).is_file():
                errors.append(f"[{index}].jd_file fixture not found: {jd_file}")

        for field in STRING_LIST_FIELDS:
            errors.extend(validate_string_list(case, index, field))

        for field in BOOLEAN_FIELDS:
            if field in case and not isinstance(case[field], bool):
                errors.append(f"[{index}].{field} must be a boolean")

        if "max_question_marks" in case and not isinstance(
            case["max_question_marks"], int
        ):
            errors.append(f"[{index}].max_question_marks must be an integer")

        expected_decision = case.get("expected_decision")
        if expected_decision is not None and expected_decision not in DECISION_VALUES:
            allowed = ", ".join(DECISION_VALUES)
            errors.append(f"[{index}].expected_decision must be one of: {allowed}")

    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate eval case schema")
    parser.add_argument(
        "--cases",
        default=str(EVAL_DIR / "test_cases.json"),
        help="eval test cases JSON path",
    )
    parser.add_argument(
        "--fixtures-dir",
        default=str(EVAL_DIR / "cases"),
        help="directory containing resume/JD fixtures",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cases = load_json(Path(args.cases))
    errors = validate_cases(cases, Path(args.fixtures_dir))
    if errors:
        print(f"校验失败: {len(errors)} 个问题")
        for error in errors:
            print(f"- {error}")
        return 1
    print(f"校验通过: {len(cases)} 条用例")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
