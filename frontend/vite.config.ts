import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiBase = env.VITE_API_BASE || ''
  const apiTarget = env.VITE_API_TARGET || 'http://localhost:8000'

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: true,
      allowedHosts: ['localhost', '127.0.0.1', '.trycloudflare.com'],
      proxy: {
        '/api': {
          target: apiTarget,
          changeOrigin: true,
          rewrite: (path) => (apiBase ? path.replace(apiBase, '') : path),
        },
      },
    },
    define: {
      __API_BASE__: JSON.stringify(apiBase || '/api'),
    },
  }
})
