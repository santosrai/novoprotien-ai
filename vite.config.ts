import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';
import { fileURLToPath } from 'url';

const __dirname = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  plugins: [react()],
  build: {
    lib: {
      entry: resolve(__dirname, 'index.ts'),
      name: 'PipelineCanvas',
      formats: ['es'],
      fileName: 'index',
    },
    rollupOptions: {
      external: [
        'react',
        'react-dom',
        'react/jsx-runtime',
        'reactflow',
        'zustand',
        'lucide-react',
        '@radix-ui/react-dialog',
        '@radix-ui/react-dropdown-menu',
        '@radix-ui/react-label',
        '@radix-ui/react-select',
        '@radix-ui/react-slot',
        '@radix-ui/react-tooltip',
        'class-variance-authority',
        'clsx',
        'tailwind-merge',
      ],
      output: {
        format: 'es',
        entryFileNames: '[name].mjs',
        chunkFileNames: '[name]-[hash].mjs',
        assetFileNames: '[name][extname]',
        preserveModules: true,
        preserveModulesRoot: '.',
      },
    },
    outDir: 'dist',
    sourcemap: true,
    emptyOutDir: true,
  },
});

