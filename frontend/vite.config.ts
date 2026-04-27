import path from 'path'
import { defineConfig } from 'vite'
import { devtools } from '@tanstack/devtools-vite'
import tsconfigPaths from 'vite-tsconfig-paths'

import { tanstackStart } from '@tanstack/react-start/plugin/vite'

import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const config = defineConfig({
  plugins: [
    devtools(),
    tsconfigPaths({ projects: ['./tsconfig.json'] }),
    tailwindcss(),
    tanstackStart({
      router: {
        routeFileIgnorePattern: '\\.test\\.(tsx?|jsx?)$',
      },
    }),
    viteReact(),
  ],
  resolve: {
    alias: {
      canvas: path.resolve(__dirname, 'src/stubs/canvas-stub.ts'),
    },
  },
})

export default config
