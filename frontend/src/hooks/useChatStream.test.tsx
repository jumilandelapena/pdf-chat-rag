import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import type { Chat } from '../api/types'
import { chat, citation, usage } from '../test/fixtures'
import { makeQueryClient } from '../test/render'
import { bodyOf, makeSseResponse, mockFetchRoutes, sseText } from '../test/sse-response'
import { useChatStream } from './useChatStream'

function setup() {
  const client = makeQueryClient()
  client.setQueryData(['chat', 'c1'], chat())
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const hook = renderHook(() => useChatStream(), { wrapper })
  return { client, hook }
}

describe('useChatStream', () => {
  it('streams tokens, then writes both messages into the chat cache on done', async () => {
    const { calls } = mockFetchRoutes({
      'POST /chats/c1/messages': () =>
        makeSseResponse([
          sseText([['status', { stage: 'retrieving' }]]),
          ': ping\n\n',
          sseText([['token', { text: 'Hello' }], ['token', { text: ' world' }]]),
          sseText([
            ['citations', [citation()]],
            ['usage', usage()],
            ['done', { message_id: 'a1', user_message_id: 'u1', rewritten_query: null }],
          ]),
        ]),
    })
    const { client, hook } = setup()
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    await act(async () => {
      await hook.result.current.send('c1', 'Which code?')
    })
    await waitFor(() => expect(hook.result.current.state.phase).toBe('idle'))
    const cached = client.getQueryData<Chat>(['chat', 'c1'])
    expect(cached?.messages.map((m) => [m.id, m.role, m.content])).toEqual([
      ['u1', 'user', 'Which code?'],
      ['a1', 'assistant', 'Hello world'],
    ])
    expect(cached?.messages[1]?.citations).toEqual([citation()])
    expect(cached?.messages[1]?.usage).toEqual(usage())
    expect(invalidate).toHaveBeenCalled()
    expect(calls[0]?.init?.headers).toMatchObject({ Accept: 'text/event-stream' })
    expect(bodyOf(calls[0]!)).toEqual({ content: 'Which code?' })
  })

  it('reports an error event without appending anything', async () => {
    mockFetchRoutes({
      'POST /chats/c1/messages': () =>
        makeSseResponse([sseText([['token', { text: 'partial' }], ['error', { code: 'max_tokens', message: 'Cut off' }]])]),
    })
    const { client, hook } = setup()
    await act(async () => {
      await hook.result.current.send('c1', 'q')
    })
    expect(hook.result.current.state.phase).toBe('error')
    expect(hook.result.current.state.error).toBe('Cut off')
    expect(hook.result.current.state.errorCode).toBe('max_tokens')
    expect(client.getQueryData<Chat>(['chat', 'c1'])?.messages).toEqual([])
  })

  it('stop() aborts the request', async () => {
    let seenSignal: AbortSignal | undefined
    mockFetchRoutes({
      'POST /chats/c1/messages': (init) => {
        seenSignal = init?.signal ?? undefined
        return makeSseResponse([sseText([['status', { stage: 'thinking' }]])], { neverClose: true })
      },
    })
    const { hook } = setup()
    let sending: Promise<void> | undefined
    act(() => {
      sending = hook.result.current.send('c1', 'q')
    })
    await waitFor(() => expect(hook.result.current.state.phase).toBe('status'))
    act(() => hook.result.current.stop())
    await act(async () => {
      await sending
    })
    expect(seenSignal?.aborted).toBe(true)
    expect(hook.result.current.state.phase).toBe('error')
    expect(hook.result.current.state.error).toBe('Stopped')
  })
})
