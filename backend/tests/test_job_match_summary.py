"""用于覆盖 JD 匹配摘要生成的回归测试。"""

from app.services.agent.job_match_summary import build_job_match_summary
from app.tools.resume.job_match_summary_tool import generate_job_match_summary


def test_build_job_match_summary_extracts_evidence_from_jd_resume_and_diff():
    """用于验证岗位匹配摘要只基于 JD、简历和已确认改动生成。"""
    original_resume = {
        "job_application": {
            "jd_text": "负责复杂前端交互、性能优化和工程化建设，要求 React 和 TypeScript。",
        },
        "projects": [
            {
                "name": "简历编辑器",
                "highlights": [{"text": "负责 React 前端开发"}],
            }
        ],
    }
    latest_resume = {
        **original_resume,
        "projects": [
            {
                "name": "简历编辑器",
                "highlights": [
                    {"text": "负责 React 前端开发，首屏性能优化 35%"}
                ],
            }
        ],
    }

    summary = build_job_match_summary(
        original_resume=original_resume,
        latest_resume_content=latest_resume,
        confirmed_diff_items=[
            {
                "before": "负责 React 前端开发",
                "after": "负责 React 前端开发，首屏性能优化 35%",
                "reason": "补充岗位关键词和量化结果",
            }
        ],
    )

    assert summary is not None
    assert "React" in summary["matched_keywords"]
    assert "性能优化" in summary["matched_keywords"]
    assert "TypeScript" in summary["missing_keywords"]
    assert summary["resume_changes"] == [
        "补充岗位关键词和量化结果：负责 React 前端开发，首屏性能优化 35%"
    ]
    assert "可补充与「TypeScript」相关的真实经历或结果" in summary["fact_gaps"]


def test_build_job_match_summary_returns_none_without_jd_text():
    """用于验证缺少 JD 时不会生成空洞摘要。"""
    summary = build_job_match_summary(
        original_resume={"projects": [{"name": "内部系统"}]},
        latest_resume_content={"projects": [{"name": "内部系统"}]},
        confirmed_diff_items=[],
    )

    assert summary is None


def test_generate_job_match_summary_tool_returns_summary_payload():
    """用于验证岗位匹配摘要工具返回前端可直接消费的 payload。"""
    resume = {
        "job_application": {"jd_text": "要求 Agent、后端和 Redis 经验。"},
        "work_experience": [{"highlights": [{"text": "负责 Agent 后端服务"}]}],
    }

    result = generate_job_match_summary(
        resume,
        confirmed_diff_items=[
            {
                "after": "负责 Agent 后端服务，支撑高并发接口",
                "reason": "补充岗位关键词",
            }
        ],
    )

    assert result["success"] is True
    assert result["job_match_summary"]["matched_keywords"] == ["Agent", "后端"]
    assert "Redis" in result["job_match_summary"]["missing_keywords"]
    assert result["job_match_summary"]["resume_changes"] == [
        "补充岗位关键词：负责 Agent 后端服务，支撑高并发接口"
    ]
