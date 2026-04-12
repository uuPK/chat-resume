# Contract 审核结论

不批准进入实现阶段。

被审核 contract：

- `docs/contracts/sprint-smart-fit-measurement-isolation.md`

# 合理之处

- 本轮目标聚焦在“智能一页试算污染正式分页状态”，问题边界清晰。
- 范围限制较好，主要围绕以下 3 个文件：
  - `frontend/src/components/preview/hooks/useSmartFit.ts`
  - `frontend/src/components/preview/hooks/useLineBasedPagination.ts`
  - `frontend/src/components/preview/PaginatedResumePreview.tsx`
- 明确不做 UI 重做、PDF 导出修改、分页算法策略调整、自动询问等扩展事项。
- 保留现有按钮入口、toast 文案、布局配置持久化逻辑，避免本轮范围膨胀。
- 验收方向包含局部 TypeScript、全量 type-check、diff 范围、ref 隔离和成功路径检查。

# 存在问题

1. “局部 TypeScript 检查通过”不可执行。

   contract 没有写出具体命令，验收时无法确认执行者和验收者使用的是同一套检查方式。

2. 核心行为标准仍偏描述性。

   “计算过程中不会因为临时 scale 变化导致正式预览分页反复跳动或写入错误页数”是本轮核心目标，但当前验收标准主要是代码结构描述，没有明确要求验证正式分页 hook 不订阅试算容器，也没有明确要求验证 `measureScale` 变化不会触发正式分页状态更新。

3. “测量规则不变”缺少可判定边界。

   “`useLineBasedPagination` 仍使用原来的测量规则，结果不因抽函数而改变”过宽。它没有列出哪些规则必须保持，例如 section/item 遍历顺序、行高度读取方式、空 DOM fallback 行为、分页高度计算输入等。

4. 全量 type-check 失败归因规则不够严格。

   “失败原因必须不是本轮修改引入”需要明确判定依据。否则执行者可以只给出概括性说明，验收者难以判断是否真正与本轮无关。

5. diff 范围与既有改动关系不清。

   contract 提到“上一轮已经提前修改代码”，但没有明确最终验收时如何处理既有改动。需要说明最终实现允许修改的文件范围，以及本轮不得把说明文档变更混入实现范围。

6. DOM/ref 隔离标准不够硬。

   需要明确正式分页测量 ref 和智能一页试算 ref 必须是两个不同 ref，不能复用同一个 DOM element，也不能通过同一个 callback ref 在不同模式之间切换用途。

# 必须修改项

1. 明确局部 TypeScript 检查命令。

   例如在 contract 中写清楚实际执行命令。如果项目没有可靠的单文件 TS 检查能力，也必须明确替代命令，而不是只写“局部 TypeScript 检查通过”。

2. 将隔离要求改为硬验收标准。

   contract 至少应包含以下标准：

   - 正式分页测量 ref 与智能一页试算 ref 必须是不同 ref。
   - `useLineBasedPagination` 只能读取正式分页测量 ref。
   - `useSmartFit` 只能读取智能一页试算 ref。
   - `measureScale` 的变化不得作为正式分页 hook 的输入或依赖。
   - 正式分页测量容器不得绑定 `measureScale` 到 padding 或 `--spacing-scale`。
   - 智能一页试算容器不得绑定真实 `spacingScale` 作为试算 scale。

3. 收紧“测量规则不变”的定义。

   contract 应明确抽函数后必须保持：

   - 原有 section/item 遍历顺序。
   - 原有行高度读取方式。
   - 原有空 DOM 或缺失元素 fallback 行为。
   - 原有分页高度计算输入。
   - 原有分页贪心策略不变。

   如果需要改变其中任意一项，必须先更新 contract，否则验收时应按不允许变更处理。

4. 明确全量 type-check 失败归因方式。

   contract 应要求记录：

   - 执行命令。
   - 退出码。
   - 关键错误文件和错误摘要。
   - 错误是否出现在本轮修改的 3 个文件中。

   如果错误出现在本轮修改文件中，默认判定不通过，除非能证明该错误在本轮之前已经存在。

5. 明确最终 diff 范围。

   contract 应写清楚最终实现允许修改的文件仅限：

   - `frontend/src/components/preview/hooks/useSmartFit.ts`
   - `frontend/src/components/preview/hooks/useLineBasedPagination.ts`
   - `frontend/src/components/preview/PaginatedResumePreview.tsx`

   如需修改其他文件，必须先更新 contract 并重新审核。

6. 增加验收步骤中的代码级检查项。

   建议增加以下步骤：

   - 对照代码确认正式分页和智能一页试算使用两个不同 ref。
   - 对照代码确认 `useLineBasedPagination` 的依赖项不包含 `measureScale` 或试算容器。
   - 对照代码确认 `useSmartFit` 的 `measureLines` 读取试算容器。
   - 对照代码确认智能一页成功路径仍调用 `onSpacingScaleChange`，失败路径不写入真实 scale。

# 是否批准进入实现阶段

不批准。

必须先按以上修改项收紧 contract，再进入实现或继续验收。
