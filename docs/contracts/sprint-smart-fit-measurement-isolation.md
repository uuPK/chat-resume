# 本轮任务名称

修复智能一页试算污染正式分页状态

# 本轮目标

让“智能一页”在点击后只通过独立测量逻辑寻找合适的 `spacingScale`，不把二分搜索过程中的临时 scale 写入正式分页预览，从而避免预览页数、页内容在计算中或计算后出现错乱。

# 为什么现在做这一轮

当前代码里智能一页和正式分页共用同一个隐藏测量容器。智能一页试算会反复切换 `measureScale`，而正式分页 hook 也监听这个容器尺寸变化，存在把临时试算结果用于正式分页的风险。这是主流程问题，优先级高于扩展交互、tooltip、自动询问等增强功能。

# 本轮范围

- 拆分正式分页测量容器和智能一页试算测量容器。
- 抽出可复用的行测量函数，让两个容器复用同一套高度计算逻辑。
- 智能一页二分搜索只读取试算容器。
- 正式分页只读取真实 `spacingScale` 对应的分页容器。
- 保持现有按钮入口、toast 文案、布局配置持久化逻辑不变。
- 最终实现允许修改的代码文件仅限：
  - `frontend/src/components/preview/hooks/useSmartFit.ts`
  - `frontend/src/components/preview/hooks/useLineBasedPagination.ts`
  - `frontend/src/components/preview/PaginatedResumePreview.tsx`

# 本轮不做

- 不新增“内容从一页变两页时自动询问”。
- 不重做布局控制面板 UI。
- 不修改 PDF 导出逻辑。
- 不调整分页算法本身的贪心策略。
- 不修复仓库现有 Playwright 类型依赖缺失问题。
- 不修改 `AGENTS.md`、`docs/prompt/` 和其他未列入本轮范围的说明文件；如因流程需要更新 contract 或 evaluator 文档，必须与实现改动分开说明。
- 不修改本 contract 列出的代码文件之外的任何实现文件；如需修改其他实现文件，必须先更新 contract 并重新审核。

# 输入

- 当前智能一页实现：
  - `frontend/src/components/preview/hooks/useSmartFit.ts`
  - `frontend/src/components/preview/hooks/useLineBasedPagination.ts`
  - `frontend/src/components/preview/PaginatedResumePreview.tsx`
- 现有产品规格：
  - `docs/contracts/spec-layout-spacing-and-smart-fit.md`

# 预期输出

- 代码层面：
  - 正式分页测量和智能一页试算测量互相隔离。
  - 智能一页成功后仍通过原有 `onSpacingScaleChange` 更新真实 scale。
  - 智能一页失败路径、已适配路径、内容过多路径不写入真实 `spacingScale`。
- 行为层面：
  - 点击“智能一页”时，计算过程中不会因为临时 scale 变化导致正式预览分页反复跳动或写入错误页数。
  - 成功后预览使用最终 scale 重新分页。
  - 如果当前已经一页，仍提示无需调整。
  - 如果最小 scale 仍放不下，仍提示内容过多。

# 交互要求（如有）

需要用户确认这个 contract 后，再继续把实现调整到严格符合这个范围。由于上一轮已经提前修改代码，确认后以这个 contract 为准做一次核对和必要修正，不扩大范围。

# 技术约束（如有）

- 不引入新依赖。
- 不重写分页算法。
- 不改变现有组件对外 props。
- 不触碰用户已有未跟踪文件。
- 使用现有 React state/ref 模式，不直接操控可见预览 DOM。

# 验收标准

- 正式分页容器的 padding 和 `--spacing-scale` 只受真实 `spacingScale` 控制。
- 智能一页试算容器的 padding 和 `--spacing-scale` 只受 `measureScale` 控制。
- 正式分页测量 ref 与智能一页试算 ref 必须是两个不同的 ref；不能复用同一个 DOM element，也不能通过同一个 callback ref 在不同模式之间切换用途。
- `useLineBasedPagination` 只能读取正式分页测量 ref。
- `useSmartFit` 调用的 `measureLines` 只能读取智能一页试算 ref，不能读取正式分页容器。
- `measureScale` 的变化不得作为正式分页 hook 的输入或依赖。
- 正式分页测量容器不得绑定 `measureScale` 到 padding 或 `--spacing-scale`。
- 智能一页试算容器不得绑定真实 `spacingScale` 作为试算 scale。
- 智能一页成功路径仍调用 `onSpacingScaleChange` 写入真实 scale。
- 智能一页失败路径、已适配路径、内容过多路径不得调用 `onSpacingScaleChange` 写入真实 scale。
- `useLineBasedPagination` 抽函数后必须保持原有测量规则：
  - 保持原有 section 遍历顺序，即按 `contentElement.children` 从前到后遍历。
  - 保持原有行元素遍历顺序，即按每个 section 内的 `[data-line-index]` 查询结果从前到后遍历。
  - 保持原有行高度读取方式，即使用 `lineElement.offsetHeight + lineElement` 的 `marginBottom`。
  - 保持原有 section 末尾折叠间距计算方式，即用最后一行 `marginBottom`、inner div `marginBottom`、section `marginBottom` 的最大值补充差额。
  - 保持原有空 DOM 或缺失 `contentRef.current` fallback 行为，即返回空行数组并由分页逻辑生成空页。
  - 保持原有分页高度计算输入，即 `calculatePages` 仍消费 `measureLines()` 返回的 `RenderableLine[]`。
  - 保持原有分页贪心策略不变。
- 局部 TypeScript 检查必须执行并通过以下命令：
  `cd frontend && npm exec tsc -- --noEmit --jsx preserve --lib dom,dom.iterable,esnext --module esnext --moduleResolution bundler --target es5 --allowJs --skipLibCheck --strict --noImplicitAny --esModuleInterop --resolveJsonModule --isolatedModules --incremental false src/components/preview/PaginatedResumePreview.tsx src/components/preview/hooks/useLineBasedPagination.ts src/components/preview/hooks/useSmartFit.ts`
- 全量 TypeScript 检查必须执行以下命令：
  `cd frontend && npm run type-check`
- 若全量 `npm run type-check` 失败，必须记录执行命令、退出码、关键错误文件和错误摘要，并明确错误是否出现在本轮允许修改的 3 个代码文件中；如果错误出现在本轮允许修改的 3 个代码文件中，默认判定不通过，除非能证明该错误在本轮之前已经存在。
- 必须执行 `git diff --name-only` 或 `git status --short` 来检查整体改动范围；除本轮允许修改的 3 个代码文件，以及 contract/评估文档这类流程文档外，不得出现其他实现文件改动。若存在其他实现文件改动，默认不通过，除非先更新 contract 并重新审核。

# 验证步骤

1. 运行局部 TypeScript 检查：
   `cd frontend && npm exec tsc -- --noEmit --jsx preserve --lib dom,dom.iterable,esnext --module esnext --moduleResolution bundler --target es5 --allowJs --skipLibCheck --strict --noImplicitAny --esModuleInterop --resolveJsonModule --isolatedModules --incremental false src/components/preview/PaginatedResumePreview.tsx src/components/preview/hooks/useLineBasedPagination.ts src/components/preview/hooks/useSmartFit.ts`

   记录执行目录、命令和退出码。
2. 运行全量 TypeScript 检查：
   `cd frontend && npm run type-check`

   记录执行目录、命令和退出码。
3. 如果全量 TypeScript 检查失败，记录关键错误文件和错误摘要，并确认错误是否出现在本轮允许修改的 3 个代码文件中。
4. 运行 `git diff --name-only` 或 `git status --short`，记录输出摘要，确认除本轮允许修改的 3 个代码文件，以及 contract/评估文档这类流程文档外，没有其他实现文件改动。
5. 查看 `git diff -- frontend/src/components/preview/hooks/useSmartFit.ts frontend/src/components/preview/hooks/useLineBasedPagination.ts frontend/src/components/preview/PaginatedResumePreview.tsx`，核对本轮 3 个代码文件的具体实现 diff。
6. 对照 `PaginatedResumePreview.tsx` 确认正式分页和智能一页试算使用两个不同 ref。
7. 对照 `PaginatedResumePreview.tsx` 确认 `useLineBasedPagination` 的输入不包含 `measureScale` 或试算容器 ref。
8. 对照 `PaginatedResumePreview.tsx` 确认 `useSmartFit` 的 `measureLines` 读取试算容器。
9. 对照 `useSmartFit.ts` 确认智能一页成功路径仍调用 `onSpacingScaleChange`，失败路径、已适配路径、内容过多路径不写入真实 scale。
10. 对照 `useLineBasedPagination.ts` 确认抽函数前后的 section 遍历、行遍历、行高度读取、section 折叠间距、空 DOM fallback、分页输入和贪心策略没有变化。
