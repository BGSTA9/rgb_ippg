'use client'
import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState } from 'react'

interface HeartRateDisplayProps {
  hr: number | null
  hrv: number | null
  snr: number | null
  fresh: boolean
  staleSeconds: number | null
}

function hrToColor(hr: number | null) {
  if (!hr) return { text: '#6b4444', glow: 'transparent' }
  if (hr >= 50 && hr <= 110) return { text: '#ff2020', glow: 'rgba(255,32,32,0.6)' }
  if (hr >= 40 && hr <= 140) return { text: '#ff6b00', glow: 'rgba(255,107,0,0.5)' }
  return { text: '#8b1c1c', glow: 'rgba(139,28,28,0.4)' }
}

export default function HeartRateDisplay({ hr, hrv, snr, fresh, staleSeconds }: HeartRateDisplayProps) {
  const [prevHr, setPrevHr] = useState<number | null>(null)
  const [beat, setBeat] = useState(false)
  const color = hrToColor(hr)

  useEffect(() => {
    if (hr !== prevHr && hr) {
      setBeat(true)
      const t = setTimeout(() => setBeat(false), 200)
      setPrevHr(hr)
      return () => clearTimeout(t)
    }
  }, [hr])

  const bpm = hr ? hr.toFixed(1) : '--'
  const [intPart, decPart] = bpm.includes('.') ? bpm.split('.') : [bpm, null]

  return (
    <div className="flex flex-col items-center justify-center h-full select-none">

      {/* Pulse rings */}
      <div className="relative flex items-center justify-center mb-2">
        {fresh && hr && (
          <>
            <div className="absolute rounded-full pulse-ring"
              style={{
                width: 160, height: 160,
                border: `1px solid ${color.text}`,
                opacity: 0.4,
              }} />
            <div className="absolute rounded-full pulse-ring"
              style={{
                width: 200, height: 200,
                border: `1px solid ${color.text}`,
                opacity: 0.2,
                animationDelay: '0.4s',
              }} />
          </>
        )}

        {/* Core circle */}
        <div className="relative flex items-center justify-center rounded-full"
          style={{
            width: 140, height: 140,
            border: `1px solid ${color.text}`,
            boxShadow: `0 0 30px ${color.glow}, 0 0 80px ${color.glow.replace('0.6', '0.15')}, inset 0 0 30px rgba(0,0,0,0.5)`,
            background: 'radial-gradient(circle, rgba(20,0,0,0.9) 0%, rgba(8,0,0,1) 70%)',
            transition: 'border-color 0.4s, box-shadow 0.4s',
          }}>

          {/* Heart icon */}
          <div className="absolute top-3 flex items-center gap-1">
            <span style={{
              color: color.text,
              fontSize: 10,
              fontFamily: 'Orbitron',
              letterSpacing: 3,
              textShadow: `0 0 8px ${color.text}`,
              opacity: 0.7,
            }}>♥</span>
            <span style={{
              color: color.text, fontSize: 8, fontFamily: 'Orbitron',
              letterSpacing: 2, opacity: 0.5,
            }}>RATE</span>
          </div>

          {/* Number */}
          <AnimatePresence mode="wait">
            <motion.div key={intPart}
              className="flex items-baseline"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.15 }}
              style={{ transform: `scale(${beat ? 1.06 : 1})`, transition: 'transform 0.15s' }}>
              <span className="font-orbitron font-black"
                style={{
                  fontSize: hr ? 52 : 40,
                  color: color.text,
                  textShadow: `0 0 16px ${color.glow}, 0 0 40px ${color.glow}`,
                  lineHeight: 1,
                  letterSpacing: hr ? -2 : 0,
                }}>
                {intPart}
              </span>
              {decPart && (
                <span className="font-orbitron font-black"
                  style={{ fontSize: 22, color: color.text, opacity: 0.5, lineHeight: 1, marginLeft: 1 }}>
                  .{decPart}
                </span>
              )}
            </motion.div>
          </AnimatePresence>

          <span className="absolute bottom-3 font-orbitron"
            style={{ fontSize: 9, color: color.text, opacity: 0.5, letterSpacing: 3 }}>
            BPM
          </span>
        </div>
      </div>

      {/* Sub metrics */}
      <div className="flex gap-6 mt-3">
        <div className="text-center">
          <div className="font-mono-tech text-xs" style={{ color: '#6b4444', letterSpacing: 1 }}>HRV</div>
          <div className="font-orbitron font-bold text-base"
            style={{ color: hrv ? '#cc6666' : '#3d1515', textShadow: hrv ? '0 0 6px rgba(204,102,102,0.4)' : 'none' }}>
            {hrv ? `${hrv.toFixed(0)}` : '--'}
          </div>
          <div className="font-mono-tech" style={{ fontSize: 9, color: '#4d2020' }}>ms</div>
        </div>

        <div className="text-center">
          <div className="font-mono-tech text-xs" style={{ color: '#6b4444', letterSpacing: 1 }}>SNR</div>
          <div className="font-orbitron font-bold text-base"
            style={{ color: snr ? (snr > 3 ? '#cc6666' : '#8b3333') : '#3d1515' }}>
            {snr !== null ? `${snr.toFixed(1)}` : '--'}
          </div>
          <div className="font-mono-tech" style={{ fontSize: 9, color: '#4d2020' }}>dB</div>
        </div>
      </div>

      {/* Status badge */}
      <motion.div className="mt-3 flex items-center gap-2 px-3 py-1 rounded-sm"
        style={{ border: '1px solid rgba(204,0,0,0.2)', background: 'rgba(15,2,2,0.8)' }}>
        <div className={`rounded-full ${fresh ? 'status-live' : ''}`}
          style={{
            width: 6, height: 6,
            background: fresh ? '#ff2020' : '#3d1515',
            transition: 'background 0.3s',
          }} />
        <span className="font-mono-tech text-xs"
          style={{ color: fresh ? '#cc4444' : '#3d1515', letterSpacing: 2 }}>
          {fresh ? 'SIGNAL LOCK' : staleSeconds ? `STALE ${staleSeconds.toFixed(0)}s` : 'WARMING UP'}
        </span>
      </motion.div>
    </div>
  )
}
