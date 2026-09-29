"""
PDF 导出服务测试模块

用于验证 PDF 导出会复用前端打印页，确保导出结果与编辑器预览保持一致。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import app.services.processing.export_service as export_service_module
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
    """用于验证 PDF 导出把内容注入无查询参数的前端打印页。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    captured: dict[str, object] = {}

    async def _capture_print_url(self, print_url: str, filepath: str, payload: dict) -> None:
        """用于捕获打印页地址和浏览器注入载荷。"""
        del self
        captured["print_url"] = print_url
        captured["filepath"] = filepath
        captured["payload"] = payload
        Path(filepath).write_bytes(b"%PDF-test")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _capture_print_url,
    )

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))
    exported = Path(filepath)
    parsed = urlparse(str(captured["print_url"]))

    assert exported.exists()
    assert exported.suffix == ".pdf"
    assert exported.read_bytes().startswith(b"%PDF")
    assert captured["filepath"] == filepath
    assert parsed.scheme == "https"
    assert parsed.netloc == "frontend.example.com"
    assert parsed.path == "/resume/print"
    assert parsed.query == ""
    assert captured["payload"] == {
        "content": _sample_resume_content(),
        "template": "default",
        "layoutConfig": None,
    }


def test_export_to_pdf_preserves_template_and_chinese_payload(tmp_path, monkeypatch):
    """用于验证浏览器注入载荷保留模板、布局和中文内容。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    captured: dict[str, object] = {}

    async def _capture_render(self, print_url: str, filepath: str, payload: dict) -> None:
        """用于捕获浏览器渲染参数。"""
        del self
        captured.update({"url": print_url, "payload": payload})
        Path(filepath).write_bytes(b"%PDF-test")

    monkeypatch.setattr(ExportService, "_render_pdf_with_playwright", _capture_render)
    asyncio.run(export_service.export_to_pdf(
        _sample_resume_content(),
        template="compact",
        layout_config={
            "moduleOrder": ["personal", "skills"],
            "visibleModules": ["personal", "skills"],
            "spacingScale": 0.5,
        },
    ))
    payload = captured["payload"]

    assert captured["url"] == "https://frontend.example.com/resume/print"
    assert isinstance(payload, dict)
    assert payload["template"] == "compact"
    assert payload["layoutConfig"] == {
        "moduleOrder": ["personal", "skills"],
        "visibleModules": ["personal", "skills"],
        "spacingScale": 0.5,
    }
    assert payload["content"]["personal_info"]["name"] == "张三"
    assert (
        payload["content"]["work_experience"][0]["summary"]
        == "负责简历系统后端开发与性能优化。"
    )


def test_render_pdf_with_playwright_uses_expected_page_settings(tmp_path, monkeypatch):
    """用于验证 Playwright 渲染时会使用正确的页面参数和 PDF 选项。"""
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://frontend.example.com")
    export_service = ExportService()
    captured: dict[str, object] = {}
    output_path = tmp_path / "resume.pdf"

    class FakePage:
        """用于记录页面导航和导出参数。"""

        async def add_init_script(self, script: str) -> None:
            """用于记录注入的简历数据。"""
            captured["script"] = script

        async def wait_for_selector(self, selector: str) -> None:
            """用于记录打印页面已出现。"""
            captured["selector"] = selector

        async def add_style_tag(self, url: str) -> None:
            """用于记录 PDF 专用分页样式。"""
            captured["style_url"] = url

        async def evaluate(self, expression: str) -> None:
            """用于记录字体加载等待。"""
            captured["evaluate"] = expression

        async def goto(self, url: str, wait_until: str) -> None:
            """用于处理goto。"""
            captured["goto"] = {"url": url, "wait_until": wait_until}

        async def emulate_media(self, media: str) -> None:
            """用于处理emulatemedia。"""
            captured["media"] = media

        async def pdf(self, **kwargs) -> None:
            """用于处理pdf。"""
            captured["pdf"] = kwargs
            Path(kwargs["path"]).write_bytes(b"%PDF-fake")

    class FakeBrowser:
        """用于模拟浏览器实例并暴露页面对象。"""

        def __init__(self) -> None:
            """用于处理init。"""
            self.page = FakePage()

        async def new_page(self, **kwargs):
            """用于处理newpage。"""
            captured["viewport"] = kwargs["viewport"]
            return self.page

        async def close(self) -> None:
            """用于处理close。"""
            captured["closed"] = True

    class FakeChromium:
        """用于记录浏览器启动参数。"""

        async def launch(self, headless: bool):
            """用于处理launch。"""
            captured["launch"] = {"headless": headless}
            return FakeBrowser()

    class FakePlaywright:
        """用于暴露假的 chromium 客户端。"""

        chromium = FakeChromium()

    class FakePlaywrightContext:
        """用于模拟 async_playwright 上下文管理器。"""

        async def __aenter__(self):
            """用于处理aenter。"""
            return FakePlaywright()

        async def __aexit__(self, exc_type, exc, tb):
            """用于处理aexit。"""
            return False

    monkeypatch.setattr(
        export_service_module,
        "async_playwright",
        lambda: FakePlaywrightContext(),
    )

    asyncio.run(
        export_service._render_pdf_with_playwright(
            "https://frontend.example.com/resume/print",
            str(output_path),
            {"content": _sample_resume_content(), "template": "classic"},
        )
    )

    assert captured["launch"] == {"headless": True}
    assert captured["viewport"] == {"width": 1280, "height": 1810}
    assert captured["goto"] == {
        "url": "https://frontend.example.com/resume/print",
        "wait_until": "networkidle",
    }
    assert captured["media"] == "screen"
    injected_payload = json.loads(str(captured["script"]).split(" = ", 1)[1].rstrip(";"))
    assert injected_payload["content"]["personal_info"]["name"] == "张三"
    assert captured["style_url"] == "https://frontend.example.com/styles/resume-pdf.css"
    assert captured["selector"] == "#resume-export-content .resume-page"
    assert captured["pdf"] == {
        "path": str(output_path),
        "format": "A4",
        "print_background": True,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    }
    assert captured["closed"] is True
    assert output_path.read_bytes().startswith(b"%PDF")


def test_export_to_pdf_falls_back_to_reportlab_when_playwright_is_unavailable(
    tmp_path,
    monkeypatch,
):
    """用于验证浏览器无法启动时仍可导出 PDF。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()
    captured: dict[str, str] = {}

    async def _raise_render_error(self, print_url: str, filepath: str, payload: dict) -> None:
        """用于模拟 Playwright 启动失败的异常分支。"""
        del self, print_url, filepath, payload
        raise export_service_module.PlaywrightError("Executable doesn't exist")

    def _capture_reportlab_render(self, resume_content: dict, filepath: str) -> None:
        """用于捕获 ReportLab 兜底调用。"""
        del self, resume_content
        captured["filepath"] = filepath
        Path(filepath).write_bytes(b"%PDF-reportlab-fallback")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _raise_render_error,
    )
    monkeypatch.setattr(
        ExportService,
        "_render_resume_pdf_with_reportlab",
        _capture_reportlab_render,
    )

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))

    assert Path(filepath).read_bytes() == b"%PDF-reportlab-fallback"
    assert captured["filepath"] == filepath


def test_export_to_pdf_falls_back_to_reportlab_when_print_page_times_out(
    tmp_path,
    monkeypatch,
):
    """用于验证前端打印页超时时仍能导出 PDF。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()
    captured: dict[str, str] = {}

    async def _raise_timeout(self, print_url: str, filepath: str, payload: dict) -> None:
        """用于模拟前端打印页加载超时。"""
        del self, print_url, filepath, payload
        raise PlaywrightTimeoutError("Timeout 30000ms exceeded")

    def _capture_reportlab_render(self, resume_content: dict, filepath: str) -> None:
        """用于捕获 ReportLab 兜底调用。"""
        del self
        captured["name"] = resume_content["personal_info"]["name"]
        captured["filepath"] = filepath
        Path(filepath).write_bytes(b"%PDF-fallback")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _raise_timeout,
    )
    monkeypatch.setattr(
        ExportService,
        "_render_resume_pdf_with_reportlab",
        _capture_reportlab_render,
    )

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))

    assert Path(filepath).read_bytes() == b"%PDF-fallback"
    assert captured["filepath"] == filepath
    assert captured["name"] == "张三"


def test_export_to_pdf_keeps_large_resume_in_browser_preview(
    tmp_path,
    monkeypatch,
):
    """用于验证长简历仍由前端预览组件渲染 PDF。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()
    large_content = _sample_resume_content()
    large_content["projects"] = [
        {
            "name": "超长项目",
            "summary": "负责复杂系统。" * 5000,
        }
    ]
    captured: dict[str, object] = {}

    async def _capture_frontend_render(self, print_url: str, filepath: str, payload: dict) -> None:
        """用于捕获超长简历的浏览器注入数据。"""
        del self
        captured.update({"url": print_url, "payload": payload})
        Path(filepath).write_bytes(b"%PDF-large-browser")

    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _capture_frontend_render,
    )

    filepath = asyncio.run(export_service.export_to_pdf(large_content))

    assert Path(filepath).read_bytes() == b"%PDF-large-browser"
    assert isinstance(captured["url"], str)
    assert captured["url"].endswith("/resume/print")
    assert len(captured["url"]) < 100
    assert isinstance(captured["payload"], dict)
    assert captured["payload"]["content"]["projects"][0]["summary"] == "负责复杂系统。" * 5000


def test_export_to_pdf_uses_reportlab_for_selector_event_loop(tmp_path, monkeypatch):
    """用于验证热重载的 Windows 事件循环会避开 Playwright。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()
    captured: dict[str, str] = {}

    async def _fail_frontend_render(self, print_url: str, filepath: str, payload: dict) -> None:
        """用于确保 Selector 事件循环不会尝试启动浏览器。"""
        del self, print_url, filepath, payload
        raise AssertionError("Selector 事件循环不应启动 Playwright")

    def _capture_reportlab_render(self, resume_content: dict, filepath: str) -> None:
        """用于捕获 Selector 事件循环下的 ReportLab 导出。"""
        del self, resume_content
        captured["filepath"] = filepath
        Path(filepath).write_bytes(b"%PDF-selector-fallback")

    monkeypatch.setattr(
        ExportService,
        "_requires_reportlab_pdf_fallback",
        lambda self: True,
    )
    monkeypatch.setattr(
        ExportService,
        "_render_pdf_with_playwright",
        _fail_frontend_render,
    )
    monkeypatch.setattr(
        ExportService,
        "_render_resume_pdf_with_reportlab",
        _capture_reportlab_render,
    )

    filepath = asyncio.run(export_service.export_to_pdf(_sample_resume_content()))

    assert Path(filepath).read_bytes() == b"%PDF-selector-fallback"
    assert captured["filepath"] == filepath


def test_get_file_url_returns_signed_download_path(tmp_path, monkeypatch):
    """用于验证导出文件地址会拼出带签名的下载路径。"""
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    export_service = ExportService()
    monkeypatch.setattr(
        export_service_module,
        "create_download_token",
        lambda filename, user_id: (
            f"expires=123&user_id={user_id}&signature=signed-{filename}"
        ),
    )

    file_url = export_service.get_file_url(
        filepath=str(tmp_path / "exports" / "resume_demo.pdf"),
        user_id=42,
    )

    assert file_url == (
        "/api/resumes/download/resume_demo.pdf?"
        "expires=123&user_id=42&signature=signed-resume_demo.pdf"
    )
