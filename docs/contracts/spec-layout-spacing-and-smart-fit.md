# Spec：简历间距精细调节 + 智能一页适配

## 背景与现状

当前布局控制（`ResumeLayoutControls`）只提供三档固定预设（舒适 / 标准 / 紧凑），对应 `resumeLayoutConfig.ts` 中的 `DENSITY_CONFIG`。这三档通过切换 Tailwind class 实现，间距变化是跳跃式的，用户无法精细控制。

分页逻辑（`useLineBasedPagination`）会自动测量内容高度并分页，但没有任何"尝试将内容压缩进一页"的机制——内容超出 A4 高度就直接分到第二页。

---

## 目标

1. **精细间距调节**：在现有三档预设之外，提供连续可调的间距控制，让用户能精确控制简历的视觉密度
2. **智能一页适配**：一键自动计算并应用最小的间距/字号缩减，使简历内容恰好填满一页，不溢出

---

## 功能一：精细间距调节

### 设计方案

#### 1.1 数据模型扩展

在现有 `ResumeLayoutConfig` 基础上增加一个 `spacingScale` 字段，取值范围 `0.5 ~ 1.5`，默认值 `1.0`（对应当前的"标准"预设）。

三档预设与 `spacingScale` 的映射关系：
- 舒适 → `1.3`
- 标准 → `1.0`
- 紧凑 → `0.7`

选择预设时自动设置 `spacingScale`；手动拖动滑块时 `density` 字段变为 `custom`（新增一个枚举值，不显示在预设列表里，仅用于标记用户已自定义）。

#### 1.2 间距如何影响渲染

`spacingScale` 以 CSS 自定义属性（`--spacing-scale`）的方式注入到简历预览根节点。所有间距相关的 CSS 值乘以这个变量。

具体影响范围：
- 各模块之间的 `margin-bottom`（section 间距）
- 条目之间的 `space-y`（item 间距）
- 页面内边距（`PAGE_PADDING`）

字号**不随 `spacingScale` 变化**，字号有单独的控制通道（见 1.3）。

#### 1.3 UI 设计

在布局控制面板的"密度"标签页改造为两层：

**第一层：快速预设**（保留现有三个按钮，点击后同步更新滑块位置）

**第二层：精细控制**（新增）
- 标题："精细调节"
- 一个水平 slider，范围 0.5–1.5，步长 0.05
- slider 下方实时显示当前数值，如"间距: 0.85×"
- slider 右侧有"重置"按钮，点击恢复 1.0

两层之间不互斥，选择预设也会移动 slider，手动拖 slider 也会取消预设高亮。

#### 1.4 持久化

`spacingScale` 跟随现有的 `saveLayoutConfig` 一起存入 `localStorage`，key 结构不变。

---

## 功能二：智能一页适配

### 核心问题

简历内容超出一页 A4（1154px 可用高度）时，用户最常见的诉求是"稍微压缩一下，不要出现第二页"。手动试调三档预设太粗糙，无法精确命中。

### 算法设计

**触发条件**：点击"智能一页"按钮，或内容从一页变为两页时自动询问是否触发。

**执行流程（二分搜索）**：

```
1. 读取当前内容总高度 contentHeight（由 useLineBasedPagination 已知）
2. 读取单页可用高度 pageHeight = A4_HEIGHT - padding * 2 - safetyMargin
3. 如果 contentHeight <= pageHeight → 已经是一页，提示用户无需调整
4. 如果 contentHeight > pageHeight * 2 → 内容超出太多，提示"内容过多，建议删减内容而非压缩排版"
5. 否则，进入二分搜索：
   - 搜索范围：spacingScale ∈ [0.5, 当前值]
   - 每次猜测一个 spacingScale → 通知 DOM 应用 → 等待 ResizeObserver 重新测量 → 读取新 contentHeight
   - 当 contentHeight ≤ pageHeight 时记录当前值为候选，继续搜索更大值（尽量保留间距）
   - 当 contentHeight > pageHeight 时减小值
   - 迭代上限：8 次（足够精度，避免用户等待）
6. 应用找到的最优 spacingScale，保存到 layoutConfig
```

**搜索的关键约束**：
- 最小 spacingScale 下限为 `0.5`（低于此值阅读体验极差，不再压缩）
- 如果 `spacingScale = 0.5` 仍然超出一页，算法放弃并提示用户"内容过多，无法自动适配一页"
- 搜索过程中 DOM 变化对用户不可见（在隐藏测量容器中进行，不影响可见预览）

### 测量机制

`useLineBasedPagination` 已经有隐藏测量容器（`invisible absolute -top-[9999px]`），智能一页算法可以复用这个容器，在其上调整 `--spacing-scale` CSS 变量并读取 `scrollHeight`，不需要修改可见预览的任何状态，直到确定最终值后一次性应用。

### UI 设计

**入口**：布局控制面板底部新增一行，或在页数指示器（当前显示"第1页/共2页"的位置）旁边显示"智能一页"按钮。

**按钮状态**：
- 内容只有一页时：按钮灰显，tooltip 说明"当前已是一页"
- 内容超出两页时：按钮禁用，tooltip 说明"内容过多，建议删减"
- 内容在一到两页之间：按钮可点击，蓝色高亮

**执行过程**：
- 按钮变为 loading 状态，显示"计算中..."
- 完成后按钮恢复，slider 同步更新到新值
- 页数指示器变为"第1页/共1页"

**结果提示**：
- 成功："已将间距从 1.0× 调整为 0.78×，简历适配一页"
- 失败："内容过多（约 1.4 页），建议删减约 X 行内容"（X 通过高度比例估算）

---

## 实现边界与不做的事

| 不做 | 原因 |
|------|------|
| 自动调整字号 | 字号影响可读性，不应由算法静默修改 |
| 跨会话记住"智能一页"状态 | spacingScale 本身已持久化，效果已保留 |
| 后端存储 spacingScale | 这是视觉偏好，不影响内容，存 localStorage 足够 |
| 拖拽式调整各模块高度 | 复杂度过高，不在本期范围 |

---

## 文件影响范围

| 文件 | 变更类型 |
|------|---------|
| `frontend/src/lib/resumeLayoutConfig.ts` | 扩展 `ResumeLayoutConfig` 接口，增加 `spacingScale`，更新 `LayoutDensity` 枚举 |
| `frontend/src/components/preview/ResumeLayoutControls.tsx` | 新增 slider UI，接入新字段 |
| `frontend/src/components/preview/PaginatedResumePreview.tsx` | 将 `spacingScale` 注入为 CSS 自定义属性 |
| `frontend/src/components/preview/hooks/useLineBasedPagination.ts` | 暴露 `contentHeight` 供智能一页算法读取 |
| `frontend/src/components/preview/sections/*.tsx` | 各 section 组件的间距改用 `var(--spacing-scale)` 乘算（或通过传入 config 驱动） |
| 新增：`frontend/src/components/preview/hooks/useSmartFit.ts` | 智能一页的二分搜索逻辑 |

---

## 验收标准

1. slider 从 1.0 拖到 0.7，预览区间距实时变化，无明显卡顿（< 100ms 响应）
2. 切换到其他简历再切回，`spacingScale` 从 localStorage 正确恢复
3. 内容跨页时点击"智能一页"，最终结果为单页，页数指示器显示"1/1"
4. 内容超出两页时，"智能一页"按钮禁用且有 tooltip 说明
5. 智能一页完成后，slider 位置与实际应用的 `spacingScale` 一致
