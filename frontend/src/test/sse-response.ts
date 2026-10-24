import { vi } from 'vitest'

export interface SseResponseInit {
  status?: number
  delayMs?: number
  contentType?: string
  neverClose?: boolean
}

/** A fetch Response whose body streams the given chunks (one enqueue per chunk). */
export function makeSseResponse(chunks: string[], init: SseResponseInit = {}): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      for (const chunk of chunks) {
        if (init.delayMs) await new Promise((r) => setTimeout(r, init.delayMs))
        controller.enqueue(encoder.encode(chunk))
      }
      if (!init.neverClose) controller.close()
    },
  })
  return new Response(stream, {
    status: init.status ?? 200,
    headers: { 'content-type': init.contentType ?? 'text/event-stream; charset=utf-8' },
  })
}

export function sseText(events: Array<[string, unknown]>): string {
  return events.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join('')
}

export const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

export type Route = (init: RequestInit | undefined, url: URL) => Response | Promise<Response>

export interface RecordedCall {
  method: string
  path: string
  init: RequestInit | undefined
}

/** Stub global fetch with routes keyed by "METHOD /path" (a trailing * matches a prefix). */
export function mockFetchRoutes(routes: Record<string, Route>) {
  const calls: RecordedCall[] = []
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const href = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
    const url = new URL(href, 'http://localhost')
    const method = (init?.method ?? 'GET').toUpperCase()
    const path = url.pathname.replace(/^\/api/, '')
    calls.push({ method, path, init })
    const key = Object.keys(routes).find((k) => {
      const [m, p] = k.split(' ')
      if (m !== method || !p) return false
      return p.endsWith('*') ? path.startsWith(p.slice(0, -1)) : p === path
    })
    if (!key) return json({ detail: `no route for ${method} ${path}` }, 404)
    return routes[key]!(init, url)
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}

export const bodyOf = (call: RecordedCall): unknown =>
  typeof call.init?.body === 'string' ? JSON.parse(call.init.body) : call.init?.body
