'use client'
// 用于提供 app/[locale]/settings/page.tsx 模块。

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from '@/i18n/navigation'
import {
  ArrowLeftIcon,
  CheckIcon,
  KeyIcon,
  SparklesIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { billingApi, type BillingStatus, type PayPalPlan } from '@/lib/api'
import { apiFetch, handleApiResponse } from '@/lib/httpClient'
import { useTranslations } from 'next-intl'

// 用于格式化套餐卡片价格。
function formatPlanCardPrice(plan: PayPalPlan | null): string {
  if (!plan) return 'PayPal'
  if (plan.currency_code === 'USD') return `$${plan.price}`
  return `${plan.price} ${plan.currency_code}`
}

// 用于格式化结账金额。
function formatCheckoutAmount(plan: PayPalPlan | null): string {
  if (!plan) return 'PayPal'
  if (plan.currency_code === 'USD') return `US$${plan.price}`
  return `${plan.price} ${plan.currency_code}`
}

// 设置页，Coinbase 风格
export default function SettingsPage() {
  const { user, isLoading: authLoading, updateUser } = useAuth()
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [isPasswordSaving, setIsPasswordSaving] = useState(false)
  const [isBillingLoading, setIsBillingLoading] = useState(false)
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const [paypalPlan, setPayPalPlan] = useState<PayPalPlan | null>(null)
  const [isPlanPickerOpen, setIsPlanPickerOpen] = useState(false)
  const [planPickerStep, setPlanPickerStep] = useState<'plans' | 'checkout'>('plans')
  const [openedFromUpgradeLink, setOpenedFromUpgradeLink] = useState(false)
  const [userLoaded, setUserLoaded] = useState(false)
  const [userSettings, setUserSettings] = useState({ fullName: '', email: '' })
  const [passwordSettings, setPasswordSettings] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  })
  const t = useTranslations('dashboard')
  const common = useTranslations('common')
  const auth = useTranslations('auth')
  const plans = [
    {
      id: 'Free',
      name: 'Free',
      price: '$0',
      tagline: t('pricing.plans.free.tagline'),
      features: t.raw('pricing.plans.free.features') as string[],
    },
    {
      id: 'Plus',
      name: 'Plus',
      price: '',
      tagline: t('pricing.plans.plus.tagline'),
      features: t.raw('pricing.plans.plus.features') as string[],
    },
    {
      id: 'Pro',
      name: 'Pro',
      price: '$19',
      tagline: t('pricing.plans.pro.tagline'),
      features: t.raw('pricing.plans.pro.features') as string[],
    },
  ]

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

  // 用于关闭套餐picker。
  const closePlanPicker = () => {
    setIsPlanPickerOpen(false)
    setPlanPickerStep('plans')
    if (openedFromUpgradeLink) {
      setOpenedFromUpgradeLink(false)
      router.replace('/settings')
    }
  }

  // 用于处理保存settings。
  const handleSaveSettings = async () => {
    if (!userSettings.fullName.trim()) {
      toast.error(t('settings.nameRequired'))
      return
    }
    setIsLoading(true)
    try {
      const response = await apiFetch('/api/auth/me', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ full_name: userSettings.fullName.trim() })
      })
      const updatedUser = await handleApiResponse<{ full_name?: string; email?: string }>(
        response,
        t('settings.saveFallback')
      )
      setUserSettings({ fullName: updatedUser.full_name || '', email: updatedUser.email || '' })
      updateUser(updatedUser)
      toast.success(t('settings.saveSuccess'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.saveError'))
    } finally {
      setIsLoading(false)
    }
  }

  // 用于处理已登录用户修改密码。
  const handleChangePassword = async () => {
    if (passwordSettings.newPassword.length < 6) {
      toast.error(auth('validation.passwordMin'))
      return
    }
    if (passwordSettings.newPassword !== passwordSettings.confirmPassword) {
      toast.error(auth('validation.passwordMismatch'))
      return
    }
    setIsPasswordSaving(true)
    try {
      const response = await apiFetch('/api/auth/change-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          current_password: passwordSettings.currentPassword,
          new_password: passwordSettings.newPassword,
        })
      })
      await handleApiResponse(response, t('settings.passwordSaveFallback'))
      setPasswordSettings({ currentPassword: '', newPassword: '', confirmPassword: '' })
      toast.success(t('settings.passwordSaveSuccess'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('settings.passwordSaveError'))
    } finally {
      setIsPasswordSaving(false)
    }
  }

  // 用于处理upgradewithpaypal。
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
      toast.error(error instanceof Error ? error.message : common('errors.network'))
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

  const currentPlanName = billingStatus?.is_active ? 'Plus' : 'Free'
  const plusPlanPrice = formatPlanCardPrice(paypalPlan)
  const checkoutAmount = formatCheckoutAmount(paypalPlan)
  const renderedPlans = plans.map(plan =>
    plan.id === 'Plus' ? { ...plan, price: plusPlanPrice } : plan
  )
  const canChangePassword = user?.has_password !== false

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
              {t('settings.back')}
            </button>
            <button
              onClick={handleSaveSettings}
              disabled={isLoading}
              className="btn-primary btn-sm"
            >
              {isLoading ? common('actions.saving') : common('actions.save')}
            </button>
          </div>
        </div>
      </header>

      {/* Content */}
      <main className="mx-auto w-full max-w-3xl px-6 py-10">
        <section
          className="p-8"
          style={{
            border: '1px solid rgba(91,97,110,0.2)',
            borderRadius: '24px',
            backgroundColor: '#ffffff',
          }}
        >
          <div className="mb-8">
            <h2 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
              {t('settings.profileTitle')}
            </h2>
            <p className="mt-2 text-base" style={{ color: '#5b616e', lineHeight: '1.5' }}>
              {t('settings.profileSubtitle')}
            </p>
          </div>

          <div className="space-y-6">
            <div>
              <label className="label">{auth('fields.name')}</label>
              <input
                type="text"
                value={userSettings.fullName}
                onChange={(e) => setUserSettings(prev => ({ ...prev, fullName: e.target.value }))}
                className="input"
                placeholder={auth('placeholders.name')}
              />
            </div>
            <div>
              <label className="label">{auth('fields.email')}</label>
              <input
                type="email"
                value={userSettings.email}
                readOnly
                className="input"
                style={{ backgroundColor: '#eef0f3', cursor: 'not-allowed', color: '#5b616e' }}
              />
            </div>
          </div>
        </section>

        {canChangePassword && (
          <section
            className="mt-8 p-8"
            style={{
              border: '1px solid rgba(91,97,110,0.2)',
              borderRadius: '24px',
              backgroundColor: '#ffffff',
            }}
          >
            <div className="mb-8 flex items-start gap-3">
              <KeyIcon className="mt-1 h-6 w-6 flex-shrink-0" style={{ color: '#0052ff' }} />
              <div>
                <h2 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                  {t('settings.passwordTitle')}
                </h2>
                <p className="mt-2 text-base" style={{ color: '#5b616e', lineHeight: '1.5' }}>
                  {t('settings.passwordSubtitle')}
                </p>
              </div>
            </div>

            <div className="space-y-6">
              <div>
                <label className="label">{t('settings.currentPassword')}</label>
                <input
                  type="password"
                  autoComplete="current-password"
                  value={passwordSettings.currentPassword}
                  onChange={(e) => setPasswordSettings(prev => ({ ...prev, currentPassword: e.target.value }))}
                  className="input"
                  placeholder={auth('placeholders.password')}
                />
              </div>
              <div>
                <label className="label">{t('settings.newPassword')}</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={passwordSettings.newPassword}
                  onChange={(e) => setPasswordSettings(prev => ({ ...prev, newPassword: e.target.value }))}
                  className="input"
                  placeholder={auth('placeholders.newPassword')}
                />
              </div>
              <div>
                <label className="label">{auth('fields.confirmPassword')}</label>
                <input
                  type="password"
                  autoComplete="new-password"
                  value={passwordSettings.confirmPassword}
                  onChange={(e) => setPasswordSettings(prev => ({ ...prev, confirmPassword: e.target.value }))}
                  className="input"
                  placeholder={auth('placeholders.confirmPassword')}
                />
              </div>
              <button
                type="button"
                onClick={handleChangePassword}
                disabled={isPasswordSaving}
                className="btn-primary btn-sm"
              >
                {isPasswordSaving ? common('actions.saving') : t('settings.passwordSave')}
              </button>
            </div>
          </section>
        )}

      </main>

      {isPlanPickerOpen && (
        <div className="fixed inset-0 z-50 overflow-y-auto px-5 pb-6 pt-16" style={{ backgroundColor: '#ffffff' }}>
          {planPickerStep === 'plans' ? (
            <div className="mx-auto max-w-7xl">
              <div className="flex items-start justify-between gap-6">
                <div>
                  <h2 className="text-[52px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.00' }}>
                    {t('settings.choosePlan')}
                  </h2>
                </div>
                <button
                  type="button"
                  onClick={closePlanPicker}
                  className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full transition-colors"
                  style={{ color: '#5b616e' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  aria-label={common('actions.close')}
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>

              <div className="mt-10 grid grid-cols-1 gap-5 lg:grid-cols-3">
                {renderedPlans.map(plan => {
                  const isCurrent = currentPlanName === plan.name
                  const isPayable = plan.name === 'Plus'
                  const isSoon = plan.name === 'Pro'
                  const hasUsdPrice = plan.price.startsWith('$')
                  const buttonLabel = isCurrent
                    ? common('status.currentPlan')
                    : isPayable
                      ? 'Plus'
                      : isSoon
                        ? common('status.comingSoon')
                        : t('settings.switchTo', { plan: plan.name })

                  return (
                    <section
                      key={plan.id}
                      className="flex min-h-[500px] flex-col p-8"
                      style={{
                        border: isCurrent ? '2px solid #0a0b0d' : '1px solid rgba(91,97,110,0.2)',
                        borderRadius: '24px',
                        backgroundColor: '#ffffff',
                      }}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <h3 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                            {plan.name}
                          </h3>
                          <p className="mt-3 text-sm font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.5' }}>
                            {plan.tagline}
                          </p>
                        </div>
                        {isCurrent && (
                          <span className="rounded-full px-2.5 py-1 text-xs font-semibold leading-none" style={{ backgroundColor: '#eef0f3', color: '#5b616e' }}>
                            {t('settings.current')}
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
                              USD / mo
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
                        disabled={isCurrent || isSoon}
                        onClick={isPayable ? () => setPlanPickerStep('checkout') : undefined}
                        className="mt-8 w-full px-5 py-3 text-base font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-black disabled:cursor-not-allowed"
                        style={{
                          borderRadius: '56px',
                          border: isCurrent ? '1px solid #0052ff' : isPayable ? '1px solid #0052ff' : '1px solid rgba(91,97,110,0.2)',
                          backgroundColor: isCurrent ? '#0052ff' : isPayable ? '#0052ff' : '#ffffff',
                          color: isCurrent ? '#ffffff' : isPayable ? '#ffffff' : '#0a0b0d',
                        }}
                        onMouseEnter={(event) => {
                          if (event.currentTarget.disabled || !isPayable) return
                          event.currentTarget.style.backgroundColor = '#578bfa'
                          event.currentTarget.style.borderColor = '#578bfa'
                        }}
                        onMouseLeave={(event) => {
                          if (!isPayable) return
                          event.currentTarget.style.backgroundColor = '#0052ff'
                          event.currentTarget.style.borderColor = '#0052ff'
                        }}
                      >
                        {buttonLabel}
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
            </div>
          ) : (
            <div className="mx-auto max-w-5xl">
              <div className="mb-8 flex items-center justify-between gap-6">
                <button
                  type="button"
                  onClick={() => setPlanPickerStep('plans')}
                  className="flex items-center gap-3 text-sm font-semibold transition-colors"
                  style={{ color: '#0a0b0d' }}
                >
                  <ArrowLeftIcon className="h-5 w-5" />
                  {t('settings.backToPlans')}
                </button>
                <button
                  type="button"
                  onClick={closePlanPicker}
                  className="flex h-10 w-10 items-center justify-center rounded-full transition-colors"
                  style={{ color: '#5b616e' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  aria-label={common('actions.close')}
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>

              <div
                className="grid overflow-hidden lg:grid-cols-[0.9fr_1.1fr]"
                style={{ border: '1px solid rgba(91,97,110,0.2)', borderRadius: '24px', backgroundColor: '#ffffff' }}
              >
                <aside className="p-8 lg:p-10" style={{ backgroundColor: '#0a0b0d', color: '#ffffff' }}>
                  <p className="text-sm font-semibold" style={{ color: 'rgba(255,255,255,0.68)', lineHeight: '1.5' }}>
                    OfferMaster Plus
                  </p>
                  <h2 className="mt-3 text-[52px] font-semibold" style={{ lineHeight: '1.00' }}>
                    {t('settings.confirmSubscription')}
                  </h2>
                  <p className="mt-5 text-base" style={{ color: 'rgba(255,255,255,0.72)', lineHeight: '1.5' }}>
                    {t('settings.checkoutDescription')}
                  </p>

                  <div className="my-8 h-px" style={{ backgroundColor: 'rgba(255,255,255,0.18)' }} />

                  <div className="space-y-4 text-base">
                    <div className="flex items-center justify-between gap-6">
                      <span style={{ color: 'rgba(255,255,255,0.72)' }}>{t('settings.subtotal')}</span>
                      <span className="font-semibold">{checkoutAmount}</span>
                    </div>
                    <div className="flex items-center justify-between gap-6 text-lg font-semibold">
                      <span>{t('settings.total')}</span>
                      <span>{checkoutAmount}</span>
                    </div>
                  </div>
                </aside>

                <main className="p-8 lg:p-10">
                  <section>
                    <h3 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                      {t('settings.contact')}
                    </h3>
                    <div className="mt-5 rounded-2xl border px-5 py-4" style={{ borderColor: 'rgba(91,97,110,0.2)', backgroundColor: '#ffffff' }}>
                      <p className="text-sm font-semibold" style={{ color: '#5b616e' }}>{auth('fields.email')}</p>
                      <p className="mt-1 truncate text-base" style={{ color: '#0a0b0d' }}>{user?.email || userSettings.email}</p>
                    </div>
                  </section>

                  <section className="mt-8">
                    <h3 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                      {t('settings.paymentMethod')}
                    </h3>
                    <div
                      className="mt-5 flex items-center justify-between gap-4 rounded-2xl border px-5 py-4"
                      style={{ borderColor: 'rgba(91,97,110,0.2)', backgroundColor: '#ffffff' }}
                    >
                      <div>
                        <p className="text-base font-semibold" style={{ color: '#0a0b0d' }}>PayPal</p>
                        <p className="mt-1 text-sm" style={{ color: '#5b616e' }}>{t('settings.paypalDescription')}</p>
                      </div>
                      <span className="rounded-full px-3 py-1 text-xs font-semibold" style={{ backgroundColor: '#eef0f3', color: '#0a0b0d' }}>
                        PayPal
                      </span>
                    </div>
                  </section>

                  <button
                    type="button"
                    onClick={handleUpgradeWithPayPal}
                    disabled={isBillingLoading}
                    className="mt-8 w-full px-5 py-4 text-base font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-black disabled:cursor-not-allowed disabled:opacity-60"
                    style={{
                      borderRadius: '56px',
                      border: '1px solid #0052ff',
                      backgroundColor: '#0052ff',
                      color: '#ffffff',
                    }}
                    onMouseEnter={(event) => {
                      if (event.currentTarget.disabled) return
                      event.currentTarget.style.backgroundColor = '#578bfa'
                      event.currentTarget.style.borderColor = '#578bfa'
                    }}
                    onMouseLeave={(event) => {
                      event.currentTarget.style.backgroundColor = '#0052ff'
                      event.currentTarget.style.borderColor = '#0052ff'
                    }}
                  >
                    {isBillingLoading ? t('settings.paypalRedirecting') : t('settings.paypalPay')}
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
