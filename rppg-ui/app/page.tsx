'use client'
import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import dynamic from 'next/dynamic'

const BVPWaveform     = dynamic(() => import('@/components/BVPWaveform'),     { ssr: false })
const HRHistory       = dynamic(() => import('@/components/HRHistory'),       { ssr: false })
const HeartRateDisplay= dynamic(() => import('@/components/HeartRateDisplay'),{ ssr: false })
const ControlBar      = dynamic(() => import('@/components/ControlBar'),      { ssr: false })
const Diagnostics     = dynamic(() => import('@/components/Diagnostics'),     { ssr: false })
const CameraFeed      = dynamic(() => import('@/components/CameraFeed'),      { ssr: false })

const MODEL_ZOO = [
  'ME-flow','ME-chunk','RhythmMamba','PhysMamba',
  'FacePhys','EfficientPhys','PhysFormer','TSCAN','PhysNet',
]
const BVP_SAMPLES = 240
const HR_HIST_LEN = 120

function generateBVP(t: number, hr: number) {
  const f = hr / 60
  return (
    Math.sin(2 * Math.PI * f * t) +
    0.3 * Math.sin(2 * Math.PI * 2 * f * t - 0.5) +
    0.1 * Math.sin(2 * Math.PI * 3 * f * t + 0.3) +
    (Math.random() - 0.5) * 0.08
  )
}

function Toast({ msg, onDone }: { msg: string; onDone: () => void }) {
  useEffect(() => { const t = setTimeout(onDone, 2500); return () => clearTimeout(t) }, [onDone])
  return (
    <motion.div
      className="fixed bottom-6 left-1/2 -translate-x-1/2 px-5 py-2 rounded-sm font-mono-tech text-sm z-50"
      style={{ border:'1px solid rgba(204,0,0,0.5)', background:'rgba(12,1,1,0.97)', color:'#cc4444', letterSpacing:1 }}
      initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }} exit={{ opacity:0, y:16 }}>
      ▶ {msg}
    </motion.div>
  )
}

export default function Home() {
  const [modelIdx, setModelIdx]     = useState(0)
  const [paused, setPaused]         = useState(false)
  const [showBVP, setShowBVP]       = useState(true)
  const [showHist, setShowHist]     = useState(true)
  const [showLog, setShowLog]       = useState(false)

  const [bvpBuf, setBvpBuf]         = useState<number[]>([])
  const [hrHist, setHrHist]         = useState<number[]>([])
  const [curHR, setCurHR]           = useState<number|null>(null)
  const [curHRV, setCurHRV]         = useState<number|null>(null)
  const [curSNR, setCurSNR]         = useState<number|null>(null)
  const [frameCount, setFrameCount] = useState(0)
  const [fps, setFps]               = useState(0)
  const [uptime, setUptime]         = useState(0)
  const [faceOk, setFaceOk]         = useState(true)
  const [lastHRTime, setLastHRTime] = useState<number|null>(null)
  const [toast, setToast]           = useState<string|null>(null)
  const [logLines, setLogLines]     = useState<string[]>([])

  const [startTime]  = useState(Date.now())
  const tRef         = useRef(0)
  const baseHR       = useRef(72 + Math.random() * 8)
  const fpsCount     = useRef({ n: 0, t: Date.now() })
  const hrTimer      = useRef(0)

  const log = useCallback((msg: string) => {
    const ts = new Date().toLocaleTimeString()
    setLogLines(l => [`[${ts}] ${msg}`, ...l].slice(0, 80))
  }, [])

  useEffect(() => {
    if (paused) return
    const id = setInterval(() => {
      const now = Date.now()
      tRef.current += 0.033
      baseHR.current = Math.max(55, Math.min(95, baseHR.current + (Math.random()-0.5)*0.05))
      if (Math.random() < 0.003) setFaceOk(f => !f)
      const sample = generateBVP(tRef.current, baseHR.current)
      setBvpBuf(b => { const n = [...b, sample]; return n.length > BVP_SAMPLES ? n.slice(-BVP_SAMPLES) : n })
      fpsCount.current.n++
      const fe = now - fpsCount.current.t
      if (fe > 600) { setFps(fpsCount.current.n / fe * 1000); fpsCount.current.n = 0; fpsCount.current.t = now }
      setFrameCount(f => f + 1)
      setUptime((now - startTime) / 1000)
      hrTimer.current += 33
      if (hrTimer.current >= 1000) {
        hrTimer.current = 0
        const hr = +(baseHR.current + (Math.random()-0.5)*1.5).toFixed(1)
        setCurHR(hr)
        setHrHist(h => [...h, hr].slice(-HR_HIST_LEN))
        setCurHRV(+(12 + Math.random()*18).toFixed(0))
        setCurSNR(+(4 + Math.random()*6).toFixed(1))
        setLastHRTime(now)
      }
    }, 33)
    return () => clearInterval(id)
  }, [paused, startTime])

  const handleReset = useCallback(() => {
    setBvpBuf([]); setHrHist([]); setCurHR(null); setCurHRV(null); setCurSNR(null)
    setLastHRTime(null); setFrameCount(0); tRef.current = 0
    baseHR.current = 72 + Math.random()*8
    log('Buffer reset'); setToast('Session reset')
  }, [log])

  const handleSave = useCallback(() => {
    setBvpBuf(buf => {
      const csv = ['t,bvp', ...buf.map((v,i) => `${(i/30).toFixed(4)},${v.toFixed(6)}`)].join('\n')
      const a = document.createElement('a')
      a.href = URL.createObjectURL(new Blob([csv], { type:'text/csv' }))
      a.download = `rppg-${Date.now()}.csv`; a.click()
      return buf
    })
    log('Session saved'); setToast('Session saved ✓')
  }, [log])

  const handlePause = useCallback(() => {
    setPaused(p => { log(p ? 'Resumed' : 'Paused'); return !p })
  }, [log])

  const handleCycleModel = useCallback(() => {
    setModelIdx(i => { const n = (i+1)%MODEL_ZOO.length; setToast(`Model: ${MODEL_ZOO[n]}`); log(`Model → ${MODEL_ZOO[n]}`); return n })
  }, [log])

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key==='p') handlePause()
      if (e.key==='r') handleReset()
      if (e.key==='s') handleSave()
      if (e.key==='g') setShowBVP(b=>!b)
      if (e.key==='h') setShowHist(b=>!b)
      if (e.key==='m') handleCycleModel()
      if (e.key==='l') setShowLog(b=>!b)
    }
    window.addEventListener('keydown', h)
    return () => window.removeEventListener('keydown', h)
  }, [handlePause, handleReset, handleSave, handleCycleModel])

  const hrAge   = lastHRTime ? (Date.now()-lastHRTime)/1000 : null
  const hrFresh = hrAge !== null && hrAge < 3
  const modelName = MODEL_ZOO[modelIdx]

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden" style={{ background:'var(--bg-void)' }}>

      {/* Header */}
      <motion.header className="flex items-center justify-between px-5 py-2 flex-shrink-0 z-10"
        style={{ borderBottom:'1px solid rgba(204,0,0,0.2)', background:'rgba(6,0,0,0.95)' }}
        initial={{ y:-30, opacity:0 }} animate={{ y:0, opacity:1 }} transition={{ duration:0.4 }}>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="relative w-8 h-8 flex items-center justify-center">
              <span style={{ fontSize:22, color:'#ff2020', filter:'drop-shadow(0 0 8px #ff2020)' }}>♥</span>
              {hrFresh && <span className="absolute animate-ping opacity-20" style={{ fontSize:22, color:'#ff2020' }}>♥</span>}
            </div>
            <div>
              <div className="font-orbitron font-black text-base flicker"
                style={{ color:'#ff2020', letterSpacing:4, textShadow:'0 0 12px rgba(255,32,32,0.7)' }}>rPPG</div>
              <div className="font-mono-tech" style={{ fontSize:9, color:'#4d2020', letterSpacing:3 }}>ULTIMATE · BIOMETRIC MONITOR</div>
            </div>
          </div>
          <div className="w-px h-7" style={{ background:'rgba(204,0,0,0.2)' }} />
          <div className="flex items-center gap-2">
            <span className="font-mono-tech" style={{ fontSize:10, color:'#3d1515', letterSpacing:2 }}>MODEL</span>
            <motion.span key={modelName} className="font-orbitron font-bold text-xs px-2 py-0.5 rounded-sm"
              style={{ color:'#cc4444', border:'1px solid rgba(204,0,0,0.3)', background:'rgba(18,0,0,0.9)', letterSpacing:1 }}
              initial={{ opacity:0, scale:0.9 }} animate={{ opacity:1, scale:1 }}>
              {modelName}
            </motion.span>
          </div>
        </div>
        <div className="flex items-center gap-5">
          <div className="text-right">
            <div className="font-mono-tech" style={{ fontSize:9, color:'#3d1515', letterSpacing:2 }}>FPS</div>
            <div className="font-orbitron font-bold text-sm" style={{ color:'#992222' }}>{fps.toFixed(1)}</div>
          </div>
          <div className="flex items-center gap-2 px-3 py-1 rounded-sm"
            style={{ border:'1px solid rgba(204,0,0,0.18)', background:'rgba(12,0,0,0.8)' }}>
            {paused
              ? <><div className="w-2 h-2 rounded-sm" style={{ background:'#ff6b00' }} /><span className="font-orbitron font-bold text-xs" style={{ color:'#ff6b00', letterSpacing:2 }}>PAUSED</span></>
              : <><div className="w-2 h-2 rounded-full status-live" /><span className="font-orbitron font-bold text-xs" style={{ color:'#ff2020', letterSpacing:2 }}>LIVE</span></>
            }
          </div>
          <button onClick={() => setShowLog(b=>!b)}
            className="font-mono-tech text-xs px-2 py-1 rounded-sm"
            style={{ color: showLog ? '#cc4444':'#3d1515', border:`1px solid ${showLog?'rgba(204,0,0,0.3)':'rgba(204,0,0,0.1)'}` }}>
            [L] LOG
          </button>
        </div>
      </motion.header>

      {/* Body */}
      <div className="flex flex-1 overflow-hidden">

        {/* Left sidebar */}
        <motion.aside className="flex flex-col gap-2 p-2 flex-shrink-0"
          style={{ width:220, borderRight:'1px solid rgba(204,0,0,0.12)' }}
          initial={{ x:-30, opacity:0 }} animate={{ x:0, opacity:1 }} transition={{ delay:0.1, duration:0.4 }}>

          {/* Camera */}
          <div className="panel-base corners rounded-sm flex-shrink-0 relative" style={{ height:155 }}>
            <div className="absolute top-2 left-3 z-10 font-mono-tech" style={{ fontSize:9, color:'#3d1515', letterSpacing:2 }}>FEED·CAM0</div>
            <div className="absolute inset-0 pt-6 p-1.5">
              <CameraFeed faceDetected={faceOk} hr={curHR} fresh={hrFresh} />
            </div>
          </div>

          <div className="flex-1 overflow-hidden">
            <Diagnostics
              faceDetected={faceOk} faceAge={0} signalFresh={hrFresh}
              signalAge={hrAge} frameCount={frameCount} fps={fps} uptime={uptime} />
          </div>
        </motion.aside>

        {/* Center */}
        <main className="flex flex-col flex-1 min-w-0 overflow-hidden">

          {/* Metrics row */}
          <motion.div className="flex flex-shrink-0"
            style={{ height:240, borderBottom:'1px solid rgba(204,0,0,0.12)' }}
            initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ delay:0.2, duration:0.4 }}>

            {/* Big HR circle */}
            <div className="flex-shrink-0 flex items-center justify-center"
              style={{ width:260, borderRight:'1px solid rgba(204,0,0,0.12)', background:'rgba(8,0,0,0.4)' }}>
              <HeartRateDisplay hr={curHR} hrv={curHRV} snr={curSNR} fresh={hrFresh} staleSeconds={hrAge} />
            </div>

            {/* Stat cards */}
            <div className="flex-1 grid grid-cols-3">
              {[
                { label:'HEART RATE', value: curHR?.toFixed(1)??'--', unit:'BPM', sz:40 },
                { label:'HRV RMSSD',  value: curHRV?.toFixed(0)??'--', unit:'ms',  sz:32 },
                { label:'SIGNAL SNR', value: curSNR?.toFixed(1)??'--', unit:'dB',  sz:32 },
              ].map((m,i) => (
                <motion.div key={m.label}
                  className="flex flex-col items-center justify-center panel-base"
                  style={{ border:'none', borderRight: i<2 ? '1px solid rgba(204,0,0,0.1)' : 'none' }}
                  initial={{ opacity:0, y:12 }} animate={{ opacity:1, y:0 }} transition={{ delay:0.3+i*0.08 }}>
                  <div className="font-mono-tech mb-2" style={{ fontSize:9, color:'#3d1515', letterSpacing:3 }}>{m.label}</div>
                  <AnimatePresence mode="wait">
                    <motion.div key={m.value} className="font-orbitron font-black"
                      style={{
                        fontSize: m.sz,
                        color: hrFresh && m.value!=='--' ? '#cc3333' : '#2d1010',
                        textShadow: hrFresh && m.value!=='--' ? '0 0 16px rgba(204,51,51,0.5)' : 'none',
                        lineHeight:1, letterSpacing:-1,
                      }}
                      initial={{ opacity:0, scale:0.92 }} animate={{ opacity:1, scale:1 }} exit={{ opacity:0 }}>
                      {m.value}
                    </motion.div>
                  </AnimatePresence>
                  <div className="font-mono-tech mt-1" style={{ fontSize:9, color:'#3d1515', letterSpacing:2 }}>{m.unit}</div>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* BVP Waveform */}
          <AnimatePresence>
            {showBVP && (
              <motion.div className="relative flex-shrink-0"
                style={{ height: showHist ? '35%' : '55%', borderBottom:'1px solid rgba(204,0,0,0.12)' }}
                initial={{ height:0, opacity:0 }} animate={{ height: showHist?'35%':'55%', opacity:1 }}
                exit={{ height:0, opacity:0 }} transition={{ duration:0.3 }}>
                <div className="absolute top-2 left-4 z-10 flex items-center gap-3">
                  <span className="font-mono-tech" style={{ fontSize:9, color:'#3d1515', letterSpacing:3 }}>BVP · BLOOD VOLUME PULSE</span>
                  <span className="font-mono-tech" style={{ fontSize:9, color:'#2d1010' }}>{Math.round(bvpBuf.length/30)}s · {bvpBuf.length} smpl</span>
                </div>
                <div className="absolute inset-0 pt-6 px-1 pb-1">
                  <BVPWaveform bvpData={bvpBuf} fps={30} paused={paused} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* HR History */}
          <AnimatePresence>
            {showHist && (
              <motion.div className="flex-1 min-h-0 relative"
                style={{ background:'rgba(8,0,0,0.3)', borderTop:'1px solid rgba(204,0,0,0.08)' }}
                initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}>
                <div className="absolute top-2 left-4 z-10 flex items-center gap-3">
                  <span className="font-mono-tech" style={{ fontSize:9, color:'#3d1515', letterSpacing:3 }}>HR HISTORY</span>
                  <span className="font-mono-tech" style={{ fontSize:9, color:'#2d1010' }}>{hrHist.length} pts</span>
                </div>
                <div className="absolute inset-0 pt-6 px-2 pb-1">
                  <HRHistory history={hrHist} currentHR={curHR} />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </main>

        {/* Log panel */}
        <AnimatePresence>
          {showLog && (
            <motion.aside className="flex flex-col flex-shrink-0 overflow-hidden"
              style={{ width:220, borderLeft:'1px solid rgba(204,0,0,0.12)' }}
              initial={{ width:0, opacity:0 }} animate={{ width:220, opacity:1 }}
              exit={{ width:0, opacity:0 }} transition={{ duration:0.22 }}>
              <div className="flex items-center justify-between px-3 py-2 flex-shrink-0"
                style={{ borderBottom:'1px solid rgba(204,0,0,0.12)' }}>
                <span className="font-mono-tech" style={{ fontSize:9, color:'#3d1515', letterSpacing:3 }}>SYS LOG</span>
                <button onClick={() => setLogLines([])} className="font-mono-tech"
                  style={{ fontSize:9, color:'#3d1515', letterSpacing:1 }}>CLR</button>
              </div>
              <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-0.5">
                {logLines.map((l,i) => (
                  <div key={i} className="font-mono-tech" style={{ fontSize:8, color:'#3d2020', lineHeight:1.7 }}>{l}</div>
                ))}
                {!logLines.length && <div className="font-mono-tech" style={{ fontSize:9, color:'#2d1010', marginTop:8 }}>No events…</div>}
              </div>
            </motion.aside>
          )}
        </AnimatePresence>
      </div>

      {/* Footer */}
      <motion.footer className="flex items-center justify-between px-5 py-2 flex-shrink-0"
        style={{ borderTop:'1px solid rgba(204,0,0,0.18)', background:'rgba(6,0,0,0.95)' }}
        initial={{ y:20, opacity:0 }} animate={{ y:0, opacity:1 }} transition={{ delay:0.15, duration:0.4 }}>
        <ControlBar
          paused={paused} showBVP={showBVP} showHistory={showHist} showFaceBox={true}
          onPause={handlePause} onReset={handleReset} onSave={handleSave}
          onToggleBVP={() => setShowBVP(b=>!b)} onToggleHistory={() => setShowHist(b=>!b)}
          onToggleFaceBox={() => {}} onCycleModel={handleCycleModel}
          modelName={modelName} models={MODEL_ZOO} />
        <div className="font-mono-tech text-right" style={{ fontSize:9, color:'#3d1515', letterSpacing:2 }}>
          UPTIME {Math.floor(uptime/60).toString().padStart(2,'0')}:{Math.floor(uptime%60).toString().padStart(2,'0')}
          <br /><span style={{ color:'#2d1010' }}>P PAUSE · R RESET · S SAVE · M MODEL · L LOG</span>
        </div>
      </motion.footer>

      {/* Toast */}
      <AnimatePresence>
        {toast && <Toast msg={toast} onDone={() => setToast(null)} />}
      </AnimatePresence>
    </div>
  )
}
