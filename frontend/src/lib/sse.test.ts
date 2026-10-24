import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { makeSseResponse } from '../test/sse-response'
import { createSseParser, readSse, type SseEvent } from './sse'

describe('createSseParser', () => {
  it('parses a single event', () => {
    const parser = createSseParser()
    expect(parser.feed('event: token\ndata: {"text":"Hi"}\n\n')).toEqual([
      { event: 'token', data: '{"text":"Hi"}', id: '' },
    ])
  })

  it('handles CRLF split across chunks', () => {
    const parser = createSseParser()
    expect(parser.feed('event: token\r')).toEqual([])
    expect(parser.feed('\ndata: "a"\r\n\r\n')).toEqual([{ event: 'token', data: '"a"', id: '' }])
  })

  it('joins multi-line data with newlines', () => {
    expect(createSseParser().feed('data: a\ndata: b\n\n')[0]?.data).toBe('a\nb')
  })

  it('ignores comments without resetting a pending event', () => {
    const parser = createSseParser()
    expect(parser.feed(': ping\n\n')).toEqual([])
    expect(parser.feed('event: x\n: ping\ndata: 1\n\n')).toEqual([{ event: 'x', data: '1', id: '' }])
  })

  it('treats a bare data field as empty data and drops event-only blocks', () => {
    expect(createSseParser().feed('data\n\n')).toEqual([{ event: 'message', data: '', id: '' }])
    expect(createSseParser().feed('event: nothing\n\n')).toEqual([])
  })

  it('keeps the last id and ignores ids containing NUL', () => {
    const parser = createSseParser()
    const [a] = parser.feed('id: 7\ndata: a\n\n')
    const [b] = parser.feed('id: x\0y\ndata: b\n\n')
    expect(a?.id).toBe('7')
    expect(b?.id).toBe('7')
  })

  it('drops an unterminated trailing event at end of stream', () => {
    const parser = createSseParser()
    expect(parser.feed('data: partial')).toEqual([])
    expect(parser.end()).toEqual([])
  })
})

async function collect(res: Response, signal?: AbortSignal, opts?: { silenceMs?: number }) {
  const out: SseEvent[] = []
  for await (const event of readSse(res, signal, opts)) out.push(event)
  return out
}

const response = (body: string, status: number, type: string) =>
  new Response(body, { status, headers: { 'content-type': type } })

describe('readSse', () => {
  it('throws ApiError with the JSON detail, the text body, or the status', async () => {
    await expect(
      collect(response(JSON.stringify({ detail: 'Chat not found' }), 404, 'application/json')),
    ).rejects.toMatchObject({ name: 'ApiError', status: 404, detail: 'Chat not found' })
    await expect(collect(response('<html>413 Request Entity Too Large</html>', 413, 'text/html'))).rejects.toMatchObject({
      status: 413,
      detail: expect.stringContaining('413'),
    })
    await expect(collect(response('{}', 200, 'application/json'))).rejects.toBeInstanceOf(ApiError)
  })

  it('accepts a charset suffix and decodes multibyte chars split across chunks', async () => {
    const bytes = new TextEncoder().encode('data: "café"\n\n')
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, 11))
        controller.enqueue(bytes.slice(11))
        controller.close()
      },
    })
    const res = new Response(stream, { headers: { 'content-type': 'text/event-stream; charset=utf-8' } })
    expect((await collect(res)).map((e) => e.data)).toEqual(['"café"'])
  })

  it('yields events from a chunked stream including a ping', async () => {
    const res = makeSseResponse(['event: status\ndata: {"stage":"retrieving"}\n\n', ': ping\n\n', 'event: token\ndata: {"text":"Hi"}\n\n'])
    expect((await collect(res)).map((e) => e.event)).toEqual(['status', 'token'])
  })

  it('fails when no bytes arrive within silenceMs', async () => {
    const res = makeSseResponse([], { neverClose: true })
    await expect(collect(res, undefined, { silenceMs: 50 })).rejects.toThrow(/Connection lost/)
  })
})
