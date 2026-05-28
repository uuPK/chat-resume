
import sys
content = "'use client'

import { Link } from '@/i18n/navigation'
import { motion } from 'framer-motion'
import { useTranslations } from 'next-intl'
import Logo from '@/components/ui/Logo'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import {
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  MicrophoneIcon,
  ArrowRightIcon,
  CheckIcon,
} from '@heroicons/react/24/solid'

export default function LandingPage() {
  const t = useTranslations('common')
  const featureItems = [
    {
      icon: <DocumentTextIcon className="w-6 h-6 text-violet-400" />,
      title: t('landing.features.resume.title'),
      desc: t('landing.features.resume.desc'),
    },
    {
      icon: <ChatBubbleLeftRightIcon className="w-6 h-6 text-violet-400" />,
      title: t('landing.features.chat.title'),
      desc: t('landing.features.chat.desc'),
    },
    {
      icon: <MicrophoneIcon className="w-6 h-6 text-violet-400" />,
      title: t('landing.features.interview.title'),
      desc: t('landing.features.interview.desc'),
    },
  ]
  const stepItems = [
    { step: '01', title: t('landing.steps.upload.title'), desc: t('landing.steps.upload.desc') },
    { step: '02', title: t('landing.steps.optimize.title'), desc: t('landing.steps.optimize.desc') },
    { step: '03', title: t('landing.steps.export.title'), desc: t('landing.steps.export.desc') },
  ]
  const statItems = [
    { label: t('landing.metrics.parse'), value: '92%' },
    { label: t('landing.metrics.keywords'), value: '+34%' },
    { label: t('landing.metrics.quantified'), value: '8' },
    { label: t('landing.metrics.interview'), value: '2.4¡Á' },
  ]

  return (
    <div className="min-h-screen bg-[#0a0a0a] text-gray-300 font-sans relative overflow-hidden">
      {/* Background Dot Grid Effect */}
      <div className="absolute inset-0 z-0 opacity-20" style={{ backgroundImage: 'radial-gradient(#4b5563 1px, transparent 1px)', backgroundSize: '32px 32px' }}></div>
      <div className="absolute inset-0 z-0 bg-gradient-to-b from-transparent via-[#0a0a0a]/80 to-[#0a0a0a]"></div>

      {/* Navbar */}
      <header className="fixed top-0 inset-x-0 z-50 border-b border-white/5 bg-[#0a0a0a]/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-16">
          <Logo size="sm" />
          <div className="flex items-center gap-4">
            <LocaleSwitcher compact />
            <Link
              href="/login"
              className="text-sm font-medium text-gray-400 hover:text-white transition-colors"
            >
              {t('nav.login')}
            </Link>
            <Link
              href="/register"
              className="px-4 py-1.5 text-sm font-medium text-white bg-violet-600 hover:bg-violet-700 transition-colors rounded-full shadow-[0_0_15px_rgba(124,58,237,0.3)] border border-violet-500/30"
            >
              {t('nav.register')}
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative z-10 pt-32 pb-20">
        <div className="max-w-7xl mx-auto px-6 text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: 'easeOut' }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/5 border border-white/10 mb-8">
              <span className="flex h-2 w-2 rounded-full bg-violet-500 animate-pulse"></span>
              <span className="text-xs font-medium text-violet-300">OfferMaster 2.0 is here</span>
            </div>
            
            <h1 className="mb-6 text-5xl md:text-7xl font-bold tracking-tight text-white leading-tight">
              {t('landing.heroPrefix')}<br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-violet-400 to-fuchsia-500">
                {t('landing.heroHighlight')}
              </span>
              {t('landing.heroSuffix')}
            </h1>
            
            <p className="max-w-2xl mx-auto text-lg md:text-xl text-gray-400 mb-10 leading-relaxed">
              {t('landing.subtitle')}
            </p>
            
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link
                href="/register"
                className="group flex items-center gap-2 px-6 py-3 text-base font-semibold text-white bg-violet-600 hover:bg-violet-500 transition-all rounded-full shadow-[0_0_25px_rgba(124,58,237,0.4)]"
              >
                {t('landing.primaryCta')}
                <ArrowRightIcon className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </Link>
            </div>
          </motion.div>
          
          {/* Stats Preview */}
          <motion.div 
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2, ease: 'easeOut' }}
            className="mt-20 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto"
          >
            {statItems.map((stat, idx) => (
              <div key={idx} className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 backdrop-blur-sm">
                <div className="text-3xl font-bold text-white mb-2">{stat.value}</div>
                <div className="text-sm text-gray-500">{stat.label}</div>
              </div>
            ))}
          </motion.div>
        </div>
      </section>

      {/* Features Section */}
      <section className="relative z-10 py-24 bg-black/40 border-y border-white/5">
        <div className="max-w-7xl mx-auto px-6">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-white mb-4">{t('landing.features.resume.title')}</h2>
            <p className="text-gray-400 max-w-2xl mx-auto">{t('landing.subtitle')}</p>
          </div>
          
          <div className="grid md:grid-cols-3 gap-8">
            {featureItems.map((feature, idx) => (
              <div key={idx} className="group p-8 rounded-3xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-colors relative overflow-hidden">
                <div className="absolute inset-0 bg-gradient-to-b from-violet-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
                <div className="w-12 h-12 rounded-xl bg-violet-500/10 flex items-center justify-center mb-6">
                  {feature.icon}
                </div>
                <h3 className="text-xl font-semibold text-white mb-3">{feature.title}</h3>
                <p className="text-gray-400 leading-relaxed">{feature.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Steps Section */}
      <section className="relative z-10 py-24">
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex flex-col md:flex-row gap-16 items-center">
            <div className="flex-1 space-y-8">
              <h2 className="text-3xl md:text-4xl font-bold text-white leading-tight">
                {t('landing.steps.optimize.title')}
              </h2>
              <p className="text-gray-400 text-lg">
                {t('landing.subtitle')}
              </p>
              <div className="space-y-6">
                {stepItems.map((step, idx) => (
                  <div key={idx} className="flex gap-4">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-violet-500/20 text-violet-400 flex items-center justify-center font-bold text-sm border border-violet-500/30">
                      {step.step}
                    </div>
                    <div>
                      <h4 className="text-white font-medium mb-1">{step.title}</h4>
                      <p className="text-gray-500 text-sm leading-relaxed">{step.desc}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Visual placeholder for app UI */}
            <div className="flex-1 w-full">
              <div className="aspect-square rounded-full bg-violet-500/5 absolute -z-10 blur-3xl w-96 h-96 top-1/2 right-0 transform -translate-y-1/2"></div>
              <div className="relative rounded-2xl overflow-hidden border border-white/10 bg-[#111] p-2 shadow-2xl">
                <div className="absolute top-0 inset-x-0 h-px bg-gradient-to-r from-transparent via-violet-500 to-transparent opacity-50"></div>
                <div className="rounded-xl border border-white/5 bg-black p-6 space-y-4">
                  {/* Mock UI */}
                  <div className="flex items-center gap-3 pb-4 border-b border-white/5">
                    <div className="w-10 h-10 rounded-full bg-violet-600/20 flex items-center justify-center">
                      <ChatBubbleLeftRightIcon className="w-5 h-5 text-violet-400" />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white">{t('landing.mockAssistantLabel')}</div>
                      <div className="text-xs text-gray-500">AI Assistant</div>
                    </div>
                  </div>
                  <div className="bg-white/5 rounded-lg p-4 text-sm text-gray-300">
                    {t('landing.mockAssistantMessage')}
                  </div>
                  <div className="flex justify-end">
                    <div className="bg-violet-600/20 border border-violet-500/30 rounded-lg p-4 text-sm text-white max-w-[80%]">
                      {t('landing.mockUserMessage')}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 py-32 border-t border-white/5 overflow-hidden">
        <div className="absolute inset-0 bg-violet-900/10 backdrop-blur-3xl"></div>
        <div className="max-w-4xl mx-auto px-6 text-center relative">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            {t('landing.subtitle')}
          </h2>
          <p className="text-xl text-gray-400 mb-10">
            Start optimizing your resume for free today.
          </p>
          <Link
            href="/register"
            className="inline-flex items-center gap-2 px-8 py-4 text-lg font-semibold text-white bg-violet-600 hover:bg-violet-500 transition-all rounded-full shadow-[0_0_30px_rgba(124,58,237,0.5)]"
          >
            {t('landing.primaryCta')}
            <ArrowRightIcon className="w-5 h-5" />
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-12 bg-black">
        <div className="max-w-7xl mx-auto px-6 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-gray-500 text-sm">
            <Logo size="sm" />
            <span>&copy; {new Date().getFullYear()} OfferMaster. All rights reserved.</span>
          </div>
          <div className="flex gap-6 text-sm text-gray-500">
            <a href="#" className="hover:text-white transition-colors">Privacy</a>
            <a href="#" className="hover:text-white transition-colors">Terms</a>
          </div>
        </div>
      </footer>
    </div>
  )
}"

with open('src/app/[locale]/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print('Done!')

