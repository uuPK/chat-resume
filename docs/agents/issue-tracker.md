# Issue Tracker：Beads (bd)

本仓库使用 **bd (beads)** 进行任务跟踪，数据存储在本地 Dolt 数据库中。

## 约定

- **查找可用工作**：`bd ready`
- **查看 issue 详情**：`bd show <id>`
- **认领工作**：`bd update <id> --claim`
- **关闭 issue**：`bd close <id>`
- **记住知识**：`bd remember`
- **完整命令参考**：`bd prime`

## 规则

- 所有任务跟踪必须使用 `bd`，不要使用 TodoWrite、TaskCreate 或 markdown TODO 列表。
- 同步架构：issues 存在本地 Dolt DB 中；同步使用 git remote 上的 `refs/dolt/data`；`.beads/issues.jsonl` 是被动导出。

## 当技能说 "publish to the issue tracker"

使用 `bd` 创建 issue。

## 当技能说 "fetch the relevant ticket"

使用 `bd show <id>` 查看 issue 详情。
