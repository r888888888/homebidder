import { createServer } from 'node:http'
import { createReadStream, existsSync, statSync } from 'node:fs'
import { resolve, join, extname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { Readable } from 'node:stream'
import app from './dist/server/server.js'

const __dirname = fileURLToPath(new URL('.', import.meta.url))
const PORT = process.env.PORT || 3000
const CLIENT_DIR = resolve(__dirname, 'dist/client')

const MIME = {
  '.js': 'application/javascript',
  '.mjs': 'application/javascript',
  '.css': 'text/css',
  '.html': 'text/html; charset=utf-8',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff': 'font/woff',
  '.woff2': 'font/woff2',
  '.ttf': 'font/ttf',
  '.map': 'application/json',
}

createServer(async (req, res) => {
  // Serve static files from dist/client/
  const pathname = req.url.split('?')[0]
  const filePath = join(CLIENT_DIR, pathname)
  if (existsSync(filePath) && statSync(filePath).isFile()) {
    const mime = MIME[extname(filePath)] || 'application/octet-stream'
    res.writeHead(200, { 'Content-Type': mime, 'Cache-Control': 'public, max-age=31536000, immutable' })
    createReadStream(filePath).pipe(res)
    return
  }

  // Fall through to SSR handler
  const url = `http://${req.headers.host}${req.url}`
  const chunks = []
  for await (const chunk of req) chunks.push(chunk)
  const body = chunks.length ? Buffer.concat(chunks) : null

  let response
  try {
    response = await app.fetch(
      new Request(url, {
        method: req.method,
        headers: req.headers,
        ...(body ? { body, duplex: 'half' } : {}),
      })
    )
  } catch (err) {
    console.error('Handler error:', err)
    res.writeHead(500).end('Internal Server Error')
    return
  }

  res.writeHead(response.status, Object.fromEntries(response.headers))
  response.body ? Readable.fromWeb(response.body).pipe(res) : res.end()
}).listen(PORT, () => console.log(`Listening on :${PORT}`))
