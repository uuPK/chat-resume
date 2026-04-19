"""
PDF 导出服务测试模块

用于验证在 Playwright 浏览器缺失时，PDF 导出仍然会回退到可用的服务端渲染方案。
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.config import settings
from app.services.processing.export_service import ExportService


def _sample_resume_content() -> dict:
    """用于构造一份足以覆盖导出字段的最小简历数据。"""
    return {
        "personal_info": {
            "name": "张三",
            "email": "zhangsan@example.com",
            "phone": "13800000000",
        },
        "education": [
            {
                "school": "测试大学",
                "degree": "本科",
                "major": "计算机科学",
                "duration": "2018-2022",
            }
        ],
        "work_experience": [
            {
                "company": "测试公司",
                "position": "后端工程师",
                "duration": "2022-至今",
                "summary": "负责简历系统后端开发与性能优化。",
                "highlights": [{"text": "接口响应时间降低 35%"}],
            }
        ],
        "skills": [{"category": "语言", "items": ["Python", "TypeScript"]}],
        "projects": [
            {
                "name": "导出平台",
                "role": "负责人",
                "duration": "2024",
                "summary": "实现多格式简历导出。",
                "highlights": [{"text": "支持 PDF 导出兜底渲染"}],
            }
        ],
    }


def test_export_to_pdf_falls_back_when_playwright_browser_is_missing(tmp_path, monkeypatch):
    """用于验证浏览器二进制缺失时会自动回退到 ReportLab 生成 PDF。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()

    async def _raise_missing_browser(self, html_content: str, filepath: str) -> None:
        del self, html_content, filepath
        raise RuntimeError(
            "BrowserType.launch: Executable doesn't exist at playwright/chromium_headless_shell-1208/test"
        )

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _raise_missing_browser,
    )

    import asyncio

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))
    exported = Path(filepath)

    assert exported.exists()
    assert exported.suffix == ".pdf"
    assert exported.read_bytes().startswith(b"%PDF")
