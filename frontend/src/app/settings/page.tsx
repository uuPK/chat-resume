'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import {
  ArrowLeftIcon,
  CheckIcon,
  CreditCardIcon,
  SparklesIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
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
    price: '$19',
    tagline: '获得完整求职工作流',
    features: ['深度简历优化', '模拟面试与复盘', '高级模型能力', '优先体验新功能'],
  },
]

function formatPlanCardPrice(plan: PayPalPlan | null): string {
  if (!plan) return 'PayPal 确认'
  if (plan.currency_code === 'USD') return `$${plan.price}`
  return `${plan.price} ${plan.currency_code}`
}

function formatCheckoutAmount(plan: PayPalPlan | null): string {
  if (!plan) return 'PayPal 确认'
  if (plan.currency_code === 'USD') return `US$${plan.price}`
  return `${plan.price} ${plan.currency_code}`
}

// 设置页，Coinbase 风格
export default function SettingsPage() {
  const { user, isLoading: authLoading, updateUser } = useAuth()
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [isBillingLoading, setIsBillingLoading] = useState(false)
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [paypalPlan, setPayPalPlan] = useState<PayPalPlan | null>(null)
  const [isPlanPickerOpen, setIsPlanPickerOpen] = useState(false)
  const [planPickerStep, setPlanPickerStep] = useState<'plans' | 'checkout'>('plans')
  const [openedFromUpgradeLink, setOpenedFromUpgradeLink] = useState(false)
  const [userLoaded, setUserLoaded] = useState(false)
  const [userSettings, setUserSettings] = useState({ fullName: '', email: '' })

  useEffect(() => {
    if (user && !authLoading && !userLoaded) {
      setUserSettings({ fullName: user.full_name || '', email: user.email || '' })
      setUserLoaded(true)
    }
  }, [user, authLoading, userLoaded])

  useEffect(() => {
    if (!user || authLoading) return
    const shouldSyncPayPalReturn = new URLSearchParams(window.location.search).get('billing') === 'success'
    billingApi.getStatus()
      .then(async status => {
        if (
          shouldSyncPayPalReturn &&
          status.provider === 'paypal' &&
          status.subscription_id &&
          !status.is_active
        ) {
          try {
            return await billingApi.syncPayPalSubscription(status.subscription_id)
          } catch {
            return status
          }
        }
        return status
      })
      .then(setBillingStatus)
      .catch(() => {
        setBillingStatus(null)
      })
    billingApi.getPayPalPlan()
      .then(setPayPalPlan)
      .catch(() => {
        setPayPalPlan(null)
      })
  }, [user, authLoading])

  useEffect(() => {
    if (new URLSearchParams(window.location.search).get('upgrade') === '1') {
      setOpenedFromUpgradeLink(true)
      setPlanPickerStep('plans')
      setIsPlanPickerOpen(true)
    }
  }, [])

  const closePlanPicker = () => {
    setIsPlanPickerOpen(false)
    setPlanPickerStep('plans')
    if (openedFromUpgradeLink) {
      setOpenedFromUpgradeLink(false)
      router.replace('/settings')
    }
  }

  const handleSaveSettings = async () => {
    if (!userSettings.fullName.trim()) {
      toast.error('姓名不能为空')
      return
    }
    setIsLoading(true)
    try {
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/me`,
        {
          method: 'PUT',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ full_name: userSettings.fullName.trim() })
        }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || '保存失败')
      }
      const updatedUser = await response.json()
      setUserSettings({ fullName: updatedUser.full_name || '', email: updatedUser.email || '' })
      updateUser(updatedUser)
      toast.success('设置已保存')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '保存设置失败')
    } finally {
      setIsLoading(false)
    }
  }

  const handleUpgradeWithPayPal = async () => {
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

  const handleManageBilling = async () => {
    if (!billingStatus?.is_active || !billingStatus.subscription_id) {
      setPlanPickerStep('plans')
      setIsPlanPickerOpen(true)
      return
    }
    if (!window.confirm('确定取消当前 PayPal 订阅吗？')) return

    setIsBillingLoading(true)
    try {
      const nextStatus = await billingApi.cancelPayPalSubscription(billingStatus.subscription_id)
      setBillingStatus(nextStatus)
      toast.success('订阅已取消')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '取消 PayPal 订阅失败')
    } finally {
      setIsBillingLoading(false)
    }
  }

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div
          className="w-10 h-10 rounded-full border-2 border-transparent animate-spin"
          style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
        />
      </div>
    )
  }

  const billingButtonLabel = billingStatus?.is_active
    ? '管理套餐'
    : isBillingLoading
      ? '跳转中...'
      : '升级套餐'
  const currentPlanName = billingStatus?.is_active ? 'Plus' : 'Free'
  const plusPlanPrice = formatPlanCardPrice(paypalPlan)
  const checkoutAmount = formatCheckoutAmount(paypalPlan)
  const renderedPlans = plans.map(plan =>
    plan.id === 'Plus' ? { ...plan, price: plusPlanPrice } : plan
  )

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff' }}>
      {/* Header */}
      <header
        className="bg-white"
        style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}
      >
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 text-sm font-semibold transition-colors"
              style={{ color: '#0a0b0d' }}
            >
              <ArrowLeftIcon className="w-4 h-4" />
              返回
            </button>
            <button
              onClick={handleSaveSettings}
              disabled={isLoading}
              className="btn-primary btn-sm"
            >
              {isLoading ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      </header>

      {/* Header */}
      <div className="py-10 px-6" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-7xl mx-auto">
          <h1 className="text-5xl font-semibold" style={{ lineHeight: '1.00', color: '#0a0b0d' }}>
            设置
          </h1>
          <p className="mt-2 text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
            管理您的个人信息
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <nav>
              <div
                className="flex items-center gap-3 px-4 py-3 text-sm font-semibold"
                style={{
                  borderRadius: '12px',
                  backgroundColor: '#eef0f3',
                  color: '#0052ff',
                }}
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                  style={{ backgroundColor: '#0052ff' }}
                >
                  {(user?.full_name || 'U')[0].toUpperCase()}
                </div>
                <div>
                  <div className="font-semibold">个人资料</div>
                  <div className="text-xs font-normal" style={{ color: '#5b616e' }}>管理您的个人信息</div>
                </div>
              </div>
            </nav>
          </div>

          {/* Main */}
          <div className="lg:col-span-3">
            <div
              className="p-8"
              style={{
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
                backgroundColor: '#ffffff',
              }}
            >
              <div className="mb-8">
                <h2 className="text-2xl font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                  个人资料
                </h2>
                <p className="mt-1 text-base" style={{ color: '#5b616e' }}>管理您的个人信息</p>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="label">姓名</label>
                  <input
                    type="text"
                    value={userSettings.fullName}
                    onChange={(e) => setUserSettings(prev => ({ ...prev, fullName: e.target.value }))}
                    className="input"
                    placeholder="请输入您的姓名"
                  />
                </div>
                <div>
                  <label className="label">邮箱地址</label>
                  <input
                    type="email"
                    value={userSettings.email}
                    readOnly
                    className="input"
                    style={{ backgroundColor: '#eef0f3', cursor: 'not-allowed', color: '#5b616e' }}
                  />
                </div>
              </div>
            </div>

            <div
              className="mt-6 p-8"
              style={{
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
                backgroundColor: '#ffffff',
              }}
            >
              <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-4">
                  <div
                    className="w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0"
                    style={{ backgroundColor: '#eef0f3', color: '#0052ff' }}
                  >
                    <CreditCardIcon className="w-5 h-5" />
                  </div>
                  <div>
                    <h2 className="text-2xl font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                      账单
                    </h2>
                    <p className="mt-1 text-base" style={{ color: '#5b616e' }}>
                      当前套餐：{billingStatus?.is_active ? 'Plus' : 'Free'}
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleManageBilling}
                  disabled={isBillingLoading}
                  className="btn-primary btn-sm w-full sm:w-auto"
                >
                  {billingButtonLabel}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {isPlanPickerOpen && (
        <div
          className="fixed inset-0 z-50 overflow-y-auto px-4 py-8"
          style={{ backgroundColor: 'rgba(255,255,255,0.96)' }}
        >
          <button
            type="button"
            onClick={closePlanPicker}
            className="absolute right-6 top-6 flex h-9 w-9 items-center justify-center rounded-full transition-colors"
            style={{ color: '#5b616e' }}
            onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
            onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
            aria-label="关闭"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>

          {planPickerStep === 'plans' ? (
            <div className="mx-auto max-w-6xl">
              <div className="text-center">
                <h2 className="text-3xl font-semibold" style={{ color: '#0a0b0d' }}>
                  选择套餐
                </h2>
              </div>

              <div className="mt-10 grid grid-cols-1 gap-5 lg:grid-cols-3">
                {renderedPlans.map(plan => {
                  const isCurrent = currentPlanName === plan.name
                  const isPayable = plan.name === 'Plus'
                  const isSoon = plan.name === 'Pro'
                  const hasUsdPrice = plan.price.startsWith('$')
                  const buttonLabel = isCurrent
                    ? '当前套餐'
                    : isPayable
                      ? '选择 Plus'
                      : isSoon
                        ? '即将推出'
                        : `切换至 ${plan.name}`

                  return (
                    <div
                      key={plan.id}
                      className="flex min-h-[520px] flex-col p-7"
                      style={{
                        border: isCurrent ? '1.5px solid #0a0b0d' : '1px solid rgba(91,97,110,0.2)',
                        borderRadius: '16px',
                        backgroundColor: '#ffffff',
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <h3 className="text-2xl font-semibold" style={{ color: '#0a0b0d' }}>
                          {plan.name}
                        </h3>
                        {isCurrent && (
                          <span className="rounded-full px-3 py-1 text-xs font-semibold" style={{ backgroundColor: '#eef0f3', color: '#5b616e' }}>
                            当前
                          </span>
                        )}
                      </div>

                      <div className="mt-8 flex items-end gap-2">
                        {hasUsdPrice ? (
                          <>
                            <span className="text-base" style={{ color: '#7b818a' }}>$</span>
                            <span className="text-5xl font-semibold leading-none" style={{ color: '#0a0b0d' }}>
                              {plan.price.replace('$', '')}
                            </span>
                            <span className="mb-1 text-sm font-medium" style={{ color: '#5b616e' }}>
                              USD / 月
                            </span>
                          </>
                        ) : (
                          <span className="text-3xl font-semibold leading-tight" style={{ color: '#0a0b0d' }}>
                            {plan.price}
                          </span>
                        )}
                      </div>
                      <p className="mt-5 text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                        {plan.tagline}
                      </p>

                      <button
                        type="button"
                        disabled={isCurrent || isSoon}
                        onClick={isPayable ? () => setPlanPickerStep('checkout') : undefined}
                        className="mt-6 w-full px-4 py-3 text-sm font-semibold transition-colors"
                        style={{
                          borderRadius: '999px',
                          border: isCurrent ? 'none' : '1px solid rgba(91,97,110,0.22)',
                          backgroundColor: isCurrent ? '#b8b8b8' : isPayable ? '#0a0b0d' : '#ffffff',
                          color: isCurrent ? '#ffffff' : isPayable ? '#ffffff' : '#0a0b0d',
                          cursor: isCurrent || isSoon ? 'not-allowed' : 'pointer',
                        }}
                      >
                        {buttonLabel}
                      </button>

                      <div className="mt-8 space-y-4">
                        {plan.features.map(feature => (
                          <div key={feature} className="flex items-start gap-3 text-sm" style={{ color: '#0a0b0d' }}>
                            {plan.name === 'Pro' ? (
                              <SparklesIcon className="mt-0.5 h-4 w-4 flex-shrink-0" />
                            ) : (
                              <CheckIcon className="mt-0.5 h-4 w-4 flex-shrink-0" />
                            )}
                            <span>{feature}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          ) : (
            <div className="mx-auto max-w-4xl">
              <button
                type="button"
                onClick={() => setPlanPickerStep('plans')}
                className="mb-8 flex items-center gap-3 text-sm font-semibold"
                style={{ color: '#0a0b0d' }}
              >
                <ArrowLeftIcon className="h-5 w-5" />
                返回套餐
              </button>

              <div className="grid min-h-[700px] grid-cols-1 overflow-hidden rounded-[20px] border lg:grid-cols-[0.95fr_1.05fr]" style={{ borderColor: 'rgba(91,97,110,0.14)', backgroundColor: '#ffffff' }}>
                <aside className="px-7 pb-9 pt-[68px] lg:px-10" style={{ backgroundColor: '#fbfbfc' }}>
                  <div className="flex items-center justify-between gap-5">
                    <div className="flex items-center gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl" style={{ backgroundColor: '#f5d94e' }}>
                        <SparklesIcon className="h-6 w-6" />
                      </div>
                      <div>
                        <div className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                          Chat Resume Plus
                        </div>
                        <div className="text-xs" style={{ color: '#7b818a' }}>
                          Plus 月度套餐
                        </div>
                      </div>
                    </div>
                    <div className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                      {checkoutAmount}
                    </div>
                  </div>

                  <div className="my-7 h-px" style={{ backgroundColor: 'rgba(91,97,110,0.16)' }} />

                  <div className="space-y-4">
                    <div className="flex items-center justify-between text-sm">
                      <span style={{ color: '#0a0b0d' }}>小计</span>
                      <span className="font-semibold" style={{ color: '#0a0b0d' }}>{checkoutAmount}</span>
                    </div>
                    <button
                      type="button"
                      className="rounded-lg px-4 py-2.5 text-xs font-semibold"
                      style={{ backgroundColor: '#eef0f3', color: '#0a0b0d' }}
                    >
                      添加促销码
                    </button>
                    <div className="h-px" style={{ backgroundColor: 'rgba(91,97,110,0.16)' }} />
                    <div className="flex items-center justify-between text-base font-semibold">
                      <span style={{ color: '#0a0b0d' }}>应付合计</span>
                      <span style={{ color: '#0a0b0d' }}>{checkoutAmount}</span>
                    </div>
                  </div>
                </aside>

                <main className="px-7 pb-9 pt-[60px] lg:px-10">
                  <section className="mx-auto w-full max-w-[360px]">
                    <h2 className="text-base font-semibold" style={{ color: '#0a0b0d' }}>
                      联系信息
                    </h2>
                    <div className="mt-3 flex items-center rounded-lg border px-4 py-3.5" style={{ borderColor: 'rgba(91,97,110,0.18)', backgroundColor: '#f8f8f9' }}>
                      <span className="w-20 text-xs" style={{ color: '#5b616e' }}>邮箱</span>
                      <span className="text-sm" style={{ color: '#0a0b0d' }}>{user?.email || userSettings.email}</span>
                    </div>
                  </section>

                  <section className="mx-auto mt-7 w-full max-w-[360px]">
                    <h2 className="text-base font-semibold" style={{ color: '#0a0b0d' }}>
                      支付方式
                    </h2>
                    <div
                      className="mt-3 flex w-full items-center gap-3 rounded-lg border px-4 py-3.5"
                      style={{ borderColor: 'rgba(91,97,110,0.2)', backgroundColor: '#ffffff' }}
                    >
                      <span className="flex h-4 w-4 items-center justify-center rounded-full border-2" style={{ borderColor: '#0a0b0d' }}>
                        <span className="h-2 w-2 rounded-full" style={{ backgroundColor: '#0a0b0d' }} />
                      </span>
                      <span className="flex items-center gap-3">
                        <span className="rounded px-2 py-0.5 text-xs font-semibold" style={{ backgroundColor: '#0070e0', color: '#ffffff' }}>PayPal</span>
                        <span className="text-sm font-medium" style={{ color: '#0a0b0d' }}>PayPal</span>
                      </span>
                    </div>
                  </section>

                  <button
                    type="button"
                    onClick={handleUpgradeWithPayPal}
                    disabled={isBillingLoading}
                    className="mx-auto mt-7 block w-full max-w-[360px] px-4 py-3.5 text-sm font-semibold shadow-md"
                    style={{
                      borderRadius: '8px',
                      backgroundColor: '#3f6dcc',
                      color: '#ffffff',
                      cursor: isBillingLoading ? 'not-allowed' : 'pointer',
                    }}
                  >
                    {isBillingLoading ? '跳转中...' : '支付'}
                  </button>
                </main>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
