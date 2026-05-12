import { useState, useEffect, useCallback, useRef } from 'react'

// A4纸张尺寸常量
export const A4_WIDTH = 816
export const A4_HEIGHT = Math.round(A4_WIDTH * 297 / 210) // 1154px，按210:297比例
export const PAGE_PADDING = 40
export const SAFETY_MARGIN = 20 // 容错余量，防止累计误差导致内容被切

// 可渲染的行元素类型
export interface RenderableLine {
  id: string
  sectionType: string
  lineIndex: number
  height: number
  element: HTMLElement
}

// 页面内容结构
export interface PageContent {
  lines: RenderableLine[]
  height: number
}

export function measureRenderableLines(contentElement: HTMLElement | null): RenderableLine[] {
  if (!contentElement) return []

  const lines: RenderableLine[] = []
  const sections = contentElement.children

  for (let i = 0; i < sections.length; i++) {
    const section = sections[i] as HTMLElement
    const sectionId = section.getAttribute('data-section-id') || `section-${i}`

    // 计算 section 级别的额外间距（section wrapper + inner div 的 margin-bottom）
    // 这部分加在该 section 最后一行上，让分页器感知到 section 之间的真实间隔
    const sectionStyle = window.getComputedStyle(section)
    const sectionMarginBottom = parseFloat(sectionStyle.marginBottom) || 0

    // inner div 的 marginBottom（section 组件自身的外层 div）
    const firstChild = section.firstElementChild as HTMLElement | null
    const innerDivMarginBottom = firstChild
      ? (parseFloat(window.getComputedStyle(firstChild).marginBottom) || 0)
      : 0

    // 获取 section 下的所有可分页行元素
    const lineElements = section.querySelectorAll('[data-line-index]')
    const sectionLines: RenderableLine[] = []

    for (let j = 0; j < lineElements.length; j++) {
      const lineElement = lineElements[j] as HTMLElement
      const lineIndex = parseInt(lineElement.getAttribute('data-line-index') || '0')

      if (lineElement.offsetHeight > 0) {
        // 将该行自身的 marginBottom 纳入高度，避免低估行间距
        const elMarginBottom = parseFloat(window.getComputedStyle(lineElement).marginBottom) || 0
        sectionLines.push({
          id: `${sectionId}-line-${lineIndex}`,
          sectionType: sectionId,
          lineIndex,
          height: lineElement.offsetHeight + elMarginBottom,
          element: lineElement
        })
      }
    }

    // 将 section 级别的额外间距加到该 section 最后一行上
    // CSS margin collapse: 最后一行的 marginBottom、innerDiv 的 marginBottom、section 的 marginBottom
    // 三者之间发生折叠，实际间距为三者的最大值，而非相加
    if (sectionLines.length > 0) {
      const lastLine = sectionLines[sectionLines.length - 1]
      const lastLineEl = lastLine.element
      const lastLineElMarginBottom = parseFloat(window.getComputedStyle(lastLineEl).marginBottom) || 0
      // 折叠后的实际间距
      const collapsedGap = Math.max(lastLineElMarginBottom, innerDivMarginBottom, sectionMarginBottom)
      // 已在循环中计入了 lastLineElMarginBottom，这里只补充差额
      const additionalOverhead = collapsedGap - lastLineElMarginBottom
      lastLine.height += additionalOverhead
    }

    lines.push(...sectionLines)
  }

  return lines
}

interface LineBasedPaginationOptions {
  containerRef: React.RefObject<HTMLElement>
  contentRef: React.RefObject<HTMLElement>
  pageHeight?: number
  spacingScale?: number
}

export function useLineBasedPagination({
  containerRef,
  contentRef,
  spacingScale = 1,
  pageHeight
}: LineBasedPaginationOptions) {
  const effectivePageHeight = pageHeight ?? (A4_HEIGHT - PAGE_PADDING * 2 * spacingScale - SAFETY_MARGIN)
  const [pages, setPages] = useState<PageContent[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [contentHeight, setContentHeight] = useState(0)
  const [isCalculating, setIsCalculating] = useState(false)
  const calculationTimeoutRef = useRef<NodeJS.Timeout>()

  // 测量所有可分页的行元素
  // 注意：offsetHeight 不含 margin，需手动加上 marginBottom 避免分页高度低估导致内容被 overflow-hidden 裁掉
  const measureLines = useCallback((): RenderableLine[] => {
    return measureRenderableLines(contentRef.current)
  }, [contentRef])

  // 贪心分页算法：按行填充页面
  const calculatePages = useCallback((lines: RenderableLine[]): PageContent[] => {
    if (lines.length === 0) {
      return [{ lines: [], height: 0 }]
    }

    const pages: PageContent[] = []
    let currentPage: PageContent = { lines: [], height: 0 }

    for (const line of lines) {
      const projectedHeight = currentPage.height + line.height

      // 如果当前页为空，必须放入（避免空页）
      // 如果可以容纳，则加入当前页
      if (currentPage.lines.length === 0 || projectedHeight <= effectivePageHeight) {
        currentPage.lines.push(line)
        currentPage.height = projectedHeight
      } else {
        // 当前页已满，创建新页
        pages.push(currentPage)
        currentPage = {
          lines: [line],
          height: line.height
        }
      }
    }

    // 添加最后一页
    if (currentPage.lines.length > 0) {
      pages.push(currentPage)
    }

    return pages.length > 0 ? pages : [{ lines: [], height: 0 }]
  }, [effectivePageHeight])

  // 重新计算分页
  const recalculatePagination = useCallback(async () => {
    if (!containerRef.current || !contentRef.current) return

    // 清除之前的计算定时器
    if (calculationTimeoutRef.current) {
      clearTimeout(calculationTimeoutRef.current)
    }

    setIsCalculating(true)

    try {
      // 等待DOM更新完成
      await new Promise(resolve => {
        calculationTimeoutRef.current = setTimeout(resolve, 100)
      })

      const lines = measureLines()
      const calculatedPages = calculatePages(lines)
      const totalHeight = lines.reduce((sum: number, l: RenderableLine) => sum + l.height, 0)

      setPages(calculatedPages)
      setTotalPages(calculatedPages.length)
      setContentHeight(totalHeight)
    } catch (error) {
      console.error('Pagination calculation error:', error)
      setPages([{ lines: [], height: 0 }])
      setTotalPages(1)
    } finally {
      setIsCalculating(false)
    }
  }, [containerRef, contentRef, measureLines, calculatePages])

  // 监听内容变化
  useEffect(() => {
    if (!contentRef.current) return

    const resizeObserver = new ResizeObserver(() => {
      recalculatePagination()
    })

    // 观察内容容器
    resizeObserver.observe(contentRef.current)

    // 观察所有子元素
    const children = contentRef.current.children
    for (let i = 0; i < children.length; i++) {
      resizeObserver.observe(children[i])
    }

    // 初始计算
    recalculatePagination()

    return () => {
      resizeObserver.disconnect()
      if (calculationTimeoutRef.current) {
        clearTimeout(calculationTimeoutRef.current)
      }
    }
  }, [contentRef, recalculatePagination])

  // 监听窗口大小变化
  useEffect(() => {
    const handleResize = () => {
      recalculatePagination()
    }

    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [recalculatePagination])

  return {
    pages,
    totalPages,
    contentHeight,
    isCalculating,
    recalculatePagination,
    measureLines,
    pageHeight: effectivePageHeight,
    A4_WIDTH,
    PAGE_PADDING
  }
}
