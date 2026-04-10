import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import { copyFileSync, mkdirSync, readdirSync } from 'fs'

// Copy fixture JSON files into dist/data/ on production build
function copyFixtures() {
  return {
    name: 'copy-fixtures',
    writeBundle() {
      const src = path.resolve(__dirname, '../demo/fixtures')
      const dest = path.resolve(__dirname, 'dist/data')
      mkdirSync(dest, { recursive: true })
      for (const file of readdirSync(src)) {
        if (file.endsWith('.json')) {
          copyFileSync(path.join(src, file), path.join(dest, file))
        }
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), copyFixtures()],
  // In dev, serve the repo root so /data/... can resolve via public dir symlink
  publicDir: 'public',
})
