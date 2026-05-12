import { Link } from '@/i18n/navigation'

// 品牌 Logo 组件，文档 + 对话气泡图标，严格使用 Coinbase Blue #0052ff
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
        {/* 背景 — 严格 Coinbase Blue，不使用 CSS 变量避免色差 */}
        <rect width="40" height="40" rx="10" fill="#0052FF" />

        {/* 文档轮廓 */}
        <rect x="9" y="7" width="15" height="19" rx="2" fill="rgba(255,255,255,0.18)" />
        <rect x="9" y="7" width="15" height="19" rx="2" stroke="rgba(255,255,255,0.7)" strokeWidth="1.4" />

        {/* 文档文字线条 */}
        <rect x="12" y="12" width="9" height="1.4" rx="0.7" fill="white" fillOpacity="0.9" />
        <rect x="12" y="15.5" width="9" height="1.4" rx="0.7" fill="white" fillOpacity="0.9" />
        <rect x="12" y="19" width="6" height="1.4" rx="0.7" fill="white" fillOpacity="0.9" />

        {/* 对话气泡 — 右下角，白色填充 */}
        <rect x="20" y="22" width="13" height="11" rx="3.5" fill="white" />
        {/* 气泡小尾巴 */}
        <path d="M23 33 L21.5 36.5 L27 33Z" fill="white" />

        {/* 气泡内三点 — Coinbase Blue */}
        <circle cx="24" cy="27.5" r="1.2" fill="#0052FF" />
        <circle cx="27" cy="27.5" r="1.2" fill="#0052FF" />
        <circle cx="30" cy="27.5" r="1.2" fill="#0052FF" />
      </svg>

      <span
        style={{
          fontSize,
          fontWeight: 600,
          letterSpacing: '-0.01em',
          color: '#0a0b0d',
          lineHeight: '1.25',
        }}
      >
        Chat Resume
      </span>
    </Link>
  )
}
