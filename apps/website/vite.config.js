import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    strictPort: true,
    // Proxy public API calls to the canonical backend.
    // The admin API (/api/admin, /api/auth) is NOT exposed here;
    // the backend enforces authorization regardless.
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    globals: true,
    exclude: ['**/node_modules/**', 'e2e/**'],
  },
})
