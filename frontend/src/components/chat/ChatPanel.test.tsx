import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { Chat } from '../../api/types'
import { chat, citation, document, message, usage } from '../../test/fixtures'
import { renderWithProviders } from '../../test/render'
import { json, makeSseResponse, mockFetchRoutes, sseText } from '../../test/sse-response'
import { ChatPanel } from './ChatPanel'
import { AssistantMessage } from './Messages'

const ANSWER = 'The pot returns 418. Done.'
const doneEvent: [string, unknown] = ['done', { message_id: 'a1', user_message_id: 'u1', rewritten_query: null }]

const PERSISTED = chat({
  message_count: 2,
  messages: [
    message({ id: 'u1', role: 'user', content: 'Which code?' }),
    message({ id: 'a1', content: ANSWER, citations: [citation({ text_end: 20 })], usage: usage() }),
  ],
})

/** The GET route returns the persisted exchange once the stream has been served, like the backend. */
function routes(streamChunks: string[], persisted: Chat = chat()) {
  let served = false
  return mockFetchRoutes({
    'GET /documents': () => json([document()]),
    'GET /chats': () => json([chat()]),
    'GET /chats/c1': () => json(served ? persisted : chat()),
    'POST /chats/c1/messages': () => {
      served = true
      return makeSseResponse(streamChunks, { delayMs: 5 })
    },
  })
}

async function ask(text: string) {
  const user = userEvent.setup()
  const box = await screen.findByLabelText('Ask a question')
  await waitFor(() => expect(box).toBeEnabled())
  await user.type(box, `${text}{Enter}`)
}

describe('ChatPanel', () => {
  it('renders the streamed answer incrementally with chips, sources and the cost line', async () => {
    routes(
      [
        sseText([['status', { stage: 'retrieving' }], ['token', { text: 'The pot ' }]]),
        sseText([['token', { text: 'returns 418.' }], ['token', { text: ' Done.' }]]),
        sseText([['citations', [citation({ text_end: 20 })]], ['usage', usage()], doneEvent]),
      ],
      PERSISTED,
    )
    const { container } = renderWithProviders(
      <ChatPanel activeChatId="c1" onSelectChat={() => undefined} pendingScope={[]} />,
    )
    await ask('Which code?')
    await screen.findByText(/^The pot/)
    await waitFor(() => expect(screen.getByRole('log')).toHaveTextContent('The pot returns 418.'))
    await waitFor(() => expect(screen.getByTestId('cost-line')).toHaveTextContent('1,000 in · 20 out'))
    const chip = screen.getByTestId('citation-chip')
    expect(chip).toHaveTextContent('[1]')
    expect(chip).toHaveAttribute('data-page', '5')
    expect(screen.getByRole('list', { name: 'Sources' })).toHaveTextContent('[1] rfc2324-htcpcp.pdf p.5')
    await waitFor(() => expect(screen.queryByTestId('streaming-indicator')).not.toBeInTheDocument())
    await waitFor(() => expect(screen.getAllByTestId('assistant-message')).toHaveLength(1))
    const streamed = container.querySelector('[data-testid="assistant-message"]')?.outerHTML
    const persisted = renderWithProviders(
      <AssistantMessage content={ANSWER} citations={[citation({ text_end: 20 })]} usage={usage()} />,
    )
    expect(streamed).toBe(persisted.container.firstElementChild?.outerHTML)
    expect(screen.getAllByLabelText('Ask a question')[0]).toHaveValue('')
  })

  it('shows the error notice and restores the question', async () => {
    routes([sseText([['error', { code: 'no_documents', message: 'Upload a PDF first.' }]])])
    renderWithProviders(<ChatPanel activeChatId="c1" onSelectChat={() => undefined} pendingScope={[]} />)
    await ask('Hello?')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Upload a PDF first. Upload a PDF and wait for the ready badge.',
    )
    expect(screen.queryByTestId('assistant-message')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByLabelText('Ask a question')).toHaveValue('Hello?'))
  })

  it('renders persisted messages identically to the finished streamed bubble', () => {
    const persisted = message({ content: ANSWER, citations: [citation({ text_end: 20 })], usage: usage() })
    const a = renderWithProviders(
      <AssistantMessage content={persisted.content} citations={persisted.citations} usage={persisted.usage} />,
    )
    const b = renderWithProviders(
      <AssistantMessage content={ANSWER} citations={[citation({ text_end: 20 })]} usage={usage()} phase="idle" />,
    )
    expect(a.container.innerHTML).toBe(b.container.innerHTML)
  })
})
