'use client'
// 用于提供 app/[locale]/page.tsx 模块。

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
} from '@heroicons/react/24/outline'

// 落地页，Coinbase 风格：白底 + 蓝色品牌色 + pill CTA
export default function LandingPage() {
  const t = useTranslations('common')
  const featureItems = [
    {
      icon: <DocumentTextIcon className="w-6 h-6" />,
      title: t('landing.features.resume.title'),
      desc: t('landing.features.resume.desc'),
      accent: '#0052ff',
    },
    {
      icon: <ChatBubbleLeftRightIcon className="w-6 h-6" />,
      title: t('landing.features.chat.title'),
      desc: t('landing.features.chat.desc'),
      accent: '#0052ff',
    },
    {
      icon: <MicrophoneIcon className="w-6 h-6" />,
      title: t('landing.features.interview.title'),
      desc: t('landing.features.interview.desc'),
      accent: '#0052ff',
    },
  ]
  const stepItems = [
    { step: '01', title: t('landing.steps.upload.title'), desc: t('landing.steps.upload.desc') },
    { step: '02', title: t('landing.steps.optimize.title'), desc: t('landing.steps.optimize.desc') },
    { step: '03', title: t('landing.steps.export.title'), desc: t('landing.steps.export.desc') },
  ]
  const insightItems = [
    t('landing.insights.metrics'),
    t('landing.insights.keywords'),
    t('landing.insights.diff'),
    t('landing.insights.report'),
  ]
  const statItems = [
    { label: t('landing.metrics.parse'), value: '92%', color: '#0052ff' },
    { label: t('landing.metrics.keywords'), value: '↑ 34%', color: '#059669' },
    { label: t('landing.metrics.quantified'), value: '8', color: '#0052ff' },
    { label: t('landing.metrics.interview'), value: '2.4×', color: '#059669' },
  ]

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff', color: '#0a0b0d' }}>

      {/* ── Navbar ── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-white" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-16">
          <Logo size="sm" />
          <div className="flex items-center gap-3">
            <LocaleSwitcher compact />
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-semibold transition-colors"
              style={{ borderRadius: '56px', color: '#0a0b0d' }}
            >
              {t('nav.login')}
            </Link>
            <Link
              href="/register"
              className="px-5 py-2 text-sm font-semibold text-white transition-colors"
              style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
            >
              {t('nav.register')}
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero — white section ── */}
      <section className="pt-16" style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-7xl mx-auto px-6 py-28 text-center">
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
          >
            {/* Display headline */}
            <h1
              className="mb-6 font-semibold"
              style={{ fontSize: 'clamp(2.5rem, 6vw, 5rem)', lineHeight: '1.00', letterSpacing: '-0.02em', color: '#0a0b0d' }}
            >
              {t('landing.heroPrefix')}<br />
              <span style={{ color: '#0052ff' }}>{t('landing.heroHighlight')}</span>{t('landing.heroSuffix')}
            </h1>

            <p
              className="mx-auto mb-12 text-lg"
              style={{ maxWidth: '560px', color: '#5b616e', lineHeight: '1.56' }}
            >
              {t('landing.subtitle')}
            </p>

            {/* CTAs */}
            <div className="flex items-center justify-center gap-4 flex-wrap">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-white transition-colors"
                style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
              >
                {t('landing.primaryCta')}
                <ArrowRightIcon className="w-4 h-4" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold transition-colors"
                style={{ borderRadius: '56px', backgroundColor: '#eef0f3', color: '#0a0b0d', border: '1px solid #eef0f3' }}
              >
                {t('landing.secondaryCta')}
              </Link>
            </div>
          </motion.div>

          {/* Hero visual */}
          <motion.div
            initial={false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="mt-20 mx-auto"
            style={{ maxWidth: '900px' }}
          >
            <div
              className="w-full p-8"
              style={{
                borderRadius: '24px',
                backgroundColor: '#ffffff',
                border: '1px solid rgba(91,97,110,0.18)',
                boxShadow: '0 8px 40px rgba(0,0,0,0.06)',
              }}
            >
              {/* Mock chat UI */}
              <div className="flex items-center gap-2 mb-6">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#ff5f57' }} />
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#ffbd2e' }} />
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: '#28ca41' }} />
                <span className="ml-3 text-sm font-medium" style={{ color: '#9ca3af' }}>
                  {t('landing.mockAssistantLabel')}
                </span>
              </div>
              <div className="space-y-4 text-left">
                <div className="flex justify-start">
                  <div className="px-4 py-3 text-sm max-w-xs" style={{ borderRadius: '16px 16px 16px 4px', backgroundColor: '#eef0f3', color: '#0a0b0d' }}>
                    {t('landing.mockAssistantMessage')}
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="px-4 py-3 text-sm max-w-xs" style={{ borderRadius: '16px 16px 4px 16px', backgroundColor: '#0052ff', color: '#ffffff' }}>
                    {t('landing.mockUserMessage')}
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="px-4 py-3 text-sm max-w-sm" style={{ borderRadius: '16px 16px 16px 4px', backgroundColor: '#eef0f3', color: '#0a0b0d' }}>
                    {t('landing.mockResultPrefix')} <span style={{ color: '#0052ff', fontWeight: 600 }}>68%</span>{t('landing.mockResultMiddle')} <span style={{ color: '#0052ff', fontWeight: 600 }}>100K+</span> {t('landing.mockResultSuffix')}
                  </div>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── Features — white section ── */}
      <section style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-7xl mx-auto px-6 py-28">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2
              className="font-semibold mb-4"
              style={{ fontSize: 'clamp(2rem, 4vw, 2.25rem)', lineHeight: '1.11', color: '#0a0b0d' }}
            >
              {t('landing.features.resume.title')}
            </h2>
            <p className="text-lg mx-auto" style={{ maxWidth: '480px', color: '#5b616e', lineHeight: '1.56' }}>
              {t('landing.subtitle')}
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {featureItems.map((item, i) => (
              <motion.div
                key={i}
                initial={false}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="p-8"
                style={{
                  border: '1px solid rgba(91,97,110,0.2)',
                  borderRadius: '20px',
                  backgroundColor: '#ffffff',
                }}
              >
                <div
                  className="w-12 h-12 rounded-2xl flex items-center justify-center mb-6"
                  style={{ backgroundColor: '#eef0f3', color: item.accent }}
                >
                  {item.icon}
                </div>
                <h3 className="text-lg font-semibold mb-3" style={{ color: '#0a0b0d' }}>{item.title}</h3>
                <p className="text-base" style={{ color: '#5b616e', lineHeight: '1.56' }}>{item.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works — gray section ── */}
      <section style={{ backgroundColor: '#eef0f3' }}>
        <div className="max-w-7xl mx-auto px-6 py-28">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2
              className="font-semibold mb-4"
              style={{ fontSize: 'clamp(2rem, 4vw, 2.25rem)', lineHeight: '1.11', color: '#0a0b0d' }}
            >
              {t('landing.steps.optimize.title')}
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {stepItems.map((item, i) => (
              <motion.div
                key={i}
                initial={false}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.5, delay: i * 0.1 }}
                className="flex gap-5"
              >
                <div
                  className="text-2xl font-bold flex-shrink-0 w-14 h-14 flex items-center justify-center rounded-2xl"
                  style={{ backgroundColor: '#0052ff', color: '#ffffff', lineHeight: '1' }}
                >
                  {item.step}
                </div>
                <div>
                  <h3 className="text-lg font-semibold mb-2" style={{ color: '#0a0b0d' }}>{item.title}</h3>
                  <p className="text-base" style={{ color: '#5b616e', lineHeight: '1.56' }}>{item.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Highlights — white section ── */}
      <section style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-7xl mx-auto px-6 py-28">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center"
          >
            <div>
              <h2
                className="font-semibold mb-6"
                style={{ fontSize: 'clamp(2rem, 4vw, 2.25rem)', lineHeight: '1.11', color: '#0a0b0d' }}
              >
                {t.rich('landing.insightTitle', {
                  // 用于处理break。
                  break: () => <br />,
                })}
              </h2>
              <p className="text-lg mb-8" style={{ color: '#5b616e', lineHeight: '1.56' }}>
                {t('landing.subtitle')}
              </p>
              <ul className="space-y-4">
                {insightItems.map((item, i) => (
                  <li key={i} className="flex items-center gap-3">
                    <div
                      className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0"
                      style={{ backgroundColor: 'rgba(0,82,255,0.1)', color: '#0052ff' }}
                    >
                      <CheckIcon className="w-3 h-3" />
                    </div>
                    <span className="text-base" style={{ color: '#0a0b0d' }}>{item}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div
              className="p-8 space-y-4"
              style={{
                borderRadius: '24px',
                backgroundColor: '#eef0f3',
                border: '1px solid rgba(91,97,110,0.15)',
              }}
            >
              {statItems.map((stat, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between px-5 py-4"
                  style={{
                    borderRadius: '12px',
                    backgroundColor: '#ffffff',
                    border: '1px solid rgba(91,97,110,0.12)',
                  }}
                >
                  <span className="text-sm font-medium" style={{ color: '#5b616e' }}>{stat.label}</span>
                  <span className="text-xl font-bold" style={{ color: stat.color }}>{stat.value}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>
      </section>

      {/* ── CTA — gray section ── */}
      <section style={{ backgroundColor: '#eef0f3' }}>
        <div className="max-w-7xl mx-auto px-6 py-28 text-center">
          <motion.div
            initial={false}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2
              className="font-semibold mb-6"
              style={{ fontSize: 'clamp(2.5rem, 5vw, 4rem)', lineHeight: '1.00', color: '#0a0b0d' }}
            >
              {t('landing.primaryCta')}
            </h2>
            <p className="text-lg mb-10 mx-auto" style={{ maxWidth: '400px', color: '#5b616e', lineHeight: '1.56' }}>
              {t('landing.subtitle')}
            </p>
            <Link
              href="/register"
              className="inline-flex items-center gap-2 px-10 py-5 text-lg font-semibold text-white transition-colors"
              style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
            >
              {t('landing.primaryCta')}
              <ArrowRightIcon className="w-5 h-5" />
            </Link>
          </motion.div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer style={{ backgroundColor: '#eef0f3', borderTop: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-7xl mx-auto px-6 py-10 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Logo size="sm" />
          <p className="text-sm" style={{ color: '#9ca3af' }}>
            © 2025 Chat Resume. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  )
}
