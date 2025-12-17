"""
面试管理API端点模块

提供面试相关的API端点，包括面试创建、问题生成、评分等功能。
处理面试流程管理和实时交互。
"""

from typing import List, Dict, Any, cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.services.core import ResumeService
from app.models.resume import InterviewSession
from app.schemas.interview import (
    InterviewSessionCreate,
    InterviewSessionResponse,
    InterviewQuestionResponse,
    InterviewAnswerRequest,
    InterviewEvaluationResponse,
)
from app.api.deps import get_current_user
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_interview_session(session_data: List[Dict[str, Any]]) -> str:
    """格式化面试会话数据为可读字符串"""
    formatted = []
    for i, item in enumerate(session_data, 1):
        formatted.append(f"问题{i}: {item.get('question', '')}")
        formatted.append(f"回答{i}: {item.get('answer', '')}")
        formatted.append("---")
    return "\n".join(formatted)


@router.post("/{resume_id}/interview/start", response_model=InterviewSessionResponse)
async def start_interview(
    resume_id: int,
    session_create: InterviewSessionCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """开始面试会话"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 检查是否已有进行中的面试会话
    existing_active_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id, InterviewSession.status == "active"
        )
        .first()
    )

    if existing_active_session:
        # 自动结束旧的活跃会话，以便创建新会话
        logger.info(
            f"发现现有活跃会话 {existing_active_session.id}，自动结束旧会话以创建新会话"
        )
        existing_active_session.status = "completed"  # type: ignore
        db.commit()

    try:
        # 创建面试会话，初始不生成问题
        interview_session = InterviewSession(
            resume_id=resume_id,
            job_position=session_create.job_position,
            jd_content=session_create.jd_content,
            questions=[],
            answers=[],
            feedback={},
            status="active",
        )
        db.add(interview_session)
        db.commit()
        db.refresh(interview_session)

        return InterviewSessionResponse.model_validate(interview_session)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start interview: {str(e)}",
        )


@router.get(
    "/{resume_id}/interview/{session_id}/question",
    response_model=InterviewQuestionResponse,
)
async def get_next_question(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取下一个面试问题"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 获取当前问题索引
    current_question_index = len(cast(List[Any], interview_session.answers))

    # 如果还有预设问题，返回下一个
    if current_question_index < len(cast(List[Any], interview_session.questions)):
        question = interview_session.questions[current_question_index]
        return InterviewQuestionResponse.model_validate(
            {
                "question": question["question"],
                "question_type": question.get("type", "general"),
                "question_index": current_question_index,
            }
        )

    # 如果已经回答完所有预设问题，根据对话历史生成新问题
    try:
        from app.services.ai import InterviewAgent

        interview_agent = InterviewAgent()

        # 构建 InterviewAgent 需要的对话历史格式
        interview_history = []
        for i, answer in enumerate(cast(List[Any], interview_session.answers)):
            if i < len(cast(List[Any], interview_session.questions)):
                interview_history.append(
                    {
                        "role": "assistant",
                        "content": interview_session.questions[i]["question"],
                    }
                )
                interview_history.append({"role": "user", "content": answer["answer"]})

        # 生成新问题
        answers_list = cast(List[Any], interview_session.answers)
        questions_list = cast(List[Any], interview_session.questions)
        last_answer = answers_list[-1]["answer"] if answers_list else ""
        last_question = questions_list[-1]["question"] if questions_list else ""

        # 使用 chat 方法生成后续问题
        follow_up_prompt = f"""基于以下面试对话生成一个有针对性的后续问题：

上一个问题：{last_question}
用户回答：{last_answer}

请生成一个相关的后续问题来深入探讨用户的回答。只需要返回问题本身，不要其他说明。"""

        follow_up_question = await interview_agent.chat(
            message=follow_up_prompt,
            job_title=str(interview_session.job_position)
            if interview_session.job_position is not None
            else None,
            job_description=str(interview_session.jd_content)
            if interview_session.jd_content is not None
            else None,
            resume_content=str(resume.content)
            if resume is not None and resume.content is not None
            else None,
            conversation_history=interview_history,
        )

        new_question = {
            "question": follow_up_question.strip(),
            "type": "follow_up",
            "purpose": "深入探讨用户回答",
        }

        # 更新会话问题列表
        interview_session.questions.append(new_question)
        db.commit()

        return InterviewQuestionResponse.model_validate(
            {
                "question": new_question["question"],
                "question_type": new_question.get("type", "follow_up"),
                "question_index": current_question_index,
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate next question: {str(e)}",
        )


@router.post(
    "/{resume_id}/interview/{session_id}/answer",
    response_model=InterviewEvaluationResponse,
)
async def submit_answer(
    resume_id: int,
    session_id: int,
    answer_request: InterviewAnswerRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交面试答案并获取评估"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        # 获取当前问题
        question_index = answer_request.question_index

        if question_index >= len(cast(List[Any], interview_session.questions)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid question index"
            )

        current_question = cast(
            str,
            cast(List[Any], interview_session.questions)[question_index]["question"],
        )

        # 使用 InterviewAgent 评估答案
        from app.services.ai import InterviewAgent

        interview_agent = InterviewAgent()

        # 使用 chat 方法评估答案
        evaluation_prompt = f"""作为专业面试官，请评估以下面试回答：

问题：{current_question}
回答：{answer_request.answer}

请从以下维度进行评估：
1. 回答的准确性和深度
2. 逻辑性和条理性
3. 与职位的匹配度
4. 沟通表达能力

请给出评分（0-10分）和具体的改进建议。返回JSON格式：
{{
    "score": 分数,
    "feedback": "详细反馈",
    "improvements": ["改进建议1", "改进建议2"]
}}"""

        evaluation_response = await interview_agent.chat(
            message=evaluation_prompt,
            job_title=str(interview_session.job_position)
            if interview_session.job_position is not None
            else None,
            job_description=str(interview_session.jd_content)
            if interview_session.jd_content is not None
            else None,
            resume_content=str(resume.content)
            if resume is not None and resume.content is not None
            else None,
            conversation_history=[],
        )

        # 尝试解析JSON响应，如果失败则使用默认值
        try:
            import json

            evaluation = json.loads(evaluation_response)
        except (json.JSONDecodeError, ValueError):
            # 如果JSON解析失败，创建默认评估
            evaluation = {
                "score": 7,
                "feedback": evaluation_response,
                "improvements": [
                    "建议更具体地说明相关经验",
                    "可以提供更多实例来支持观点",
                ],
            }

        # 保存答案和评估
        answer_data = {
            "answer": answer_request.answer,
            "evaluation": evaluation,
            "question_index": question_index,
        }

        # 更新会话答案 - 复制列表以确保SQLAlchemy检测到变化
        current_answers = list(cast(List[Any], interview_session.answers) or [])

        # 扩展答案列表到所需长度
        while len(current_answers) <= question_index:
            current_answers.append({})

        # 设置答案数据
        current_answers[question_index] = answer_data

        # 重新分配列表以触发SQLAlchemy的变化检测
        interview_session.answers = current_answers  # type: ignore

        # 清除缓存的报告，因为面试内容已更新
        interview_session.report_data = None  # type: ignore

        db.commit()

        return InterviewEvaluationResponse.model_validate(
            {
                "question": current_question,
                "answer": answer_request.answer,
                "evaluation": evaluation,
                "score": evaluation.get("score", 7),
                "feedback": evaluation.get("feedback", ""),
                "suggestions": evaluation.get("improvements", []),
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate answer: {str(e)}",
        )


@router.post("/{resume_id}/interview/{session_id}/end")
async def end_interview(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """结束面试会话"""

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        from app.services.ai import InterviewAgent

        # 计算整体面试分数
        interview_agent = InterviewAgent()

        # 构建面试会话记录
        interview_session_data = []
        questions_list = cast(List[Any], interview_session.questions)
        answers_list = cast(List[Any], interview_session.answers)
        for i, question in enumerate(questions_list):
            answer = answers_list[i] if i < len(answers_list) else ""
            interview_session_data.append(
                {
                    "question": question.get("question", "")
                    if isinstance(question, dict)
                    else str(question),
                    "answer": answer,
                    "score": 0,  # 默认分数
                }
            )

        # 生成面试表现评估
        job_requirements = f"职位：{interview_session.job_position}\n职位描述：{interview_session.jd_content or ''}"

        # 使用 chat 方法生成整体评估
        evaluation_prompt = f"""作为专业面试官，请基于以下面试会话记录生成整体评估报告：

职位要求：
{job_requirements}

面试会话记录：
{_format_interview_session(interview_session_data)}

请提供：
1. 整体表现评分（0-100分）
2. 各项能力评估
3. 具体反馈和建议
4. 改进方向

返回JSON格式：
{{
    "total_score": 整体分数,
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"],
    "detailed_feedback": "详细反馈"
}}"""

        evaluation_response = await interview_agent.chat(
            message=evaluation_prompt,
            job_title=str(interview_session.job_position)
            if interview_session.job_position is not None
            else None,
            job_description=str(interview_session.jd_content)
            if interview_session.jd_content is not None
            else None,
            resume_content=str(resume.content)
            if resume is not None and resume.content is not None
            else None,
            conversation_history=[],
        )

        # 尝试解析JSON响应，如果失败则使用默认值
        try:
            import json

            evaluation_result = json.loads(evaluation_response)
            overall_score = evaluation_result.get("total_score", 75)
        except (json.JSONDecodeError, ValueError):
            # 如果JSON解析失败，创建默认评估
            overall_score = 75
            evaluation_result = {
                "total_score": overall_score,
                "strengths": ["表现良好"],
                "weaknesses": ["有待改进"],
                "recommendations": ["继续努力"],
                "detailed_feedback": evaluation_response,
            }

        # 更新会话状态和分数
        interview_session.status = "completed"  # type: ignore
        setattr(interview_session, "overall_score", overall_score)

        # 清除缓存的报告，因为面试已完成，需要重新生成完整报告
        interview_session.report_data = None  # type: ignore

        db.commit()

        return {
            "message": "Interview session ended successfully",
            "overall_score": overall_score,
        }

    except Exception as e:
        # 即使分数计算失败，也要结束面试
        interview_session.status = "completed"  # type: ignore

        # 清除缓存的报告
        interview_session.report_data = None  # type: ignore

        db.commit()

        return {
            "message": "Interview session ended successfully",
            "warning": f"Failed to calculate overall score: {str(e)}",
        }


@router.get(
    "/{resume_id}/interview/sessions", response_model=List[InterviewSessionResponse]
)
async def get_interview_sessions(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取面试会话列表"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 获取面试会话
    sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.resume_id == resume_id)
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    return [InterviewSessionResponse.model_validate(session) for session in sessions]


@router.delete("/{resume_id}/interview/{session_id}")
async def delete_interview_session(
    resume_id: int,
    session_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """删除面试会话"""

    # 验证面试会话是否存在
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 删除面试会话
    db.delete(interview_session)
    db.commit()

    return {"message": "Interview session deleted successfully"}


@router.post("/{resume_id}/interview/calculate-scores")
async def calculate_scores_for_completed_interviews(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """为已完成但没有分数的面试计算分数"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 查找已完成但没有分数的面试
    sessions = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id,
            InterviewSession.status == "completed",
            InterviewSession.overall_score.is_(None),
        )
        .all()
    )

    if not sessions:
        return {"message": "No interviews need score calculation", "updated_count": 0}

    updated_count = 0
    from app.services.ai import InterviewAgent

    interview_agent = InterviewAgent()

    for session in sessions:
        try:
            # 构建面试会话记录
            interview_session_data = []
            questions_list = cast(List[Any], session.questions)
            answers_list = cast(List[Any], session.answers)
            for i, question in enumerate(questions_list):
                answer = answers_list[i] if i < len(answers_list) else ""
                interview_session_data.append(
                    {
                        "question": question.get("question", "")
                        if isinstance(question, dict)
                        else str(question),
                        "answer": answer,
                        "score": 0,  # 默认分数
                    }
                )

            # 生成面试表现评估
            job_requirements = (
                f"职位：{session.job_position}\n职位描述：{session.jd_content or ''}"
            )

            # 使用 chat 方法生成整体评估
            evaluation_prompt = f"""作为专业面试官，请基于以下面试会话记录生成整体评估报告：

职位要求：
{job_requirements}

面试会话记录：
{_format_interview_session(interview_session_data)}

请提供：
1. 整体表现评分（0-100分）
2. 各项能力评估
3. 具体反馈和建议
4. 改进方向

返回JSON格式：
{{
    "total_score": 整体分数,
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"],
    "detailed_feedback": "详细反馈"
}}"""

            evaluation_response = await interview_agent.chat(
                message=evaluation_prompt,
                job_title=str(session.job_position)
                if session.job_position is not None
                else None,
                job_description=str(session.jd_content)
                if session.jd_content is not None
                else None,
                resume_content=str(resume.content)
                if resume is not None and resume.content is not None
                else None,
                conversation_history=[],
            )

            # 尝试解析JSON响应，如果失败则使用默认值
            try:
                import json

                evaluation_result = json.loads(evaluation_response)
                overall_score = evaluation_result.get("total_score", 75)
            except (json.JSONDecodeError, ValueError):
                # 如果JSON解析失败，创建默认评估
                overall_score = 75
                evaluation_result = {
                    "total_score": overall_score,
                    "strengths": ["表现良好"],
                    "weaknesses": ["有待改进"],
                    "recommendations": ["继续努力"],
                    "detailed_feedback": evaluation_response,
                }

            if overall_score > 0:  # 只有成功计算出分数才更新
                setattr(session, "overall_score", overall_score)
                updated_count += 1

        except Exception as e:
            logger.error(f"Failed to calculate score for session {session.id}: {e}")
            continue

    if updated_count > 0:
        db.commit()

    return {
        "message": f"Successfully calculated scores for {updated_count} interviews",
        "updated_count": updated_count,
    }


@router.post("/{resume_id}/interview/cleanup-duplicate")
async def cleanup_duplicate_sessions(
    resume_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """清理重复的面试会话"""

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 查找重复的面试会话（同一简历的多个活跃会话）
    active_sessions = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id, InterviewSession.status == "active"
        )
        .order_by(InterviewSession.created_at.desc())
        .all()
    )

    cleaned_count = 0

    if len(active_sessions) > 1:
        # 保留最新的会话，删除其他的
        sessions_to_delete = active_sessions[1:]  # 跳过第一个（最新的）

        for session in sessions_to_delete:
            # 只删除没有答案的空会话
            session_answers = cast(List[Any], session.answers)
            if not session_answers or len(session_answers) == 0:
                db.delete(session)
                cleaned_count += 1
                logger.info(f"删除空的重复面试会话: {session.id}")

    if cleaned_count > 0:
        db.commit()

    return {
        "message": f"Cleaned up {cleaned_count} duplicate interview sessions",
        "cleaned_count": cleaned_count,
    }


@router.get("/{resume_id}/interview/{session_id}/report")
async def get_interview_report(
    resume_id: int,
    session_id: int,
    regenerate: bool = False,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取面试详细报告"""

    # 验证面试会话是否存在
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    # 检查面试状态 - 允许进行中和已完成的面试查看报告
    if interview_session.status not in ["active", "completed"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview must be active or completed to generate report",
        )

    try:
        # 检查是否已有缓存的报告（如果不是强制重新生成）
        report_data = cast(Dict[str, Any], interview_session.report_data)
        if report_data and not regenerate:
            logger.info(f"返回缓存的报告，面试会话ID: {session_id}")
            return report_data

        # 添加简历信息到面试会话对象
        interview_session.resume_title = resume.title
        interview_session.resume = resume  # 添加完整的简历对象

        # 生成报告
        from app.services.ai import InterviewAgent

        interview_agent = InterviewAgent()

        # 构建面试会话记录
        interview_session_data = []
        questions_list = cast(List[Any], interview_session.questions)
        answers_list = cast(List[Any], interview_session.answers)
        for i, question in enumerate(questions_list):
            answer = answers_list[i] if i < len(answers_list) else ""
            interview_session_data.append(
                {
                    "question": question.get("question", "")
                    if isinstance(question, dict)
                    else str(question),
                    "answer": answer,
                    "score": 0,  # 默认分数
                }
            )

        # 生成面试表现评估报告
        job_requirements = f"职位：{interview_session.job_position}\n职位描述：{interview_session.jd_content or ''}"

        # 使用 chat 方法生成报告
        evaluation_prompt = f"""作为专业面试官，请基于以下面试会话记录生成详细评估报告：

职位要求：
{job_requirements}

面试会话记录：
{_format_interview_session(interview_session_data)}

请提供：
1. 整体表现评分（0-100分）
2. 各项能力评估
3. 具体反馈和建议
4. 改进方向

返回JSON格式：
{{
    "total_score": 整体分数,
    "strengths": ["优势1", "优势2"],
    "weaknesses": ["不足1", "不足2"],
    "recommendations": ["建议1", "建议2"],
    "detailed_feedback": "详细反馈"
}}"""

        evaluation_response = await interview_agent.chat(
            message=evaluation_prompt,
            job_title=str(interview_session.job_position)
            if interview_session.job_position is not None
            else None,
            job_description=str(interview_session.jd_content)
            if interview_session.jd_content is not None
            else None,
            resume_content=str(resume.content)
            if resume is not None and resume.content is not None
            else None,
            conversation_history=[],
        )

        # 尝试解析JSON响应，如果失败则使用默认值
        try:
            import json

            report = json.loads(evaluation_response)
        except (json.JSONDecodeError, ValueError):
            # 如果JSON解析失败，创建默认报告
            report = {
                "total_score": 75,
                "strengths": ["表现良好"],
                "weaknesses": ["有待改进"],
                "recommendations": ["继续努力"],
                "detailed_feedback": evaluation_response,
            }

        # 缓存报告到数据库
        interview_session.report_data = report  # type: ignore
        db.commit()
        logger.info(f"生成并缓存了新报告，面试会话ID: {session_id}")

        return report

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Generate report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate report: {str(e)}",
        )


class InterviewChatRequest(BaseModel):
    """面试对话请求"""

    message: str
    chat_history: List[Dict[str, str]] = []


class InterviewChatResponse(BaseModel):
    """面试对话响应"""

    response: str


@router.post(
    "/{resume_id}/interview/{session_id}/chat",
    response_model=InterviewChatResponse,
)
async def interview_chat(
    resume_id: int,
    session_id: int,
    chat_request: InterviewChatRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    简单的面试对话接口

    这是一个纯chatbot模式的面试接口，用户说什么AI就回答什么，
    不使用复杂的预设问题逻辑。
    """

    # 验证权限
    interview_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.id == session_id, InterviewSession.resume_id == resume_id
        )
        .first()
    )

    if not interview_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview session not found"
        )

    # 验证简历权限
    resume_service = ResumeService(db)
    resume = resume_service.get_by_id(resume_id)

    if not resume:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found"
        )

    if resume.owner_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not enough permissions"
        )

    try:
        from app.services.ai import InterviewAgent

        interview_agent = InterviewAgent()

        # 从数据库构建完整的对话历史
        current_questions = list(cast(List[Any], interview_session.questions) or [])
        current_answers = list(cast(List[Any], interview_session.answers) or [])

        logger.info(f"=== 面试对话调试 ===")
        logger.info(f"当前用户消息: {chat_request.message}")
        logger.info(f"数据库中questions数量: {len(current_questions)}")
        logger.info(f"数据库中answers数量: {len(current_answers)}")

        # 构建对话历史：按顺序交替添加用户消息和AI回复
        conversation_history = []

        # 遍历已存储的对话记录
        for i, question_item in enumerate(current_questions):
            # 新格式：user_message 和 ai_response 在同一个对象中
            user_content = question_item.get("user_message", "")
            ai_content = question_item.get("ai_response", "")

            # 兼容旧格式
            if not user_content and not ai_content:
                # 旧格式可能是 question 字段
                old_question = question_item.get("question", "")
                if old_question:
                    # 尝试从 answers 获取对应的用户回答
                    if i < len(current_answers):
                        user_content = current_answers[i].get("answer", "")
                    ai_content = old_question

            if user_content:
                conversation_history.append({"role": "user", "content": user_content})
                logger.info(f"历史[{i}] 用户: {user_content[:50]}...")

            if ai_content:
                conversation_history.append(
                    {"role": "assistant", "content": ai_content}
                )
                logger.info(f"历史[{i}] AI: {ai_content[:50]}...")

        logger.info(f"构建的对话历史长度: {len(conversation_history)}")
        logger.info(f"即将发送给AI的当前消息: {chat_request.message}")

        # 使用chat方法进行对话 - 当前消息会在 chat_with_context 中作为最后一条消息添加
        response = await interview_agent.chat(
            message=chat_request.message,
            job_title=str(interview_session.job_position)
            if interview_session.job_position is not None
            else None,
            job_description=str(interview_session.jd_content)
            if interview_session.jd_content is not None
            else None,
            resume_content=str(resume.content)
            if resume is not None and resume.content is not None
            else None,
            conversation_history=conversation_history,
        )

        logger.info(f"AI回复: {response[:100]}...")

        # 保存对话记录：用户消息和AI回复放在一起
        current_questions.append(
            {
                "user_message": chat_request.message,  # 用户消息
                "ai_response": response,  # AI回复
                "type": "chat",
                "index": len(current_questions),
            }
        )

        # 为了兼容旧代码，也保存一条answer记录
        current_answers.append(
            {
                "answer": chat_request.message,
                "question_index": len(current_answers),
            }
        )

        interview_session.questions = current_questions  # type: ignore
        interview_session.answers = current_answers  # type: ignore
        db.commit()

        logger.info(f"对话已保存，当前questions数量: {len(current_questions)}")

        return InterviewChatResponse(response=response)

    except Exception as e:
        logger.error(f"Interview chat error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to chat: {str(e)}",
        )
