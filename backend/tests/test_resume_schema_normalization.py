import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.resume import ResumeContent  # noqa: E402


class ResumeSchemaNormalizationTests(unittest.TestCase):
    def test_work_experience_description_is_normalized_to_summary_and_highlights(self):
        content = ResumeContent.model_validate(
            {
                "work_experience": [
                    {
                        "company": "某科技公司",
                        "position": "后端工程师",
                        "duration": "2022-01 - 2024-01",
                        "description": "负责核心后台开发\n优化异步任务调度\n推动接口性能提升",
                    }
                ]
            }
        ).model_dump(mode="json")

        work = content["work_experience"][0]
        self.assertEqual(
            [item["text"] for item in work["highlights"]],
            ["负责核心后台开发", "优化异步任务调度", "推动接口性能提升"],
        )
        self.assertEqual(work["description"], "")

    def test_project_achievements_are_merged_into_highlights(self):
        content = ResumeContent.model_validate(
            {
                "projects": [
                    {
                        "name": "简历优化系统",
                        "role": "后端开发",
                        "duration": "2024",
                        "description": "面向求职场景的简历优化产品",
                        "achievements": ["支持 AI 改写", "支持 PDF 导出"],
                    }
                ]
            }
        ).model_dump(mode="json")

        project = content["projects"][0]
        self.assertEqual(project["overview"], "面向求职场景的简历优化产品")
        self.assertEqual(
            [item["text"] for item in project["highlights"]],
            ["支持 AI 改写", "支持 PDF 导出"],
        )
        self.assertEqual(project["description"], "")
        self.assertEqual(project["summary"], "")
        self.assertEqual(project["achievements"], [])

    def test_education_description_is_normalized_to_summary_and_highlights(self):
        content = ResumeContent.model_validate(
            {
                "education": [
                    {
                        "school": "北京大学",
                        "major": "计算机科学与技术",
                        "degree": "本科",
                        "duration": "2018-2022",
                        "description": "主修计算机基础课程\n获得国家奖学金",
                    }
                ]
            }
        ).model_dump(mode="json")

        education = content["education"][0]
        self.assertEqual(
            [item["text"] for item in education["highlights"]],
            ["主修计算机基础课程", "获得国家奖学金"],
        )
        self.assertEqual(education["description"], "")


if __name__ == "__main__":
    unittest.main()
