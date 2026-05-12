"""Deep Agents harness profile customization for business agents."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from langchain.agents.middleware.types import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import SystemMessage

CHINESE_BASE_SYSTEM_PROMPT = """## 核心行为

- 简洁、直接。除非用户要求，不要过度解释。
- 不要添加不必要的开场白，例如“当然！”、“好问题！”、“我现在会...”。
- 不要说“我现在要做 X”；直接执行。
- 如果请求信息不足，只问推进下一步所需的最少问题。
- 如果用户询问处理思路，先解释，再执行。

## 专业客观性

- 优先保证准确性，而不是迎合用户的判断。
- 当用户不正确时，礼貌地指出分歧。
- 避免不必要的夸张、赞美或情绪化认同。

## 执行任务

当用户要求你做事时：

1. 先理解：阅读相关文件，检查现有模式。快速但充分地收集能开始行动的证据，然后迭代。
2. 行动：实现解决方案。快速推进，但保持准确。
3. 验证：按用户的要求检查工作，而不是只检查你自己的输出。第一次尝试很少完全正确；需要迭代。

持续工作，直到任务完整完成。不要中途停下来解释你打算怎么做；直接完成。只有在任务完成或确实被阻塞时才把控制权交还给用户。

当事情出错时：
- 如果同一件事反复失败，停下来分析原因；不要重复尝试同一种方法。
- 如果被阻塞，告诉用户问题是什么，并请求指导。

## 澄清请求

- 不要询问用户已经提供的信息。
- 当请求意图清楚时，使用合理默认值。
- 优先补齐缺失的语义信息，例如内容、交付形式、详细程度或告警条件。
- 当一个简短的阻塞性追问能推动任务时，不要先长篇解释工具、调度或集成限制。
- 先问定义领域的问题，再问实现细节问题。
- 对监控或告警请求，询问哪些信号、阈值或条件应该触发告警。

## 进度更新

对于较长任务，按合理间隔提供简短进度更新：用一句话概括已完成的工作和下一步。"""

EXCLUDED_DEEPAGENTS_TOOLS = frozenset(
    {
        "ls",
        "glob",
        "grep",
        "execute",
    }
)

_FILESYSTEM_PROMPT_MARKERS = (
    "## Following Conventions",
    "## Filesystem Tools `ls`, `read_file`, `write_file`, `edit_file`, `glob`, `grep`",
    "## Large Tool Results",
    "## Execute Tool `execute`",
)

CHINESE_WRITE_TODOS_SYSTEM_PROMPT = """## `write_todos`

你可以使用 `write_todos` 工具来管理和规划复杂目标。
当任务较复杂时，用它把工作拆成清晰步骤、跟踪进度，并让用户看到当前推进状态。

完成某一步后，必须及时把对应 todo 标记为 completed，不要把多个完成状态攒到最后一起更新。
对于只有少数步骤的简单任务，直接完成任务，不要使用这个工具。
写 todo 会消耗时间和 token，只在它确实能帮助管理复杂多步骤任务时使用。

## Todo 使用注意事项
- 不要并行调用多次 `write_todos`。
- 可以根据新信息调整 todo：新增必要任务、删除不再相关的任务、更新后续步骤。"""

CHINESE_TASK_SYSTEM_PROMPT = """## `task`（子代理调度器）

你可以使用 `task` 工具启动短生命周期子代理，让它们处理相互独立的任务。子代理只在本次任务期间存在，并返回一个结构化结果。

什么时候使用 task：
- 任务复杂且包含多个步骤，并且可以完整委托给子代理。
- 子任务之间相互独立，可以并行处理。
- 子任务需要大量上下文、搜索或分析，可能挤占主线程上下文。
- 隔离执行能提高可靠性，例如代码执行、结构化搜索或数据整理。
- 你只需要子代理最终结果，不需要观察其中间过程。

子代理生命周期：
1. Spawn：提供明确角色、任务说明和预期输出。
2. Run：子代理自主完成任务。
3. Return：子代理返回单个结构化结果。
4. Reconcile：主代理整合结果并回复用户。

什么时候不要使用 task：
- 你需要查看子代理的中间步骤。
- 任务很简单，只需要少量工具调用或简单查询。
- 委托不能减少 token、复杂度或上下文压力。
- 拆分只会增加延迟而没有收益。

## task 使用注意事项
- 能并行的独立任务应尽量并行发起，节省用户时间。
- 对多部分复杂目标，可以用 `task` 隔离子任务。
- 只有当任务确实复杂、独立且适合委托时才使用 `task`。"""

_configured = False


class DeepAgentsPromptMiddleware(AgentMiddleware[Any, Any, Any]):
    """Localize Deep Agents middleware prompts and hide excluded tool guidance."""

    @property
    def name(self) -> str:
        """Return the LangChain middleware identifier."""
        return "DeepAgentsPromptMiddleware"

    def wrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], ModelResponse[Any]],
    ) -> ModelResponse[Any]:
        return handler(self._rewrite_system_prompt(request))

    async def awrap_model_call(
        self,
        request: ModelRequest[Any],
        handler: Callable[[ModelRequest[Any]], Awaitable[ModelResponse[Any]]],
    ) -> ModelResponse[Any]:
        return await handler(self._rewrite_system_prompt(request))

    @classmethod
    def _rewrite_system_prompt(cls, request: ModelRequest[Any]) -> ModelRequest[Any]:
        system_message = request.system_message
        if system_message is None:
            return request

        content_blocks = []
        changed = False
        for block in system_message.content_blocks:
            if not isinstance(block, dict) or block.get("type") != "text":
                content_blocks.append(block)
                continue

            rewritten_text = cls._rewrite_text_block(str(block.get("text", "")))
            if rewritten_text is None:
                changed = True
                continue
            if rewritten_text != block.get("text"):
                changed = True
                content_blocks.append({"type": "text", "text": rewritten_text})
                continue
            content_blocks.append(block)

        if not changed:
            return request
        return request.override(system_message=SystemMessage(content_blocks=content_blocks))

    @classmethod
    def _rewrite_text_block(cls, text: str) -> str | None:
        if any(marker in text for marker in _FILESYSTEM_PROMPT_MARKERS):
            return None
        if "## `write_todos`" in text:
            return CHINESE_WRITE_TODOS_SYSTEM_PROMPT
        if "## `task` (subagent spawner)" in text:
            return cls._translate_task_prompt(text)
        return text

    @staticmethod
    def _translate_task_prompt(text: str) -> str:
        marker = "Available subagent types:\n"
        if marker not in text:
            return CHINESE_TASK_SYSTEM_PROMPT

        _, _, available_agents = text.partition(marker)
        translated_agents = available_agents.strip().replace(
            "general-purpose: General-purpose agent for researching complex questions, searching for files and content, and executing multi-step tasks. When you are searching for a keyword or file and are not confident that you will find the right match in the first few tries use this agent to perform the search for you. This agent has access to all tools as the main agent.",
            "general-purpose：通用子代理，用于研究复杂问题、搜索文件和内容、执行多步骤任务。当你不确定首次搜索能否找到正确关键词或文件时，可以用它来完成搜索。它拥有与主代理相同的工具权限。",
        )
        if not translated_agents:
            return CHINESE_TASK_SYSTEM_PROMPT
        return f"{CHINESE_TASK_SYSTEM_PROMPT}\n\n可用子代理类型：\n{translated_agents}"


def configure_deepagents_harness_profile() -> None:
    """Replace the SDK default base prompt with a Chinese base prompt."""
    global _configured
    if _configured:
        return

    from deepagents import HarnessProfile, register_harness_profile

    register_harness_profile(
        "openai",
        HarnessProfile(
            base_system_prompt=CHINESE_BASE_SYSTEM_PROMPT,
            excluded_tools=EXCLUDED_DEEPAGENTS_TOOLS,
            extra_middleware=[DeepAgentsPromptMiddleware()],
        ),
    )
    _configured = True


__all__ = [
    "CHINESE_BASE_SYSTEM_PROMPT",
    "CHINESE_TASK_SYSTEM_PROMPT",
    "CHINESE_WRITE_TODOS_SYSTEM_PROMPT",
    "DeepAgentsPromptMiddleware",
    "EXCLUDED_DEEPAGENTS_TOOLS",
    "configure_deepagents_harness_profile",
]
