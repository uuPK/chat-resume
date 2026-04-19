"""
PDF 导出服务测试模块

用于验证 PDF 导出会复用前端打印页，确保导出结果与编辑器预览保持一致。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.infra.config import settings
from app.services.processing.export_service import ExportService


def _sample_resume_content() -> dict:
    """用于构造一份足以覆盖打印页载荷的最小简历数据。"""
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
            }
        ],
        "skills": [{"category": "语言", "items": ["Python", "TypeScript"]}],
        "projects": [
            {
                "name": "导出平台",
                "role": "负责人",
                "duration": "2024",
                "summary": "实现多格式简历导出。",
            }
        ],
    }


def test_export_to_pdf_uses_frontend_print_page(tmp_path, monkeypatch):
    """用于验证 PDF 导出会把前端打印页 URL 交给 Playwright。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    captured: dict[str, str] = {}

    async def _capture_print_url(self, print_url: str, filepath: str) -> None:
        """用于捕获传给 Playwright 的打印页 URL，避免真实启动浏览器。"""
        del self
        captured["print_url"] = print_url
        captured["filepath"] = filepath
        Path(filepath).write_bytes(b"%PDF-test")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _capture_print_url,
    )

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))
    exported = Path(filepath)
    parsed = urlparse(captured["print_url"])
    query = parse_qs(parsed.query)

    assert exported.exists()
    assert exported.suffix == ".pdf"
    assert exported.read_bytes().startswith(b"%PDF")
    assert captured["filepath"] == filepath
    assert parsed.scheme == "https"
    assert parsed.netloc == "frontend.example.com"
    assert parsed.path == "/resume/print"
    assert "data" in query
    assert query["data"][0]
