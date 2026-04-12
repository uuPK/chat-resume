# Contract 审核结论

不批准进入实现阶段。

被审核 contract：

- `docs/contracts/sprint-smart-fit-measurement-isolation.md`

# 合理之处

- 本轮目标仍然聚焦在“智能一页试算污染正式分页状态”，范围没有扩散到 UI、PDF 导出或分页策略重写。
- 已明确最终实现允许修改的 3 个代码文件，范围比上一版更清晰。
- 已补充 ref 隔离、`measureScale` 不进入正式分页 hook、成功路径和失败路径是否调用 `onSpacingScaleChange` 等关键验收标准。
- 已将“测量规则不变”拆成可检查的具体规则，包括 section 遍历、行遍历、行高度读取、section 折叠间距、空 DOM fallback、分页输入和贪心策略。
- 已要求执行局部 TypeScript 检查和全量 `npm run type-check`，并要求记录全量检查失败的归因信息。

# 存在问题

1. 局部 TypeScript 检查命令的执行目录不明确。

   contract 写的局部命令使用 `src/components/...` 路径：

   `npm exec tsc -- --noEmit ... src/components/preview/PaginatedResumePreview.tsx ...`

   这个命令看起来必须在 `frontend` 目录执行。如果验收者在仓库根目录执行，路径应当是 `frontend/src/...`，否则命令会因为路径不存在或配置上下文不一致而失败。当前 contract 没有明确 `cd frontend`，因此“局部 TypeScript 检查必须执行并通过”仍不可稳定复现。

2. 全量 TypeScript 检查命令的执行目录也不明确。

   contract 写的是 `npm run type-check`，但没有说明是在仓库根目录执行还是在 `frontend` 目录执行。若项目的 `type-check` script 位于 `frontend/package.json`，验收者在根目录执行会得到错误结论。

3. diff 范围验证命令无法证明“只修改 3 个文件”。

   contract 的第 4 个验证步骤是：

   `git diff -- frontend/src/components/preview/hooks/useSmartFit.ts frontend/src/components/preview/hooks/useLineBasedPagination.ts frontend/src/components/preview/PaginatedResumePreview.tsx`

   这个命令只显示指定 3 个文件的 diff，不能发现其他文件是否也被修改。因此它不能验收“最终实现允许修改的代码文件仅限这 3 个文件”这一范围约束。

4. “不改 `AGENTS.md`、`docs/prompt/` 等未跟踪说明文件”表述不准确。

   `AGENTS.md` 当前已经存在于仓库路径中，但是否未跟踪需要以 `git status --short` 为准。contract 不应把文件跟踪状态写死为“未跟踪”。更稳妥的标准是“不修改 `AGENTS.md`、`docs/prompt/` 和其他非本轮实现文件”。

# 必须修改项

1. 明确所有命令的执行目录。

   如果 TypeScript 检查应在 `frontend` 目录执行，contract 应写成：

   `cd frontend && npm exec tsc -- --noEmit --jsx preserve --lib dom,dom.iterable,esnext --module esnext --moduleResolution bundler --target es5 --allowJs --skipLibCheck --strict --noImplicitAny --esModuleInterop --resolveJsonModule --isolatedModules --incremental false src/components/preview/PaginatedResumePreview.tsx src/components/preview/hooks/useLineBasedPagination.ts src/components/preview/hooks/useSmartFit.ts`

   全量检查也应写成：

   `cd frontend && npm run type-check`

   如果实际应在仓库根目录执行，则路径必须改为 `frontend/src/...`，并确认根目录存在对应 npm script。

2. 修改 diff 范围验证方式。

   contract 应增加能够发现所有改动文件的命令，例如：

   `git diff --name-only`

   或：

   `git status --short`

   验收标准应明确：除允许的 3 个代码文件，以及 contract/评估文档这类流程文档外，不得出现其他实现文件改动。若存在其他实现文件改动，默认不通过，除非先更新 contract 并重新审核。

3. 修正“不改未跟踪说明文件”的表述。

   建议改为：

   “不修改 `AGENTS.md`、`docs/prompt/` 和其他未列入本轮范围的说明文件；如因流程需要更新 contract 或 evaluator 文档，必须与实现改动分开说明。”

4. 在验证步骤中补充命令输出记录要求。

   建议明确记录：

   - 局部 TypeScript 检查的执行目录、命令和退出码。
   - 全量 TypeScript 检查的执行目录、命令和退出码。
   - `git diff --name-only` 或 `git status --short` 的输出摘要。

# 是否批准进入实现阶段

不批准。

新版 contract 已经接近可验收，但仍需先修正命令执行目录和 diff 范围检查方式。否则验收者可能因为执行目录不同得到不可复现的 TypeScript 结果，也无法证明实现没有越界修改。
