'use client'
import { motion } from 'framer-motion'

interface HRHistoryProps {
  history: number[]
  currentHR: number | null
}

function hrColor(hr: number | null): string {
  if (!hr) return '#6b4444'
  if (hr >= 50 && hr <= 110) return '#ff2020'
  if (hr >= 40 && hr <= 140) return '#ff6b00'
  return '#8b0000'
}

export default function HRHistory({ history, currentHR }: HRHistoryProps) {
  const w = 400
  const h = 80
  const pad = { x: 8, y: 8 }
  const innerW = w - pad.x * 2
  const innerH = h - pad.y * 2

  const buildSparkline = () => {
    if (history.length < 2) return { path: '', area: '' }
    const lo = Math.max(40, Math.min(...history) - 5)
    const hi = Math.min(180, Math.max(...history) + 5)
    const span = Math.max(hi - lo, 1)
    const n = history.length

    const pts = history.map((v, i) => {
      const x = pad.x + (i / (n - 1)) * innerW
      const y = pad.y + innerH - ((v - lo) / span) * innerH
      return { x, y }
    })

    const linePath = 'M ' + pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' L ')
    const areaPath = linePath
      + ` L ${pts[pts.length - 1].x.toFixed(1)},${(h - pad.y).toFixed(1)}`
      + ` L ${pts[0].x.toFixed(1)},${(h - pad.y).toFixed(1)} Z`

    return { path: linePath, area: areaPath, lo, hi, pts }
  }

  const { path, area, lo, hi, pts } = buildSparkline() as any
  const color = hrColor(currentHR)

  return (
    <svg className="w-full h-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
      <defs>
        <linearGradient id="hr-area-grad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
        <filter id="hr-glow">
          <feGaussianBlur stdDeviation="2" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map((f, i) => (
        <line key={i}
          x1={pad.x} y1={pad.y + f * innerH}
          x2={pad.x + innerW} y2={pad.y + f * innerH}
          stroke="rgba(204,0,0,0.1)" strokeWidth="1" strokeDasharray="3 5" />
      ))}

      {path ? (
        <>
          {/* Area fill */}
          <path d={area} fill="url(#hr-area-grad)" />

          {/* Glow */}
          <path d={path} fill="none" stroke={color} strokeWidth="4"
            strokeOpacity="0.2" filter="url(#hr-glow)" />

          {/* Main line */}
          <motion.path
            key={history.length}
            d={path}
            fill="none"
            stroke={color}
            strokeWidth="1.5"
            strokeLinecap="round"
            initial={{ pathLength: 0 }}
            animate={{ pathLength: 1 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
          />

          {/* Last dot */}
          {pts?.length > 0 && (
            <motion.circle
              cx={pts[pts.length - 1].x}
              cy={pts[pts.length - 1].y}
              r="3"
              fill={color}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', stiffness: 300 }}
            />
          )}

          {/* Y-axis labels */}
          {lo && <text x={pad.x + innerW + 2} y={pad.y + innerH} fontSize="8"
            fill="rgba(107,68,68,0.8)" fontFamily="Share Tech Mono">{lo?.toFixed(0)}</text>}
          {hi && <text x={pad.x + innerW + 2} y={pad.y + 8} fontSize="8"
            fill="rgba(107,68,68,0.8)" fontFamily="Share Tech Mono">{hi?.toFixed(0)}</text>}
        </>
      ) : (
        <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle"
          fill="rgba(107,0,0,0.6)" fontFamily="Share Tech Mono" fontSize="10">
          NO HISTORY
        </text>
      )}
    </svg>
  )
}
