'use client'

import { Link } from '@/i18n/navigation'
import { motion } from 'framer-motion'
import { useTranslations } from 'next-intl'
import Logo from '@/components/ui/Logo'
import {
  SparklesIcon,
  MicrophoneIcon,
  ChartBarSquareIcon,
  AcademicCapIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline'

export default function LandingPage() {
  const t = useTranslations('common')

  const bentoFeatures = [
    {
      id: 'agent',
      icon: <SparklesIcon className="w-8 h-8 text-violet-600" />,
      title: t('landing.features.agent.title'),
      desc: t('landing.features.agent.desc'),
      colSpan: 'md:col-span-2',
      bgClass: 'bg-white',
    },
    {
      id: 'radar',
      icon: <ChartBarSquareIcon className="w-8 h-8 text-blue-600" />,
      title: t('landing.features.radar.title'),
      desc: t('landing.features.radar.desc'),
      colSpan: 'md:col-span-1',
      bgClass: 'bg-white',
    },
    {
      id: 'interview',
      icon: <MicrophoneIcon className="w-8 h-8 text-rose-600" />,
      title: t('landing.features.interview.title'),
      desc: t('landing.features.interview.desc'),
      colSpan: 'md:col-span-1',
      bgClass: 'bg-white',
    },
    {
      id: 'learning',
      icon: <AcademicCapIcon className="w-8 h-8 text-emerald-600" />,
      title: t('landing.features.learning.title'),
      desc: t('landing.features.learning.desc'),
      colSpan: 'md:col-span-2',
      bgClass: 'bg-white',
    },
  ]

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-gray-900 font-sans relative selection:bg-violet-200">
      {/* Navbar */}
      <header className="fixed top-0 inset-x-0 z-50 border-b border-gray-200 bg-white/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-16">
          <Logo size="sm" />
          <div className="flex items-center gap-6">
            <Link
              href="/login"
              className="text-sm font-medium text-gray-600 hover:text-gray-900 transition-colors"
            >
              {t('nav.login')}
            </Link>
            <Link
              href="/register"
              className="px-5 py-2 text-sm font-medium text-white bg-gray-900 hover:bg-gray-800 transition-colors rounded-full shadow-sm"
            >
              {t('nav.register')}
            </Link>
          </div>
        </div>
      </header>

      {/* Asymmetrical Hero Section */}
      <section className="relative z-10 pt-40 pb-24 overflow-hidden">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-2 gap-12 items-center">
            {/* Left Content */}
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, ease: 'easeOut' }}
              className="max-w-2xl"
            >
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-violet-100 border border-violet-200 mb-8">
                <span className="flex h-2 w-2 rounded-full bg-violet-600 animate-pulse"></span>
                <span className="text-xs font-semibold text-violet-800">OfferMaster AI</span>
              </div>
              
              <h1 className="mb-6 text-6xl md:text-7xl font-extrabold tracking-tight text-gray-900 leading-[1.1]">
                {t('landing.heroPrefix')}
                <br />
                <span className="text-violet-600">
                  {t('landing.heroHighlight')}
                </span>
                {t('landing.heroSuffix')}
              </h1>
              
              <p className="text-lg md:text-xl text-gray-600 mb-10 leading-relaxed max-w-lg">
                {t('landing.subtitle')}
              </p>
              
              <div className="flex flex-col sm:flex-row items-start gap-4">
                <Link
                  href="/register"
                  className="group flex items-center gap-2 px-8 py-4 text-base font-semibold text-white bg-violet-600 hover:bg-violet-700 transition-all rounded-full shadow-lg hover:shadow-xl hover:-translate-y-0.5"
                >
                  {t('landing.primaryCta')}
                  <ArrowRightIcon className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </Link>
              </div>
            </motion.div>

            {/* Right Abstract Visuals */}
            <motion.div
              initial={{ opacity: 0, x: 30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.8, delay: 0.2, ease: 'easeOut' }}
              className="relative hidden md:block h-[500px]"
            >
              {/* Decorative overlapping cards */}
              <div className="absolute right-0 top-10 w-[400px] h-[300px] bg-white rounded-2xl shadow-2xl border border-gray-100 p-6 transform rotate-3 hover:rotate-0 transition-transform duration-500 z-20">
                <div className="flex items-center gap-3 border-b border-gray-100 pb-4 mb-4">
                  <div className="w-10 h-10 rounded-full bg-violet-100 flex items-center justify-center">
                    <SparklesIcon className="w-5 h-5 text-violet-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">Resume Agent</h3>
                    <p className="text-xs text-gray-500">Injecting keywords...</p>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="h-3 bg-gray-100 rounded w-full"></div>
                  <div className="h-3 bg-gray-100 rounded w-5/6"></div>
                  <div className="h-3 bg-violet-100 rounded w-4/6"></div>
                </div>
              </div>

              <div className="absolute right-20 top-40 w-[350px] h-[250px] bg-white rounded-2xl shadow-xl border border-gray-100 p-6 transform -rotate-6 hover:-rotate-0 transition-transform duration-500 z-10">
                 <div className="flex items-center gap-3 border-b border-gray-100 pb-4 mb-4">
                  <div className="w-10 h-10 rounded-full bg-blue-100 flex items-center justify-center">
                    <ChartBarSquareIcon className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900">Job Radar</h3>
                    <p className="text-xs text-gray-500">Match Score: 94%</p>
                  </div>
                </div>
                <div className="flex gap-2 mb-2">
                  <span className="px-2 py-1 bg-gray-100 text-xs rounded text-gray-600">React</span>
                  <span className="px-2 py-1 bg-green-100 text-xs rounded text-green-700">Go</span>
                  <span className="px-2 py-1 bg-gray-100 text-xs rounded text-gray-600">Docker</span>
                </div>
              </div>
              
              {/* Background gradient blob */}
              <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-violet-400/20 rounded-full blur-3xl -z-10"></div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Bento Box Features Section */}
      <section className="relative z-10 py-24 bg-white border-y border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-16 max-w-2xl">
            <h2 className="text-4xl font-bold text-gray-900 mb-4">
              不仅是工具，更是求职大脑
            </h2>
            <p className="text-gray-600 text-lg">
              围绕“拿 Offer”为核心重构的所有功能，助你在各个环节建立绝对优势。
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {bentoFeatures.map((feature, idx) => (
              <motion.div 
                key={feature.id}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                className={`${feature.colSpan} ${feature.bgClass} p-8 rounded-3xl border border-gray-200 hover:shadow-xl transition-shadow duration-300 relative overflow-hidden group`}
              >
                <div className="mb-6 relative z-10">
                  {feature.icon}
                </div>
                <h3 className="text-2xl font-bold text-gray-900 mb-3 relative z-10">{feature.title}</h3>
                <p className="text-gray-600 leading-relaxed relative z-10 max-w-sm">{feature.desc}</p>
                
                {/* Subtle hover gradient background */}
                <div className="absolute inset-0 bg-gradient-to-br from-transparent to-gray-50 opacity-0 group-hover:opacity-100 transition-opacity"></div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Modern Minimal CTA */}
      <section className="relative z-10 py-32 bg-[#F9FAFB]">
        <div className="max-w-3xl mx-auto px-6 text-center">
          <h2 className="text-4xl md:text-5xl font-extrabold text-gray-900 mb-8 tracking-tight">
            准备好迎接你的下一个 Offer 了吗？
          </h2>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 px-10 py-4 text-lg font-semibold text-white bg-gray-900 hover:bg-violet-600 transition-colors rounded-full shadow-lg hover:shadow-xl hover:-translate-y-1 transform duration-300"
          >
            免费体验 OfferMaster
            <ArrowRightIcon className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Minimal Footer */}
      <footer className="border-t border-gray-200 py-12 bg-white">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm">
            <Logo size="sm" />
            <span>&copy; {new Date().getFullYear()} OfferMaster. All rights reserved.</span>
          </div>
          <div className="flex gap-8 text-sm font-medium text-gray-500">
            <a href="#" className="hover:text-gray-900 transition-colors">隐私政策</a>
            <a href="#" className="hover:text-gray-900 transition-colors">服务条款</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
