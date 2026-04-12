/**
 * 简历布局配置模块
 * 
 * 管理简历的视觉密度、间距、模块顺序等配置
 */

export type LayoutDensity = 'comfortable' | 'normal' | 'compact' | 'custom'
export type ResumeModule = 'personal' | 'education' | 'work' | 'skills' | 'projects'

/**
 * 三档预设对应的 spacingScale 值
 */
export const DENSITY_SPACING_SCALE: Record<Exclude<LayoutDensity, 'custom'>, number> = {
  comfortable: 1.3,
  normal: 1.0,
  compact: 0.7
}

/**
 * 布局密度配置
 */
export const DENSITY_CONFIG = {
  comfortable: {
    sectionMargin: 'mb-8',
    titleMargin: 'mb-4',
    itemSpacing: 'space-y-6',
    fontSize: {
      name: 'text-3xl',
      position: 'text-xl',
      sectionTitle: 'text-xl',
      itemTitle: 'text-base',
      body: 'text-sm'
    },
    padding: {
      page: 48,
      section: 'py-2'
    }
  },
  normal: {
    sectionMargin: 'mb-6',
    titleMargin: 'mb-3',
    itemSpacing: 'space-y-4',
    fontSize: {
      name: 'text-2xl',
      position: 'text-lg',
      sectionTitle: 'text-lg',
      itemTitle: 'text-base',
      body: 'text-sm'
    },
    padding: {
      page: 40,
      section: 'py-1.5'
    }
  },
  compact: {
    sectionMargin: 'mb-4',
    titleMargin: 'mb-2',
    itemSpacing: 'space-y-3',
    fontSize: {
      name: 'text-xl',
      position: 'text-base',
      sectionTitle: 'text-base',
      itemTitle: 'text-sm',
      body: 'text-xs'
    },
    padding: {
      page: 32,
      section: 'py-1'
    }
  }
} as const

/**
 * 默认模块顺序
 */
export const DEFAULT_MODULE_ORDER: ResumeModule[] = [
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
 * 简历布局配置接口
 */
export interface ResumeLayoutConfig {
  density: LayoutDensity
  moduleOrder: ResumeModule[]
  visibleModules: Set<ResumeModule>
  spacingScale: number  // 连续间距缩放，范围 0.5–1.5，默认 1.0
}

/**
 * 默认布局配置
 */
export const DEFAULT_LAYOUT_CONFIG: ResumeLayoutConfig = {
  density: 'normal',
  moduleOrder: DEFAULT_MODULE_ORDER,
  visibleModules: new Set(DEFAULT_MODULE_ORDER),
  spacingScale: 1.0
}

/**
 * 获取密度配置（'custom' 密度回退到 'normal'）
 */
export function getDensityConfig(density: LayoutDensity) {
  if (density === 'custom') return DENSITY_CONFIG['normal']
  return DENSITY_CONFIG[density]
}

/**
 * 保存布局配置到localStorage
 */
export function saveLayoutConfig(resumeId: number, config: ResumeLayoutConfig): void {
  const key = `resume_layout_${resumeId}`
  const serialized = {
    ...config,
    visibleModules: Array.from(config.visibleModules)
  }
  localStorage.setItem(key, JSON.stringify(serialized))
}

/**
 * 从localStorage加载布局配置
 */
export function loadLayoutConfig(resumeId: number): ResumeLayoutConfig {
  const key = `resume_layout_${resumeId}`
  const stored = localStorage.getItem(key)

  if (!stored) {
    return DEFAULT_LAYOUT_CONFIG
  }

  try {
    const parsed = JSON.parse(stored)
    return {
      ...parsed,
      spacingScale: typeof parsed.spacingScale === 'number' ? parsed.spacingScale : 1.0,
      visibleModules: new Set(parsed.visibleModules || DEFAULT_MODULE_ORDER)
    }
  } catch {
    return DEFAULT_LAYOUT_CONFIG
  }
}
