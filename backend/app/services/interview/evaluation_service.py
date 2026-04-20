"""
面试评估服务模块

用于集中处理题后评估、报告生成、提示兜底和问题生成共享逻辑。
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Optional

from sqlalchemy.orm import Session, sessionmaker

from app.agents.interview import InterviewerAgent
from app.models import InterviewSession, InterviewTurn

logger = logging.getLogger(__name__)

_interviewer_agent = InterviewerAgent()


def extract_keywords(text: str, limit: int = 6) -> list[str]:
    """用于从问题或岗位信息里提取可复用的关键词。"""
    keywords: list[str] = []
    for keyword in re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", text or ""):
        normalized = keyword.strip()
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in {
            "请问",
            "一下",
            "一个",
            "这个",
            "那个",
            "为什么",
            "怎么",
            "是否",
        }:
            continue
        if lowered not in {item.lower() for item in keywords}:
            keywords.append(normalized)
        if len(keywords) >= limit:
            break
    return keywords


def contains_keyword(text: str, keywords: list[str]) -> bool:
    """用于判断一段回答是否命中了问题或岗位关键词。"""
    normalized = (text or "").lower()
    return any(keyword.lower() in normalized for keyword in keywords)


def analyze_turn(turn: InterviewTurn) -> dict[str, bool]:
    """用于把单题回答转成报告生成需要的基础信号。"""
    answer = (turn.answer or "").strip()
    question_keywords = extract_keywords(turn.question, limit=4)
    answer_keywords = extract_keywords(answer, limit=8)

    directly_answers = not question_keywords or contains_keyword(
        answer, question_keywords
    )
    has_ownership = any(
        token in answer for token in ("我", "自己", "主导", "负责", "推进")
    )
    has_metrics = any(char.isdigit() for char in answer)
    has_context = len(answer) >= 60
    has_depth = len(answer) >= 120
    has_reflection = any(
        token in answer for token in ("复盘", "总结", "学到", "改进", "下次")
    )
    mentions_result = (
        any(
            token in answer
            for token in ("结果", "效果", "提升", "增长", "降低", "优化")
        )
        or has_metrics
    )

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


def build_report_dimension(
    title: str, assessment: str, evidence: str, advice: str
) -> dict[str, str]:
    """用于统一构造前端可直接展示的报告维度项。"""
    return {
        "title": title,
        "assessment": assessment,
        "evidence": evidence,
        "advice": advice,
    }


def build_interview_report(
    *,
    turns: list[InterviewTurn],
    target_title: str = "",
    target_company: str = "",
    ended_by_user: bool = False,
) -> dict[str, Any]:
    """用于把整场问答整理成结构化面试报告。"""
    answered_turns = [turn for turn in turns if (turn.answer or "").strip()]
    if not answered_turns:
        summary_prefix = (
            "本场面试已提前结束。" if ended_by_user else "本场模拟面试已结束。"
        )
        return {
            "summary": (
                f"{summary_prefix} 当前样本还不足，"
                "建议至少完成 3 题后再看完整复盘。"
            ),
            "dimensions": [
                build_report_dimension(
                    "切题度",
                    "当前样本不足，暂时无法判断切题稳定性。",
                    "还没有形成可用于评估的完整回答。",
                    "下一轮先完成 3 道题，并且每题先用一句话直接回答问题。",
                ),
                build_report_dimension(
                    "表达清晰度",
                    "当前样本不足，暂时无法判断表达组织。",
                    "还没有形成可用于评估的完整回答。",
                    "先按背景、动作、结果三段式组织回答。",
                ),
                build_report_dimension(
                    "项目/经历深度",
                    "当前样本不足，暂时无法判断项目展开能力。",
                    "还没有形成可用于评估的完整回答。",
                    "下一轮优先补具体场景、个人动作和结果指标。",
                ),
                build_report_dimension(
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

    analyzed_turns = [(turn, analyze_turn(turn)) for turn in answered_turns]
    total = len(analyzed_turns)
    direct_count = sum(1 for _, signal in analyzed_turns if signal["directly_answers"])
    context_count = sum(1 for _, signal in analyzed_turns if signal["has_context"])
    ownership_count = sum(1 for _, signal in analyzed_turns if signal["has_ownership"])
    metrics_count = sum(1 for _, signal in analyzed_turns if signal["has_metrics"])
    result_count = sum(1 for _, signal in analyzed_turns if signal["mentions_result"])
    reflection_count = sum(
        1
        for turn, signal in analyzed_turns
        if turn.question_type == "behavioral" and signal["has_reflection"]
    )
    role_keywords = extract_keywords(f"{target_company} {target_title}", limit=6)
    role_match_count = sum(
        1
        for turn, _signal in analyzed_turns
        if role_keywords and contains_keyword(turn.answer or "", role_keywords)
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
    if (
        any(turn.question_type == "behavioral" for turn, _signal in analyzed_turns)
        and reflection_count == 0
    ):
        recurring_issues.append("行为题里复盘不足，缺少你从事件里学到了什么。")
    recurring_issues = recurring_issues[:3] or [
        "整体完成度尚可，下一轮重点把回答说得更具体。"
    ]

    if direct_count >= max(1, total - 1):
        strongest_point = "多数回答能先回应问题本身"
    elif ownership_count >= max(1, total - 1):
        strongest_point = "部分回答已经能讲清个人贡献"
    elif metrics_count >= max(1, total // 2):
        strongest_point = "部分回答已经开始补充结果指标"
    else:
        strongest_point = "能持续完成整场问答"

    issue_pressure = (
        total - direct_count + total - ownership_count + total - metrics_count
    )
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

    clarity_hits = sum(
        1
        for _, signal in analyzed_turns
        if signal["has_context"] and signal["directly_answers"]
    )
    if clarity_hits >= max(1, total - 1):
        clarity_assessment = "回答组织相对清楚，听者能跟上你的表达节奏。"
    elif clarity_hits >= max(1, total // 2):
        clarity_assessment = "表达有基础，但部分回答仍然过短或跳步骤。"
    else:
        clarity_assessment = "表达组织偏弱，很多回答缺少基本的背景和过程说明。"
    clarity_evidence = f"{clarity_hits}/{total} 题同时具备基本切题和背景展开。"
    clarity_advice = "统一按背景、动作、结果三段式说，避免只给一句结论。"

    depth_hits = sum(
        1
        for _, signal in analyzed_turns
        if signal["has_ownership"] and signal["mentions_result"]
    )
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
    depth_advice = (
        "每个项目都固定补三件事：你具体做了什么、为什么这样做、最后结果怎样。"
    )

    if not role_keywords:
        role_assessment = "这场更多基于简历追问，岗位匹配表达样本还不够。"
        role_evidence = "当前没有足够明确的目标岗位关键词可用于判断匹配度。"
        role_advice = "下轮开始前把目标岗位和公司补全，并准备一版岗位动机。"
    elif role_match_count >= max(1, total // 2):
        role_assessment = "回答里已经能主动贴近目标岗位，匹配表达比较自然。"
        role_evidence = (
            f"{role_match_count}/{total} 题回答中主动提到了岗位或公司相关关键词。"
        )
        role_advice = "继续把岗位关键词和代表项目绑定起来，说清楚为什么你适合这个岗位。"
    else:
        role_assessment = "岗位匹配点表达偏弱，回答更多停留在经历本身，没有主动贴岗位。"
        role_evidence = (
            f"{role_match_count}/{total} 题回答中主动提到了岗位或公司相关关键词。"
        )
        role_advice = "每次回答最后补一句：这段经历为什么和目标岗位直接相关。"

    next_training_plan: list[str] = []
    if direct_count <= max(1, total // 2):
        next_training_plan.append("先练“直接回答问题”，每题先用一句话给结论，再展开。")
    if ownership_count <= max(1, total // 2):
        next_training_plan.append(
            "再练“个人贡献”，每个项目都明确说出你亲自负责的动作和决策。"
        )
    if metrics_count <= max(1, total // 2):
        next_training_plan.append("再练“量化结果”，每题至少补一个结果指标或业务影响。")
    if (
        any(turn.question_type == "behavioral" for turn, _signal in analyzed_turns)
        and reflection_count == 0
    ):
        next_training_plan.append("行为题补一层复盘，说明你从这件事里学到了什么。")
    next_training_plan = next_training_plan[:3] or [
        "下一轮继续保持直接回答问题的习惯。",
        "把已有项目答案压缩成更稳定的背景、动作、结果结构。",
    ]

    resume_feedback: list[str] = []
    if metrics_count <= max(1, total // 2):
        resume_feedback.append(
            "简历里的项目成果需要补成可直接复述的数字，否则面试里也很难自然讲出指标。"
        )
    if ownership_count <= max(1, total // 2):
        resume_feedback.append(
            "简历里的项目描述要更突出“我主导/我负责”的部分，降低团队口吻。"
        )
    if direct_count <= max(1, total // 2):
        resume_feedback.append(
            "简历里的项目背景和目标可以写得更清楚，方便面试时快速切题。"
        )
    if role_keywords and role_match_count <= max(1, total // 3):
        resume_feedback.append(
            (
                "简历里需要更明显地突出与"
                f"“{target_title or target_company}”直接相关的能力和经历。"
            )
        )
    resume_feedback = resume_feedback[:3] or [
        "简历和面试表达基本一致，下一轮重点继续打磨结果和细节。"
    ]

    return {
        "summary": summary,
        "dimensions": [
            build_report_dimension(
                "切题度", focus_assessment, focus_evidence, focus_advice
            ),
            build_report_dimension(
                "表达清晰度", clarity_assessment, clarity_evidence, clarity_advice
            ),
            build_report_dimension(
                "项目/经历深度", depth_assessment, depth_evidence, depth_advice
            ),
            build_report_dimension(
                "岗位匹配度", role_assessment, role_evidence, role_advice
            ),
        ],
        "recurring_issues": recurring_issues,
        "weaknesses": recurring_issues,
        "next_training_plan": next_training_plan,
        "resume_feedback": resume_feedback,
    }


def fallback_hint(turn: InterviewTurn) -> list[str]:
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


async def generate_question(
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


def build_turn_history(
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


def build_session_factory(db: Session) -> sessionmaker:
    """用于给后台评估任务创建独立数据库会话工厂。"""
    return sessionmaker(autocommit=False, autoflush=False, bind=db.get_bind())


def log_async_task_failure(task: asyncio.Task[Any]) -> None:
    """用于统一记录后台异步任务里的异常，避免静默失败。"""
    try:
        task.result()
    except Exception:
        logger.exception("Interview background task failed")


def fallback_evaluation(question: str, answer: str) -> str:
    """用于在 LLM 评估失败时提供简短文本兜底结果。"""
    normalized = (answer or "").strip()
    gaps: list[str] = []
    missing_question_focus = False
    question_keywords = re.findall(r"[\u4e00-\u9fffA-Za-z]{2,}", question or "")
    if question_keywords and not any(
        keyword in normalized for keyword in question_keywords[:4]
    ):
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
        return (
            "面试系统反馈："
            + "；".join(gaps[:2])
            + "。建议先直接回答问题，再补充个人贡献和结果。"
        )
    return (
        "面试系统反馈：回答基本切题，但还可以补充更具体的个人动作和结果，让信息更完整。"
    )


async def evaluate_answer_with_llm(
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
        return fallback_evaluation(question, answer)
    except Exception:
        logger.warning("LLM evaluation failed, falling back to rule-based evaluation")
        return fallback_evaluation(question, answer)


async def persist_turn_evaluation(
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
    evaluation_text = await evaluate_answer_with_llm(
        question=question,
        answer=answer,
        resume_content=resume_content,
        history=history,
        event_callback=event_callback,
    )

    db = session_factory()
    try:
        session = (
            db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
        )
        turn = db.query(InterviewTurn).filter(InterviewTurn.id == turn_id).first()
        if (
            not session
            or session.user_id != user_id
            or not turn
            or turn.session_id != session_id
        ):
            return evaluation_text

        turn.evaluation = evaluation_text
        if session.status == "completed" and isinstance(session.report_data, dict):
            session.report_data = build_interview_report(
                turns=list(session.turns or []),
                target_title=session.target_title or "",
                target_company=session.target_company or "",
                ended_by_user="已提前结束"
                in str((session.report_data or {}).get("summary") or ""),
            )
        db.commit()
        return evaluation_text
    finally:
        db.close()
