"""用于基于 JD、简历和已确认改动生成岗位匹配摘要。"""

from __future__ import annotations

import re
from typing import Any, TypedDict

from app.tools.resume.shared import summarize_value


class JobMatchSummary(TypedDict):
    """用于描述前端展示的岗位匹配证据链摘要。"""

    matched_keywords: list[str]
    missing_keywords: list[str]
    resume_changes: list[str]
    fact_gaps: list[str]


_COMMON_CHINESE_KEYWORDS = (
    "性能优化",
    "工程化",
    "复杂前端交互",
    "前端",
    "后端",
    "全栈",
    "数据分析",
    "用户增长",
    "项目管理",
    "团队协作",
    "系统设计",
    "高并发",
    "微服务",
    "Agent",
)
_ENGLISH_KEYWORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9+#.\-]{1,}\b")
_NUMBER_RE = re.compile(r"\d")


def build_job_match_summary(
    *,
    original_resume: dict[str, Any],
    latest_resume_content: dict[str, Any] | None,
    confirmed_diff_items: list[dict[str, Any]],
) -> JobMatchSummary | None:
    """用于生成一次 Agent 优化后的岗位匹配摘要。"""
    source_resume = latest_resume_content or original_resume
    jd_text = _extract_jd_text(source_resume)
    if not jd_text:
        return None

    resume_text = _flatten_resume_text_without_jd(source_resume)
    keywords = _extract_keywords(jd_text)
    matched_keywords = [keyword for keyword in keywords if keyword in resume_text][:6]
    missing_keywords = [keyword for keyword in keywords if keyword not in resume_text][:6]
    resume_changes = _summarize_confirmed_changes(confirmed_diff_items)
    fact_gaps = _build_fact_gaps(missing_keywords, jd_text, resume_changes)

    if not any([matched_keywords, missing_keywords, resume_changes, fact_gaps]):
        return None
    return {
        "matched_keywords": matched_keywords,
        "missing_keywords": missing_keywords,
        "resume_changes": resume_changes,
        "fact_gaps": fact_gaps,
    }


def _extract_jd_text(resume_content: dict[str, Any]) -> str:
    """用于从简历内容中读取目标岗位 JD 文本。"""
    job_application = resume_content.get("job_application")
    if not isinstance(job_application, dict):
        return ""
    jd_text = job_application.get("jd_text")
    return str(jd_text or "").strip()


def _extract_keywords(jd_text: str) -> list[str]:
    """用于从 JD 中提取可解释的轻量关键词。"""
    positioned: list[tuple[int, str]] = []
    positioned.extend(
        (jd_text.index(keyword), keyword)
        for keyword in _COMMON_CHINESE_KEYWORDS
        if keyword in jd_text
    )
    positioned.extend(
        (match.start(), match.group(0))
        for match in _ENGLISH_KEYWORD_RE.finditer(jd_text)
    )
    return _dedupe([keyword for _, keyword in sorted(positioned)])


def _flatten_resume_text(value: Any) -> str:
    """用于把结构化简历压平成可搜索文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return "\n".join(_flatten_resume_text(item) for item in value.values())
    if isinstance(value, list):
        return "\n".join(_flatten_resume_text(item) for item in value)
    return str(value)


def _flatten_resume_text_without_jd(resume_content: dict[str, Any]) -> str:
    """用于排除 JD 字段后生成简历正文匹配文本。"""
    return "\n".join(
        _flatten_resume_text(value)
        for key, value in resume_content.items()
        if key != "job_application"
    )


def _summarize_confirmed_changes(diff_items: list[dict[str, Any]]) -> list[str]:
    """用于把已确认 diff 压缩成用户可读的优化变化。"""
    changes = []
    for item in diff_items:
        after = summarize_value(item.get("after"), max_length=100)
        if after == "空":
            continue
        reason = str(item.get("reason") or "").strip()
        changes.append(f"{reason}：{after}" if reason else after)
    return _dedupe(changes)[:4]


def _build_fact_gaps(
    missing_keywords: list[str],
    jd_text: str,
    resume_changes: list[str],
) -> list[str]:
    """用于生成需要用户补充真实事实的提示。"""
    gaps = [
        f"可补充与「{keyword}」相关的真实经历或结果"
        for keyword in missing_keywords[:3]
    ]
    needs_number = any(word in jd_text for word in ("量化", "指标", "提升", "优化"))
    has_numbered_change = any(_NUMBER_RE.search(change) for change in resume_changes)
    if needs_number and not has_numbered_change:
        gaps.append("可补充真实量化结果，说明优化幅度或业务影响")
    return _dedupe(gaps)[:4]


def _dedupe(values: list[str]) -> list[str]:
    """用于按出现顺序去重并移除空值。"""
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


__all__ = ["JobMatchSummary", "build_job_match_summary"]
