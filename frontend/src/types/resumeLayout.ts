/**
 * 简历布局共享类型
 *
 * 用于承接预览、编辑器和 Hook 之间共用的模块类型定义。
 */

export type ResumeModule = 'personal' | 'education' | 'work' | 'skills' | 'projects'

export type ResumeTemplateStyle = 'classic' | 'modern' | 'formal'

export interface ModuleConfig {
  type: ResumeModule
  visible: boolean
  order: number
  label: string
}
