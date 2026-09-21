"""Tests for realtime interview prompt and greeting construction."""

from app.entrypoints.http.interview_realtime import (
    _build_greeting,
    _build_interviewer_system_role,
)


def test_build_greeting_chinese_with_context() -> None:
    """Include target context in a Chinese greeting."""
    text = _build_greeting(
        target_title="后端工程师",
        target_company="字节跳动",
        language="zh-CN",
    )
    assert "后端工程师" in text
    assert "字节跳动" in text


def test_build_greeting_english_with_context() -> None:
    """Include target context in an English greeting."""
    text = _build_greeting(
        target_title="Backend Engineer",
        target_company="ByteDance",
        language="en",
    )
    assert "Backend Engineer" in text
    assert "ByteDance" in text


def test_build_greeting_without_context_uses_generic_copy() -> None:
    """Avoid placeholder names when no target context is available."""
    text = _build_greeting(target_title="", target_company="", language="zh-CN")
    assert "目标岗位" not in text
    assert "目标公司" not in text
    assert len(text) > 5


def test_interviewer_system_role_contains_context_and_rules() -> None:
    """Render resume, job, plan, question bank, and operating rules."""
    text = _build_interviewer_system_role(
        target_title="后端工程师",
        target_company="字节跳动",
        language="zh-CN",
        difficulty="hard",
        jd_text="负责高并发服务",
        resume_text="候选人姓名：张三",
        interview_history="面试官：请介绍项目",
        interview_plan="阶段：简历项目深挖；重点：技术取舍",
        rag_questions="Question: Redis 如何实现分布式锁？",
    )

    assert "中文模拟面试官" in text
    assert "后端工程师" in text
    assert "候选人简历摘要：\n候选人姓名：张三" in text
    assert "岗位 JD 摘要：\n负责高并发服务" in text
    assert "简历项目深挖" in text
    assert "Redis 如何实现分布式锁" in text
    assert "每次只问一个问题" in text
    assert "绝不替候选人回答" in text


def test_interviewer_system_role_stays_within_context_limit() -> None:
    """Trim large source fields before the model receives the prompt."""
    text = _build_interviewer_system_role(
        target_title="后端工程师",
        target_company="字节跳动",
        language="zh-CN",
        difficulty="hard",
        jd_text="JD" * 3000,
        resume_text="简历" * 3000,
        interview_history="历史" * 3000,
        interview_plan="计划" * 3000,
        rag_questions="题库" * 3000,
    )

    assert len(text) <= 4000
    assert "每次只问一个问题" in text
