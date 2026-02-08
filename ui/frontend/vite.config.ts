import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Backend API port for local development proxy
// Configurable via VITE_API_PORT env var, defaults to 8729
// Note: In production (Vercel), set VITE_API_URL instead and the proxy is not used
const apiPort = process.env.VITE_API_PORT || '8729'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    host: true, // Listen on all interfaces for LAN access
    proxy: {
      '/api': {
        target: `http://localhost:${apiPort}`,
        changeOrigin: true,
      },
    },
  },
})
