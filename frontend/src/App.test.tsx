import { screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import App, { ACTIVE_CHAT_KEY } from './App'
import { chat } from './test/fixtures'
import { renderWithProviders } from './test/render'
import { json, mockFetchRoutes } from './test/sse-response'

const health = { status: 'ok', llm_provider: 'mock', embeddings_provider: 'fake', answer_model: 'mock', documents: 0 }

describe('App', () => {
  it('falls back to the newest chat when the stored id is stale and shows the provider badge', async () => {
    localStorage.setItem(ACTIVE_CHAT_KEY, 'gone')
    mockFetchRoutes({
      'GET /health': () => json(health),
      'GET /chats': () => json([chat({ id: 'newest' }), chat({ id: 'older' })]),
      'GET /chats/newest': () => json(chat({ id: 'newest' })),
      'GET /documents': () => json([]),
    })
    renderWithProviders(<App />)
    await waitFor(() => expect(screen.getByRole('combobox', { name: 'Chat' })).toHaveValue('newest'))
    expect(await screen.findByTestId('provider-badge')).toHaveTextContent('provider: mock')
    expect(localStorage.getItem(ACTIVE_CHAT_KEY)).toBe('newest')
    expect(screen.queryByText(/Waking up/)).not.toBeInTheDocument()
  })

  it('shows the waking-up banner while /health fails', async () => {
    mockFetchRoutes({
      'GET /health': () => json({ detail: 'down' }, 503),
      'GET /chats': () => json([]),
      'GET /documents': () => json([]),
    })
    renderWithProviders(<App />)
    expect(await screen.findByText(/Waking up the server/, {}, { timeout: 6000 })).toBeInTheDocument()
    expect(screen.queryByTestId('provider-badge')).not.toBeInTheDocument()
  }, 10_000)
})
