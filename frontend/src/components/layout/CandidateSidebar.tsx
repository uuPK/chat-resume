'use client'

import { Link } from '@/i18n/navigation'
import { usePathname } from '@/i18n/navigation'
import { useTranslations } from 'next-intl'
import {
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  BriefcaseIcon,
  AcademicCapIcon,
  HomeIcon,
} from '@heroicons/react/24/solid'
import toast from 'react-hot-toast'

interface CandidateSidebarProps {
  hasResumes?: boolean;
  firstResumeId?: number;
}

export default function CandidateSidebar({ hasResumes = false, firstResumeId }: CandidateSidebarProps) {
  const t = useTranslations('resume.center')
  const pathname = usePathname()

  const getSidebarUrl = (type: 'edit' | 'jobs' | 'learning-path') => {
    if (!hasResumes || !firstResumeId) return '/resumes'
    return `/resume/${firstResumeId}/${type}`
  }

  const handleSidebarClick = (e: React.MouseEvent, type: 'edit' | 'jobs' | 'learning-path') => {
    if (!hasResumes || !firstResumeId) {
      e.preventDefault()
      toast('请先新建或上传一份简历！', { icon: '📝' })
    }
  }

  const isActive = (path: string) => {
    if (path === '/dashboard' && pathname === '/dashboard') return true
    if (path !== '/dashboard' && pathname.startsWith(path)) return true
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
    <aside
      className="hidden w-[220px] shrink-0 border-r border-gray-100 dark:border-gray-800 bg-white dark:bg-[#0a0a0a] px-3 py-5 md:flex md:flex-col"
    >
      <div className="space-y-5">
        <div>
          <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
            总览
          </p>
          <div className="space-y-1">
            <Link href="/dashboard" className={linkClass('/dashboard')}>
              <HomeIcon className={iconClass('/dashboard')} />
              <span>工作台 (Dashboard)</span>
            </Link>
            <Link href="/jobs" className={linkClass('/jobs')}>
              <BriefcaseIcon className={iconClass('/jobs')} />
              <span>发现机会 (Jobs)</span>
            </Link>
          </div>
        </div>

        <div>
          <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
            {t('sidebarResume')}
          </p>
          <div className="space-y-1">
            <Link href="/resumes" className={linkClass('/resumes')}>
              <DocumentTextIcon className={iconClass('/resumes')} />
              <span>{t('sidebarMyResumes')}</span>
            </Link>

            <Link
              href={getSidebarUrl('edit')}
              onClick={(e) => handleSidebarClick(e, 'edit')}
              className={linkClass('/resume')}
            >
              <SparklesIcon className={iconClass('/resume')} />
              <span>{t('sidebarResumeOptimize')}</span>
            </Link>
          </div>
        </div>

        <div>
          <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider text-gray-400 dark:text-gray-500">
            {t('sidebarInterview')}
          </p>
          <div className="space-y-1">
            <Link
              href={getSidebarUrl('jobs')}
              onClick={(e) => handleSidebarClick(e, 'jobs')}
              className={linkClass('/resume/jobs')}
            >
              <BriefcaseIcon className={iconClass('/resume/jobs')} />
              <span>{t('sidebarJobRadar')}</span>
            </Link>

            <Link
              href="/interviews"
              className={linkClass('/interviews')}
            >
              <ChatBubbleLeftRightIcon className={iconClass('/interviews')} />
              <span>{t('sidebarMockInterview')}</span>
            </Link>

            <Link
              href={getSidebarUrl('learning-path')}
              onClick={(e) => handleSidebarClick(e, 'learning-path')}
              className={linkClass('/resume/learning-path')}
            >
              <AcademicCapIcon className={iconClass('/resume/learning-path')} />
              <span>{t('sidebarLearningPath')}</span>
            </Link>
          </div>
        </div>
      </div>
    </aside>
  )
}
