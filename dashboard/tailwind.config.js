/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: {
          main: '#08080e',
          sidebar: '#0c0c16',
          header: '#0a0a14',
          card: '#0f0f1a',
          hover: '#131320',
        },
        border: {
          DEFAULT: '#1e1e30',
          hover: '#2a2a40',
        },
        text: {
          primary: '#ffffff',
          secondary: '#9090a8',
          muted: '#6b7280',
          subtle: '#3a3a52',
          faint: '#2e2e45',
        },
        f1: {
          red: '#e10600',
          green: '#22c55e',
          amber: '#eab308',
          red2: '#ef4444',
          gold: '#FFD700',
          orange: '#f97316',
        },
      },
      fontFamily: {
        condensed: ["'Barlow Condensed'", 'sans-serif'],
        body: ["'Barlow'", 'sans-serif'],
        mono: ["'JetBrains Mono'", 'monospace'],
      },
    },
  },
  plugins: [],
};
