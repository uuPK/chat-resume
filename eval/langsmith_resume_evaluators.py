"""用于提供 langsmith_resume_evaluators.py 评测辅助逻辑。"""

from __future__ import annotations

from typing import Any


TOOL_NAME_ALIASES = {
    "优化简介": "update_overview",
    "优化成果": "update_bullet",
    "优化要点": "update_bullet",
    "新增成果": "add_bullet",
    "新增要点": "add_bullet",
    "删除成果": "remove_bullet",
    "删除要点": "remove_bullet",
    "读取简历": "read_resume",
}


def _collect_text(value: Any) -> str:
    """用于收集text。"""
    parts: list[str] = []

    def collect(item: Any) -> None:
        """用于收集当前数据。"""
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


def _strings(value: Any) -> list[str]:
    """用于处理strings。"""
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _unique(values: list[str]) -> list[str]:
    """用于处理unique。"""
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _tool_calls(outputs: dict[str, Any]) -> list[str]:
    """用于处理toolcalls。"""
    raw_tool_calls = outputs.get("tool_calls")
    if raw_tool_calls is None:
        raw_tool_calls = outputs.get("toolCalls")
    normalized = []
    for item in raw_tool_calls or []:
        if isinstance(item, dict):
            name = item.get("name") or item.get("tool") or item.get("tool_name")
        else:
            name = item
        normalized.append(TOOL_NAME_ALIASES.get(str(name), str(name)))
    return _unique(normalized)


def resume_agent_regression_checks(outputs, reference_outputs):
    """用于处理简历Agentregressionchecks。"""
    tool_name_aliases = {
        "优化简介": "update_overview",
        "优化成果": "update_bullet",
        "优化要点": "update_bullet",
        "新增成果": "add_bullet",
        "新增要点": "add_bullet",
        "删除成果": "remove_bullet",
        "删除要点": "remove_bullet",
        "读取简历": "read_resume",
    }

    def collect_text(value):
        """用于收集text。"""
        parts = []

        def collect(item):
            """用于收集当前数据。"""
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

    def strings(value):
        """用于处理strings。"""
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def unique(values):
        """用于处理unique。"""
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def tool_calls(value):
        """用于处理toolcalls。"""
        raw_tool_calls = value.get("tool_calls") or value.get("toolCalls") or []
        normalized = []
        for item in raw_tool_calls:
            if isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("tool_name")
            else:
                name = item
            normalized.append(tool_name_aliases.get(str(name), str(name)))
        return unique(normalized)

    actual_tools = tool_calls(outputs)
    expected_tools = unique(strings(reference_outputs.get("expected_tool_calls")))
    tool_hits = sum(1 for tool in actual_tools if tool in expected_tools)
    tool_precision = tool_hits / len(actual_tools) if actual_tools else 1.0
    tool_recall = tool_hits / len(expected_tools) if expected_tools else 1.0
    tool_f1 = (
        2 * tool_precision * tool_recall / (tool_precision + tool_recall)
        if tool_precision + tool_recall
        else 0.0
    )

    output_text = collect_text(outputs)
    forbidden_hits = [
        term
        for term in strings(reference_outputs.get("forbidden_content"))
        if term and term in output_text
    ]
    missing_keywords = [
        term
        for term in strings(reference_outputs.get("must_contain_keywords"))
        if term and term not in output_text
    ]

    expect_no_tools = bool(
        reference_outputs.get("expect_refusal")
        or reference_outputs.get("expect_moderate_refusal")
    )
    refusal_pass = not actual_tools if expect_no_tools else True

    max_question_marks = reference_outputs.get("max_question_marks")
    question_count = output_text.count("?") + output_text.count("？")
    if isinstance(max_question_marks, int):
        question_pass = question_count <= max_question_marks
    else:
        question_pass = True

    expected_decision = reference_outputs.get("expected_decision")
    actual_decision = outputs.get("decision")
    if expected_decision and actual_decision:
        decision_pass = str(actual_decision) == str(expected_decision)
    else:
        decision_pass = True

    return [
        {"key": "tool_f1", "score": round(tool_f1, 3)},
        {"key": "expected_tools_pass", "score": actual_tools == expected_tools},
        {"key": "forbidden_content_pass", "score": not forbidden_hits},
        {"key": "required_keywords_pass", "score": not missing_keywords},
        {"key": "refusal_policy_pass", "score": refusal_pass},
        {"key": "question_count_pass", "score": question_pass},
        {"key": "decision_pass", "score": decision_pass},
    ]


def resume_tool_f1(outputs, reference_outputs):
    """用于处理简历toolf1。"""
    tool_name_aliases = {
        "优化简介": "update_overview",
        "优化成果": "update_bullet",
        "优化要点": "update_bullet",
        "新增成果": "add_bullet",
        "新增要点": "add_bullet",
        "删除成果": "remove_bullet",
        "删除要点": "remove_bullet",
        "读取简历": "read_resume",
    }

    def unique(values):
        """用于处理unique。"""
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def strings(value):
        """用于处理strings。"""
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def tool_calls(value):
        """用于处理toolcalls。"""
        raw_tool_calls = value.get("tool_calls") or value.get("toolCalls") or []
        normalized = []
        for item in raw_tool_calls:
            if isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("tool_name")
            else:
                name = item
            normalized.append(tool_name_aliases.get(str(name), str(name)))
        return unique(normalized)

    actual_tools = tool_calls(outputs)
    expected_tools = unique(strings(reference_outputs.get("expected_tool_calls")))
    hit_count = sum(1 for tool in actual_tools if tool in expected_tools)
    precision = hit_count / len(actual_tools) if actual_tools else 1.0
    recall = hit_count / len(expected_tools) if expected_tools else 1.0
    score = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {"key": "resume_tool_f1", "score": round(score, 3)}


def resume_expected_tools_pass(outputs, reference_outputs):
    """用于处理简历expectedtoolspass。"""
    tool_name_aliases = {
        "优化简介": "update_overview",
        "优化成果": "update_bullet",
        "优化要点": "update_bullet",
        "新增成果": "add_bullet",
        "新增要点": "add_bullet",
        "删除成果": "remove_bullet",
        "删除要点": "remove_bullet",
        "读取简历": "read_resume",
    }

    def unique(values):
        """用于处理unique。"""
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    def strings(value):
        """用于处理strings。"""
        if not isinstance(value, list):
            return []
        return [str(item) for item in value]

    def tool_calls(value):
        """用于处理toolcalls。"""
        raw_tool_calls = value.get("tool_calls") or value.get("toolCalls") or []
        normalized = []
        for item in raw_tool_calls:
            if isinstance(item, dict):
                name = item.get("name") or item.get("tool") or item.get("tool_name")
            else:
                name = item
            normalized.append(tool_name_aliases.get(str(name), str(name)))
        return unique(normalized)

    actual_tools = tool_calls(outputs)
    expected_tools = unique(strings(reference_outputs.get("expected_tool_calls")))
    return {"key": "resume_expected_tools_pass", "score": actual_tools == expected_tools}


def resume_forbidden_content_pass(outputs, reference_outputs):
    """用于处理简历forbiddencontentpass。"""
    def collect_text(value):
        """用于收集text。"""
        parts = []

        def collect(item):
            """用于收集当前数据。"""
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

    forbidden = reference_outputs.get("forbidden_content")
    forbidden_terms = [str(item) for item in forbidden] if isinstance(forbidden, list) else []
    output_text = collect_text(outputs)
    passed = not any(term and term in output_text for term in forbidden_terms)
    return {"key": "resume_forbidden_content_pass", "score": passed}


def resume_required_keywords_pass(outputs, reference_outputs):
    """用于处理简历requiredkeywordspass。"""
    def collect_text(value):
        """用于收集text。"""
        parts = []

        def collect(item):
            """用于收集当前数据。"""
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

    required = reference_outputs.get("must_contain_keywords")
    keywords = [str(item) for item in required] if isinstance(required, list) else []
    output_text = collect_text(outputs)
    passed = all(keyword in output_text for keyword in keywords if keyword)
    return {"key": "resume_required_keywords_pass", "score": passed}


def resume_refusal_policy_pass(outputs, reference_outputs):
    """用于处理简历refusalpolicypass。"""
    def unique(values):
        """用于处理unique。"""
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

    raw_tool_calls = outputs.get("tool_calls") or outputs.get("toolCalls") or []
    actual_tools = unique([str(item.get("name") if isinstance(item, dict) else item) for item in raw_tool_calls])
    expects_refusal = bool(
        reference_outputs.get("expect_refusal")
        or reference_outputs.get("expect_moderate_refusal")
    )
    passed = not actual_tools if expects_refusal else True
    return {"key": "resume_refusal_policy_pass", "score": passed}


def resume_question_count_pass(outputs, reference_outputs):
    """用于处理简历questioncountpass。"""
    def collect_text(value):
        """用于收集text。"""
        parts = []

        def collect(item):
            """用于收集当前数据。"""
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

    max_question_marks = reference_outputs.get("max_question_marks")
    question_count = collect_text(outputs).count("?") + collect_text(outputs).count("？")
    if isinstance(max_question_marks, int):
        passed = question_count <= max_question_marks
    else:
        passed = True
    return {"key": "resume_question_count_pass", "score": passed}


def resume_decision_pass(outputs, reference_outputs):
    """用于处理简历decisionpass。"""
    expected_decision = reference_outputs.get("expected_decision")
    actual_decision = outputs.get("decision")
    if expected_decision and actual_decision:
        passed = str(actual_decision) == str(expected_decision)
    else:
        passed = True
    return {"key": "resume_decision_pass", "score": passed}
