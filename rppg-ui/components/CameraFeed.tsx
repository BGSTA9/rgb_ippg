'use client'
import { motion, AnimatePresence } from 'framer-motion'

interface CameraFeedProps {
  faceDetected: boolean
  hr: number | null
  fresh: boolean
}

export default function CameraFeed({ faceDetected, hr, fresh }: CameraFeedProps) {
  // Simulated face tracking box position
  const box = { x: 28, y: 22, w: 44, h: 56 }

  function hrToColor(hr: number | null) {
    if (!hr || !fresh) return '#6b0000'
    if (hr >= 50 && hr <= 110) return '#ff2020'
    if (hr >= 40 && hr <= 140) return '#ff6b00'
    return '#8b1c1c'
  }

  const color = hrToColor(hr)

  return (
    <div className="relative w-full h-full rounded-sm overflow-hidden"
      style={{
        background: '#050101',
        border: '1px solid rgba(204,0,0,0.2)',
      }}>

      {/* Simulated camera noise / placeholder */}
      <div className="absolute inset-0 grid-bg opacity-20" />

      {/* Camera frame guides */}
      <svg className="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
        <defs>
          <filter id="cam-glow">
            <feGaussianBlur stdDeviation="0.5" result="blur" />
            <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
          </filter>
        </defs>

        {/* Center crosshair */}
        <line x1="50" y1="46" x2="50" y2="54" stroke="rgba(204,0,0,0.2)" strokeWidth="0.3" />
        <line x1="46" y1="50" x2="54" y2="50" stroke="rgba(204,0,0,0.2)" strokeWidth="0.3" />

        {/* Simulated face oval */}
        <AnimatePresence>
          {faceDetected && (
            <motion.ellipse
              cx="50" cy="42" rx="16" ry="20"
              fill="none"
              stroke={color}
              strokeWidth="0.4"
              strokeDasharray="2 3"
              initial={{ opacity: 0 }}
              animate={{ opacity: 0.4 }}
              exit={{ opacity: 0 }}
              filter="url(#cam-glow)"
            />
          )}
        </AnimatePresence>

        {/* Face bounding box */}
        <AnimatePresence>
          {faceDetected && (
            <motion.g
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}>
              {/* Box */}
              <rect x={box.x} y={box.y} width={box.w} height={box.h}
                fill="none" stroke={color} strokeWidth="0.5"
                filter="url(#cam-glow)" />

              {/* Corner ticks */}
              {[
                [box.x, box.y, 4, 0, 0, 4],
                [box.x + box.w, box.y, -4, 0, 0, 4],
                [box.x, box.y + box.h, 4, 0, 0, -4],
                [box.x + box.w, box.y + box.h, -4, 0, 0, -4],
              ].map(([cx, cy, dx1, dy1, dx2, dy2], i) => (
                <g key={i}>
                  <line x1={cx} y1={cy} x2={cx + dx1} y2={cy + dy1}
                    stroke={color} strokeWidth="1.2" />
                  <line x1={cx} y1={cy} x2={cx + dx2} y2={cy + dy2}
                    stroke={color} strokeWidth="1.2" />
                </g>
              ))}

              {/* HR label above box */}
              <rect x={box.x} y={box.y - 8} width={26} height={7}
                fill={color} rx="0.5" />
              <text x={box.x + 13} y={box.y - 3}
                textAnchor="middle" dominantBaseline="middle"
                fill="black" fontFamily="Orbitron" fontSize="3.5" fontWeight="bold">
                {hr ? `${hr.toFixed(0)} BPM` : 'TRACKING'}
              </text>

              {/* Scan line */}
              <motion.line
                x1={box.x} x2={box.x + box.w}
                stroke={color}
                strokeWidth="0.3"
                strokeOpacity="0.6"
                initial={{ y1: box.y, y2: box.y }}
                animate={{ y1: [box.y, box.y + box.h, box.y], y2: [box.y, box.y + box.h, box.y] }}
                transition={{ repeat: Infinity, duration: 2, ease: 'linear' }}
              />

              {/* Landmark dots */}
              {[[50, 36], [44, 38], [56, 38], [50, 46], [46, 52], [54, 52]].map(([lx, ly], i) => (
                <circle key={i} cx={lx} cy={ly} r="0.8"
                  fill={color} opacity="0.5" />
              ))}
            </motion.g>
          )}
        </AnimatePresence>

        {/* No face */}
        {!faceDetected && (
          <text x="50" y="50" textAnchor="middle" dominantBaseline="middle"
            fill="rgba(107,0,0,0.5)" fontFamily="Share Tech Mono" fontSize="5">
            NO FACE DETECTED
          </text>
        )}

        {/* REC indicator */}
        <circle cx="94" cy="6" r="2" fill="#ff2020" opacity="0.8">
          <animate attributeName="opacity" values="0.8;0.2;0.8" dur="2s" repeatCount="indefinite" />
        </circle>
        <text x="90" y="6" textAnchor="end" dominantBaseline="middle"
          fill="rgba(255,32,32,0.6)" fontFamily="Share Tech Mono" fontSize="3.5">
          REC
        </text>
      </svg>

      {/* Overlay vignette */}
      <div className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at center, transparent 60%, rgba(2,0,0,0.7) 100%)' }} />
    </div>
  )
}
