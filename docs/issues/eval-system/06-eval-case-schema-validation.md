## Parent

PRD: `PRD.md`

## What to build

为评测用例增加 schema 校验入口，确保新增或修改 case 时能及时发现字段类型错误、ID 重复、fixture 引用失效和期望字段格式错误。

这个切片的目标是保护基准集质量，避免 malformed case 静默削弱评估系统。

## Acceptance criteria

- [x] 校验所有 case 的 ID 唯一且非空。
- [x] 校验简历 fixture 和 JD fixture 引用存在。
- [x] 校验期望字段类型正确，例如关键词列表、禁用内容列表、期望工具调用列表、决策期望枚举。
- [x] 校验失败时输出所有问题，而不是遇到第一个问题就退出。
- [x] 提供可通过 `uv run` 执行的校验入口。
- [x] 添加测试覆盖合法 case、重复 ID、缺失 fixture、字段类型错误和非法枚举值。

## Blocked by

Blocked by: `02-consume-explicit-case-expectations.md`
