'use client'
import { motion, AnimatePresence } from 'framer-motion'

interface DiagnosticsProps {
  faceDetected: boolean
  faceAge: number | null
  signalFresh: boolean
  signalAge: number | null
  frameCount: number
  fps: number
  uptime: number
}

function StatRow({ label, value, unit, color }: { label: string; value: string; unit?: string; color?: string }) {
  return (
    <div className="flex items-baseline justify-between py-1"
      style={{ borderBottom: '1px solid rgba(204,0,0,0.08)' }}>
      <span className="font-mono-tech text-xs" style={{ color: '#4d2020', letterSpacing: 1 }}>
        {label}
      </span>
      <span className="font-mono-tech text-sm" style={{ color: color || '#cc4444' }}>
        {value}<span style={{ fontSize: 9, color: '#4d2020', marginLeft: 2 }}>{unit}</span>
      </span>
    </div>
  )
}

export default function Diagnostics({
  faceDetected, faceAge, signalFresh, signalAge, frameCount, fps, uptime
}: DiagnosticsProps) {
  const faceOk = faceDetected || (faceAge !== null && faceAge < 1.5)
  const uptimeFmt = `${Math.floor(uptime / 60).toString().padStart(2, '0')}:${Math.floor(uptime % 60).toString().padStart(2, '0')}`

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Face status */}
      <div className="panel-base corners p-3 rounded-sm">
        <div className="font-mono-tech text-xs mb-2" style={{ color: '#4d2020', letterSpacing: 2 }}>
          FACE TRACK
        </div>
        <div className="flex items-center gap-2">
          <motion.div
            animate={{ opacity: faceOk ? [1, 0.3, 1] : 1 }}
            transition={{ repeat: faceOk ? Infinity : 0, duration: 1.2 }}
            className="rounded-full flex-shrink-0"
            style={{
              width: 8, height: 8,
              background: faceOk ? '#ff2020' : '#3d1515',
              boxShadow: faceOk ? '0 0 8px #ff2020, 0 0 20px rgba(255,32,32,0.4)' : 'none',
            }} />
          <span className="font-orbitron font-bold text-sm"
            style={{ color: faceOk ? '#ff2020' : '#6b1515', letterSpacing: 1 }}>
            {faceOk ? 'LOCKED' : 'SEARCHING'}
          </span>
        </div>
        {!faceOk && (
          <motion.p className="font-raj text-xs mt-1"
            style={{ color: '#4d1515' }}
            initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            Center face in frame
          </motion.p>
        )}
        {faceAge !== null && faceOk && (
          <p className="font-mono-tech mt-1" style={{ fontSize: 9, color: '#4d2020' }}>
            last seen {faceAge.toFixed(1)}s ago
          </p>
        )}
      </div>

      {/* Signal status */}
      <div className="panel-base corners p-3 rounded-sm">
        <div className="font-mono-tech text-xs mb-2" style={{ color: '#4d2020', letterSpacing: 2 }}>
          SIGNAL
        </div>
        <div className="flex items-center gap-2">
          <div className="rounded-full flex-shrink-0"
            style={{
              width: 8, height: 8,
              background: signalFresh ? '#ff2020' : signalAge === null ? '#ff6b00' : '#3d1515',
              boxShadow: signalFresh ? '0 0 8px #ff2020' : 'none',
            }} />
          <span className="font-orbitron font-bold text-sm"
            style={{
              color: signalFresh ? '#ff2020' : signalAge === null ? '#ff6b00' : '#4d1515',
              letterSpacing: 1,
            }}>
            {signalFresh ? 'LIVE' : signalAge === null ? 'INIT' : 'STALE'}
          </span>
        </div>
        {signalAge !== null && !signalFresh && (
          <p className="font-mono-tech mt-1" style={{ fontSize: 9, color: '#4d2020' }}>
            {signalAge.toFixed(0)}s since update
          </p>
        )}
      </div>

      {/* Stats */}
      <div className="panel-base p-3 rounded-sm flex-1">
        <div className="font-mono-tech text-xs mb-2" style={{ color: '#4d2020', letterSpacing: 2 }}>
          SESSION
        </div>
        <StatRow label="UPTIME"  value={uptimeFmt} />
        <StatRow label="FRAMES"  value={frameCount.toString()} />
        <StatRow label="FPS"     value={fps.toFixed(1)} unit="fps" color="#cc6666" />
      </div>
    </div>
  )
}
