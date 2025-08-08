import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
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
        manualChunks: {
          vendor: ['react', 'react-dom'],
          molstar: ['molstar']
        }
      }
    }
  },
  ssr: {
    noExternal: ['molstar']
  }
})