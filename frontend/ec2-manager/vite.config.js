import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Get Lambda URL from environment variable or use default
const LAMBDA_URL = process.env.VITE_LAMBDA_URL || process.env.LAMBDA_URL || ''

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true
  },
  base: '/',
  server: {
    proxy: LAMBDA_URL ? {
      '/api': {
        target: LAMBDA_URL,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '/api'),
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('proxy error', err);
          });
        },
      }
    } : {
      // Default: proxy to mock server for local testing
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            console.log('⚠️  Mock API server not running on port 8000');
            console.log('   Start it with: python3 scripts/mock_api_server.py');
            console.log('   Or set LAMBDA_URL to use real Lambda API');
          });
        },
      }
    }
  }
})
