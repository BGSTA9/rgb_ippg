import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        void:    '#020000',
        dark:    '#0a0101',
        panel:   '#0f0202',
        card:    '#150303',
        'red-core': '#cc0000',
        'red-hot':  '#ff2020',
        'red-glow': '#ff4444',
        'red-dim':  '#6b0000',
        'red-deep': '#2d0000',
        'red-trace':'#ff6060',
        amber:   '#ff6b00',
        'text-bright': '#ffd4d4',
        'text-mid':    '#cc9999',
        'text-dim':    '#6b4444',
      },
      fontFamily: {
        orbitron: ['Orbitron', 'monospace'],
        mono:     ['Share Tech Mono', 'monospace'],
        raj:      ['Rajdhani', 'sans-serif'],
      },
      animation: {
        'pulse-slow': 'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
        'spin-slow':  'spin 8s linear infinite',
      },
    },
  },
  plugins: [],
}
export default config
