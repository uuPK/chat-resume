"""
面试规划服务模块

用于集中管理结构化面试的阶段定义和提问提示词拼装。
"""

from __future__ import annotations

from typing import Any

from app.schemas.resume import dump_resume_content_for_frontend

# 用于统一定义不同面试阶段的固定约束，避免路由层散落 prompt 片段。
ROUND_INSTRUCTIONS: dict[str, str] = {
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


def get_round_instructions(question_type: str) -> str:
    """用于按面试阶段返回固定提问约束。"""
    return ROUND_INSTRUCTIONS.get(question_type, "")


def build_first_round_prompt(question_type: str, round_goal: str) -> str:
    """用于生成首轮提问时的系统提示。"""
    instructions = get_round_instructions(question_type)
    return (
        f"{instructions}\n开始一场模拟面试。"
        f"当前阶段目标：{round_goal}。请直接提出第一题。"
    )


def build_next_round_prompt(question_type: str, round_goal: str) -> str:
    """用于生成切换到下一轮时的提问提示。"""
    instructions = get_round_instructions(question_type)
    return f"{instructions}\n进入下一阶段：{round_goal}。请直接提出该阶段的第一个问题。"


def build_same_round_prompt(
    question_type: str, round_goal: str, remaining_questions: int
) -> str:
    """用于生成同一轮内继续追问时的提问提示。"""
    instructions = get_round_instructions(question_type)
    return (
        f"{instructions}\n当前面试阶段：{round_goal}"
        f"（本阶段还可再问 {remaining_questions} 题）。"
        "根据候选人刚才的回答，决定追问细节还是转向该阶段下一个核心问题。"
    )


def build_hint_prompt(
    *,
    question_type: str,
    question: str,
    round_goal: str,
    target_title: str,
) -> str:
    """用于生成练习模式下的答题提示词。"""
    instructions = get_round_instructions(question_type)
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


def rounds_for_type(interview_type: str) -> list[dict[str, Any]]:
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
            {
                "type": "resume_deep_dive",
                "goal": "项目真实性与个人贡献",
                "max_questions": 4,
            },
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


def build_plan(resume_content: dict[str, Any], interview_type: str) -> dict[str, Any]:
    """用于构建一场结构化面试的初始计划。"""
    normalized_content = dump_resume_content_for_frontend(resume_content or {})
    return {
        "rounds": rounds_for_type(interview_type),
        "resume_highlights": {
            "work_experience_count": len(
                normalized_content.get("work_experience") or []
            ),
            "project_count": len(normalized_content.get("projects") or []),
            "target_title": (
                (normalized_content.get("job_application") or {}).get("target_title")
                or ""
            ),
            "target_company": (
                (normalized_content.get("job_application") or {}).get("target_company")
                or ""
            ),
        },
    }
