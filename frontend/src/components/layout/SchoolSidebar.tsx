'use client'

import { Link } from '@/i18n/navigation'
import { usePathname } from '@/i18n/navigation'
import {
  AcademicCapIcon,
  ChartPieIcon,
  PlusCircleIcon,
  BookOpenIcon,
} from '@heroicons/react/24/solid'

export default function SchoolSidebar() {
  const pathname = usePathname()

  const isActive = (path: string) => {
    if (path === '/school/dashboard' && pathname === '/school/dashboard') return true
    if (path !== '/school/dashboard' && pathname.startsWith(path)) return true
    return false
  }

  const linkClass = (path: string) => `flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] font-medium transition-colors ${
    isActive(path) 
      ? 'bg-primary-50 text-primary-700 dark:bg-primary-900/20 dark:text-primary-400' 
      : 'text-gray-500 hover:bg-gray-50 dark:text-gray-400 dark:hover:bg-gray-800'
  }`

  const iconClass = (path: string) => `h-4 w-4 ${
    isActive(path) ? 'text-primary-600 dark:text-primary-400' : 'text-gray-400'
  }`

  return (
    <div className="flex h-full flex-col">
      <div className="flex-1 overflow-y-auto p-3">
        <div className="space-y-6">
          <div>
            <h3 className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              数据中心
            </h3>
            <div className="space-y-0.5">
              <Link href="/school/dashboard" className={linkClass('/school/dashboard')}>
                <ChartPieIcon className={iconClass('/school/dashboard')} />
                人才供需看板
              </Link>
            </div>
          </div>

          <div>
            <h3 className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-wider text-gray-400 dark:text-gray-500">
              AI 教研
            </h3>
            <div className="space-y-0.5">
              <Link href="/school/curriculum/new" className={linkClass('/school/curriculum/new')}>
                <PlusCircleIcon className={iconClass('/school/curriculum/new')} />
                智能生成大纲
              </Link>
              <Link href="/school/courses" className={linkClass('/school/courses')}>
                <BookOpenIcon className={iconClass('/school/courses')} />
                课程管理
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
