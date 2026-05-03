'use client'
import { motion } from 'framer-motion'

interface ControlBarProps {
  paused: boolean
  showBVP: boolean
  showHistory: boolean
  showFaceBox: boolean
  onPause: () => void
  onReset: () => void
  onSave: () => void
  onToggleBVP: () => void
  onToggleHistory: () => void
  onToggleFaceBox: () => void
  onCycleModel: () => void
  modelName: string
  models: string[]
}

interface BtnProps {
  label: string
  icon: string
  active?: boolean
  variant?: 'primary' | 'ghost' | 'danger' | 'amber'
  onClick: () => void
  kbd?: string
}

function Btn({ label, icon, active, variant = 'ghost', onClick, kbd }: BtnProps) {
  const variants = {
    primary: {
      bg: 'rgba(204,0,0,0.15)',
      border: 'rgba(204,0,0,0.5)',
      text: '#ff4444',
      hover: 'rgba(204,0,0,0.25)',
    },
    ghost: {
      bg: active ? 'rgba(204,0,0,0.12)' : 'transparent',
      border: active ? 'rgba(204,0,0,0.4)' : 'rgba(204,0,0,0.15)',
      text: active ? '#cc4444' : '#6b4444',
      hover: 'rgba(204,0,0,0.08)',
    },
    danger: {
      bg: 'transparent',
      border: 'rgba(139,0,0,0.3)',
      text: '#8b1c1c',
      hover: 'rgba(139,0,0,0.1)',
    },
    amber: {
      bg: active ? 'rgba(255,107,0,0.12)' : 'transparent',
      border: active ? 'rgba(255,107,0,0.4)' : 'rgba(204,0,0,0.15)',
      text: active ? '#ff6b00' : '#6b4444',
      hover: 'rgba(255,107,0,0.08)',
    },
  }
  const v = variants[variant]

  return (
    <motion.button
      onClick={onClick}
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.96 }}
      className="relative flex flex-col items-center gap-1 px-3 py-2 rounded-sm transition-colors"
      style={{
        background: v.bg,
        border: `1px solid ${v.border}`,
        color: v.text,
        minWidth: 56,
      }}>
      <span style={{ fontSize: 16 }}>{icon}</span>
      <span className="font-raj font-semibold" style={{ fontSize: 10, letterSpacing: 1 }}>{label}</span>
      {kbd && (
        <span className="font-mono-tech"
          style={{ fontSize: 8, color: 'rgba(107,68,68,0.6)', letterSpacing: 1 }}>
          [{kbd}]
        </span>
      )}
    </motion.button>
  )
}

export default function ControlBar({
  paused, showBVP, showHistory, showFaceBox,
  onPause, onReset, onSave, onToggleBVP, onToggleHistory, onToggleFaceBox, onCycleModel,
  modelName, models,
}: ControlBarProps) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <Btn label={paused ? 'RESUME' : 'PAUSE'} icon={paused ? '▶' : '⏸'}
        variant={paused ? 'amber' : 'ghost'} active={paused}
        onClick={onPause} kbd="P" />
      <Btn label="RESET" icon="↺" variant="danger" onClick={onReset} kbd="R" />
      <Btn label="SAVE" icon="⬇" variant="primary" onClick={onSave} kbd="S" />

      <div className="w-px self-stretch mx-1" style={{ background: 'rgba(204,0,0,0.15)' }} />

      <Btn label="BVP" icon="〜" active={showBVP} onClick={onToggleBVP} kbd="G" />
      <Btn label="HISTORY" icon="▦" active={showHistory} onClick={onToggleHistory} kbd="H" />
      <Btn label="FACE" icon="◎" active={showFaceBox} onClick={onToggleFaceBox} kbd="F" />

      <div className="w-px self-stretch mx-1" style={{ background: 'rgba(204,0,0,0.15)' }} />

      <motion.button
        onClick={onCycleModel}
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className="flex items-center gap-2 px-3 py-2 rounded-sm"
        style={{
          border: '1px solid rgba(204,0,0,0.25)',
          background: 'rgba(10,1,1,0.8)',
        }}>
        <span style={{ fontSize: 11, color: '#6b4444', fontFamily: 'Share Tech Mono', letterSpacing: 1 }}>
          MODEL
        </span>
        <span className="font-orbitron font-bold"
          style={{ fontSize: 10, color: '#cc4444', letterSpacing: 1 }}>
          {modelName}
        </span>
        <span style={{ fontSize: 9, color: '#4d2020' }}>▲▼</span>
      </motion.button>
    </div>
  )
}
