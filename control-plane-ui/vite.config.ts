import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

const fixturesDir = path.resolve(__dirname, '../demo/fixtures')

// Serves fixture JSON at /data/* in dev, copies to dist/data/ on build
function fixtureData(): import('vite').Plugin {
  return {
    name: 'fixture-data',

    // Dev: serve /data/foo.json from ../demo/fixtures/foo.json
    configureServer(server) {
      server.middlewares.use('/data', (req, res, next) => {
        const file = path.join(fixturesDir, req.url!.replace(/^\//, ''))
        if (fs.existsSync(file) && file.endsWith('.json')) {
          res.setHeader('Content-Type', 'application/json')
          fs.createReadStream(file).pipe(res)
        } else {
          next()
        }
      })
    },

    // Build: copy fixtures into dist/data/
    writeBundle() {
      const dest = path.resolve(__dirname, 'dist/data')
      fs.mkdirSync(dest, { recursive: true })
      for (const file of fs.readdirSync(fixturesDir)) {
        if (file.endsWith('.json')) {
          fs.copyFileSync(path.join(fixturesDir, file), path.join(dest, file))
        }
      }
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), fixtureData()],
})
