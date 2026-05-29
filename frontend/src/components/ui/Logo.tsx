import { Link } from '@/i18n/navigation'

// 品牌 Logo 组件，火箭 + 星星图标，代表"拿到 Offer 起飞"
export default function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const iconSize = size === 'lg' ? 44 : size === 'sm' ? 36 : 40
  const fontSize = size === 'lg' ? '22px' : size === 'sm' ? '18px' : '20px'

  return (
    <Link href="/" className="flex items-center gap-2.5" style={{ textDecoration: 'none' }}>
      <img
        src="/offermaster_logo.png"
        alt="OfferMaster Logo"
        width={iconSize}
        height={iconSize}
        className="object-contain"
        style={{ flexShrink: 0 }}
      />

      <span
        style={{
          fontSize,
          fontWeight: 700,
          letterSpacing: '-0.02em',
          color: '#18181b',
          lineHeight: '1.25',
        }}
      >
        OfferMaster
      </span>
    </Link>
  )
}
