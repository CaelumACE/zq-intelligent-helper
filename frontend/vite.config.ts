import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    allowedHosts: ['localhost', '127.0.0.1', '.trycloudflare.com'],
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
