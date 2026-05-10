/**
 * 简历布局配置模块
 * 
 * 管理简历的视觉密度、间距、模块顺序等配置
 */

import type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'

export type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'

export type LayoutDensity = 'comfortable' | 'normal' | 'compact' | 'custom'

export const TEMPLATE_STYLE_LABELS: Record<ResumeTemplateStyle, string> = {
  classic: '经典',
  modern: '现代',
}

/**
 * 三档预设对应的 spacingScale 值
 */
export const DENSITY_SPACING_SCALE: Record<Exclude<LayoutDensity, 'custom'>, number> = {
  comfortable: 1.3,
  normal: 1.0,
  compact: 0.7
}

/**
 * 默认模块顺序
 */
const DEFAULT_MODULE_ORDER: ResumeModule[] = [
  'personal',
  'education',
  'work',
  'projects',
  'skills'
]

/**
 * 模块显示名称
 */
export const MODULE_LABELS: Record<ResumeModule, string> = {
  personal: '个人信息',
  education: '教育经历',
  work: '工作经验',
  skills: '技能',
  projects: '项目经验'
}

/**
 * 将布局配置转换成预览和编辑器共用的模块列表。
 */
export function buildModuleConfig(
  moduleOrder: ResumeModule[],
  visibleModules: Set<ResumeModule>,
): ModuleConfig[] {
  return moduleOrder.map((module, index) => ({
    type: module,
    visible: visibleModules.has(module),
    order: index,
    label: MODULE_LABELS[module],
  }))
}

/**
 * 默认模块配置列表。
 */
export const DEFAULT_MODULE_CONFIG: ModuleConfig[] = buildModuleConfig(
  DEFAULT_MODULE_ORDER,
  new Set(DEFAULT_MODULE_ORDER),
)

/**
 * 简历布局配置接口
 */
export interface ResumeLayoutConfig {
  density: LayoutDensity
  moduleOrder: ResumeModule[]
  visibleModules: Set<ResumeModule>
  spacingScale: number  // 连续间距缩放，范围 0.5–1.5，默认 1.0
  templateStyle: ResumeTemplateStyle
}

/**
 * 默认布局配置
 */
export const DEFAULT_LAYOUT_CONFIG: ResumeLayoutConfig = {
  density: 'normal',
  moduleOrder: DEFAULT_MODULE_ORDER,
  visibleModules: new Set(DEFAULT_MODULE_ORDER),
  spacingScale: 1.0,
  templateStyle: 'classic',
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

/**
 * 将服务端返回的 layout_config 原始对象转换为 ResumeLayoutConfig
 */
export function deserializeLayoutConfig(raw: Record<string, unknown> | null | undefined): ResumeLayoutConfig {
  if (!raw) return DEFAULT_LAYOUT_CONFIG
  try {
    const templateStyle = raw.templateStyle === 'modern' ? 'modern' : 'classic'
    return {
      density: (raw.density as LayoutDensity) || 'normal',
      moduleOrder: (raw.moduleOrder as ResumeModule[]) || DEFAULT_MODULE_ORDER,
      spacingScale: typeof raw.spacingScale === 'number' ? raw.spacingScale : 1.0,
      visibleModules: new Set((raw.visibleModules as ResumeModule[]) || DEFAULT_MODULE_ORDER),
      templateStyle,
    }
  } catch {
    return DEFAULT_LAYOUT_CONFIG
  }
}

/**
 * 将 ResumeLayoutConfig 序列化为可存 JSON 的对象（Set → Array）
 */
function serializeLayoutConfig(config: ResumeLayoutConfig) {
  return {
    density: config.density,
    moduleOrder: config.moduleOrder,
    visibleModules: Array.from(config.visibleModules),
    spacingScale: config.spacingScale,
    templateStyle: config.templateStyle,
  }
}

/**
 * 保存布局配置到 localStorage（作为离线缓存）
 */
export function saveLayoutConfig(resumeId: number, config: ResumeLayoutConfig): void {
  const key = `resume_layout_${resumeId}`
  localStorage.setItem(key, JSON.stringify(serializeLayoutConfig(config)))
}

/**
 * 从 localStorage 加载布局配置（用于首次渲染前的占位，避免闪烁）
 */
export function loadLayoutConfig(resumeId: number): ResumeLayoutConfig {
  const key = `resume_layout_${resumeId}`
  const stored = localStorage.getItem(key)
  if (!stored) return DEFAULT_LAYOUT_CONFIG
  try {
    const parsed = JSON.parse(stored)
    return deserializeLayoutConfig(parsed)
  } catch {
    return DEFAULT_LAYOUT_CONFIG
  }
}

/**
 * 将布局配置持久化到服务端，同时更新 localStorage 缓存
 * debounce 由调用方控制（edit/page.tsx 中 800ms）
 */
export async function saveLayoutConfigToServer(resumeId: number, config: ResumeLayoutConfig): Promise<void> {
  // 同步更新本地缓存
  saveLayoutConfig(resumeId, config)

  await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/layout`, {
    method: 'PUT',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(serializeLayoutConfig(config)),
  })
  // 不抛错误——布局配置保存失败不应中断用户操作
}
