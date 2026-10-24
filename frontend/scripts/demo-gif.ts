/**
 * Record docs/demo.gif from a running stack with the real provider.
 *
 *   npm run demo:gif -- --clean --base-url http://localhost:5173
 *
 * Options: --base-url (default http://localhost:5173), --out (default ../docs/demo.gif),
 * --width 960, --height 600, --colors 128, --max-bytes 3000000, --clean (delete all documents
 * and chats first so the recording starts from an empty app).
 *
 * The script drives the real UI: upload the RFC sample, type the teapot question, let the
 * answer stream, click the first citation and show the highlighted page. Frames are encoded
 * with one global palette; if the file is larger than --max-bytes it retries once with 64
 * colours at 800x500.
 */
import { chromium, type Page } from '@playwright/test'
import gifenc from 'gifenc'
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { parseArgs } from 'node:util'
import { PNG } from 'pngjs'

const { GIFEncoder, applyPalette, quantize } = gifenc

const { values: args } = parseArgs({
  options: {
    'base-url': { type: 'string', default: 'http://localhost:5173' },
    out: { type: 'string', default: fileURLToPath(new URL('../../docs/demo.gif', import.meta.url)) },
    width: { type: 'string', default: '960' },
    height: { type: 'string', default: '600' },
    colors: { type: 'string', default: '128' },
    'max-bytes': { type: 'string', default: '3000000' },
    clean: { type: 'boolean', default: false },
  },
})

const RFC_PDF = fileURLToPath(new URL('../../sample-pdfs/rfc2324-htcpcp.pdf', import.meta.url))
const QUESTION = 'What error code is returned when you try to brew coffee with a teapot?'

interface Frame {
  png: Buffer
  delay: number
}

async function capture(baseUrl: string, width: number, height: number, clean: boolean): Promise<Frame[]> {
  const browser = await chromium.launch()
  const page = await browser.newPage({ viewport: { width, height }, deviceScaleFactor: 1 })
  const frames: Frame[] = []
  const shot = async (delay: number) => frames.push({ png: await page.screenshot({ type: 'png' }), delay })
  try {
    if (clean) await cleanServer(page, baseUrl)
    await page.goto(baseUrl)
    const badge = page.getByTestId('provider-badge')
    await badge.waitFor({ timeout: 60_000 })
    const provider = await badge.textContent()
    if (!provider?.includes('anthropic')) {
      throw new Error(`The stack runs the ${provider ?? 'unknown'} provider; start it with LLM_PROVIDER=anthropic`)
    }
    await shot(600)

    await page.getByRole('button', { name: 'New chat' }).click()
    await page.getByLabel('Upload PDFs').setInputFiles({
      name: 'rfc2324-htcpcp.pdf',
      mimeType: 'application/pdf',
      buffer: readFileSync(RFC_PDF),
    })
    const row = page.getByTestId('doc-row').filter({ hasText: 'rfc2324-htcpcp.pdf' }).first()
    await row.getByTestId('doc-status').waitFor({ timeout: 30_000 })
    await shot(500)
    await row.getByTestId('doc-status').and(page.locator('[data-status="ready"]')).waitFor({ timeout: 120_000 })
    await shot(900)

    const box = page.getByLabel('Ask a question')
    await box.waitFor()
    for (let i = 0; i < QUESTION.length; i += 18) {
      await box.pressSequentially(QUESTION.slice(i, i + 18), { delay: 25 })
      if (frames.length < 7) await shot(350)
    }
    await page.keyboard.press('Enter')
    await page.getByTestId('streaming-indicator').waitFor({ timeout: 10_000 }).catch(() => undefined)
    await shot(400)

    const answer = page.getByTestId('assistant-message').last()
    let lastLength = -1
    let streamingFrames = 0
    const deadline = Date.now() + 60_000
    while (Date.now() < deadline) {
      await page.waitForTimeout(300)
      const text = (await answer.textContent().catch(() => '')) ?? ''
      const done = (await answer.getByTestId('cost-line').count()) > 0
      if (text.length !== lastLength && streamingFrames < 8) {
        await shot(350)
        streamingFrames++
        lastLength = text.length
      }
      if (done) break
    }
    await answer.getByTestId('cost-line').waitFor({ timeout: 30_000 })
    await shot(1500)

    await answer.getByTestId('citation-chip').first().click()
    await page.getByTestId('viewer-page-indicator').waitFor({ timeout: 30_000 })
    await page
      .locator('.react-pdf__Page__textContent mark.quote-hit')
      .first()
      .waitFor({ timeout: 30_000 })
      .catch(() => page.getByTestId('cited-passage').waitFor({ timeout: 10_000 }))
    await page.waitForTimeout(500)
    await shot(800)
    await shot(4000)
  } finally {
    await browser.close()
  }
  return frames
}

async function cleanServer(page: Page, baseUrl: string) {
  for (const path of ['/api/documents', '/api/chats']) {
    const res = await page.request.get(`${baseUrl}${path}`)
    if (!res.ok()) throw new Error(`${path}: HTTP ${res.status()}`)
    for (const item of (await res.json()) as Array<{ id: string }>) {
      await page.request.delete(`${baseUrl}${path}/${item.id}`)
    }
  }
}

function encode(frames: Frame[], colors: number): Uint8Array {
  const unique = frames.filter((f, i) => i === 0 || !f.png.equals(frames[i - 1]!.png))
  const decoded = unique.map((f) => ({ ...PNG.sync.read(f.png), delay: f.delay }))
  const { width, height } = decoded[0]!
  const keyFrames = [0, Math.floor(decoded.length / 2), decoded.length - 1].map((i) => decoded[i]!)
  const sample = Buffer.concat(keyFrames.map((f) => f.data))
  const palette = quantize(sample, colors)
  const gif = GIFEncoder()
  decoded.forEach((frame, i) => {
    const indexed = applyPalette(frame.data, palette)
    gif.writeFrame(indexed, width, height, { palette, first: i === 0, delay: frame.delay, repeat: 0 })
  })
  gif.finish()
  return gif.bytes()
}

async function main() {
  const baseUrl = args['base-url']!.replace(/\/$/, '')
  const maxBytes = Number(args['max-bytes'])
  let width = Number(args.width)
  let height = Number(args.height)
  let colors = Number(args.colors)
  for (let attempt = 0; attempt < 2; attempt++) {
    const frames = await capture(baseUrl, width, height, args.clean ?? false)
    const bytes = encode(frames, colors)
    mkdirSync(dirname(args.out!), { recursive: true })
    writeFileSync(args.out!, bytes)
    console.log(`wrote ${args.out}: ${bytes.length} bytes, ${frames.length} frames, ${width}x${height}, ${colors} colours`)
    if (bytes.length <= maxBytes) return
    console.warn(`larger than ${maxBytes} bytes; retrying smaller`)
    width = 800
    height = 500
    colors = 64
  }
  console.error('demo.gif is still too large; reduce --width/--height or the number of frames')
  process.exit(1)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
