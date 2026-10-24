import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Chat } from '../../api/types'
import { chat, document as doc } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { bodyOf, json, mockFetchRoutes } from '../../test/sse-response'
import { DocumentsPanel } from './DocumentsPanel'

const DOCS = [
  doc({ id: 'd1', filename: 'a.pdf' }),
  doc({ id: 'd2', filename: 'b.pdf' }),
  doc({ id: 'd3', filename: 'c.pdf', status: 'processing', page_count: null, chunk_count: null }),
  doc({ id: 'd4', filename: 'd.pdf', status: 'failed', error: 'No extractable text' }),
]

function setup(chatValue: Chat | null = chat()) {
  const { calls } = mockFetchRoutes({
    'GET /documents': () => json(DOCS),
    'PATCH /chats/c1': (init) => json({ ...chat(), ...(JSON.parse(init?.body as string) as object) }),
    'DELETE /documents/*': () => new Response(null, { status: 204 }),
    'POST /documents': () => json([doc()], 201),
  })
  const result = renderWithProviders(
    <DocumentsPanel chat={chatValue} pendingScope={[]} onPendingScopeChange={() => undefined} />,
  )
  if (chatValue) result.client.setQueryData(['chat', chatValue.id], chatValue)
  return { calls, ...result }
}

describe('DocumentsPanel', () => {
  it('renders status badges, counts and errors', async () => {
    setup()
    const badges = await screen.findAllByTestId('doc-status')
    expect(badges.map((b) => b.getAttribute('data-status'))).toEqual(['ready', 'ready', 'processing', 'failed'])
    expect(screen.getAllByText('10 pages · 12 chunks')).toHaveLength(2)
    expect(screen.getByText('No extractable text')).toBeInTheDocument()
    expect(screen.getByLabelText('Include c.pdf in chat scope')).toBeDisabled()
    expect(screen.getByText('Documents')).toBeInTheDocument()
  })

  it('unchecking a document sends the remaining ids', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Include a.pdf in chat scope'))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(bodyOf(calls.find((c) => c.method === 'PATCH')!)).toEqual({ document_ids: ['d2'] })
  })

  it('re-checking every ready document sends an empty list and locks the last box', async () => {
    const { calls } = setup(chat({ document_ids: ['d2'] }))
    const user = userEvent.setup()
    const last = await screen.findByLabelText('Include b.pdf in chat scope')
    expect(last).toBeChecked()
    expect(last).toBeDisabled()
    expect(last).toHaveAttribute('title', 'At least one document must stay in scope')
    await user.click(screen.getByLabelText('Include a.pdf in chat scope'))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    expect(bodyOf(calls.find((c) => c.method === 'PATCH')!)).toEqual({ document_ids: [] })
  })

  it('deletes only after the confirm click', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    await user.click(await screen.findByLabelText('Delete a.pdf'))
    expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
    await user.click(screen.getByLabelText('Confirm delete a.pdf'))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.path === '/documents/d1')).toBe(true))
  })

  it('rejects oversized files client-side and uploads valid ones', async () => {
    const { calls } = setup()
    const user = userEvent.setup()
    const big = new File(['x'], 'big.pdf', { type: 'application/pdf' })
    Object.defineProperty(big, 'size', { value: 60 * 1024 * 1024 })
    await user.upload(await screen.findByLabelText('Upload PDFs'), big)
    expect(await screen.findByRole('alert')).toHaveTextContent('big.pdf exceeds 50 MiB')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
    const small = new File(['%PDF-1.4'], 'small.pdf', { type: 'application/pdf' })
    await user.upload(screen.getByLabelText('Upload PDFs'), small)
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.path === '/documents')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.init?.body).toBeInstanceOf(FormData)
  })
})
