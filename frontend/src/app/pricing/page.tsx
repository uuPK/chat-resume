'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  ArrowRightIcon,
  CheckIcon,
  SparklesIcon,
} from '@heroicons/react/24/outline'
import Logo from '@/components/ui/Logo'
import { useAuth } from '@/lib/auth'
import { billingApi, type BillingStatus, type PayPalPlan } from '@/lib/api'

const plans = [
  {
    id: 'Free',
    name: 'Free',
    price: '$0',
    tagline: '开始优化简历',
    features: ['简历编辑与预览', '基础 AI 优化', 'PDF 导出'],
  },
  {
    id: 'Plus',
    name: 'Plus',
    price: '',
    tagline: '解锁更多优化能力',
    features: ['更多 AI 对话额度', 'JD 匹配分析', '面试问答训练', '更多导出样式'],
  },
  {
    id: 'Pro',
    name: 'Pro',
    price: '$20',
    tagline: '获得完整求职工作流',
    features: ['深度简历优化', '模拟面试与复盘', '高级模型能力', '优先体验新功能'],
  },
]

// 格式化 PayPal 返回的套餐价格，未登录或配置缺失时保留可用占位。
function formatPlanCardPrice(plan: PayPalPlan | null): string {
  if (!plan) return 'PayPal 确认'
  if (plan.currency_code === 'USD') return `$${plan.price}`
  return `${plan.price} ${plan.currency_code}`
}

// 独立定价页，修复直接访问 /pricing 时的 404。
export default function PricingPage() {
  const router = useRouter()
  const { user, isLoading: authLoading } = useAuth()
  const [isBillingLoading, setIsBillingLoading] = useState(false)
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [paypalPlan, setPayPalPlan] = useState<PayPalPlan | null>(null)

  useEffect(() => {
    if (!user || authLoading) return
    billingApi.getStatus()
      .then(setBillingStatus)
      .catch(() => setBillingStatus(null))
    billingApi.getPayPalPlan()
      .then(setPayPalPlan)
      .catch(() => setPayPalPlan(null))
  }, [user, authLoading])

  const handleChoosePlus = async () => {
    if (!user) {
      router.push('/login?next=/pricing')
      return
    }

    setIsBillingLoading(true)
    try {
      const checkout = await billingApi.createPayPalSubscription()
      setBillingStatus({
        provider: checkout.provider,
        subscription_id: checkout.subscription_id,
        status: checkout.status,
        is_active: false,
      })
      window.location.href = checkout.approval_url
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '创建 PayPal 订阅失败')
    } finally {
      setIsBillingLoading(false)
    }
  }

  const currentPlanName = billingStatus?.is_active ? 'Plus' : 'Free'
  const renderedPlans = plans.map(plan =>
    plan.id === 'Plus' ? { ...plan, price: formatPlanCardPrice(paypalPlan) } : plan
  )

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff', color: '#0a0b0d' }}>
      <header className="sticky top-0 z-50 bg-white" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Logo size="sm" />
          <div className="flex items-center gap-3">
            <Link
              href={user ? '/resumes' : '/login'}
              className="px-4 py-2 text-sm font-semibold transition-colors"
              style={{ borderRadius: '56px', color: '#0a0b0d' }}
            >
              {user ? '进入应用' : '登录'}
            </Link>
            <Link
              href={user ? '/settings' : '/register'}
              className="px-5 py-2 text-sm font-semibold text-white transition-colors"
              style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
            >
              {user ? '账户设置' : '免费开始'}
            </Link>
          </div>
        </div>
      </header>

      <main>
        <section className="mx-auto max-w-7xl px-6 py-8 md:py-10">
          <div className="max-w-3xl">
            <h1 className="text-[52px] font-semibold md:text-[72px]" style={{ color: '#0a0b0d', lineHeight: '1.00' }}>
              选择适合你的求职加速套餐
            </h1>
            <p className="mt-4 max-w-2xl text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
              从免费简历优化开始，需要更多 AI 对话额度、JD 匹配分析和面试训练时再升级 Plus。
            </p>
          </div>

          <div className="mt-8 grid grid-cols-1 gap-5 lg:grid-cols-3">
            {renderedPlans.map(plan => {
              const isCurrent = user && currentPlanName === plan.name
              const isPayable = plan.name === 'Plus'
              const isSoon = plan.name === 'Pro'
              const hasUsdPrice = plan.price.startsWith('$')
              const buttonLabel = isCurrent
                ? '当前套餐'
                : isPayable
                  ? (isBillingLoading ? '跳转中...' : '选择 Plus')
                  : isSoon
                    ? '即将推出'
                    : user
                      ? '当前免费'
                      : '免费开始'

              return (
                <section
                  key={plan.id}
                  className="flex min-h-[500px] flex-col p-8"
                  style={{
                    border: plan.name === 'Plus' ? '2px solid #0052ff' : '1px solid rgba(91,97,110,0.2)',
                    borderRadius: '24px',
                    backgroundColor: '#ffffff',
                  }}
                >
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h2 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                        {plan.name}
                      </h2>
                      <p className="mt-3 text-sm font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.5' }}>
                        {plan.tagline}
                      </p>
                    </div>
                    {plan.name === 'Plus' && (
                      <span className="rounded-full px-2.5 py-1 text-xs font-semibold leading-none" style={{ backgroundColor: '#eef0f3', color: '#0052ff' }}>
                        推荐
                      </span>
                    )}
                  </div>

                  <div className="mt-9 flex items-end gap-2">
                    {hasUsdPrice ? (
                      <>
                        <span className="mb-2 text-base" style={{ color: '#5b616e' }}>$</span>
                        <span className="text-[64px] font-semibold leading-none" style={{ color: '#0a0b0d' }}>
                          {plan.price.replace('$', '')}
                        </span>
                        <span className="mb-2 text-sm font-semibold" style={{ color: '#5b616e' }}>
                          USD / 月
                        </span>
                      </>
                    ) : (
                      <span className="text-[32px] font-semibold leading-tight" style={{ color: '#0a0b0d' }}>
                        {plan.price}
                      </span>
                    )}
                  </div>

                  <button
                    type="button"
                    disabled={Boolean(isCurrent || isSoon || isBillingLoading)}
                    onClick={isPayable ? handleChoosePlus : () => router.push(user ? '/resumes' : '/register')}
                    className="mt-8 flex w-full items-center justify-center gap-2 px-5 py-3 text-base font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-black disabled:cursor-not-allowed disabled:opacity-70"
                    style={{
                      borderRadius: '56px',
                      border: isPayable ? '1px solid #0052ff' : '1px solid rgba(91,97,110,0.2)',
                      backgroundColor: isPayable ? '#0052ff' : '#ffffff',
                      color: isPayable ? '#ffffff' : '#0a0b0d',
                    }}
                  >
                    {buttonLabel}
                    {!isCurrent && !isSoon && <ArrowRightIcon className="h-4 w-4" />}
                  </button>

                  <div className="mt-8 space-y-4">
                    {plan.features.map(feature => (
                      <div key={feature} className="flex items-start gap-3 text-base" style={{ color: '#0a0b0d', lineHeight: '1.5' }}>
                        {plan.name === 'Pro' ? (
                          <SparklesIcon className="mt-1 h-4 w-4 flex-shrink-0" />
                        ) : (
                          <CheckIcon className="mt-1 h-4 w-4 flex-shrink-0" />
                        )}
                        <span>{feature}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )
            })}
          </div>
        </section>
      </main>
    </div>
  )
}
