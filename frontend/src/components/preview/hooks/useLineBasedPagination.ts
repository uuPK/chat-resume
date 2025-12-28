import { useState, useEffect, useCallback, useRef } from 'react'

// A4纸张尺寸常量
export const A4_WIDTH = 816
export const A4_HEIGHT = Math.round(A4_WIDTH * 297 / 210) // 1154px，按210:297比例
export const PAGE_MARGIN = 0
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

interface LineBasedPaginationOptions {
  containerRef: React.RefObject<HTMLElement>
  contentRef: React.RefObject<HTMLElement>
  pageHeight?: number
}

export function useLineBasedPagination({
  containerRef,
  contentRef,
  pageHeight = A4_HEIGHT - PAGE_MARGIN * 2 - PAGE_PADDING * 2 - SAFETY_MARGIN
}: LineBasedPaginationOptions) {
  const [pages, setPages] = useState<PageContent[]>([])
  const [totalPages, setTotalPages] = useState(1)
  const [isCalculating, setIsCalculating] = useState(false)
  const calculationTimeoutRef = useRef<NodeJS.Timeout>()

  // 测量所有可分页的行元素
  const measureLines = useCallback((): RenderableLine[] => {
    if (!contentRef.current) return []

    const lines: RenderableLine[] = []
    const sections = contentRef.current.children

    for (let i = 0; i < sections.length; i++) {
      const section = sections[i] as HTMLElement
      const sectionId = section.getAttribute('data-section-id') || `section-${i}`

      // 获取section下的所有可分页行元素
      const lineElements = section.querySelectorAll('[data-line-index]')
      
      for (let j = 0; j < lineElements.length; j++) {
        const lineElement = lineElements[j] as HTMLElement
        const lineIndex = parseInt(lineElement.getAttribute('data-line-index') || '0')
        
        if (lineElement.offsetHeight > 0) {
          lines.push({
            id: `${sectionId}-line-${lineIndex}`,
            sectionType: sectionId,
            lineIndex,
            height: lineElement.offsetHeight,
            element: lineElement
          })
        }
      }
    }

    return lines
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
      if (currentPage.lines.length === 0 || projectedHeight <= pageHeight) {
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
  }, [pageHeight])

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
      
      setPages(calculatedPages)
      setTotalPages(calculatedPages.length)
    } catch (error) {
      console.error('分页计算错误:', error)
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
  }, [recalculatePagination])

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
    isCalculating,
    recalculatePagination,
    pageHeight,
    A4_WIDTH,
    PAGE_MARGIN,
    PAGE_PADDING
  }
}

