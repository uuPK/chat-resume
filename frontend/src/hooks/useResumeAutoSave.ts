/**
 * 简历自动保存 Hook
 *
 * 用于把编辑页里的自动保存状态机和定时器集中管理，降低页面复杂度。
 */

'use client'
// 用于提供 hooks/useResumeAutoSave.ts 模块。

import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { useTranslations } from 'next-intl'

import type { Resume } from '@/lib/api'

export type AutoSaveStatus = 'idle' | 'pending' | 'saving' | 'success' | 'error'

const AUTO_SAVE_DELAY = 1500

interface UseResumeAutoSaveOptions {
  setResume: React.Dispatch<React.SetStateAction<Resume | null>>
  saveResume: (resume: Resume) => Promise<Resume>
}

/**
 * 提供简历自动保存所需的状态、草稿更新和手动触发保存能力。
 */
// 用于封装简历自动保存相关状态和行为。
export function useResumeAutoSave({ setResume, saveResume }: UseResumeAutoSaveOptions) {
  const t = useTranslations('resume.editor')
  const [autoSaveStatus, setAutoSaveStatus] = useState<AutoSaveStatus>('idle')
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const statusResetTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const resumeRef = useRef<Resume | null>(null)
  const hasUnsavedChangesRef = useRef(false)
  const savePromiseRef = useRef<Promise<void> | null>(null)

  /**
   * 在组件卸载时清理自动保存相关定时器，避免状态泄漏。
   */
  useEffect(() => {
    return () => {
      if (autoSaveTimeoutRef.current) clearTimeout(autoSaveTimeoutRef.current)
      if (statusResetTimeoutRef.current) clearTimeout(statusResetTimeoutRef.current)
    }
  }, [])

  /**
   * 同步服务端或外部更新后的简历快照，避免误触发自动保存。
   */
  const syncResumeSnapshot = useCallback((resume: Resume | null, options: { saved?: boolean } = {}) => {
    resumeRef.current = resume
    if (options.saved) {
      hasUnsavedChangesRef.current = false
      setAutoSaveStatus('idle')
    }
  }, [])

  /**
   * 在保存成功后短暂显示成功状态，再自动回到 idle。
   */
  const scheduleStatusReset = useCallback(() => {
    if (statusResetTimeoutRef.current) {
      clearTimeout(statusResetTimeoutRef.current)
    }
    statusResetTimeoutRef.current = setTimeout(() => {
      setAutoSaveStatus((status) => (status === 'success' ? 'idle' : status))
    }, 2000)
  }, [])

  /**
   * 执行一次真实保存，并把服务端返回的新快照同步回页面状态。
   */
  const performAutoSave = useCallback(async ({ showSuccessToast = false }: { showSuccessToast?: boolean } = {}) => {
    if (!resumeRef.current || !hasUnsavedChangesRef.current) return
    if (savePromiseRef.current) return savePromiseRef.current

    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
      autoSaveTimeoutRef.current = null
    }

    const snapshot = resumeRef.current
    const saveTask = (async () => {
      setAutoSaveStatus('saving')
      try {
        const savedResume = await saveResume(snapshot)
        if (resumeRef.current?.id === savedResume.id && resumeRef.current === snapshot) {
          resumeRef.current = savedResume
          setResume(savedResume)
          hasUnsavedChangesRef.current = false
          setAutoSaveStatus('success')
          scheduleStatusReset()
        } else {
          setAutoSaveStatus('pending')
        }
        if (showSuccessToast) {
          toast.success(t('saveSuccess'))
        }
      } catch (error) {
        setAutoSaveStatus('error')
        toast.error(t('autoSaveError'))
        throw error
      } finally {
        savePromiseRef.current = null
      }
    })()

    savePromiseRef.current = saveTask
    return saveTask
  }, [saveResume, scheduleStatusReset, setResume, t])

  /**
   * 标记当前简历已有未保存修改，并启动防抖保存。
   */
  const scheduleAutoSave = useCallback(() => {
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }
    setAutoSaveStatus('pending')
    autoSaveTimeoutRef.current = setTimeout(() => {
      void performAutoSave().catch(() => {
        // 自动保存失败已在 performAutoSave 内更新状态和 toast；这里消费 Promise，
        // 避免浏览器控制台出现 unhandledRejection。
      })
    }, AUTO_SAVE_DELAY)
  }, [performAutoSave])

  /**
   * 用统一入口更新本地草稿，避免页面手动维护多个 ref。
   */
  const updateDraft = useCallback((updater: (resume: Resume) => Resume) => {
    setResume((previousResume) => {
      if (!previousResume) return previousResume
      const updatedResume = updater(previousResume)
      resumeRef.current = updatedResume
      hasUnsavedChangesRef.current = true
      return updatedResume
    })
    scheduleAutoSave()
  }, [scheduleAutoSave, setResume])

  return {
    autoSaveStatus,
    resumeRef,
    syncResumeSnapshot,
    updateDraft,
    performAutoSave,
    scheduleAutoSave,
    setAutoSaveStatus,
  }
}
