'use client'

import { Link } from '@/i18n/navigation'
import { motion } from 'framer-motion'
import { useTranslations } from 'next-intl'
import Logo from '@/components/ui/Logo'
import {
  SparklesIcon,
  BriefcaseIcon,
  AcademicCapIcon,
  ArrowRightIcon,
  UserGroupIcon
} from '@heroicons/react/24/outline'

export default function LandingPage() {
  const t = useTranslations('common')

  const pillars = [
    {
      id: 'candidate',
      icon: <SparklesIcon className="w-8 h-8 text-primary-600" />,
      role: '求职者 (Candidate)',
      title: 'AI 驱动的职业起飞引擎',
      desc: '借助大模型重构简历，生成高通过率版本。进行逼真的 AI 语音模拟面试，获得深度复盘，让你在每次真实面试中都游刃有余。',
      bgClass: 'bg-primary-50',
      borderClass: 'border-primary-100',
    },
    {
      id: 'enterprise',
      icon: <BriefcaseIcon className="w-8 h-8 text-slate-600" />,
      role: '企业端 (Enterprise)',
      title: '精准触达，告别海选',
      desc: '大模型自动比对 JD 与收到简历的契合度，生成深度匹配热力图。自动生成针对该候选人的“必问探底问题”，让非技术 HR 也能精准识人。',
      bgClass: 'bg-slate-50',
      borderClass: 'border-slate-200',
    },
    {
      id: 'school',
      icon: <AcademicCapIcon className="w-8 h-8 text-emerald-600" />,
      role: '教研端 (School)',
      title: '消除市场技能断层',
      desc: '实时抓取企业真实 JD 与求职者能力的差异，发现“最缺技能”。只需一键，AI 即可自动生成针对性的速成教研大纲，完美填补市场空白。',
      bgClass: 'bg-emerald-50',
      borderClass: 'border-emerald-100',
    },
  ]

  return (
    <div className="min-h-screen bg-[#F9FAFB] text-gray-900 font-sans relative selection:bg-primary-200">
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

      {/* Hero Section */}
      <section className="relative z-10 pt-40 pb-32 overflow-hidden text-center px-6">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] bg-primary-400/20 rounded-full blur-[100px] -z-10"></div>
        
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
          className="max-w-4xl mx-auto"
        >
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary-100 border border-primary-200 mb-8">
            <span className="flex h-2 w-2 rounded-full bg-primary-600 animate-pulse"></span>
            <span className="text-xs font-semibold text-primary-800">OfferMaster 生态网络</span>
          </div>
          
          <h1 className="mb-6 text-5xl md:text-7xl font-extrabold tracking-tight text-gray-900 leading-[1.15]">
            重塑 <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary-600 to-violet-500">人才与机会</span><br />
            的连接方式
          </h1>
          
          <p className="text-lg md:text-xl text-gray-600 mb-10 leading-relaxed max-w-2xl mx-auto">
            不止是一个简历工具。我们通过底层的大模型技术，将求职者、招聘企业与高校教研紧密连接，打造三端联动的下一代职业发展与招聘平台。
          </p>
          
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              href="/register"
              className="group flex items-center justify-center gap-2 px-8 py-4 w-full sm:w-auto text-base font-semibold text-white bg-primary-600 hover:bg-primary-700 transition-all rounded-full shadow-lg hover:shadow-xl hover:-translate-y-0.5"
            >
              免费加入生态网络
              <ArrowRightIcon className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
            </Link>
            <Link
              href="/login"
              className="group flex items-center justify-center gap-2 px-8 py-4 w-full sm:w-auto text-base font-semibold text-gray-700 bg-white border border-gray-200 hover:border-gray-300 hover:bg-gray-50 transition-all rounded-full shadow-sm"
            >
              登入已有账户
            </Link>
          </div>
        </motion.div>
      </section>

      {/* Three Pillars Section */}
      <section className="relative z-10 py-24 bg-white border-y border-gray-200">
        <div className="max-w-7xl mx-auto px-6">
          <div className="mb-20 text-center max-w-3xl mx-auto">
            <UserGroupIcon className="w-12 h-12 text-gray-400 mx-auto mb-6" />
            <h2 className="text-4xl font-bold text-gray-900 mb-6">
              为生态中的每一个角色赋能
            </h2>
            <p className="text-gray-600 text-lg">
              市场缺什么，高校就教什么，人才就学什么。OfferMaster 利用 AI 消除信息差，让求职和招聘变得前所未有的高效。
            </p>
          </div>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {pillars.map((pillar, idx) => (
              <motion.div 
                key={pillar.id}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: "-100px" }}
                transition={{ duration: 0.6, delay: idx * 0.15 }}
                className={`${pillar.bgClass} border ${pillar.borderClass} p-10 rounded-3xl hover:shadow-xl transition-all duration-300 relative overflow-hidden group hover:-translate-y-1`}
              >
                <div className="mb-6 relative z-10 bg-white w-16 h-16 rounded-2xl flex items-center justify-center shadow-sm">
                  {pillar.icon}
                </div>
                <div className="text-sm font-bold text-gray-500 mb-2 uppercase tracking-wider">{pillar.role}</div>
                <h3 className="text-2xl font-bold text-gray-900 mb-4 relative z-10">{pillar.title}</h3>
                <p className="text-gray-600 leading-relaxed relative z-10 text-base">{pillar.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works Connection Diagram */}
      <section className="relative z-10 py-24 bg-gray-900 text-white overflow-hidden">
        <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-gray-700 to-transparent"></div>
        <div className="max-w-7xl mx-auto px-6 text-center">
          <h2 className="text-3xl md:text-4xl font-bold mb-16">
            数据流转与闭环
          </h2>
          <div className="flex flex-col md:flex-row items-center justify-center gap-4 md:gap-8">
            <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 w-64">
              <div className="text-primary-400 font-bold mb-2">1. 企业 (Enterprise)</div>
              <div className="text-sm text-gray-400">发布岗位需求，LLM 提炼市场高频缺失技能</div>
            </div>
            <ArrowRightIcon className="w-6 h-6 text-gray-600 hidden md:block" />
            <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 w-64">
              <div className="text-emerald-400 font-bold mb-2">2. 高校 (School)</div>
              <div className="text-sm text-gray-400">捕获缺口，AI 一键生成教研大纲并发布到平台</div>
            </div>
            <ArrowRightIcon className="w-6 h-6 text-gray-600 hidden md:block" />
            <div className="bg-gray-800 p-6 rounded-2xl border border-gray-700 w-64">
              <div className="text-blue-400 font-bold mb-2">3. 求职者 (Candidate)</div>
              <div className="text-sm text-gray-400">精准补齐短板，更新简历，获得该企业面试邀请</div>
            </div>
          </div>
        </div>
      </section>

      {/* Minimal Footer */}
      <footer className="py-12 bg-[#F9FAFB]">
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
