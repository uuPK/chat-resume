"""用于覆盖 test_resume_agent.py 对应的回归测试。"""

import json
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.agents.resume.agent import ResumeAgent  # noqa: E402
from app.agents.resume.stream_events import (  # noqa: E402
    normalize_resume_stream_payload,
    tool_pending_event,
)
from app.agents.resume.executor import ResumeToolExecutor  # noqa: E402
from app.tools.resume.registry import RESUME_TOOLS_SCHEMA  # noqa: E402
from app.tools.resume.update_highlight_tool import update_highlight  # noqa: E402
from app.types.stream import public_resume_stream_event  # noqa: E402
from app.prompts import load_prompt  # noqa: E402
from scripts.run_resume_agent_smoke import resume_changed  # noqa: E402


def _render_resume_system_prompt(**kwargs: object) -> str:
    """用于按真实 prompt loader 渲染简历 Agent 系统提示词。"""
    return load_prompt("resume_agent").render(**kwargs)


class ResumeAgentPromptContextTests(unittest.TestCase):
    def test_prompt_context_includes_job_application_fields(self):
        """用于验证prompt上下文includes任务applicationfields。"""
        agent = ResumeAgent()
        context = agent._build_prompt_context(
            {
                "resume_content": {
                    "job_application": {
                        "target_title": "前端工程师",
                        "target_company": "字节跳动",
                        "jd_text": "负责复杂前端交互、性能优化和工程化建设",
                    },
                    "projects": [],
                }
            }
        )

        self.assertEqual(context["target_title"], "前端工程师")
        self.assertEqual(context["target_company"], "字节跳动")
        self.assertIn("性能优化", context["jd_text"])
        self.assertIn('"job_application"', context["resume_json"])

    def test_resume_tools_schema_exposes_optional_reason_field(self):
        """用于验证简历toolsschemaexposesoptionalreasonfield。"""
        schema = RESUME_TOOLS_SCHEMA
        update_bullet = next(
            tool for tool in schema if tool["function"]["name"] == "update_bullet"
        )

        properties = update_bullet["function"]["parameters"]["properties"]
        self.assertIn("reason", properties)
        self.assertEqual(properties["reason"]["type"], "string")

    def test_resume_tools_schema_exposes_bullet_tools(self):
        """用于验证简历toolsschemaexposesbullettools。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertIn("update_bullet", tool_names)
        self.assertIn("add_bullet", tool_names)
        self.assertIn("remove_bullet", tool_names)
        self.assertNotIn("update_highlight", tool_names)
        self.assertNotIn("add_highlight", tool_names)
        self.assertNotIn("remove_highlight", tool_names)

    def test_resume_tools_schema_exposes_full_resume_edit_tools(self):
        """用于验证简历toolsschema暴露全简历编辑工具。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertIn("update_summary", tool_names)
        self.assertIn("update_profile", tool_names)
        self.assertIn("update_item_fields", tool_names)
        self.assertIn("update_skills", tool_names)
        self.assertIn("add_resume_item", tool_names)
        self.assertIn("remove_resume_item", tool_names)

    def test_resume_tools_schema_does_not_expose_custom_memory_tools(self):
        """用于验证简历toolsschemadoesnotexposecustommemorytools。"""
        tool_names = {tool["function"]["name"] for tool in RESUME_TOOLS_SCHEMA}

        self.assertNotIn("read_user_memory", tool_names)
        self.assertNotIn("write_user_memory", tool_names)

    def test_update_summary_tool_updates_summary_text_with_diff(self):
        """用于验证update_summary通过执行器修改个人总结并返回diff。"""
        resume_content = {"summary": {"text": "3年后端开发经验"}}
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="update_summary",
            tool_input={"text": "3年 AI 应用工程经验，熟悉 Agent 工具调用", "reason": "贴合 JD 定位"},
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(
            resume_content["summary"]["text"],
            "3年 AI 应用工程经验，熟悉 Agent 工具调用",
        )
        self.assertIn("贴合 JD 定位", result["result"]["diff_summary"])
        self.assertEqual(result["updated_section_name"], "个人总结")

    def test_update_profile_tool_updates_safe_profile_fields(self):
        """用于验证update_profile只修改可安全优化的个人信息字段。"""
        resume_content = {"personal_info": {"name": "张三", "position": "后端开发"}}
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="update_profile",
            tool_input={
                "fields": {
                    "position": "AI 应用工程师",
                    "headline": "熟悉 Agent 工具调用与后端工程化",
                },
                "reason": "强化目标岗位定位",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["personal_info"]["name"], "张三")
        self.assertEqual(resume_content["personal_info"]["position"], "AI 应用工程师")
        self.assertIn("Agent 工具调用", resume_content["personal_info"]["headline"])
        self.assertIn("强化目标岗位定位", result["result"]["diff_summary"])

    def test_update_item_fields_tool_updates_project_fields(self):
        """用于验证update_item_fields修改项目条目的非bullet字段。"""
        resume_content = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "overview": "简历编辑器",
                    "role": "开发",
                }
            ]
        }
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="update_item_fields",
            tool_input={
                "section": "projects",
                "item_id": "proj_1",
                "fields": {
                    "overview": "基于 ReAct Agent 的简历优化工作台",
                    "role": "全栈负责人",
                    "technologies": ["FastAPI", "Next.js", "Agent Tools"],
                },
                "reason": "补强项目定位和技术栈",
            },
            context={"resume_content": resume_content},
        )

        project = resume_content["projects"][0]
        self.assertTrue(result["result"]["success"])
        self.assertEqual(project["role"], "全栈负责人")
        self.assertIn("ReAct Agent", project["overview"])
        self.assertIn("Agent Tools", project["technologies"])
        self.assertIn("补强项目定位和技术栈", result["result"]["diff_summary"])

    def test_update_skills_tool_replaces_skill_items(self):
        """用于验证update_skills精确更新技能分类和技能列表。"""
        resume_content = {
            "skills": [
                {"id": "skill_1", "category": "后端", "items": ["Python", "FastAPI"]},
            ]
        }
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="update_skills",
            tool_input={
                "category_id": "skill_1",
                "category": "AI 应用工程",
                "items": ["Python", "FastAPI", "Agent Tools", "RAG"],
                "mode": "replace",
                "reason": "补充 JD 关键词",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(resume_content["skills"][0]["category"], "AI 应用工程")
        self.assertEqual(
            resume_content["skills"][0]["items"],
            ["Python", "FastAPI", "Agent Tools", "RAG"],
        )
        self.assertIn("补充 JD 关键词", result["result"]["diff_summary"])

    def test_add_resume_item_tool_requires_source_and_adds_project(self):
        """用于验证add_resume_item带事实来源新增项目条目。"""
        resume_content = {"projects": []}
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="add_resume_item",
            tool_input={
                "section": "projects",
                "item": {
                    "name": "Agent 简历优化",
                    "overview": "用户明确提供的项目经历",
                    "role": "负责人",
                },
                "source": "用户在本轮消息中明确提供",
                "reason": "补充目标岗位相关项目",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(len(resume_content["projects"]), 1)
        self.assertTrue(resume_content["projects"][0]["id"].startswith("proj_"))
        self.assertEqual(resume_content["projects"][0]["role"], "负责人")
        self.assertIn("补充目标岗位相关项目", result["result"]["diff_summary"])

    def test_remove_resume_item_tool_removes_existing_skill_category(self):
        """用于验证remove_resume_item删除已有技能分类。"""
        resume_content = {
            "skills": [
                {"id": "skill_1", "category": "旧技能", "items": ["jQuery"]},
                {"id": "skill_2", "category": "后端", "items": ["Python"]},
            ]
        }
        executor = ResumeToolExecutor()

        result = executor.execute(
            tool_name="remove_resume_item",
            tool_input={
                "section": "skills",
                "item_id": "skill_1",
                "reason": "删除与目标岗位弱相关的技能分类",
            },
            context={"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual([item["id"] for item in resume_content["skills"]], ["skill_2"])
        self.assertIn("删除与目标岗位弱相关", result["result"]["diff_summary"])

    def test_resume_tool_result_includes_structured_diff_reason(self):
        """用于验证简历tool结果includesstructureddiffreason。"""
        resume_content = {
            "projects": [
                {
                    "id": "proj_1",
                    "name": "Chat Resume",
                    "highlights": [
                        {"id": "hl_1", "text": "负责前端开发"},
                    ],
                }
            ]
        }

        result = update_highlight(
            resume_content,
            section="projects",
            item_id="proj_1",
            highlight_id="hl_1",
            text="主导前端重构，首屏加载提速 35%",
            reason="补充量化结果",
        )

        self.assertTrue(result["success"])
        self.assertIn("改动理由：补充量化结果", result["diff_summary"])
        self.assertEqual(result["diff_items"][0]["reason"], "补充量化结果")
        self.assertIn("35%", result["diff_items"][0]["after"])

    def test_resume_agent_smoke_change_detector_checks_nested_highlights(self):
        """用于验证resumeagentsmokechangedetectorchecks嵌套要点。"""
        before = {
            "work_experience": [
                {
                    "id": "work_1",
                    "summary": "负责内部系统开发",
                    "highlights": [{"id": "hl_1", "text": "维护多个后台服务"}],
                }
            ]
        }
        after = {
            "work_experience": [
                {
                    "id": "work_1",
                    "summary": "负责内部系统开发",
                    "highlights": [{"id": "hl_1", "text": "优化多个后台服务"}],
                }
            ]
        }

        self.assertTrue(resume_changed(before, after))

    def test_update_bullet_tool_updates_existing_highlights_storage(self):
        """用于验证updatebullettoolupdatesexistinghighlightsstorage。"""
        agent = ResumeAgent()
        resume_content = {
            "work_experience": [
                {
                    "id": "work_1",
                    "highlights": [
                        {"id": "hl_1", "text": "负责后端开发"},
                    ],
                }
            ]
        }

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": {
                        "section": "work_experience",
                        "item_id": "work_1",
                        "bullet_id": "hl_1",
                        "text": "负责后端服务治理，接口错误率下降 20%",
                    },
                }
            },
            {"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertEqual(result["tool_name"], "优化要点")
        self.assertIn("下降 20%", resume_content["work_experience"][0]["highlights"][0]["text"])

    def test_update_bullet_tool_accepts_common_model_argument_aliases(self):
        """用于验证updatebullettoolaccepts常见模型参数别名。"""
        agent = ResumeAgent()
        resume_content = {
            "work_experience": [
                {
                    "id": "work_1",
                    "highlights": [
                        {"id": "hl_1", "text": "负责后端开发"},
                    ],
                }
            ]
        }

        result = agent._run_tool(
            {
                "function": {
                    "name": "update_bullet",
                    "arguments": {
                        "section": "work",
                        "item_id": "work_1",
                        "highlight_id": "hl_1",
                        "text": "负责后端服务治理，接口错误率下降 20%",
                    },
                }
            },
            {"resume_content": resume_content},
        )

        self.assertTrue(result["result"]["success"])
        self.assertIn("下降 20%", resume_content["work_experience"][0]["highlights"][0]["text"])

    def test_resume_stream_event_contract_keeps_structured_diff(self):
        """用于验证简历stream事件contractkeepsstructureddiff。"""
        event = tool_pending_event(
            call_id="call_1",
            tool_id="update_bullet",
            tool_call={
                "id": "call_1",
                "type": "function",
                "function": {"name": "update_bullet", "arguments": {}},
            },
            tool_display_name="优化要点",
            tool_input={"section": "projects"},
            diff_summary="旧文本 diff",
            diff_items=[
                {
                    "before": "负责前端开发",
                    "after": "主导前端重构，首屏加载提速 35%",
                    "reason": "补充量化结果",
                }
            ],
            tool_calls=[],
        )

        self.assertEqual(event["event_type"], "tool_pending")
        self.assertTrue(event["tool_pending"])
        self.assertEqual(event["tool_id"], "update_bullet")
        self.assertEqual(event["tool_display_name"], "优化要点")
        self.assertEqual(event["tool_name"], "优化要点")
        self.assertEqual(event["diff_items"][0]["reason"], "补充量化结果")

    def test_resume_stream_event_normalizes_legacy_payload(self):
        """用于验证简历stream事件normalizeslegacypayload。"""
        event = normalize_resume_stream_payload(
            {
                "tool_pending": True,
                "call_id": "call_1",
                "tool_call": {
                    "function": {
                        "name": "update_highlight",
                    }
                },
                "tool_name": "update_highlight",
                "diff_items": [{"before": "A", "after": "B", "reason": 123}],
            }
        )

        self.assertEqual(event["event_type"], "tool_pending")
        self.assertEqual(event["tool_id"], "update_highlight")
        self.assertEqual(event["tool_display_name"], "update_highlight")
        self.assertEqual(event["diff_items"][0]["reason"], "123")

    def test_resume_stream_event_does_not_expose_runtime_context(self):
        """用于验证简历stream事件doesnotexposeruntime上下文。"""
        resume_content = {"projects": [{"id": "proj_1", "highlights": []}]}

        event = normalize_resume_stream_payload(
            {
                "tool_confirmed": True,
                "call_id": "call_1",
                "context": {
                    "resume_content": resume_content,
                    "allowed_sections": {"projects"},
                },
            },
            resume_content=resume_content,
        )

        self.assertNotIn("context", event)
        self.assertEqual(event["resume_content"], resume_content)
        json.dumps({k: v for k, v in event.items() if v is not None})

    def test_public_resume_stream_event_strips_internal_fields(self):
        """用于验证public简历stream事件stripsinternalfields。"""
        event = public_resume_stream_event(
            {
                "event_type": "tool_result",
                "internal_only": False,
                "content": "",
                "context": {"resume_content": {"projects": []}},
                "display_message": None,
                "done": False,
            }
        )

        self.assertNotIn("context", event)
        self.assertNotIn("internal_only", event)
        self.assertNotIn("display_message", event)
        self.assertEqual(event["event_type"], "tool_result")

    def test_system_prompt_is_thin_stable_business_policy(self):
        """用于验证系统提示词只保留薄业务边界。"""
        rendered = _render_resume_system_prompt(
            target_title="前端工程师",
            target_company="字节跳动",
            jd_text="负责复杂前端交互与性能优化",
            resume_json="{}",
        )

        self.assertIn("根据当前简历、用户目标和 API tools", rendered)
        self.assertIn("不要编造经历、数字、奖项、年限或业务结果", rendered)
        self.assertNotIn("可用工具", rendered)
        self.assertNotIn("量化改写优先级", rendered)
        self.assertNotIn("简历优化策略", rendered)

    def test_system_prompt_does_not_expose_memory_tools(self):
        """用于验证systempromptdoesnotexposememorytools。"""
        rendered = _render_resume_system_prompt(
            target_title="AI Agent 开发工程师",
            target_company="腾讯",
            jd_text="负责 Agent 产品能力建设",
            resume_json="{}",
        )

        self.assertNotIn("read_user_memory", rendered)
        self.assertNotIn("write_user_memory", rendered)
        self.assertNotIn("${toolsList}", rendered)
        self.assertNotIn("${guidelines}", rendered)
        self.assertNotIn("Pi 文档", rendered)

    def test_system_prompt_leaves_tool_choice_to_model(self):
        """用于验证系统提示词把工具选择交给模型判断。"""
        rendered = _render_resume_system_prompt(
            target_title="产品经理",
            target_company="美团",
            jd_text="负责策略优化与跨团队协同",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        self.assertIn("按 ReAct 方式工作", rendered)
        self.assertIn("每轮最多调用 1 个工具", rendered)
        self.assertIn("是否调用工具、调用哪个工具、何时继续调用下一个工具", rendered)
        self.assertNotIn("默认执行 `optimize-first`", rendered)
        self.assertNotIn("首轮", rendered)
        self.assertNotIn("必须直接调用工具产出改动", rendered)

    def test_system_prompt_uses_kimi_style_tool_turn_contract(self):
        """用于验证工具轮协议采用 Kimi 风格：调用工具时不输出解释。"""
        rendered = _render_resume_system_prompt(
            target_title="产品经理",
            target_company="美团",
            jd_text="负责策略优化与跨团队协同",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        self.assertIn("当你调用工具时，不要输出解释", rendered)
        self.assertIn("工具调用本身应该自解释", rendered)
        self.assertNotIn("问不能生成文字生成知己", rendered)

    def test_tool_schema_descriptions_carry_tool_protocol(self):
        """用于验证工具使用协议收敛在工具 schema 描述中。"""
        descriptions = {
            tool["function"]["name"]: tool["function"]["description"]
            for tool in RESUME_TOOLS_SCHEMA
        }

        self.assertIn("section 只能是 education", descriptions["update_bullet"])
        self.assertIn("item_id 和 bullet_id 必须来自当前简历 JSON", descriptions["update_bullet"])
        self.assertIn("section 必须是 projects", descriptions["update_overview"])
        self.assertIn("该工具不修改简历", descriptions["generate_job_match_summary"])

    def test_system_prompt_omits_tool_call_protocol_section(self):
        """用于验证系统提示词不再硬编码工具协议正文。"""
        rendered = _render_resume_system_prompt(
            target_title="前端工程师",
            target_company="字节跳动",
            jd_text="负责复杂前端交互与性能优化",
            resume_json='{"projects": [{"id": "proj_1", "highlights": [{"id": "hl_1", "text": "负责前端开发"}]}]}',
        )

        self.assertNotIn("工具调用协议", rendered)
        self.assertNotIn("改单条要点用 `update_bullet", rendered)
        self.assertNotIn("改项目简介只用 `update_overview", rendered)

    def test_system_prompt_limits_follow_up_to_defined_exception_cases(self):
        """用于验证systempromptlimitsfollowuptodefinedexception用例。"""
        rendered = _render_resume_system_prompt(
            target_title="运营",
            target_company="小红书",
            jd_text="负责活动运营与增长分析",
            resume_json='{"projects": [{"id": "proj_1", "highlights": []}]}',
        )

        self.assertIn("缺输入", rendered)
        self.assertIn("高风险", rendered)
        self.assertIn("指令冲突", rendered)
        self.assertIn("追问必须短、具体、单轮可答", rendered)
        self.assertIn("禁止泛泛地问“要不要我帮你优化”", rendered)

    def test_system_prompt_explicitly_blocks_high_risk_fabrication_requests(self):
        """用于验证systempromptexplicitlyblockshighriskfabricationrequests。"""
        rendered = _render_resume_system_prompt(
            target_title="高级后端工程师",
            target_company="字节跳动",
            jd_text="负责高并发系统设计与稳定性建设",
            resume_json='{"work_experience": [{"id": "work_1", "highlights": []}]}',
        )

        self.assertIn("补一些我没做过的项目", rendered)
        self.assertIn("假装更多年限", rendered)
        self.assertIn("我不能编造你没做过的项目或虚构年限", rendered)
        self.assertIn("不能直接调用工具", rendered)


if __name__ == "__main__":
    unittest.main()
