# Issue tracker：GitHub

本仓库的 Issues 和 PRD 都存放在 GitHub Issues 中。所有相关操作使用 `gh` CLI。

## 约定

- **创建 issue**：`gh issue create --title "..." --body "..."`。多行正文请使用 heredoc。
- **读取 issue**：`gh issue view <number> --comments`，需要时同时获取评论和标签。
- **列出 issues**：`gh issue list --state open --json number,title,body,labels,comments --jq '[.[] | {number, title, body, labels: [.labels[].name], comments: [.comments[].body]}]'`，按需添加 `--label` 和 `--state` 过滤。
- **评论 issue**：`gh issue comment <number> --body "..."`
- **添加 / 移除标签**：`gh issue edit <number> --add-label "..."` / `--remove-label "..."`
- **关闭 issue**：`gh issue close <number> --comment "..."`

在仓库目录内运行时，`gh` 会自动从 `git remote -v` 推断对应 GitHub 仓库。

## 当技能说 “publish to the issue tracker”

创建一个 GitHub Issue。

## 当技能说 “fetch the relevant ticket”

运行 `gh issue view <number> --comments`。
