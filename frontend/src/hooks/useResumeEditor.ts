/**
 * 简历编辑业务 Hook
 *
 * 用于集中管理简历加载、局部更新、布局配置、自动保存和导出行为。
 */

'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import toast from 'react-hot-toast'

import { resumeApi, type Resume } from '@/lib/api'
import {
  buildModuleConfig,
  DEFAULT_LAYOUT_CONFIG,
  deserializeLayoutConfig,
  loadLayoutConfig,
  ResumeLayoutConfig,
  ResumeModule,
  saveLayoutConfig,
  saveLayoutConfigToServer,
} from '@/lib/resumeLayoutConfig'
import type { ModuleConfig } from '@/types/resumeLayout'

import { AutoSaveStatus, useResumeAutoSave } from './useResumeAutoSave'

const EDITOR_SECTION_TO_MODULE: Partial<Record<string, ResumeModule>> = {
  personal: 'personal',
  education: 'education',
  work: 'work',
  projects: 'projects',
  skills: 'skills',
}

interface UseResumeEditorOptions {
  resumeId: string
  isAuthenticated: boolean
}

/**
 * 提供编辑页主业务状态，减少 page.tsx 中的数据、副作用和保存逻辑。
 */
export function useResumeEditor({ resumeId, isAuthenticated }: UseResumeEditorOptions) {
  const router = useRouter()
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [activeSection, setActiveSection] = useState('job_application')
  const [layoutConfig, setLayoutConfig] = useState<ResumeLayoutConfig>(DEFAULT_LAYOUT_CONFIG)
  const layoutSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [previewTotalPages, setPreviewTotalPages] = useState(0)
  const [isSmartFitting, setIsSmartFitting] = useState(false)
  const smartFitTriggerRef = useRef<(() => Promise<any>) | null>(null)

  const {
    autoSaveStatus,
    syncResumeSnapshot,
    updateDraft,
    performAutoSave,
    setAutoSaveStatus,
  } = useResumeAutoSave({
    setResume,
    saveResume: async (draftResume) => (
      resumeApi.updateResume(draftResume.id, {
        title: draftResume.title,
        content: draftResume.content,
      })
    ),
  })

  /**
   * 首次进入页面时先读本地布局缓存，避免服务端快照回来前出现闪烁。
   */
  useEffect(() => {
    if (!resumeId) return
    setLayoutConfig(loadLayoutConfig(parseInt(resumeId, 10)))
  }, [resumeId])

  /**
   * 组件卸载时清理布局保存防抖定时器，避免重复请求。
   */
  useEffect(() => {
    return () => {
      if (layoutSaveTimeoutRef.current) {
        clearTimeout(layoutSaveTimeoutRef.current)
      }
    }
  }, [])

  /**
   * 拉取服务端简历并同步本地编辑快照。
   */
  const fetchResume = useCallback(async () => {
    if (!resumeId || !isAuthenticated) return

    try {
      setResumeLoading(true)
      const data = await resumeApi.getResume(parseInt(resumeId, 10))
      setResume(data)
      syncResumeSnapshot(data, { saved: true })
      const serverConfig = deserializeLayoutConfig(data.layout_config as Record<string, unknown> | null)
      setLayoutConfig(serverConfig)
      saveLayoutConfig(parseInt(resumeId, 10), serverConfig)
    } catch {
      toast.error('获取简历失败')
      router.push('/dashboard')
    } finally {
      setResumeLoading(false)
    }
  }, [isAuthenticated, resumeId, router, syncResumeSnapshot])

  /**
   * 更新布局配置并在防抖后同步到服务端，避免每次拖拽都立即发请求。
   */
  const handleLayoutConfigChange = useCallback((newConfig: ResumeLayoutConfig) => {
    setLayoutConfig(newConfig)
    if (!resumeId) return
    const id = parseInt(resumeId, 10)
    saveLayoutConfig(id, newConfig)
    if (layoutSaveTimeoutRef.current) {
      clearTimeout(layoutSaveTimeoutRef.current)
    }
    layoutSaveTimeoutRef.current = setTimeout(() => {
      void saveLayoutConfigToServer(id, newConfig)
    }, 800)
  }, [resumeId])

  /**
   * 触发预览区的智能一页能力，并把结果反馈给用户。
   */
  const handleSmartFitHeaderClick = useCallback(async () => {
    if (!smartFitTriggerRef.current || isSmartFitting) return
    setIsSmartFitting(true)
    try {
      const result = await smartFitTriggerRef.current()
      if (!result) return
      if (result.status === 'already_fits') {
        toast('当前简历已是一页，无需调整', { icon: '✅' })
      } else if (result.status === 'too_much_content') {
        toast.error(`内容过多（约 ${result.pages} 页），建议删减内容`)
      } else if (result.status === 'success') {
        toast.success(`已将间距从 ${result.oldScale.toFixed(2)}× 调整为 ${result.newScale.toFixed(2)}×，简历适配一页`)
      }
    } finally {
      setIsSmartFitting(false)
    }
  }, [isSmartFitting])

  /**
   * 导出当前简历为 PDF，并直接触发浏览器下载。
   */
  const handleExportPDF = useCallback(async () => {
    if (!resume) {
      toast.error('简历不存在')
      return
    }

    try {
      setExporting(true)
      const toastId = toast.loading('正在生成PDF...')
      const result = await resumeApi.exportResume(resume.id, 'pdf')
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const downloadUrl = `${apiBaseUrl}${result.download_url}`
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = result.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      toast.success('PDF导出成功', { id: toastId })
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'PDF导出失败')
    } finally {
      setExporting(false)
    }
  }, [resume])

  /**
   * 更新指定简历模块内容，并交给自动保存 Hook 处理脏数据状态。
   */
  const updateResumeContent = useCallback((section: string, data: unknown) => {
    updateDraft((previousResume) => ({
      ...previousResume,
      content: {
        ...previousResume.content,
        [section]: data,
      },
    }))
  }, [updateDraft])

  /**
   * 更新简历标题，并交给自动保存 Hook 处理脏数据状态。
   */
  const updateResumeTitle = useCallback((title: string) => {
    updateDraft((previousResume) => ({
      ...previousResume,
      title,
    }))
  }, [updateDraft])

  /**
   * 识别 JD 图片中的文字，供页面把 OCR 能力注入给编辑组件。
   */
  const recognizeJobDescriptionImage = useCallback(async (file: File) => {
    const result = await resumeApi.ocrJobDescriptionImage(file)
    return result.text
  }, [])

  /**
   * 接收 Agent 回写的整份简历内容，并把它视为新的已保存快照。
   */
  const applyAgentResumeContent = useCallback((content: Resume['content']) => {
    setAutoSaveStatus('idle')
    setResume((previousResume) => {
      if (!previousResume) return previousResume
      const updatedResume = { ...previousResume, content }
      syncResumeSnapshot(updatedResume, { saved: true })
      return updatedResume
    })
  }, [setAutoSaveStatus, syncResumeSnapshot])

  const moduleOrder = useMemo<ModuleConfig[]>(
    () => buildModuleConfig(layoutConfig.moduleOrder, layoutConfig.visibleModules),
    [layoutConfig],
  )

  const editorSections = useMemo(() => {
    const allSections = [
      { key: 'job_application', label: '岗位' },
      { key: 'personal', label: '个人' },
      { key: 'education', label: '教育' },
      { key: 'work', label: '工作' },
      { key: 'projects', label: '项目' },
      { key: 'skills', label: '技能' },
    ]
    return allSections.filter((section) => {
      const mappedModule = EDITOR_SECTION_TO_MODULE[section.key]
      return mappedModule ? layoutConfig.visibleModules.has(mappedModule) : true
    })
  }, [layoutConfig.visibleModules])

  /**
   * 当当前编辑模块被隐藏时，自动切到仍然可见的第一个模块。
   */
  useEffect(() => {
    const activeModule = EDITOR_SECTION_TO_MODULE[activeSection]
    if (!activeModule || layoutConfig.visibleModules.has(activeModule)) {
      return
    }
    const fallbackSection = editorSections[0]?.key || 'job_application'
    if (fallbackSection !== activeSection) {
      setActiveSection(fallbackSection)
    }
  }, [activeSection, editorSections, layoutConfig.visibleModules])

  return {
    resume,
    resumeLoading,
    exporting,
    autoSaveStatus: autoSaveStatus as AutoSaveStatus,
    activeSection,
    setActiveSection,
    layoutConfig,
    previewTotalPages,
    setPreviewTotalPages,
    isSmartFitting,
    smartFitTriggerRef,
    moduleOrder,
    editorSections,
    fetchResume,
    performAutoSave,
    handleLayoutConfigChange,
    handleSmartFitHeaderClick,
    handleExportPDF,
    recognizeJobDescriptionImage,
    updateResumeContent,
    updateResumeTitle,
    applyAgentResumeContent,
  }
}
