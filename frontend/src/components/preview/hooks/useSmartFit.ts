'use client'

import { useCallback, useRef, useState } from 'react'
import { A4_HEIGHT, PAGE_PADDING, SAFETY_MARGIN, RenderableLine } from './useLineBasedPagination'

export type SmartFitResult =
  | { status: 'already_fits' }
  | { status: 'too_much_content'; pages: number }
  | { status: 'success'; oldScale: number; newScale: number }
  | { status: 'failed' }

interface UseSmartFitOptions {
  currentScale: number
  onComplete: (newScale: number) => void
  // 通过 React state 驱动测量容器 scale，避免直接操控 DOM 与 React 冲突
  setMeasureScale: (scale: number) => void
  // 等待 React 将测量容器渲染到指定 scale 后 resolve
  waitForMeasureScale: (targetScale: number) => Promise<void>
  // 与分页算法完全相同的测量逻辑
  measureLines: () => RenderableLine[]
}

// 对于给定的 scale，计算有效页高（可填充内容高度）
function effectivePageHeight(scale: number) {
  return A4_HEIGHT - PAGE_PADDING * 2 * scale - SAFETY_MARGIN
}

export function useSmartFit({
  currentScale,
  onComplete,
  setMeasureScale,
  waitForMeasureScale,
  measureLines,
}: UseSmartFitOptions) {
  const [isRunning, setIsRunning] = useState(false)
  const abortRef = useRef(false)

  const runSmartFit = useCallback(async (): Promise<SmartFitResult> => {
    if (isRunning) return { status: 'failed' }

    setIsRunning(true)
    abortRef.current = false

    // 通过 React state 切换测量容器到指定 scale，等待渲染完成后测量
    const measureTotalHeight = async (scale: number): Promise<number> => {
      setMeasureScale(scale)
      await waitForMeasureScale(scale)
      const lines = measureLines()
      return lines.reduce((sum, l) => sum + l.height, 0)
    }

    try {
      // 当前 scale 下的内容总高度
      const currentContentHeight = await measureTotalHeight(currentScale)
      const currentPageHeight = effectivePageHeight(currentScale)

      if (abortRef.current) return { status: 'failed' }

      if (currentContentHeight <= currentPageHeight) {
        return { status: 'already_fits' }
      }

      // 检查最小 scale（0.5）能否放下
      const minContentHeight = await measureTotalHeight(0.5)
      const minPageHeight = effectivePageHeight(0.5)

      if (abortRef.current) return { status: 'failed' }

      if (minContentHeight > minPageHeight) {
        const approxPages = Math.ceil(minContentHeight / minPageHeight)
        return { status: 'too_much_content', pages: approxPages }
      }

      // 二分搜索：找最大的能放入一页的 spacingScale
      let lo = 0.5
      let hi = currentScale
      let bestScale = 0.5

      for (let i = 0; i < 8; i++) {
        if (abortRef.current) return { status: 'failed' }
        const mid = (lo + hi) / 2
        const h = await measureTotalHeight(mid)
        if (h <= effectivePageHeight(mid)) {
          bestScale = mid
          lo = mid
        } else {
          hi = mid
        }
      }

      // 取整到 0.05 步长
      bestScale = Math.round(bestScale / 0.05) * 0.05
      bestScale = Math.max(0.5, Math.min(1.5, bestScale))

      // 验证取整后仍能放下
      const verifyH = await measureTotalHeight(bestScale)
      if (verifyH > effectivePageHeight(bestScale) && bestScale > 0.5) {
        bestScale = Math.max(0.5, bestScale - 0.05)
      }

      onComplete(bestScale)
      return { status: 'success', oldScale: currentScale, newScale: bestScale }
    } finally {
      // 恢复测量容器到当前实际 scale（会在 onComplete 触发 prop 变化后自动同步）
      setMeasureScale(currentScale)
      setIsRunning(false)
    }
  }, [currentScale, isRunning, onComplete, setMeasureScale, waitForMeasureScale, measureLines])

  const abort = useCallback(() => {
    abortRef.current = true
  }, [])

  return { isRunning, runSmartFit, abort }
}
