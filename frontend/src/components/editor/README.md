# 模块顺序编辑器使用指南

## 快速开始

### 第一步：在编辑页面引入组件

在 `app/resume/[id]/edit/page.tsx` 中集成模块顺序编辑器：

```typescript
'use client'

import { useState } from 'react'
import ResumePreview from '@/components/preview/ResumePreview'
import ModuleOrderEditor from '@/components/editor/ModuleOrderEditor'
import { ModuleConfig, DEFAULT_MODULE_ORDER } from '@/components/preview/PaginatedResumePreview'

export default function ResumeEditPage() {
  // 简历内容状态
  const [resumeContent, setResumeContent] = useState({...})
  
  // 模块顺序状态
  const [moduleOrder, setModuleOrder] = useState<ModuleConfig[]>(DEFAULT_MODULE_ORDER)

  return (
    <div className="grid grid-cols-3 gap-6">
      {/* 左侧：编辑区域 */}
      <div className="col-span-1">
        {/* 现有的编辑表单 */}
        <div>...</div>
        
        {/* 新增：模块顺序编辑器 */}
        <div className="mt-6">
          <ModuleOrderEditor 
            moduleOrder={moduleOrder}
            onChange={setModuleOrder}
          />
        </div>
      </div>

      {/* 右侧：预览区域 */}
      <div className="col-span-2">
        <ResumePreview 
          content={resumeContent}
          moduleOrder={moduleOrder}  {/* 传入自定义顺序 */}
        />
      </div>
    </div>
  )
}
```

### 第二步：持久化配置（可选）

如果需要保存用户的模块顺序偏好：

```typescript
// 在简历数据中添加模块顺序配置
interface Resume {
  id: number
  content: ResumeContent
  moduleOrder?: ModuleConfig[]  // 新增字段
}

// 保存时一起提交
const saveResume = async () => {
  await resumeApi.updateResume(resumeId, {
    content: resumeContent,
    module_order: moduleOrder  // 保存模块顺序
  })
}

// 加载时恢复配置
useEffect(() => {
  const loadResume = async () => {
    const resume = await resumeApi.getResume(resumeId)
    setResumeContent(resume.content)
    if (resume.module_order) {
      setModuleOrder(resume.module_order)
    }
  }
  loadResume()
}, [resumeId])
```

## 使用场景示例

### 场景1：应届毕业生

**目标**：突出教育背景和项目经验

```typescript
// 点击"应届生模板"按钮，自动应用以下配置：
const freshGraduateOrder = [
  { type: 'personal', visible: true, order: 0, label: '个人信息' },
  { type: 'education', visible: true, order: 1, label: '教育背景' },    // 提前
  { type: 'projects', visible: true, order: 2, label: '项目经验' },     // 提前
  { type: 'skills', visible: true, order: 3, label: '技能专长' },
  { type: 'work', visible: true, order: 4, label: '实习经验' },         // 靠后
]
```

### 场景2：资深工程师

**目标**：突出丰富的工作经验

```typescript
// 点击"资深工程师"按钮，自动应用以下配置：
const seniorEngineerOrder = [
  { type: 'personal', visible: true, order: 0, label: '个人信息' },
  { type: 'work', visible: true, order: 1, label: '工作经验' },         // 最重要
  { type: 'skills', visible: true, order: 2, label: '技能专长' },
  { type: 'projects', visible: true, order: 3, label: '核心项目' },
  { type: 'education', visible: true, order: 4, label: '教育背景' },    // 不太重要
]
```

### 场景3：技术专家/开源贡献者

**目标**：突出技术能力和开源项目

```typescript
// 点击"技术专家"按钮，自动应用以下配置：
const techExpertOrder = [
  { type: 'personal', visible: true, order: 0, label: '个人信息' },
  { type: 'skills', visible: true, order: 1, label: '技术栈' },         // 最重要
  { type: 'projects', visible: true, order: 2, label: '开源项目' },     // 很重要
  { type: 'work', visible: true, order: 3, label: '工作经历' },
  { type: 'education', visible: false, order: 4, label: '教育背景' },   // 隐藏
]
```

### 场景4：自定义配置

**手动调整**：用户可以自己拖拽调整

1. 点击上下箭头改变顺序
2. 点击眼睛图标隐藏不需要的模块
3. 实时预览效果

## 组件API

### ModuleOrderEditor Props

```typescript
interface ModuleOrderEditorProps {
  moduleOrder?: ModuleConfig[]          // 当前模块顺序配置
  onChange: (newOrder: ModuleConfig[]) => void  // 配置改变时的回调
}
```

### ModuleConfig 结构

```typescript
interface ModuleConfig {
  type: 'personal' | 'education' | 'work' | 'skills' | 'projects'
  visible: boolean   // 是否显示该模块
  order: number      // 显示顺序（0最靠前）
  label: string      // 模块显示名称
}
```

## 高级用法

### 根据岗位类型自动推荐顺序

```typescript
const getRecommendedOrder = (jobTitle: string): ModuleConfig[] => {
  const lowerTitle = jobTitle.toLowerCase()
  
  // 前端开发
  if (lowerTitle.includes('前端') || lowerTitle.includes('frontend')) {
    return [
      { type: 'personal', visible: true, order: 0, label: '个人信息' },
      { type: 'skills', visible: true, order: 1, label: '技术栈' },
      { type: 'projects', visible: true, order: 2, label: '项目经验' },
      { type: 'work', visible: true, order: 3, label: '工作经验' },
      { type: 'education', visible: true, order: 4, label: '教育背景' },
    ]
  }
  
  // 产品经理
  if (lowerTitle.includes('产品') || lowerTitle.includes('product')) {
    return [
      { type: 'personal', visible: true, order: 0, label: '个人信息' },
      { type: 'work', visible: true, order: 1, label: '工作经验' },
      { type: 'projects', visible: true, order: 2, label: '产品案例' },
      { type: 'skills', visible: true, order: 3, label: '专业技能' },
      { type: 'education', visible: true, order: 4, label: '教育背景' },
    ]
  }
  
  // 默认顺序
  return DEFAULT_MODULE_ORDER
}

// 使用
useEffect(() => {
  if (jobApplication.position) {
    const recommended = getRecommendedOrder(jobApplication.position)
    setModuleOrder(recommended)
  }
}, [jobApplication.position])
```

### 添加拖拽排序功能（高级）

如果需要拖拽功能，可以集成 `react-beautiful-dnd`：

```typescript
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd'

// 在ModuleOrderEditor中添加拖拽支持
const onDragEnd = (result: DropResult) => {
  if (!result.destination) return
  
  const items = Array.from(modules)
  const [reorderedItem] = items.splice(result.source.index, 1)
  items.splice(result.destination.index, 0, reorderedItem)
  
  // 更新order值
  const updatedItems = items.map((item, index) => ({
    ...item,
    order: index
  }))
  
  setModules(updatedItems)
  onChange(updatedItems)
}
```

## 注意事项

1. **个人信息模块**
   - 始终保持 `visible: true`
   - 建议始终保持 `order: 0`（第一位）
   - 在UI中禁用隐藏按钮

2. **模块可见性**
   - 隐藏的模块不会在预览中渲染
   - 但仍保留在配置中，可以随时恢复

3. **顺序编号**
   - order值越小，越靠前
   - 建议从0开始连续递增
   - 组件会自动按order排序

4. **性能考虑**
   - 配置变化时会触发预览重新渲染
   - 使用 `useMemo` 优化性能
   - 考虑添加防抖处理

## 完整示例代码

查看完整实现：
- 组件代码：`/components/editor/ModuleOrderEditor.tsx`
- 集成示例：`/app/resume/[id]/edit/page.tsx`
- 类型定义：`/components/preview/PaginatedResumePreview.tsx`

## 效果演示

```
┌─────────────────────────────────────────────┐
│ 自定义模块顺序                               │
├─────────────────────────────────────────────┤
│ [1] 个人信息          [↑] [↓] [👁]          │
│ [2] 工作经验          [↑] [↓] [👁]          │  ← 可以调整
│ [3] 项目经验          [↑] [↓] [👁]          │
│ [4] 技能专长          [↑] [↓] [👁]          │
│ [5] 教育背景          [↑] [↓] [👁️‍🗨️]        │  ← 已隐藏
└─────────────────────────────────────────────┘
```

实时预览会立即反映你的调整！

