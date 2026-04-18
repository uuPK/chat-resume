'use client'

import Link from 'next/link'
import { motion } from 'framer-motion'
import Logo from '@/components/ui/Logo'
import {
  SparklesIcon,
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  MicrophoneIcon,
  ArrowRightIcon,
  CheckIcon,
} from '@heroicons/react/24/outline'

// 落地页，Coinbase 风格：白底 + 蓝色品牌色 + pill CTA
export default function LandingPage() {
  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff', color: '#0a0b0d' }}>

      {/* ── Navbar ── */}
      <header className="fixed top-0 inset-x-0 z-50 bg-white" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-7xl mx-auto px-6 flex items-center justify-between h-16">
          <Logo size="sm" />
          <div className="flex items-center gap-3">
            <Link
              href="/login"
              className="px-4 py-2 text-sm font-semibold transition-colors"
              style={{ borderRadius: '56px', color: '#0a0b0d' }}
            >
              登录
            </Link>
            <Link
              href="/register"
              className="px-5 py-2 text-sm font-semibold text-white transition-colors"
              style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
            >
              免费开始
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero — white section ── */}
      <section className="pt-16" style={{ backgroundColor: '#ffffff' }}>
        <div className="max-w-7xl mx-auto px-6 py-28 text-center">
          <motion.div
            initial={{ opacity: 0, y: 32 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7 }}
          >
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-4 py-1.5 mb-10 text-sm font-semibold"
              style={{
                borderRadius: '100000px',
                backgroundColor: 'rgba(0,82,255,0.08)',
                color: '#0052ff',
                border: '1px solid rgba(0,82,255,0.2)',
              }}
            >
              <SparklesIcon className="w-4 h-4" />
              AI 驱动的简历优化平台
            </div>

            {/* Display headline */}
            <h1
              className="mb-6 font-semibold"
              style={{ fontSize: 'clamp(2.5rem, 6vw, 5rem)', lineHeight: '1.00', letterSpacing: '-0.02em', color: '#0a0b0d' }}
            >
              让每一份简历<br />
              <span style={{ color: '#0052ff' }}>精准命中</span>目标岗位
            </h1>

            <p
              className="mx-auto mb-12 text-lg"
              style={{ maxWidth: '560px', color: '#5b616e', lineHeight: '1.56' }}
            >
              上传简历，与 AI 对话优化内容，模拟面试练习表达，一站式提升求职竞争力。
            </p>

            {/* CTAs */}
            <div className="flex items-center justify-center gap-4 flex-wrap">
              <Link
                href="/register"
                className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold text-white transition-colors"
                style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
              >
                免费开始使用
                <ArrowRightIcon className="w-4 h-4" />
              </Link>
              <Link
                href="/login"
                className="inline-flex items-center gap-2 px-8 py-4 text-base font-semibold transition-colors"
                style={{ borderRadius: '56px', backgroundColor: '#eef0f3', color: '#0a0b0d', border: '1px solid #eef0f3' }}
              >
                已有账户，去登录
              </Link>
            </div>
          </motion.div>

          {/* Hero visual */}
          <motion.div
            initial={{ opacity: 0, y: 48 }}
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
                  AI Resume Assistant
                </span>
              </div>
              <div className="space-y-4 text-left">
                <div className="flex justify-start">
                  <div className="px-4 py-3 text-sm max-w-xs" style={{ borderRadius: '16px 16px 16px 4px', backgroundColor: '#eef0f3', color: '#0a0b0d' }}>
                    你好！我已分析你的简历，发现工作经历的描述缺乏量化数据，建议补充具体成果。
                  </div>
                </div>
                <div className="flex justify-end">
                  <div className="px-4 py-3 text-sm max-w-xs" style={{ borderRadius: '16px 16px 4px 16px', backgroundColor: '#0052ff', color: '#ffffff' }}>
                    好的，帮我优化「后端开发」这段经历
                  </div>
                </div>
                <div className="flex justify-start">
                  <div className="px-4 py-3 text-sm max-w-sm" style={{ borderRadius: '16px 16px 16px 4px', backgroundColor: '#eef0f3', color: '#0a0b0d' }}>
                    已将「参与系统优化」改写为「通过缓存改造将接口响应时间降低 <span style={{ color: '#0052ff', fontWeight: 600 }}>68%</span>，支撑 <span style={{ color: '#0052ff', fontWeight: 600 }}>10万+</span> 日活」✅
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
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2
              className="font-semibold mb-4"
              style={{ fontSize: 'clamp(2rem, 4vw, 2.25rem)', lineHeight: '1.11', color: '#0a0b0d' }}
            >
              一个平台，覆盖求职全流程
            </h2>
            <p className="text-lg mx-auto" style={{ maxWidth: '480px', color: '#5b616e', lineHeight: '1.56' }}>
              从简历撰写到面试准备，AI 全程陪你冲击理想 offer
            </p>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              {
                icon: <DocumentTextIcon className="w-6 h-6" />,
                title: 'AI 简历优化',
                desc: '上传现有简历，AI 识别不足，针对目标岗位重写亮点，量化每项成果。',
                accent: '#0052ff',
              },
              {
                icon: <ChatBubbleLeftRightIcon className="w-6 h-6" />,
                title: '对话式编辑',
                desc: '像和同事沟通一样告诉 AI 你的想法，实时预览修改效果，随时撤销确认。',
                accent: '#0052ff',
              },
              {
                icon: <MicrophoneIcon className="w-6 h-6" />,
                title: '模拟面试',
                desc: '基于你的简历和目标 JD，AI 生成专项面试题，给出详细点评和改进建议。',
                accent: '#0052ff',
              },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 24 }}
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
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
            className="text-center mb-16"
          >
            <h2
              className="font-semibold mb-4"
              style={{ fontSize: 'clamp(2rem, 4vw, 2.25rem)', lineHeight: '1.11', color: '#0a0b0d' }}
            >
              三步完成简历升级
            </h2>
          </motion.div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {[
              { step: '01', title: '上传简历', desc: '支持 PDF、Word、TXT 格式，AI 自动解析结构化内容。' },
              { step: '02', title: '对话优化', desc: '告知目标公司和岗位，AI 针对性重写每一段经历。' },
              { step: '03', title: '导出投递', desc: '一键导出精美 PDF，直接投递目标岗位。' },
            ].map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 24 }}
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
            initial={{ opacity: 0, y: 24 }}
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
                不只是改简历，<br />更是帮你思考
              </h2>
              <p className="text-lg mb-8" style={{ color: '#5b616e', lineHeight: '1.56' }}>
                AI 会分析你的背景与目标岗位的匹配度，主动指出差距，给出量化改写建议，而不是单纯润色文字。
              </p>
              <ul className="space-y-4">
                {[
                  '自动识别简历中缺失的量化数据',
                  '针对 JD 关键词定向强化描述',
                  '实时 Diff 预览，逐条确认或拒绝修改',
                  '面试报告指出薄弱点和训练计划',
                ].map((item, i) => (
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
              {[
                { label: '简历解析质量', value: '92%', color: '#0052ff' },
                { label: '关键词匹配率', value: '↑ 34%', color: '#059669' },
                { label: '量化指标覆盖', value: '8 项', color: '#0052ff' },
                { label: '面试通过率提升', value: '2.4×', color: '#059669' },
              ].map((stat, i) => (
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
            initial={{ opacity: 0, y: 24 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2
              className="font-semibold mb-6"
              style={{ fontSize: 'clamp(2.5rem, 5vw, 4rem)', lineHeight: '1.00', color: '#0a0b0d' }}
            >
              现在就开始
            </h2>
            <p className="text-lg mb-10 mx-auto" style={{ maxWidth: '400px', color: '#5b616e', lineHeight: '1.56' }}>
              免费注册，上传简历，与 AI 对话，拿到你想要的 offer。
            </p>
            <Link
              href="/register"
              className="inline-flex items-center gap-2 px-10 py-5 text-lg font-semibold text-white transition-colors"
              style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
            >
              免费开始使用
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
