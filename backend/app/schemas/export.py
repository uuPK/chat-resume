"""
导出相关数据模式

定义简历和面试报告导出相关的Pydantic模式。
支持多种格式导出的数据验证和序列化。
"""

from pydantic import BaseModel
from typing import Optional


class ExportRequest(BaseModel):
    format: str  # pdf, docx, html
    template: Optional[str] = "default"


class ExportResponse(BaseModel):
    download_url: str
    filename: str
    format: str
