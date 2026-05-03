'use client'
import { useEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'

interface BVPWaveformProps {
  bvpData: number[]
  fps: number
  paused: boolean
}

export default function BVPWaveform({ bvpData, fps, paused }: BVPWaveformProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [dims, setDims] = useState({ w: 800, h: 120 })

  useEffect(() => {
    const obs = new ResizeObserver(entries => {
      for (const e of entries) {
        const { width, height } = e.contentRect
        setDims({ w: Math.floor(width), h: Math.floor(height) })
      }
    })
    if (svgRef.current?.parentElement) obs.observe(svgRef.current.parentElement)
    return () => obs.disconnect()
  }, [])

  const { w, h } = dims
  const pad = { x: 12, y: 12 }
  const innerW = w - pad.x * 2
  const innerH = h - pad.y * 2

  const buildPath = () => {
    if (!bvpData.length) return ''
    const n = bvpData.length
    const mean = bvpData.reduce((s, v) => s + v, 0) / n
    const centered = bvpData.map(v => v - mean)
    const max = Math.max(...centered.map(Math.abs)) || 1

    const points = centered.map((v, i) => {
      const x = pad.x + (i / (n - 1)) * innerW
      const y = pad.y + innerH / 2 - (v / max) * (innerH / 2 - 4)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })

    return `M ${points.join(' L ')}`
  }

  const path = buildPath()
  const gradId = 'bvp-grad'

  // Grid lines
  const gridCols = 8
  const gridRows = 4

  return (
    <div className="relative w-full h-full grid-bg overflow-hidden rounded-sm">
      {/* Fade edges */}
      <div className="absolute inset-y-0 left-0 w-8 z-10"
           style={{ background: 'linear-gradient(90deg,#0f0202,transparent)' }} />
      <div className="absolute inset-y-0 right-0 w-8 z-10"
           style={{ background: 'linear-gradient(-90deg,#0f0202,transparent)' }} />

      <svg ref={svgRef} className="w-full h-full" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%"   stopColor="#cc0000" stopOpacity="0" />
            <stop offset="20%"  stopColor="#ff2020" stopOpacity="0.9" />
            <stop offset="80%"  stopColor="#ff4444" stopOpacity="1" />
            <stop offset="100%" stopColor="#ff6060" stopOpacity="0.7" />
          </linearGradient>
          <filter id="bvp-glow">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
          <clipPath id="bvp-clip">
            <rect x={pad.x} y={pad.y} width={innerW} height={innerH} />
          </clipPath>
        </defs>

        {/* Grid */}
        {Array.from({ length: gridCols + 1 }).map((_, i) => (
          <line key={`vc${i}`}
            x1={pad.x + (i / gridCols) * innerW} y1={pad.y}
            x2={pad.x + (i / gridCols) * innerW} y2={pad.y + innerH}
            stroke="rgba(204,0,0,0.12)" strokeWidth="1" />
        ))}
        {Array.from({ length: gridRows + 1 }).map((_, i) => (
          <line key={`hr${i}`}
            x1={pad.x} y1={pad.y + (i / gridRows) * innerH}
            x2={pad.x + innerW} y2={pad.y + (i / gridRows) * innerH}
            stroke="rgba(204,0,0,0.12)" strokeWidth="1" />
        ))}

        {/* Center baseline */}
        <line x1={pad.x} y1={h / 2} x2={pad.x + innerW} y2={h / 2}
          stroke="rgba(204,0,0,0.2)" strokeWidth="1" strokeDasharray="4 6" />

        {/* Glow copy */}
        {path && (
          <path d={path} fill="none" stroke="rgba(255,32,32,0.25)"
            strokeWidth="6" strokeLinecap="round" filter="url(#bvp-glow)"
            clipPath="url(#bvp-clip)" />
        )}

        {/* Main trace */}
        {path && (
          <motion.path
            key={bvpData.length}
            d={path}
            fill="none"
            stroke={`url(#${gradId})`}
            strokeWidth="2"
            strokeLinecap="round"
            clipPath="url(#bvp-clip)"
            initial={{ pathLength: 0, opacity: 0 }}
            animate={{ pathLength: 1, opacity: 1 }}
            transition={{ duration: 0.6, ease: 'easeOut' }}
          />
        )}

        {!path && (
          <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle"
            fill="rgba(107,0,0,0.8)" fontFamily="Share Tech Mono" fontSize="13">
            AWAITING SIGNAL…
          </text>
        )}

        {paused && (
          <text x={w / 2} y={h / 2} textAnchor="middle" dominantBaseline="middle"
            fill="rgba(255,107,0,0.6)" fontFamily="Orbitron" fontSize="11" fontWeight="700">
            ⏸ PAUSED
          </text>
        )}
      </svg>
    </div>
  )
}
