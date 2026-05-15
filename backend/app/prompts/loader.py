"""
Prompt Loader - 按照 AgentSpec 模式管理 Prompt

设计参考 MoonshotAI/kimi-cli 的 agentspec.py：
- YAML 文件声明结构（模型参数、变量默认值）
- Markdown 文件存放 Prompt 正文
- Jinja2 负责变量渲染（支持 ${VAR} 和 {% if %} 条件块）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, StrictUndefined, UndefinedError

PROMPTS_DIR = Path(__file__).parent


@dataclass(frozen=True, slots=True)
class AgentPromptSpec:
    """已解析的 Agent Prompt 规格"""

    name: str
    version: str
    description: str
    system_prompt_path: Path
    system_prompt_args: dict[str, Any]  # 变量默认值
    model_defaults: dict[str, Any]  # temperature、max_tokens 等

    def render(self, **kwargs) -> str:
        """渲染 Prompt，kwargs 中的值覆盖 system_prompt_args 里的默认值"""
        context = {**self.system_prompt_args, **kwargs}
        raw = self.system_prompt_path.read_text(encoding="utf-8")
        try:
            env = Environment(
                variable_start_string="${",
                variable_end_string="}",
                undefined=StrictUndefined,
            )
            return env.from_string(raw).render(**context)
        except UndefinedError as e:
            raise ValueError(f"Prompt '{self.name}' 渲染失败，缺少变量: {e}") from e

    def __repr__(self) -> str:
        """用于返回对象的调试展示文本。"""
        return f"AgentPromptSpec(name={self.name!r}, version={self.version!r})"


def load_prompt(agent_name: str) -> AgentPromptSpec:
    """
    按 agent 名称加载 Prompt 规格。

    目录结构：
        prompts/<agent_name>/agent.yaml   # 结构配置
        prompts/<agent_name>/system.md    # Prompt 正文
    """
    spec_file = PROMPTS_DIR / agent_name / "agent.yaml"
    if not spec_file.exists():
        raise FileNotFoundError(f"Prompt spec not found: {spec_file}")

    with open(spec_file, encoding="utf-8") as f:
        data: dict[str, Any] = yaml.safe_load(f)

    version = str(data.get("version", "1.0"))
    agent = data.get("agent", {})

    prompt_path = (
        spec_file.parent / agent.get("system_prompt_path", "./system.md")
    ).resolve()
    if not prompt_path.exists():
        raise FileNotFoundError(f"System prompt file not found: {prompt_path}")

    return AgentPromptSpec(
        name=agent.get("name", agent_name),
        version=version,
        description=agent.get("description", ""),
        system_prompt_path=prompt_path,
        system_prompt_args=agent.get("system_prompt_args", {}),
        model_defaults=agent.get("model_defaults", {}),
    )
