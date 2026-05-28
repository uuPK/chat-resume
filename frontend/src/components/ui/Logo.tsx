import { Link } from '@/i18n/navigation'

// 品牌 Logo 组件，火箭 + 星星图标，代表"拿到 Offer 起飞"
export default function Logo({ size = 'md' }: { size?: 'sm' | 'md' | 'lg' }) {
  const iconSize = size === 'lg' ? 44 : size === 'sm' ? 36 : 40
  const fontSize = size === 'lg' ? '22px' : size === 'sm' ? '18px' : '20px'

  return (
    <Link href="/" className="flex items-center gap-2.5" style={{ textDecoration: 'none' }}>
      <svg
        width={iconSize}
        height={iconSize}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ flexShrink: 0 }}
      >
        {/* 圆角背景 — 紫罗兰渐变 */}
        <defs>
          <linearGradient id="logoBg" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#7C3AED" />
            <stop offset="100%" stopColor="#A855F7" />
          </linearGradient>
        </defs>
        <rect width="40" height="40" rx="12" fill="url(#logoBg)" />

        {/* 火箭主体 */}
        <path
          d="M20 8C20 8 14 14 14 22C14 26 16.5 29 20 30C23.5 29 26 26 26 22C26 14 20 8 20 8Z"
          fill="white"
          fillOpacity="0.95"
        />

        {/* 火箭窗口 */}
        <circle cx="20" cy="19" r="2.5" fill="#7C3AED" />

        {/* 左尾翼 */}
        <path d="M14 24L10 27L14 28Z" fill="white" fillOpacity="0.7" />

        {/* 右尾翼 */}
        <path d="M26 24L30 27L26 28Z" fill="white" fillOpacity="0.7" />

        {/* 尾焰 */}
        <path d="M18 30L20 35L22 30" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" opacity="0.8" />

        {/* 小星星 */}
        <circle cx="10" cy="12" r="1.2" fill="white" fillOpacity="0.6" />
        <circle cx="31" cy="15" r="0.9" fill="white" fillOpacity="0.5" />
      </svg>

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
