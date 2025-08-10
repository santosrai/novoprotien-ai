import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8787',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  optimizeDeps: {
    exclude: ['molstar'],
    include: ['style-to-js', 'style-to-object', 'debug', 'ms', 'extend'],
    esbuildOptions: {
      target: 'es2020'
    }
  },
  resolve: {
    alias: {
      'style-to-js': 'style-to-js/cjs/index.js'
    }
  },
  define: {
    global: 'globalThis'
  },
  build: {
    commonjsOptions: {
      include: [/node_modules/],
      transformMixedEsModules: true
    },
    rollupOptions: {
      external: [],
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/molstar')) return 'molstar'
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) return 'vendor'
          return undefined
        }
      }
    }
  },
  ssr: {
    noExternal: ['molstar']
  }
})