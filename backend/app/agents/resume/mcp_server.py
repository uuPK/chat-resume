"""
符合 Anthropic MCP 标准的简历操作工具服务器 (MCP Server)。
这个模块将底层的简历修改能力（增删改查）对外暴露为标准的 MCP 协议接口。
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent, CallToolResult
import mcp.types

from app.tools.resume.registry import RESUME_TOOL_CATALOG, execute_resume_tool

logger = logging.getLogger(__name__)

# 创建 MCP Server 实例
mcp_server = Server("ResumeOptimizationServer")

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """向外网（或 LangGraph 客户端）广播当前 Server 支持哪些工具。"""
    tools = []
    for definition in RESUME_TOOL_CATALOG:
        if definition.schema:
            function_def = definition.schema.get("function", {})
            name = function_def.get("name")
            description = function_def.get("description", "")
            parameters = function_def.get("parameters", {})
            
            if name:
                tools.append(Tool(
                    name=name,
                    description=description,
                    inputSchema=parameters
                ))
    return tools

@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """接收来自 Agent 的调用请求并执行底层函数。"""
    try:
        # 注意：在真实的微服务 MCP 架构中，resume_content 不会每次传来传去，
        # 而是只传 resume_id，MCP Server 自己查库。
        # 这里为了兼容当前系统的入参，我们从 arguments 的侧信道里提取 resume_content
        resume_content = arguments.pop("_resume_content", {})
        user_id = arguments.pop("_user_id", None)
        resume_id = arguments.pop("_resume_id", None)
        
        if name in ("read_memory", "update_memory"):
            if user_id is not None: arguments["user_id"] = user_id
            if resume_id is not None: arguments["resume_id"] = resume_id
            
        result = execute_resume_tool(
            tool_name=name,
            resume_content=resume_content,
            **arguments
        )
        
        # 很多工具返回 awaitable，如果是，就等待
        import inspect
        if inspect.isawaitable(result):
            result = await result
            
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
        
    except Exception as e:
        logger.error(f"MCP Tool execution failed: {e}")
        return [TextContent(type="text", text=json.dumps({"success": False, "error": str(e)}))]

if __name__ == "__main__":
    # 作为一个独立的微服务启动时，使用 stdio 标准输入输出作为通信通道
    import mcp.server.stdio
    import asyncio
    
    async def main():
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp.server.InitializationOptions(
                    server_name="ResumeOptimizationServer",
                    server_version="1.0.0",
                    capabilities=mcp.types.ServerCapabilities(
                        tools={}
                    )
                )
            )
            
    asyncio.run(main())
