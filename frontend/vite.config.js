import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_URL || 'http://localhost:9000',
        changeOrigin: true,
        // Required so the console log WebSocket
        // (/api/console/ws) is upgraded and proxied.
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
        // Long-lived SSE (/usage/stream) must not be buffered/timed out.
        timeout: 0,
        proxyTimeout: 0,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes, _req, res) => {
            const ct = String(proxyRes.headers['content-type'] || '')
            if (!ct.includes('text/event-stream')) return
            res.setHeader('Cache-Control', 'no-cache, no-transform')
            res.setHeader('X-Accel-Buffering', 'no')
            // Flush headers immediately so EventSource connects.
            if (typeof res.flushHeaders === 'function') {
              res.flushHeaders()
            }
          })
        },
      },
      '/v1': {
        target: process.env.VITE_API_URL || 'http://localhost:9000',
        changeOrigin: true,
        timeout: 0,
        proxyTimeout: 0,
      },
    },
  },
})
