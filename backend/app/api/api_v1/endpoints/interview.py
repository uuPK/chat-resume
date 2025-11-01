"""
面试管理API端点模块

提供面试相关的API端点，包括面试创建、问题生成、评分等功能。
处理面试流程管理和实时交互。
"""

from typing import List, Dict, Any, cast
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
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

    # 检查是否已有进行中的面试会话，避免重复创建
    existing_active_session = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.resume_id == resume_id, InterviewSession.status == "active"
        )
        .first()
    )

    if existing_active_session:
        # 如果已有进行中的会话，返回现有会话而不是创建新的
        logger.info(f"发现现有活跃会话 {existing_active_session.id}，返回现有会话")
        return InterviewSessionResponse.model_validate(existing_active_session)

    try:
        from app.services.ai import InterviewAgent
        from app.services.ai.chat_service import AIProvider

        # 生成初始面试问题
        interview_agent = InterviewAgent(AIProvider.OPENROUTER)
        # 确保 resume.content 是字典类型
        resume_content: Dict[str, Any] = (
            cast(Dict[str, Any], resume.content) if resume.content else {}
        )
        questions_result = await interview_agent.generate_interview_questions(
            job_title="候选人",
            job_description=session_create.jd_content or "",
            resume_content=str(resume_content),
            question_types=["behavioral", "technical", "situational", "general"],
            difficulty="medium",
        )
        questions = questions_result.get("questions", [])

        # 创建面试会话
        interview_session = InterviewSession(
            resume_id=resume_id,
            job_position=session_create.job_position,
            interview_mode=session_create.interview_mode,
            jd_content=session_create.jd_content,
            questions=questions,
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
    current_question_index = len(interview_session.answers)

    # 如果还有预设问题，返回下一个
    if current_question_index < len(interview_session.questions):
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
        from app.services.ai.chat_service import AIProvider

        interview_agent = InterviewAgent(AIProvider.OPENROUTER)

        # 构建 InterviewAgent 需要的对话历史格式
        interview_history = []
        for i, answer in enumerate(interview_session.answers):
            if i < len(interview_session.questions):
                interview_history.append(
                    {
                        "role": "assistant",
                        "content": interview_session.questions[i]["question"],
                    }
                )
                interview_history.append({"role": "user", "content": answer["answer"]})

        # 生成新问题
        last_answer = (
            interview_session.answers[-1]["answer"] if interview_session.answers else ""
        )
        last_question = (
            interview_session.questions[-1]["question"]
            if interview_session.questions
            else ""
        )

        follow_up_result = await interview_agent.generate_follow_up_question(
            original_question=last_question,
            user_answer=last_answer,
            feedback_score=7,  # 默认分数
        )

        new_question = {
            "question": follow_up_result["follow_up_question"],
            "type": follow_up_result["question_type"],
            "purpose": follow_up_result["purpose"],
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

        if question_index >= len(interview_session.questions):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid question index"
            )

        current_question = interview_session.questions[question_index]["question"]

        # 使用 InterviewAgent 评估答案
        from app.services.ai import InterviewAgent
        from app.services.ai.chat_service import AIProvider

        interview_agent = InterviewAgent(AIProvider.OPENROUTER)
        evaluation = await interview_agent.conduct_interview(
            question=current_question,
            user_answer=answer_request.answer,
            question_context="面试评估",
            interview_history=[],
        )

        # 保存答案和评估
        answer_data = {
            "answer": answer_request.answer,
            "evaluation": evaluation,
            "question_index": question_index,
        }

        # 更新会话答案 - 复制列表以确保SQLAlchemy检测到变化
        current_answers = list(interview_session.answers or [])

        # 扩展答案列表到所需长度
        while len(current_answers) <= question_index:
            current_answers.append({})

        # 设置答案数据
        current_answers[question_index] = answer_data

        # 重新分配列表以触发SQLAlchemy的变化检测
        interview_session.answers = current_answers

        # 清除缓存的报告，因为面试内容已更新
        interview_session.report_data = None

        db.commit()

        return InterviewEvaluationResponse.model_validate(
            {
                "question": current_question,
                "answer": answer_request.answer,
                "evaluation": evaluation,
                "score": evaluation.get("score", 0),
                "feedback": evaluation.get("feedback", ""),
                "suggestions": evaluation.get("suggestions", []),
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
        from app.services.ai.chat_service import AIProvider

        # 计算整体面试分数
        interview_agent = InterviewAgent(AIProvider.OPENROUTER)

        # 构建面试会话记录
        interview_session_data = []
        for i, question in enumerate(interview_session.questions):
            answer = (
                interview_session.answers[i]
                if i < len(interview_session.answers)
                else ""
            )
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
        evaluation_result = await interview_agent.evaluate_interview_performance(
            interview_session=interview_session_data, job_requirements=job_requirements
        )

        overall_score = evaluation_result.get("total_score", 85)

        # 更新会话状态和分数
        interview_session.status = "completed"
        interview_session.overall_score = overall_score

        # 清除缓存的报告，因为面试已完成，需要重新生成完整报告
        interview_session.report_data = None

        db.commit()

        return {
            "message": "Interview session ended successfully",
            "overall_score": overall_score,
        }

    except Exception as e:
        # 即使分数计算失败，也要结束面试
        interview_session.status = "completed"

        # 清除缓存的报告
        interview_session.report_data = None

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
    from app.services.ai.chat_service import AIProvider

    interview_agent = InterviewAgent(AIProvider.OPENROUTER)

    for session in sessions:
        try:
            # 构建面试会话记录
            interview_session_data = []
            for i, question in enumerate(session.questions):
                answer = session.answers[i] if i < len(session.answers) else ""
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
            evaluation_result = await interview_agent.evaluate_interview_performance(
                interview_session=interview_session_data,
                job_requirements=job_requirements,
            )

            overall_score = evaluation_result.get("total_score", 85)

            if overall_score > 0:  # 只有成功计算出分数才更新
                session.overall_score = overall_score
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
            if not session.answers or len(session.answers) == 0:
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
        if interview_session.report_data and not regenerate:
            logger.info(f"返回缓存的报告，面试会话ID: {session_id}")
            return interview_session.report_data

        # 添加简历信息到面试会话对象
        interview_session.resume_title = resume.title
        interview_session.resume = resume  # 添加完整的简历对象

        # 生成报告
        from app.services.ai import InterviewAgent
        from app.services.ai.chat_service import AIProvider

        interview_agent = InterviewAgent(AIProvider.OPENROUTER)

        # 构建面试会话记录
        interview_session_data = []
        for i, question in enumerate(interview_session.questions):
            answer = (
                interview_session.answers[i]
                if i < len(interview_session.answers)
                else ""
            )
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
        report = await interview_agent.evaluate_interview_performance(
            interview_session=interview_session_data, job_requirements=job_requirements
        )

        # 缓存报告到数据库
        interview_session.report_data = report
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
