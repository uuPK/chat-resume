/**
 * 编辑页三栏布局 Hook
 *
 * 用于集中管理左中右面板的宽度、折叠状态和拖拽逻辑。
 */

'use client'

import { useCallback, useMemo, useRef, useState } from 'react'

/**
 * 提供编辑页三栏布局状态和拖拽处理函数。
 */
// 用于封装面板布局相关状态和行为。
export function usePanelLayout() {
  const [editorOpen, setEditorOpen] = useState(true)
  const [editorFlex, setEditorFlex] = useState(30)
  const [agentFlex, setAgentFlex] = useState(30)
  const mainPanelsRef = useRef<HTMLDivElement>(null)

  /**
   * 处理左侧编辑栏拖拽，保证中间预览区域保留最小宽度。
   */
  const handleEditorDividerPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startFlex = editorFlex
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    // 用于处理onpointermove。
    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!mainPanelsRef.current) return
      const containerWidth = mainPanelsRef.current.offsetWidth
      const delta = moveEvent.clientX - startX
      const deltaFlex = (delta / containerWidth) * 100
      const nextEditorFlex = Math.min(45, Math.max(18, startFlex + deltaFlex))
      const previewFlex = 100 - nextEditorFlex - agentFlex
      if (previewFlex >= 25) {
        setEditorFlex(nextEditorFlex)
      }
    }

    // 用于处理onpointerup。
    const onPointerUp = () => {
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      document.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerup', onPointerUp)
    }

    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
  }, [agentFlex, editorFlex])

  /**
   * 处理右侧 Agent 栏拖拽，保证中间预览区域保留最小宽度。
   */
  const handleAgentDividerPointerDown = useCallback((event: React.PointerEvent) => {
    event.preventDefault()
    const startX = event.clientX
    const startFlex = agentFlex
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'

    // 用于处理onpointermove。
    const onPointerMove = (moveEvent: PointerEvent) => {
      if (!mainPanelsRef.current) return
      const containerWidth = mainPanelsRef.current.offsetWidth
      const delta = startX - moveEvent.clientX
      const deltaFlex = (delta / containerWidth) * 100
      const nextAgentFlex = Math.min(45, Math.max(18, startFlex + deltaFlex))
      const previewFlex = 100 - editorFlex - nextAgentFlex
      if (previewFlex >= 25) {
        setAgentFlex(nextAgentFlex)
      }
    }

    // 用于处理onpointerup。
    const onPointerUp = () => {
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      document.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerup', onPointerUp)
    }

    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
  }, [agentFlex, editorFlex])

  const previewFlex = 100 - editorFlex - agentFlex
  const collapsedAgentFlex = 100 - previewFlex
  const editorAnimateWidth = useMemo(
    () => (editorOpen ? `calc(${editorFlex}% - 8px)` : '48px'),
    [editorFlex, editorOpen],
  )

  return {
    editorOpen,
    setEditorOpen,
    editorFlex,
    agentFlex,
    previewFlex,
    collapsedAgentFlex,
    editorAnimateWidth,
    mainPanelsRef,
    handleEditorDividerPointerDown,
    handleAgentDividerPointerDown,
  }
}
