import { describe, expect, it } from 'vitest'
import { bodyOf, json, mockFetchRoutes } from '../test/sse-response'
import { chat, document } from '../test/fixtures'
import { createChat, getChat, patchChat, uploadDocuments } from './client'

describe('api client', () => {
  it('uploads files as multipart with the field name files', async () => {
    const { calls } = mockFetchRoutes({ 'POST /documents': () => json([document()], 201) })
    const file = new File([new Uint8Array([37, 80, 68, 70])], 'a.pdf', { type: 'application/pdf' })
    await uploadDocuments([file])
    const body = calls[0]?.init?.body as FormData
    expect(body).toBeInstanceOf(FormData)
    expect(body.getAll('files')).toHaveLength(1)
    expect(calls[0]?.init?.headers).toBeUndefined()
  })

  it('creates and patches chats with explicit document id lists', async () => {
    const { calls } = mockFetchRoutes({
      'POST /chats': () => json(chat(), 201),
      'PATCH /chats/c1': () => json(chat({ document_ids: [] })),
    })
    await createChat({ document_ids: [] })
    await patchChat('c1', { document_ids: [] })
    expect(bodyOf(calls[0]!)).toEqual({ document_ids: [] })
    expect(bodyOf(calls[1]!)).toEqual({ document_ids: [] })
    expect(calls[1]?.method).toBe('PATCH')
  })

  it('normalises null citations to an empty array', async () => {
    mockFetchRoutes({
      'GET /chats/c1': () =>
        json({ ...chat(), messages: [{ id: 'm', role: 'user', content: 'q', citations: null, usage: null, created_at: 'x' }] }),
    })
    const result = await getChat('c1')
    expect(result.messages[0]?.citations).toEqual([])
  })

  it('surfaces the error detail', async () => {
    mockFetchRoutes({ 'GET /chats/c1': () => json({ detail: 'Chat not found' }, 404) })
    await expect(getChat('c1')).rejects.toMatchObject({ status: 404, detail: 'Chat not found' })
  })
})
