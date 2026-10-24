import { parseError } from '../api/client'

export interface SseEvent {
  event: string
  data: string
  id: string
}

/** Incremental WHATWG event-stream parser (handles CRLF split across chunks, comments, ids). */
export function createSseParser() {
  let buffer = ''
  let pendingLF = false
  let eventType = ''
  let dataLines: string[] = []
  let hasData = false
  let lastId = ''
  const out: SseEvent[] = []

  function dispatch() {
    if (!hasData) {
      eventType = ''
      return
    }
    out.push({ event: eventType || 'message', data: dataLines.join('\n'), id: lastId })
    eventType = ''
    dataLines = []
    hasData = false
  }

  function processLine(line: string) {
    if (line === '') {
      dispatch()
      return
    }
    if (line.startsWith(':')) return
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    let value = colon === -1 ? '' : line.slice(colon + 1)
    if (value.startsWith(' ')) value = value.slice(1)
    if (field === 'event') eventType = value
    else if (field === 'data') {
      dataLines.push(value)
      hasData = true
    } else if (field === 'id' && !value.includes('\0')) lastId = value
  }

  function feed(chunk: string): SseEvent[] {
    let text = chunk
    if (pendingLF && text.startsWith('\n')) text = text.slice(1)
    pendingLF = false
    buffer += text
    let start = 0
    for (;;) {
      const cr = buffer.indexOf('\r', start)
      const lf = buffer.indexOf('\n', start)
      let idx = -1
      let len = 1
      if (cr !== -1 && (lf === -1 || cr < lf)) {
        idx = cr
        if (buffer[cr + 1] === '\n') len = 2
        else if (cr === buffer.length - 1) pendingLF = true
      } else if (lf !== -1) {
        idx = lf
      }
      if (idx === -1) break
      processLine(buffer.slice(start, idx))
      start = idx + len
    }
    buffer = buffer.slice(start)
    return out.splice(0)
  }

  /** End of stream: an unterminated trailing event is dropped, as the spec requires. */
  function end(): SseEvent[] {
    buffer = ''
    return out.splice(0)
  }

  return { feed, end }
}

export interface ReadSseOptions {
  /** Abort when no bytes (not even a `: ping`) arrive for this long. */
  silenceMs?: number
}

export async function* readSse(
  res: Response,
  signal?: AbortSignal,
  opts: ReadSseOptions = {},
): AsyncGenerator<SseEvent> {
  const silenceMs = opts.silenceMs ?? 60_000
  const contentType = res.headers.get('content-type') ?? ''
  if (!res.ok || !contentType.startsWith('text/event-stream')) throw await parseError(res)
  if (!res.body) throw new Error('Response has no body')
  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  const parser = createSseParser()
  let timer: ReturnType<typeof setTimeout> | undefined
  let timedOut = false
  const resetTimer = () => {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      timedOut = true
      void reader.cancel()
    }, silenceMs)
  }
  const onAbort = () => void reader.cancel()
  signal?.addEventListener('abort', onAbort)
  try {
    resetTimer()
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      resetTimer()
      for (const event of parser.feed(value)) yield event
    }
    for (const event of parser.end()) yield event
    if (timedOut) throw new Error(`Connection lost (no data for ${Math.round(silenceMs / 1000)} s)`)
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')
  } finally {
    if (timer) clearTimeout(timer)
    signal?.removeEventListener('abort', onAbort)
    reader.cancel().catch(() => undefined)
  }
}
