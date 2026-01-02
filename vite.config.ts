import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0', // Allow external connections (required for TestSprite tunnel)
    port: 3000,
    strictPort: false,
    proxy: {
      '/api': {
        target: 'http://localhost:8787',
        changeOrigin: true,
        secure: false,
      }
    },
    // Optimize dev server performance
    hmr: {
      overlay: false // Disable error overlay for faster reloads
    },
    // Pre-bundle dependencies for faster loading
    warmup: {
      clientFiles: ['./src/main.tsx', './src/App.tsx']
    }
  },
  optimizeDeps: {
    exclude: ['molstar'], // Exclude molstar from pre-bundling (load on demand)
    include: ['style-to-js', 'style-to-object', 'debug', 'ms', 'extend', 'react', 'react-dom', 'react-router-dom'],
    esbuildOptions: {
      target: 'es2020'
    },
    // Force optimization of common dependencies
    force: false
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
          // Split molstar into its own chunk (lazy loaded)
          if (id.includes('node_modules/molstar')) return 'molstar'
          // Split React into vendor chunk
          if (id.includes('node_modules/react') || id.includes('node_modules/react-dom')) return 'vendor'
          // Split large dependencies
          if (id.includes('node_modules/reactflow')) return 'reactflow'
          if (id.includes('node_modules/react-markdown')) return 'markdown'
          if (id.includes('node_modules/@monaco-editor')) return 'monaco'
          // Group other node_modules
          if (id.includes('node_modules')) return 'vendor-other'
          return undefined
        }
      },
      // Optimize chunk size
      treeshake: {
        moduleSideEffects: false
      }
    },
    // Increase chunk size warning limit for large libraries
    chunkSizeWarningLimit: 1000,
    // Enable source maps only in dev (faster builds)
    sourcemap: false
  },
  ssr: {
    noExternal: ['molstar']
  }
})