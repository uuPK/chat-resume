"""
结构化面试 API

提供面试 session / turn 的最小闭环接口。
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from uuid import uuid4

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session, noload, sessionmaker

from app.entrypoints.http.deps import get_current_user
from app.agents.interview import InterviewerAgent
from app.infra.database import get_db
from app.infra.langfuse_observer import LangfuseRunObserver
from app.infra.request_context import log_context
from app.models import InterviewSession, InterviewTurn
from app.schemas.resume import dump_resume_content_for_frontend
from app.services.domain import ResumeService

router = APIRouter()

_interviewer_agent = InterviewerAgent()


def _now() -> datetime:
    """用于统一生成带时区的当前时间。"""
    return datetime.now(timezone.utc)


def _get_resume_for_user(db: Session, resume_id: int, user_id: int):
    """用于校验用户对目标简历的访问权限。"""
    resume = ResumeService(db).get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    if resume.owner_id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions")
    return resume


_ROUND_INSTRUCTIONS: dict[str, str] = {
    "warmup": (
        "【当前阶段：热身】"
        "目标是建立基本画像、确认岗位匹配度。"
        "只问自我介绍、求职动机、近期状态等开放性问题。"
        "不要追技术细节，不要追项目数字，不要出行为题。"
        "语气可以稍微轻松，帮候选人热身。"
    ),
    "resume_deep_dive": (
        "【当前阶段：项目深挖】"
        "目标是验证简历真实性，挖出候选人的真实贡献和量化结果。"
        "紧盯简历里的具体项目或工作经历，逐一追问：你具体做了什么、遇到了什么困难、最终结果是什么数字。"
        "如果候选人回答空泛，必须追问：个人贡献是什么、结果怎么量化、是怎么解决问题的。"
        "不要转移到和简历无关的话题。"
    ),
    "behavioral": (
        "【当前阶段：行为面试】"
        "目标是考察软技能，要求候选人用 STAR 结构（情境、任务、行动、结果）回答。"
        "典型问题：团队冲突经历、失败项目的处理、跨部门协作、在压力下的决策。"
        "如果回答缺少结果或个人行动，必须追问最终结果和复盘结论。"
        "不要出纯技术题。"
    ),
    "technical": (
        "【当前阶段：技术考察】"
        "目标是考察技术深度、工程判断和系统思维。"
        "可以问架构设计、技术选型理由、性能优化、线上排障经历、代码质量等。"
        "如果候选人给出结论，必须追问：为什么这样选、有什么取舍、遇到了什么坑。"
        "不要问纯行为或软技能问题。"
    ),
    "closing": (
        "【当前阶段：收尾】"
        "目标是给候选人反问机会，并做简短的面试收尾。"
        "可以问：你对这个岗位或团队有什么想了解的？你觉得自己最大的短板是什么？"
        "不要出新的技术题或行为题。语气回归轻松，给候选人一个好的结束体验。"
    ),
}


def _round_instructions(question_type: str) -> str:
    """用于按面试阶段返回固定提问约束。"""
    return _ROUND_INSTRUCTIONS.get(question_type, "")


def _build_first_round_prompt(question_type: str, round_goal: str) -> str:
    """用于生成首轮提问时的系统提示。"""
    instructions = _round_instructions(question_type)
    return f"{instructions}\n开始一场模拟面试。当前阶段目标：{round_goal}。请直接提出第一题。"


def _build_next_round_prompt(question_type: str, round_goal: str) -> str:
    """用于生成切换到下一轮时的提问提示。"""
    instructions = _round_instructions(question_type)
    return f"{instructions}\n进入下一阶段：{round_goal}。请直接提出该阶段的第一个问题。"


def _build_same_round_prompt(question_type: str, round_goal: str, remaining_questions: int) -> str:
    """用于生成同一轮内继续追问时的提问提示。"""
    instructions = _round_instructions(question_type)
    return (
        f"{instructions}\n当前面试阶段：{round_goal}（本阶段还可再问 {remaining_questions} 题）。"
        "根据候选人刚才的回答，决定追问细节还是转向该阶段下一个核心问题。"
    )


def _build_hint_prompt(
    *,
    question_type: str,
    question: str,
    round_goal: str,
    target_title: str,
) -> str:
    """用于生成练习模式下的答题提示词。"""
    instructions = _round_instructions(question_type)
    role_hint = f"目标岗位：{target_title}。" if target_title else ""
    return (
        f"{instructions}\n"
        f"{role_hint}"
        f"当前问题：{question}\n"
        f"当前阶段目标：{round_goal}\n"
        "请给候选人 3 条简短提示，帮助其组织答案。"
        "每条提示都要可执行，聚焦回答结构、关键信息和量化结果。"
        "不要直接替候选人写完整答案。"
    )


def _rounds_for_type(interview_type: str) -> list[dict[str, Any]]:
    """用于根据面试类型生成默认轮次规划。"""
    if interview_type == "behavioral":
        return [
            {"type": "warmup", "goal": "自我介绍与背景确认", "max_questions": 2},
            {"type": "behavioral", "goal": "行为事件与协作能力", "max_questions": 4},
            {"type": "behavioral", "goal": "冲突处理与复盘能力", "max_questions": 3},
            {"type": "closing", "goal": "总结与反问", "max_questions": 2},
        ]
    if interview_type == "technical":
        return [
            {"type": "warmup", "goal": "自我介绍与岗位匹配", "max_questions": 2},
            {"type": "resume_deep_dive", "goal": "项目真实性与个人贡献", "max_questions": 4},
            {"type": "technical", "goal": "技术深度与工程判断", "max_questions": 4},
            {"type": "technical", "goal": "系统设计与排障能力", "max_questions": 3},
            {"type": "closing", "goal": "总结与反问", "max_questions": 2},
        ]
    return [
        {"type": "warmup", "goal": "自我介绍与背景确认", "max_questions": 2},
        {"type": "resume_deep_dive", "goal": "项目深挖与个人贡献", "max_questions": 15},
        {"type": "behavioral", "goal": "行为能力与沟通协作", "max_questions": 3},
        {"type": "closing", "goal": "总结与反问", "max_questions": 2},
    ]


def _build_plan(resume_content: dict[str, Any], interview_type: str) -> dict[str, Any]:
    """用于构建一场结构化面试的初始计划。"""
    resume_content = dump_resume_content_for_frontend(resume_content or {})
    return {
        "rounds": _rounds_for_type(interview_type),
        "resume_highlights": {
            "work_experience_count": len(resume_content.get("work_experience") or []),
            "project_count": len(resume_content.get("projects") or []),
            "target_title": ((resume_content.get("job_application") or {}).get("target_title") or ""),
            "target_company": ((resume_content.get("job_application") or {}).get("target_company") or ""),
        },
    }


def _serialize_turn(turn: InterviewTurn) -> dict[str, Any]:
    """用于把面试轮次对象转换成响应字典。"""
    return {
        "id": turn.id,
        "turn_index": turn.turn_index,
        "round_index": turn.round_index,
        "question": turn.question,
        "question_type": turn.question_type,
        "intent": turn.intent,
        "expected_points": turn.expected_points,
        "answer": turn.answer,
        "evaluation": _normalize_evaluation_text(turn.evaluation),
        "follow_up_count": turn.follow_up_count,
        "status": turn.status,
        "asked_at": turn.asked_at.isoformat() if turn.asked_at else None,
        "answered_at": turn.answered_at.isoformat() if turn.answered_at else None,
    }


def _serialize_session(session: InterviewSession) -> dict[str, Any]:
    """用于把完整面试 session 转成前端可消费结构。"""
    turns = list(session.turns or [])
    return {
        "id": session.id,
        "resume_id": session.resume_id,
        "target_title": session.target_title,
        "target_company": session.target_company,
        "jd_text": session.jd_text,
        "interview_type": session.interview_type,
        "difficulty": session.difficulty,
        "language": session.language,
        "mode": session.mode,
        "status": session.status,
        "current_round_index": session.current_round_index,
        "current_turn_index": session.current_turn_index,
        "plan": session.plan_json,
        "report_data": session.report_data,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "turns": [_serialize_turn(turn) for turn in turns],
        "current_turn": _serialize_turn(turns[-1]) if turns else None,
    }


def _serialize_session_summary(
    session: InterviewSession,
    *,
    answered_turn_count: int = 0,
) -> dict[str, Any]:
    """用于把面试 session 转成列表页摘要结构。"""
    return {
        "id": session.id,
        "resume_id": session.resume_id,
        "target_title": session.target_title,
        "target_company": session.target_company,
        "interview_type": session.interview_type,
        "difficulty": session.difficulty,
        "language": session.language,
        "mode": session.mode,
        "status": session.status,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "answered_turn_count": answered_turn_count,
    }


def _latest_turn(session: InterviewSession) -> Optional[InterviewTurn]:
    """用于获取当前 session 最新的一轮提问。"""
    turns = list(session.turns or [])
    return turns[-1] if turns else None


def _normalize_evaluation_text(evaluation: Any) -> str:
    """用于把历史结构化评估和新文本评估统一转换成纯文本。"""
    if isinstance(evaluation, str):
        return evaluation.strip()
    if not isinstance(evaluation, dict):
        return ""

    parts: list[str] = []
    summary = str(evaluation.get("summary") or "").strip()
    if summary:
        parts.append(summary)

    gaps = [str(item).strip() for item in (evaluation.get("gaps") or []) if str(item).strip()]
    if gaps:
        parts.append("问题：" + "；".join(gaps[:3]))

    evidence = [str(item).strip() for item in (evaluation.get("evidence") or []) if str(item).strip()]
    if evidence:
        parts.append("亮点：" + "；".join(evidence[:2]))

    return "\n".join(parts).strip()


def _extract_keywords(text: str, limit: int = 6) -> list[str]:
    """用于从问题或岗位信息里提取可复用的关键词。"""
    keywords: list[str] = []
    for keyword in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", text or ""):
        normalized = keyword.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in {"请问", "一下", "一个", "这个", "那个", "为什么", "怎么", "是否"}:
            continue
        if lowered not in {item.lower() for item in keywords}:
            keywords.append(normalized)
        if len(keywords) >= limit:
            break
    return keywords


def _contains_keyword(text: str, keywords: list[str]) -> bool:
    """用于判断一段回答是否命中了问题或岗位关键词。"""
    normalized = (text or "").lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def _analyze_turn(turn: InterviewTurn) -> dict[str, bool]:
    """用于把单题回答转成报告生成需要的基础信号。"""
    answer = (turn.answer or "").strip()
    question_keywords = _extract_keywords(turn.question, limit=4)
    answer_keywords = _extract_keywords(answer, limit=8)

    directly_answers = not question_keywords or _contains_keyword(answer, question_keywords)
    has_ownership = any(token in answer for token in ("我", "自己", "主导", "负责", "推进"))
    has_metrics = any(char.isdigit() for char in answer)
    has_context = len(answer) >= 60
    has_depth = len(answer) >= 120
    has_reflection = any(token in answer for token in ("复盘", "总结", "学到", "改进", "下次"))
    mentions_result = any(token in answer for token in ("结果", "效果", "提升", "增长", "降低", "优化")) or has_metrics

    return {
        "directly_answers": directly_answers,
        "has_ownership": has_ownership,
        "has_metrics": has_metrics,
        "has_context": has_context,
        "has_depth": has_depth,
        "has_reflection": has_reflection,
        "mentions_result": mentions_result,
        "has_answer_keywords": bool(answer_keywords),
    }


def _build_report_dimension(title: str, assessment: str, evidence: str, advice: str) -> dict[str, str]:
    """用于统一构造前端可直接展示的报告维度项。"""
    return {
        "title": title,
        "assessment": assessment,
        "evidence": evidence,
        "advice": advice,
    }


def _build_interview_report(
    *,
    turns: list[InterviewTurn],
    target_title: str = "",
    target_company: str = "",
    ended_by_user: bool = False,
) -> dict[str, Any]:
    """用于把整场问答整理成结构化面试报告。"""
    answered_turns = [turn for turn in turns if (turn.answer or "").strip()]
    if not answered_turns:
        summary_prefix = "本场面试已提前结束。" if ended_by_user else "本场模拟面试已结束。"
        return {
            "summary": f"{summary_prefix} 当前样本还不足，建议至少完成 3 题后再看完整复盘。",
            "dimensions": [
                _build_report_dimension(
                    "切题度",
                    "当前样本不足，暂时无法判断切题稳定性。",
                    "还没有形成可用于评估的完整回答。",
                    "下一轮先完成 3 道题，并且每题先用一句话直接回答问题。",
                ),
                _build_report_dimension(
                    "表达清晰度",
                    "当前样本不足，暂时无法判断表达组织。",
                    "还没有形成可用于评估的完整回答。",
                    "先按背景、动作、结果三段式组织回答。",
                ),
                _build_report_dimension(
                    "项目/经历深度",
                    "当前样本不足，暂时无法判断项目展开能力。",
                    "还没有形成可用于评估的完整回答。",
                    "下一轮优先补具体场景、个人动作和结果指标。",
                ),
                _build_report_dimension(
                    "岗位匹配度",
                    "当前样本不足，暂时无法判断岗位匹配表达。",
                    "还没有形成可用于评估的完整回答。",
                    "先把岗位动机和最相关项目准备成可直接复述的版本。",
                ),
            ],
            "recurring_issues": ["先至少完成 3 道题，再看模式性问题会更有参考价值。"],
            "weaknesses": ["先至少完成 3 道题，再看模式性问题会更有参考价值。"],
            "next_training_plan": [
                "先补足最基本的 3 道问答样本。",
                "每题先给结论，再展开背景、动作、结果。",
            ],
            "resume_feedback": ["简历里先补充最能代表岗位匹配度的项目和结果指标。"],
        }

    analyzed_turns = [(turn, _analyze_turn(turn)) for turn in answered_turns]
    total = len(analyzed_turns)
    direct_count = sum(1 for _, signal in analyzed_turns if signal["directly_answers"])
    context_count = sum(1 for _, signal in analyzed_turns if signal["has_context"])
    depth_count = sum(1 for _, signal in analyzed_turns if signal["has_depth"])
    ownership_count = sum(1 for _, signal in analyzed_turns if signal["has_ownership"])
    metrics_count = sum(1 for _, signal in analyzed_turns if signal["has_metrics"])
    result_count = sum(1 for _, signal in analyzed_turns if signal["mentions_result"])
    reflection_count = sum(
        1
        for turn, signal in analyzed_turns
        if turn.question_type == "behavioral" and signal["has_reflection"]
    )

    role_keywords = _extract_keywords(f"{target_company} {target_title}", limit=6)
    role_match_count = sum(
        1
        for turn, _signal in analyzed_turns
        if role_keywords and _contains_keyword(turn.answer or "", role_keywords)
    )

    recurring_issues: list[str] = []
    if direct_count <= max(1, total // 2):
        recurring_issues.append("多次没有直接回答问题本身，建议先给结论再展开。")
    if ownership_count <= max(1, total // 2):
        recurring_issues.append("多次没有把个人贡献讲清楚，需要明确“我做了什么”。")
    if metrics_count <= max(1, total // 2):
        recurring_issues.append("多次缺少量化结果或具体指标，回答说服力不够。")
    if context_count <= max(1, total // 2):
        recurring_issues.append("多次缺少背景和过程，回答容易显得过短。")
    if any(turn.question_type == "behavioral" for turn, _signal in analyzed_turns) and reflection_count == 0:
        recurring_issues.append("行为题里复盘不足，缺少你从事件里学到了什么。")
    recurring_issues = recurring_issues[:3] or ["整体完成度尚可，下一轮重点把回答说得更具体。"]

    if direct_count >= max(1, total - 1):
        strongest_point = "多数回答能先回应问题本身"
    elif ownership_count >= max(1, total - 1):
        strongest_point = "部分回答已经能讲清个人贡献"
    elif metrics_count >= max(1, total // 2):
        strongest_point = "部分回答已经开始补充结果指标"
    else:
        strongest_point = "能持续完成整场问答"

    issue_pressure = 0
    issue_pressure += total - direct_count
    issue_pressure += total - ownership_count
    issue_pressure += total - metrics_count
    if issue_pressure <= total:
        overall_verdict = "整体已经具备继续深聊的基础"
    elif issue_pressure <= total * 2:
        overall_verdict = "整体可以继续，但稳定性还不够"
    else:
        overall_verdict = "当前回答质量还不稳定，容易在关键题上失分"

    summary_prefix = "本场面试已提前结束。" if ended_by_user else "本场模拟面试已结束。"
    summary = (
        f"{summary_prefix}{overall_verdict}。"
        f"当前最需要优先修正的是：{recurring_issues[0]}"
        f"相对做得更好的是：{strongest_point}。"
    )

    if direct_count >= max(1, total - 1):
        focus_assessment = "大多数回答都能先回应问题本身，切题度比较稳定。"
    elif direct_count >= max(1, total // 2):
        focus_assessment = "有一部分回答能切题，但稳定性不足，容易答着答着偏开。"
    else:
        focus_assessment = "多次偏离题干重点，切题度是当前最明显的问题。"
    focus_evidence = f"{direct_count}/{total} 题在回答里明显命中了题干关键词。"
    focus_advice = "下一轮每题先用一句话直接回答问题，再补背景、动作和结果。"

    clarity_hits = sum(1 for _, signal in analyzed_turns if signal["has_context"] and signal["directly_answers"])
    if clarity_hits >= max(1, total - 1):
        clarity_assessment = "回答组织相对清楚，听者能跟上你的表达节奏。"
    elif clarity_hits >= max(1, total // 2):
        clarity_assessment = "表达有基础，但部分回答仍然过短或跳步骤。"
    else:
        clarity_assessment = "表达组织偏弱，很多回答缺少基本的背景和过程说明。"
    clarity_evidence = f"{clarity_hits}/{total} 题同时具备基本切题和背景展开。"
    clarity_advice = "统一按背景、动作、结果三段式说，避免只给一句结论。"

    depth_hits = sum(1 for _, signal in analyzed_turns if signal["has_ownership"] and signal["mentions_result"])
    if depth_hits >= max(1, total - 1):
        depth_assessment = "项目和经历能讲到个人动作与结果，深度相对够用。"
    elif depth_hits >= max(1, total // 2):
        depth_assessment = "有部分题目能展开到个人贡献，但深度不够稳定。"
    else:
        depth_assessment = "项目和经历多数停留在表面，个人贡献和结果讲得不够深。"
    depth_evidence = (
        f"{ownership_count}/{total} 题明确讲到个人贡献，"
        f"{result_count}/{total} 题补到了结果或效果。"
    )
    depth_advice = "每个项目都固定补三件事：你具体做了什么、为什么这样做、最后结果怎样。"

    if not role_keywords:
        role_assessment = "这场更多基于简历追问，岗位匹配表达样本还不够。"
        role_evidence = "当前没有足够明确的目标岗位关键词可用于判断匹配度。"
        role_advice = "下轮开始前把目标岗位和公司补全，并准备一版岗位动机。"
    elif role_match_count >= max(1, total // 2):
        role_assessment = "回答里已经能主动贴近目标岗位，匹配表达比较自然。"
        role_evidence = f"{role_match_count}/{total} 题回答中主动提到了岗位或公司相关关键词。"
        role_advice = "继续把岗位关键词和代表项目绑定起来，说清楚为什么你适合这个岗位。"
    else:
        role_assessment = "岗位匹配点表达偏弱，回答更多停留在经历本身，没有主动贴岗位。"
        role_evidence = f"{role_match_count}/{total} 题回答中主动提到了岗位或公司相关关键词。"
        role_advice = "每次回答最后补一句：这段经历为什么和目标岗位直接相关。"

    next_training_plan: list[str] = []
    if direct_count <= max(1, total // 2):
        next_training_plan.append("先练“直接回答问题”，每题先用一句话给结论，再展开。")
    if ownership_count <= max(1, total // 2):
        next_training_plan.append("再练“个人贡献”，每个项目都明确说出你亲自负责的动作和决策。")
    if metrics_count <= max(1, total // 2):
        next_training_plan.append("再练“量化结果”，每题至少补一个结果指标或业务影响。")
    if any(turn.question_type == "behavioral" for turn, _signal in analyzed_turns) and reflection_count == 0:
        next_training_plan.append("行为题补一层复盘，说明你从这件事里学到了什么。")
    next_training_plan = next_training_plan[:3] or [
        "下一轮继续保持直接回答问题的习惯。",
        "把已有项目答案压缩成更稳定的背景、动作、结果结构。",
    ]

    resume_feedback: list[str] = []
    if metrics_count <= max(1, total // 2):
        resume_feedback.append("简历里的项目成果需要补成可直接复述的数字，否则面试里也很难自然讲出指标。")
    if ownership_count <= max(1, total // 2):
        resume_feedback.append("简历里的项目描述要更突出“我主导/我负责”的部分，降低团队口吻。")
    if direct_count <= max(1, total // 2):
        resume_feedback.append("简历里的项目背景和目标可以写得更清楚，方便面试时快速切题。")
    if role_keywords and role_match_count <= max(1, total // 3):
        resume_feedback.append(
            f"简历里需要更明显地突出与“{target_title or target_company}”直接相关的能力和经历。"
        )
    resume_feedback = resume_feedback[:3] or ["简历和面试表达基本一致，下一轮重点继续打磨结果和细节。"]

    return {
        "summary": summary,
        "dimensions": [
            _build_report_dimension("切题度", focus_assessment, focus_evidence, focus_advice),
            _build_report_dimension("表达清晰度", clarity_assessment, clarity_evidence, clarity_advice),
            _build_report_dimension("项目/经历深度", depth_assessment, depth_evidence, depth_advice),
            _build_report_dimension("岗位匹配度", role_assessment, role_evidence, role_advice),
        ],
        "recurring_issues": recurring_issues,
        "weaknesses": recurring_issues,
        "next_training_plan": next_training_plan,
        "resume_feedback": resume_feedback,
    }


def _fallback_hint(turn: InterviewTurn) -> list[str]:
    """用于在提示生成失败时返回可直接使用的练习建议。"""
    tips = [
        "先交代背景和目标，再说明你亲自做了什么。",
        "一定讲出结果，最好补一到两个量化指标。",
        "把重点放在个人贡献和关键决策，不要只讲团队工作。",
    ]
    if turn.question_type == "behavioral":
        tips = [
            "按 STAR 结构回答：情境、任务、行动、结果。",
            "重点讲你本人采取了什么行动，不要只描述团队。",
            "最后补一句复盘，说明你从这件事里学到了什么。",
        ]
    elif turn.question_type == "technical":
        tips = [
            "先给结论，再说明为什么这样设计或选择。",
            "补充技术取舍、风险和你如何验证方案有效。",
            "最好举一个线上问题、性能指标或工程细节来支撑答案。",
        ]
    return tips




async def _generate_question(
    *,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
    prompt: str,
    event_callback=None,
) -> str:
    """用于调用面试 Agent 生成下一道问题。"""
    result = await _interviewer_agent.chat(
        user_message=prompt,
        resume_content=resume_content,
        conversation_history=history,
        event_callback=event_callback,
    )
    return (result.get("content") or "").strip()


def _build_turn_history(
    session: InterviewSession,
    *,
    current_turn: Optional[InterviewTurn] = None,
    pending_answer: str = "",
) -> list[dict[str, str]]:
    """用于整理问答历史，供下一题生成和题后评估共享上下文。"""
    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer and item is not current_turn:
            history.append({"role": "user", "content": item.answer})
    if pending_answer.strip():
        history.append({"role": "user", "content": pending_answer.strip()})
    return history


def _build_session_factory(db: Session) -> sessionmaker:
    """用于给后台评估任务创建独立数据库会话工厂。"""
    return sessionmaker(autocommit=False, autoflush=False, bind=db.get_bind())


def _log_async_task_failure(task: asyncio.Task[Any]) -> None:
    """用于统一记录后台异步任务里的异常，避免静默失败。"""
    try:
        task.result()
    except Exception:
        logger.exception("Interview background task failed")


def _fallback_evaluation(question: str, answer: str) -> str:
    """用于在 LLM 评估失败时提供简短文本兜底结果。"""
    normalized = (answer or "").strip()
    gaps: list[str] = []
    missing_question_focus = False
    question_keywords = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", question or "")
    if question_keywords and not any(keyword in normalized for keyword in question_keywords[:4]):
        missing_question_focus = True
    if len(normalized) < 60:
        gaps.append("回答偏短，缺少背景和结果")
    if "我" not in normalized:
        gaps.append("个人贡献不够明确")
    if not any(ch.isdigit() for ch in normalized):
        gaps.append("缺少量化结果或具体指标")
    if missing_question_focus:
        gaps.insert(0, "没有直接回应问题本身")
    if gaps:
        return "面试系统反馈：" + "；".join(gaps[:2]) + "。建议先直接回答问题，再补充个人贡献和结果。"
    return "面试系统反馈：回答基本切题，但还可以补充更具体的个人动作和结果，让信息更完整。"


async def _evaluate_answer_with_llm(
    *,
    question: str,
    answer: str,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
    event_callback=None,
) -> str:
    """用于让 LLM 对候选人回答做文本评估。"""
    prompt = (
        f"[EVALUATE]\n"
        f"面试问题：{question}\n"
        f"候选人回答：{answer}\n"
        "请从面试系统的角度给出简短反馈，不要使用面试官训话口吻。"
        "先指出是否答到问题本身，再指出最关键的缺口，并给一个最重要的补强建议。"
        "长度控制在 1 到 2 句话。"
    )
    try:
        result = await _interviewer_agent.chat(
            user_message=prompt,
            resume_content=resume_content,
            conversation_history=history,
            event_callback=event_callback,
        )
        raw = (result.get("content") or "").strip()
        if raw:
            return raw
        return _fallback_evaluation(question, answer)
    except Exception:
        logger.warning("LLM evaluation failed, falling back to rule-based evaluation")
        return _fallback_evaluation(question, answer)


async def _persist_turn_evaluation(
    *,
    session_factory: sessionmaker,
    user_id: int,
    session_id: int,
    turn_id: int,
    question: str,
    answer: str,
    resume_content: dict[str, Any],
    history: list[dict[str, str]],
    event_callback=None,
) -> str:
    """用于异步生成并落库单题评估，避免阻塞下一题生成。"""
    evaluation_text = await _evaluate_answer_with_llm(
        question=question,
        answer=answer,
        resume_content=resume_content,
        history=history,
        event_callback=event_callback,
    )

    db = session_factory()
    try:
        session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        turn = db.query(InterviewTurn).filter(InterviewTurn.id == turn_id).first()
        if not session or session.user_id != user_id or not turn or turn.session_id != session_id:
            return evaluation_text

        turn.evaluation = evaluation_text
        if session.status == "completed" and isinstance(session.report_data, dict):
            session.report_data = _build_interview_report(
                turns=list(session.turns or []),
                target_title=session.target_title or "",
                target_company=session.target_company or "",
                ended_by_user="已提前结束" in str((session.report_data or {}).get("summary") or ""),
            )
        db.commit()
        return evaluation_text
    finally:
        db.close()


class InterviewCreateRequest(BaseModel):
    """用于承载创建结构化面试的请求参数。"""

    resume_id: int
    target_title: str = ""
    target_company: str = ""
    jd_text: str = ""
    interview_type: str = "general"
    difficulty: str = "medium"
    language: str = "zh-CN"
    mode: str = "practice"


class InterviewAnswerRequest(BaseModel):
    """用于承载候选人的一次作答内容。"""

    answer: str = Field(min_length=1)


class InterviewHintResponse(BaseModel):
    """用于返回练习模式下当前题目的提示内容。"""

    hints: List[str]


class InterviewActionResponse(BaseModel):
    """用于统一返回面试动作后的最新 session 结果。"""

    session: Dict[str, Any]
    message: Optional[str] = None
    evaluation: Optional[str] = None
    next_action: Optional[str] = None


@router.post("/", response_model=InterviewActionResponse)
async def create_interview(
    request: InterviewCreateRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于创建一场新的结构化模拟面试。"""
    resume = _get_resume_for_user(db, request.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    plan = _build_plan(resume_content, request.interview_type)
    job_application = (resume_content.get("job_application") or {}) if isinstance(resume_content, dict) else {}

    session = InterviewSession(
        user_id=current_user["id"],
        resume_id=request.resume_id,
        target_title=request.target_title or str(job_application.get("target_title", "") or ""),
        target_company=request.target_company or str(job_application.get("target_company", "") or ""),
        jd_text=request.jd_text or str(job_application.get("jd_text", "") or ""),
        interview_type=request.interview_type,
        difficulty=request.difficulty,
        language=request.language,
        mode=request.mode,
        status="interview_ready",
        current_round_index=0,
        current_turn_index=0,
        plan_json=plan,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return InterviewActionResponse(session=_serialize_session(session), next_action="start")


@router.post("/{session_id}/hint", response_model=InterviewHintResponse)
async def get_interview_hint(
    session_id: int,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于在练习模式下为当前题目生成简短提示。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.mode != "practice":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Hints are only available in practice mode")

    turn = _latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active question to hint")

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    history: list[dict[str, str]] = []
    for item in list(session.turns or []):
        history.append({"role": "assistant", "content": item.question})
        if item.answer:
            history.append({"role": "user", "content": item.answer})

    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="hint_interview",
        user_id=current_user["id"],
        input_text=turn.question,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    prompt = _build_hint_prompt(
        question_type=turn.question_type,
        question=turn.question,
        round_goal=turn.intent or "",
        target_title=session.target_title or "",
    )
    hints = _fallback_hint(turn)
    try:
        with observer:
            result = await _interviewer_agent.chat(
                user_message=prompt,
                resume_content=resume_content,
                conversation_history=history,
                event_callback=observer.on_runtime_event,
            )
        raw = (result.get("content") or "").strip()
        parsed = [
            re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", line).strip()
            for line in raw.splitlines()
            if line.strip()
        ]
        if parsed:
            hints = parsed[:3]
        observer.finish("hint_generated")
    except Exception as exc:
        observer.fail(str(exc))
        logger.warning("Hint generation failed, falling back to default hints")
    return InterviewHintResponse(hints=hints)


@router.get("/", response_model=List[Dict[str, Any]])
async def list_interviews(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回当前用户的面试 session 列表。"""
    answered_turn_counts = (
        db.query(
            InterviewTurn.session_id.label("session_id"),
            func.sum(
                case(
                    (InterviewTurn.answer.isnot(None), 1),
                    else_=0,
                )
            ).label("answered_turn_count"),
        )
        .group_by(InterviewTurn.session_id)
        .subquery()
    )
    sessions = (
        db.query(
            InterviewSession,
            func.coalesce(answered_turn_counts.c.answered_turn_count, 0).label("answered_turn_count"),
        )
        .outerjoin(answered_turn_counts, answered_turn_counts.c.session_id == InterviewSession.id)
        .options(noload(InterviewSession.turns))
        .filter(InterviewSession.user_id == current_user["id"])
        .order_by(InterviewSession.id.desc())
        .all()
    )
    return [
        _serialize_session_summary(session, answered_turn_count=int(answered_turn_count or 0))
        for session, answered_turn_count in sessions
    ]


@router.get("/{session_id}", response_model=InterviewActionResponse)
async def get_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回单场面试的完整状态。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewActionResponse(session=_serialize_session(session))


@router.delete("/{session_id}", response_model=Dict[str, str])
async def delete_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于删除当前用户的一场面试记录及其关联轮次。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")

    db.delete(session)
    db.commit()
    return {"message": "Interview session deleted"}


@router.post("/{session_id}/start", response_model=InterviewActionResponse)
async def start_interview(
    session_id: int,
    http_request: Request,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于启动一场待开始的面试并生成第一题。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status not in {"created", "interview_ready"}:
        return InterviewActionResponse(session=_serialize_session(session))

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="start_interview",
        user_id=current_user["id"],
        input_text="开始模拟面试并生成第一题",
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    rounds = ((session.plan_json or {}).get("rounds") or [])
    first_round = rounds[0] if rounds else {}
    round_goal = first_round.get("goal", "自我介绍与岗位匹配")
    try:
        with observer:
            question = await _generate_question(
                resume_content=resume_content,
                history=[],
                prompt=_build_first_round_prompt(first_round.get("type", "warmup"), round_goal),
                event_callback=observer.on_runtime_event,
            )
    except Exception as exc:
        observer.fail(str(exc))
        raise
    if not question:
        question = "先用两分钟做一个和目标岗位最相关的自我介绍。"

    turn = InterviewTurn(
        session_id=session.id,
        turn_index=1,
        round_index=0,
        question=question,
        question_type=rounds[0]["type"] if rounds else "warmup",
        intent=round_goal,
        status="asked",
        asked_at=_now(),
    )
    session.status = "waiting_user_answer"
    session.current_turn_index = 1
    session.started_at = session.started_at or _now()
    db.add(turn)
    db.commit()
    db.refresh(session)
    observer.finish(question)
    return InterviewActionResponse(
        session=_serialize_session(session),
        message=question,
        next_action="answer",
    )


@router.post("/{session_id}/answer", response_model=InterviewActionResponse)
async def answer_interview(
    session_id: int,
    request: InterviewAnswerRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于处理一次回答并生成下一题或结束面试。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interview already completed")

    turn = _latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active question to answer")

    answer_text = request.answer.strip()

    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="answer_interview",
        user_id=current_user["id"],
        input_text=answer_text,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )
    history = _build_turn_history(session, current_turn=turn, pending_answer=answer_text)
    background_session_factory = _build_session_factory(db)

    turn.answer = answer_text
    turn.answered_at = _now()
    turn.status = "done"

    rounds = ((session.plan_json or {}).get("rounds") or [])
    current_round = rounds[turn.round_index] if turn.round_index < len(rounds) else {}
    max_q = int(current_round.get("max_questions") or 2)
    questions_in_round = sum(1 for t in session.turns if t.round_index == turn.round_index)
    force_next_round = questions_in_round >= max_q

    if force_next_round:
        next_round_index = turn.round_index + 1
    else:
        next_round_index = turn.round_index

    if force_next_round and next_round_index >= len(rounds):
        session.status = "completed"
        session.ended_at = _now()
        session.report_data = _build_interview_report(
            turns=list(session.turns or []),
            target_title=session.target_title or "",
            target_company=session.target_company or "",
        )
        db.commit()
        db.refresh(session)
        evaluation_task = asyncio.create_task(
            _persist_turn_evaluation(
                session_factory=background_session_factory,
                user_id=current_user["id"],
                session_id=session.id,
                turn_id=turn.id,
                question=turn.question,
                answer=answer_text,
                resume_content=resume_content,
                history=history,
                event_callback=None,
            )
        )
        evaluation_task.add_done_callback(_log_async_task_failure)
        observer.finish("interview_completed")
        return InterviewActionResponse(
            session=_serialize_session(session),
            next_action="completed",
        )

    if force_next_round:
        next_round = rounds[next_round_index]
        prompt = _build_next_round_prompt(next_round["type"], next_round["goal"])
        new_round_index = next_round_index
        new_round_type = next_round["type"]
        new_round_goal = next_round["goal"]
    else:
        remaining = max_q - questions_in_round
        prompt = _build_same_round_prompt(current_round["type"], current_round["goal"], remaining)
        new_round_index = turn.round_index
        new_round_type = current_round["type"]
        new_round_goal = current_round["goal"]

    evaluation_task = asyncio.create_task(
        _persist_turn_evaluation(
            session_factory=background_session_factory,
            user_id=current_user["id"],
            session_id=session.id,
            turn_id=turn.id,
            question=turn.question,
            answer=answer_text,
            resume_content=resume_content,
            history=history,
            event_callback=None,
        )
    )
    evaluation_task.add_done_callback(_log_async_task_failure)

    try:
        with observer:
            question = await _generate_question(
                resume_content=resume_content,
                history=history,
                prompt=prompt,
                event_callback=observer.on_runtime_event,
            )
    except Exception as exc:
        observer.fail(str(exc))
        raise
    if not question:
        question = "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"

    next_turn = InterviewTurn(
        session_id=session.id,
        turn_index=session.current_turn_index + 1,
        round_index=new_round_index,
        question=question,
        question_type=new_round_type,
        intent=new_round_goal,
        status="asked",
        asked_at=_now(),
    )
    session.current_turn_index += 1
    session.current_round_index = new_round_index
    session.status = "waiting_user_answer"
    db.add(next_turn)
    db.commit()
    db.refresh(session)
    observer.finish(question)
    return InterviewActionResponse(
        session=_serialize_session(session),
        message=question,
        next_action="next_question",
    )


@router.post("/{session_id}/answer/stream")
async def answer_interview_stream(
    session_id: int,
    http_request: Request,
    request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于流式生成下一题并在结束时返回最新 session。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    if session.status == "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Interview already completed")

    turn = _latest_turn(session)
    if not turn or turn.status != "asked":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No active question to answer")

    answer_text = request.answer.strip()
    resume = _get_resume_for_user(db, session.resume_id, current_user["id"])
    resume_content = resume.content if isinstance(resume.content, dict) else {}
    run_id = uuid4().hex
    observer = LangfuseRunObserver(
        run_id=run_id,
        agent_type="interview",
        run_kind="answer_interview_stream",
        user_id=current_user["id"],
        input_text=answer_text,
        metadata={
            "interview_session_id": session.id,
            "resume_id": session.resume_id,
            "request_id": getattr(http_request.state, "request_id", None),
        },
    )

    history = _build_turn_history(session, current_turn=turn, pending_answer=answer_text)
    background_session_factory = _build_session_factory(db)

    turn.answer = answer_text
    turn.answered_at = _now()
    turn.status = "done"
    db.commit()
    db.refresh(session)

    async def generate():
        nonlocal session
        with log_context(
            request_id=getattr(http_request.state, "request_id", None),
            session_id=str(session_id),
        ):
            logger.info("Interview stream started")
            with observer:
                rounds = ((session.plan_json or {}).get("rounds") or [])
                current_round = rounds[turn.round_index] if turn.round_index < len(rounds) else {}
                max_q = int(current_round.get("max_questions") or 2)
                questions_in_round = sum(1 for t in session.turns if t.round_index == turn.round_index)
                force_next_round = questions_in_round >= max_q

                if force_next_round:
                    next_round_index = turn.round_index + 1
                else:
                    next_round_index = turn.round_index

                is_completed = force_next_round and next_round_index >= len(rounds)

                # 1. 决定 prompt
                if is_completed:
                    prompt = None
                elif force_next_round:
                    next_round = rounds[next_round_index]
                    prompt = _build_next_round_prompt(next_round["type"], next_round["goal"])
                else:
                    remaining = max_q - questions_in_round
                    prompt = _build_same_round_prompt(current_round["type"], current_round["goal"], remaining)

                queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
                accumulated = ""

                async def stream_next_question() -> None:
                    """用于把下一题的 token 按流式事件推入队列。"""
                    nonlocal accumulated
                    if prompt is None:
                        await queue.put({"type": "question_complete"})
                        return
                    try:
                        async for chunk in _interviewer_agent.chat_stream(
                            user_message=prompt,
                            resume_content=resume_content,
                            conversation_history=history,
                            event_callback=observer.on_runtime_event,
                        ):
                            token = chunk.get("content") or ""
                            if token:
                                accumulated += token
                                await queue.put({"type": "token", "content": token})
                    except Exception as e:
                        observer.fail(str(e))
                        logger.warning("Stream generation failed: %s", e)
                    finally:
                        await queue.put({"type": "question_complete"})

                async def stream_turn_evaluation() -> None:
                    """用于并行生成当前题评估，并把结果作为事件推入队列。"""
                    if session.mode != "practice":
                        await queue.put({"type": "evaluation_complete"})
                        return
                    try:
                        evaluation_text = await _persist_turn_evaluation(
                            session_factory=background_session_factory,
                            user_id=current_user["id"],
                            session_id=session.id,
                            turn_id=turn.id,
                            question=turn.question,
                            answer=answer_text,
                            resume_content=resume_content,
                            history=history,
                            event_callback=None,
                        )
                        await queue.put(
                            {
                                "type": "evaluation",
                                "turn_id": turn.id,
                                "evaluation": evaluation_text,
                            }
                        )
                    finally:
                        await queue.put({"type": "evaluation_complete"})

                question_task = asyncio.create_task(stream_next_question())
                question_task.add_done_callback(_log_async_task_failure)
                evaluation_task = asyncio.create_task(stream_turn_evaluation())
                evaluation_task.add_done_callback(_log_async_task_failure)

                question_completed = False
                evaluation_completed = session.mode != "practice"
                done_emitted = False

                while not (done_emitted and evaluation_completed):
                    event = await queue.get()
                    event_type = str(event.get("type") or "")

                    if event_type == "token":
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        continue

                    if event_type == "evaluation":
                        yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                        continue

                    if event_type == "evaluation_complete":
                        evaluation_completed = True
                        continue

                    if event_type != "question_complete":
                        continue

                    question_completed = True
                    question = accumulated.strip() or None

                    if is_completed:
                        session.status = "completed"
                        session.ended_at = _now()
                        session.report_data = _build_interview_report(
                            turns=list(session.turns or []),
                            target_title=session.target_title or "",
                            target_company=session.target_company or "",
                        )
                        db.commit()
                        db.refresh(session)
                        done_payload = {
                            "type": "done",
                            "next_action": "completed",
                            "session": _serialize_session(session),
                        }
                    else:
                        if force_next_round:
                            next_round = rounds[next_round_index]
                            new_round_type = next_round["type"]
                            new_round_goal = next_round["goal"]
                        else:
                            new_round_type = current_round["type"]
                            new_round_goal = current_round["goal"]
                        if not question:
                            question = "挑一个你最能代表岗位匹配度的项目，讲清楚背景、目标、你的动作和结果。"
                        next_turn = InterviewTurn(
                            session_id=session.id,
                            turn_index=session.current_turn_index + 1,
                            round_index=next_round_index,
                            question=question,
                            question_type=new_round_type,
                            intent=new_round_goal,
                            status="asked",
                            asked_at=_now(),
                        )
                        session.current_turn_index += 1
                        session.current_round_index = next_round_index
                        session.status = "waiting_user_answer"
                        db.add(next_turn)
                        db.commit()
                        db.refresh(session)
                        done_payload = {
                            "type": "done",
                            "next_action": "next_question",
                            "message": question,
                            "session": _serialize_session(session),
                        }

                    logger.info("Interview stream completed next_action=%s", done_payload["next_action"])
                    observer.finish(done_payload.get("message") or done_payload["next_action"])
                    yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"
                    done_emitted = True

                if not question_completed:
                    await question_task
                if not evaluation_completed:
                    await evaluation_task

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{session_id}/end", response_model=InterviewActionResponse)
async def end_interview(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于让用户主动结束当前面试。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")

    turns = list(session.turns or [])
    session.status = "completed"
    session.ended_at = _now()
    session.report_data = _build_interview_report(
        turns=turns,
        target_title=session.target_title or "",
        target_company=session.target_company or "",
        ended_by_user=True,
    )
    db.commit()
    db.refresh(session)
    return InterviewActionResponse(session=_serialize_session(session), next_action="completed")


@router.get("/{session_id}/report", response_model=InterviewActionResponse)
async def get_interview_report(
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """用于返回指定面试的最终报告视图。"""
    session = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found")
    return InterviewActionResponse(session=_serialize_session(session))
