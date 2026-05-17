"""用于基于 JD、简历和已确认改动生成岗位匹配摘要。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, TypedDict

from app.tools.resume.shared import summarize_value


class JobMatchSummary(TypedDict):
    """用于描述前端展示的岗位匹配证据链摘要。"""

    matched_keywords: list[str]
    missing_keywords: list[str]
    resume_changes: list[str]
    fact_gaps: list[str]
    top_gaps: list["JobMatchTopGap"]


class JobMatchTopGap(TypedDict):
    """用于描述本轮最值得处理的岗位缺口。"""

    gap: str
    priority_reason: str
    jd_evidence: list[str]
    resume_anchor: str
    suggested_edit: str
    risk: str


@dataclass(frozen=True)
class CapabilitySpec:
    """用于把零散 JD 关键词归并成能力缺口。"""

    name: str
    keywords: tuple[str, ...]
    resume_signals: tuple[str, ...]
    edit_direction: str


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
    "工具调用",
    "工作流",
    "可观测",
    "流式输出",
    "检索增强",
    "向量数据库",
    "消息队列",
    "Agent",
)
_CAPABILITY_SPECS = (
    CapabilitySpec(
        name="Agent 工具调用与工作流编排",
        keywords=(
            "Agent",
            "tool",
            "tools",
            "calling",
            "workflow",
            "orchestration",
            "ReAct",
            "human-in-the-loop",
            "工具调用",
            "工作流",
        ),
        resume_signals=("Agent", "工具", "workflow", "ReAct", "确认", "SSE"),
        edit_direction="补充 Agent 如何拆解任务、选择工具、处理工具结果和等待用户确认。",
    ),
    CapabilitySpec(
        name="RAG / LlamaIndex 落地经验",
        keywords=(
            "RAG",
            "LlamaIndex",
            "LangChain",
            "retrieval",
            "embedding",
            "vector",
            "检索增强",
            "向量数据库",
        ),
        resume_signals=("RAG", "检索", "向量", "知识库", "Agent", "LLM"),
        edit_direction="如果真实做过，补充检索、索引、召回、重排或引用校验链路。",
    ),
    CapabilitySpec(
        name="Agent 可观测与前端呈现",
        keywords=("SSE", "streaming", "trace", "React", "TypeScript", "可观测", "流式输出"),
        resume_signals=("SSE", "stream", "React", "TypeScript", "前端", "工具调用"),
        edit_direction="补充如何把工具调用、执行结果和确认 diff 实时展示给用户。",
    ),
    CapabilitySpec(
        name="后端 API 与系统设计",
        keywords=("FastAPI", "API", "backend", "后端", "高并发", "微服务", "系统设计"),
        resume_signals=("FastAPI", "API", "后端", "服务", "并发", "数据库"),
        edit_direction="补充 API 设计、会话状态、错误恢复、性能或可靠性处理。",
    ),
    CapabilitySpec(
        name="工程基础设施经验",
        keywords=("MySQL", "PostgreSQL", "Redis", "RabbitMQ", "database", "queue", "消息队列"),
        resume_signals=("MySQL", "PostgreSQL", "Redis", "RabbitMQ", "数据库", "队列"),
        edit_direction="如果真实使用过，补充数据存储、缓存、队列或异步任务的落地场景。",
    ),
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
    matched_keywords = [
        keyword for keyword in keywords if _contains_keyword(resume_text, keyword)
    ][:6]
    missing_keywords = [
        keyword for keyword in keywords if not _contains_keyword(resume_text, keyword)
    ][:8]
    resume_changes = _summarize_confirmed_changes(confirmed_diff_items)
    fact_gaps = _build_fact_gaps(missing_keywords, jd_text, resume_changes)
    top_gaps = build_job_match_top_gaps(
        resume_content=source_resume,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        jd_text=jd_text,
    )

    if not any(
        [matched_keywords, missing_keywords, resume_changes, fact_gaps, top_gaps]
    ):
        return None
    return {
        "matched_keywords": matched_keywords[:6],
        "missing_keywords": missing_keywords[:6],
        "resume_changes": resume_changes,
        "fact_gaps": fact_gaps,
        "top_gaps": top_gaps,
    }


def build_job_match_top_gaps(
    *,
    resume_content: dict[str, Any],
    matched_keywords: list[str],
    missing_keywords: list[str],
    jd_text: str,
    limit: int = 3,
) -> list[JobMatchTopGap]:
    """用于从缺失关键词中归并出本轮最值得处理的能力缺口。"""
    if not jd_text or not missing_keywords:
        return []

    candidates = _capability_gap_candidates(
        resume_content=resume_content,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        jd_text=jd_text,
    )
    fallback = _keyword_gap_candidates(
        resume_content=resume_content,
        matched_keywords=matched_keywords,
        missing_keywords=missing_keywords,
        jd_text=jd_text,
    )
    ranked = sorted(
        _dedupe_top_gaps(candidates + fallback),
        key=lambda item: _top_gap_score(item, jd_text),
        reverse=True,
    )
    return ranked[: max(1, min(limit, 3))]


def _capability_gap_candidates(
    *,
    resume_content: dict[str, Any],
    matched_keywords: list[str],
    missing_keywords: list[str],
    jd_text: str,
) -> list[JobMatchTopGap]:
    """用于把 JD 缺失关键词聚合成能力级缺口。"""
    gaps: list[JobMatchTopGap] = []
    for spec in _CAPABILITY_SPECS:
        missing = [
            keyword
            for keyword in missing_keywords
            if _keyword_in_group(keyword, spec.keywords)
        ]
        if not missing:
            continue
        matched = [
            keyword
            for keyword in matched_keywords
            if _keyword_in_group(keyword, spec.keywords + spec.resume_signals)
        ]
        evidence = _find_jd_evidence_for_keywords(spec.keywords, jd_text)
        anchor, risk = _find_resume_anchor(
            resume_content,
            list(spec.resume_signals) + matched,
        )
        gaps.append(
            {
                "gap": spec.name,
                "priority_reason": _build_capability_priority_reason(
                    gap_name=spec.name,
                    missing=missing,
                    evidence=evidence,
                    risk=risk,
                ),
                "jd_evidence": evidence,
                "resume_anchor": anchor,
                "suggested_edit": _build_capability_suggested_edit(
                    spec=spec,
                    anchor=anchor,
                    missing=missing,
                    risk=risk,
                ),
                "risk": risk,
            }
        )
    return gaps


def _keyword_gap_candidates(
    *,
    resume_content: dict[str, Any],
    matched_keywords: list[str],
    missing_keywords: list[str],
    jd_text: str,
) -> list[JobMatchTopGap]:
    """用于为未归类关键词生成兜底缺口。"""
    result: list[JobMatchTopGap] = []
    for keyword in missing_keywords:
        if any(_keyword_in_group(keyword, spec.keywords) for spec in _CAPABILITY_SPECS):
            continue
        evidence = _find_jd_evidence_for_keywords((keyword,), jd_text)
        anchor, risk = _find_resume_anchor(resume_content, matched_keywords)
        result.append(
            {
                "gap": f"{keyword} 相关经验表达不足",
                "priority_reason": _build_keyword_priority_reason(
                    keyword=keyword,
                    jd_text=jd_text,
                    evidence=evidence,
                    risk=risk,
                ),
                "jd_evidence": evidence,
                "resume_anchor": anchor,
                "suggested_edit": _build_keyword_suggested_edit(
                    keyword=keyword,
                    anchor=anchor,
                    risk=risk,
                ),
                "risk": risk,
            }
        )
    return result


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


def _find_jd_evidence_for_keywords(
    keywords: tuple[str, ...],
    jd_text: str,
) -> list[str]:
    """用于提取包含任一目标关键词的 JD 原文证据句。"""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"[\n。；;.!?？]+", jd_text)
        if sentence.strip()
    ]
    evidence = [
        sentence
        for sentence in sentences
        if any(_contains_keyword(sentence, keyword) for keyword in keywords)
    ]
    return _dedupe(evidence)[:2] or [jd_text.strip()[:120]]


def _find_resume_anchor(
    resume_content: dict[str, Any],
    signals: list[str],
) -> tuple[str, str]:
    """用于找到最适合承接补强建议的简历位置。"""
    candidates = _resume_anchor_candidates(resume_content)
    if not candidates:
        return "当前简历", "insufficient_evidence"

    scored: list[tuple[int, str]] = []
    for anchor, text in candidates:
        score = sum(1 for signal in signals if signal and _contains_keyword(text, signal))
        scored.append((score, anchor))
    best_score, best_anchor = max(scored, key=lambda item: item[0])
    if best_score >= 2:
        return best_anchor, "can_improve"
    if best_score == 1:
        return best_anchor, "needs_user_confirmation"
    return best_anchor, "insufficient_evidence"


def _resume_anchor_candidates(resume_content: dict[str, Any]) -> list[tuple[str, str]]:
    """用于生成可补强位置候选。"""
    section_titles = {
        "projects": "项目经历",
        "work_experience": "工作经历",
        "education": "教育经历",
        "skills": "技能专长",
    }
    candidates: list[tuple[str, str]] = []
    for section_key in ("projects", "work_experience", "education", "skills"):
        section = resume_content.get(section_key)
        title = section_titles[section_key]
        if isinstance(section, list):
            for index, item in enumerate(section, start=1):
                if not isinstance(item, dict):
                    continue
                name = str(
                    item.get("name")
                    or item.get("company")
                    or item.get("school")
                    or f"{title}{index}"
                )
                candidates.append((f"{title} · {name}", _flatten_resume_text(item)))
        elif section:
            candidates.append((title, _flatten_resume_text(section)))
    return [(anchor, text) for anchor, text in candidates if text.strip()]


def _build_capability_priority_reason(
    *,
    gap_name: str,
    missing: list[str],
    evidence: list[str],
    risk: str,
) -> str:
    """用于生成能力缺口的排序解释。"""
    evidence_text = " ".join(evidence)
    level = "JD 明确提到"
    if any(marker in evidence_text for marker in ("必须", "要求", "负责", "核心")):
        level = "JD 核心职责或要求中强调"
    elif any(marker in evidence_text for marker in ("优先", "加分")):
        level = "JD 加分项中提到"
    risk_reason = {
        "can_improve": "简历已有相邻经历，可直接补强表达",
        "needs_user_confirmation": "简历有相邻锚点，但需要确认真实经历",
        "insufficient_evidence": "简历暂无足够证据，不能直接编造",
    }[risk]
    return f"{level}「{gap_name}」，关联缺失项：{', '.join(missing[:4])}；{risk_reason}。"


def _build_keyword_priority_reason(
    *,
    keyword: str,
    jd_text: str,
    evidence: list[str],
    risk: str,
) -> str:
    """用于生成兜底关键词缺口的排序解释。"""
    count = jd_text.lower().count(keyword.lower())
    evidence_text = " ".join(evidence)
    level = "JD 提到"
    if any(marker in evidence_text for marker in ("必须", "要求", "负责", "核心")):
        level = "JD 核心职责或要求中出现"
    elif any(marker in evidence_text for marker in ("优先", "加分")):
        level = "JD 加分项中出现"
    risk_reason = {
        "can_improve": "且简历已有可补强锚点",
        "needs_user_confirmation": "但需要用户确认真实经历",
        "insufficient_evidence": "但简历暂无可支撑证据",
    }[risk]
    return f"{level}「{keyword}」{count} 次，{risk_reason}。"


def _build_capability_suggested_edit(
    *,
    spec: CapabilitySpec,
    anchor: str,
    missing: list[str],
    risk: str,
) -> str:
    """用于生成能力缺口的安全修改方向。"""
    keywords = "、".join(missing[:3])
    if risk == "can_improve":
        return f"在「{anchor}」中补强「{keywords}」相关表达：{spec.edit_direction}"
    if risk == "needs_user_confirmation":
        return f"先确认你是否真实做过「{keywords}」相关工作；确认后再补到「{anchor}」。"
    return f"不要直接写入「{keywords}」。需要用户先提供真实项目、职责或结果后再改简历。"


def _build_keyword_suggested_edit(
    *,
    keyword: str,
    anchor: str,
    risk: str,
) -> str:
    """用于生成兜底关键词的安全修改方向。"""
    if risk == "can_improve":
        return f"在「{anchor}」中补充与「{keyword}」相关的真实动作、工具链或结果。"
    if risk == "needs_user_confirmation":
        return f"先确认你是否有「{keyword}」相关经历；确认后再补到「{anchor}」。"
    return f"简历暂无可支撑「{keyword}」的证据，需要用户提供真实经历后再补。"


def _top_gap_score(gap: JobMatchTopGap, jd_text: str) -> int:
    """用于给能力缺口排序。"""
    evidence = " ".join(gap["jd_evidence"])
    score = sum(jd_text.count(keyword) for keyword in _extract_keywords(evidence)) * 4
    if any(marker in evidence for marker in ("必须", "要求", "负责", "核心")):
        score += 12
    if any(marker in evidence for marker in ("优先", "加分")):
        score += 4
    if gap["risk"] == "can_improve":
        score += 6
    elif gap["risk"] == "needs_user_confirmation":
        score += 3
    return score


def _keyword_in_group(keyword: str, group: tuple[str, ...]) -> bool:
    """用于判断关键词是否属于一个能力组。"""
    return any(
        _contains_keyword(keyword, item) or _contains_keyword(item, keyword)
        for item in group
    )


def _contains_keyword(text: str, keyword: str) -> bool:
    """用于大小写不敏感地匹配英文关键词，同时保留中文直接匹配。"""
    if not text or not keyword:
        return False
    return keyword.lower() in text.lower()


def _dedupe_top_gaps(gaps: list[JobMatchTopGap]) -> list[JobMatchTopGap]:
    """用于按 gap 名称去重。"""
    result: list[JobMatchTopGap] = []
    seen: set[str] = set()
    for gap in gaps:
        name = gap["gap"]
        if name in seen:
            continue
        seen.add(name)
        result.append(gap)
    return result


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


__all__ = [
    "JobMatchSummary",
    "JobMatchTopGap",
    "build_job_match_summary",
    "build_job_match_top_gaps",
]
