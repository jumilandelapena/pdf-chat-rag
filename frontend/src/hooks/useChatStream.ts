import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useReducer, useRef } from 'react'
import { streamMessage } from '../api/client'
import type { Chat, Citation, ErrorCode, Message, SseEventMap, StatusStage, Usage } from '../api/types'
import { readSse } from '../lib/sse'

export type StreamPhase = 'idle' | 'connecting' | 'status' | 'streaming' | 'error'

export interface StreamState {
  phase: StreamPhase
  stage: StatusStage | null
  chatId: string | null
  question: string
  text: string
  citations: Citation[]
  usage: Usage | null
  error: string | null
  errorCode: ErrorCode | null
}

type Action =
  | { type: 'send'; chatId: string; question: string }
  | { type: 'status'; stage: StatusStage }
  | { type: 'token'; text: string }
  | { type: 'citations'; citations: Citation[] }
  | { type: 'usage'; usage: Usage }
  | { type: 'error'; message: string; code: ErrorCode | null }
  | { type: 'reset' }

export const INITIAL_STREAM: StreamState = {
  phase: 'idle',
  stage: null,
  chatId: null,
  question: '',
  text: '',
  citations: [],
  usage: null,
  error: null,
  errorCode: null,
}

export const STAGE_TEXT: Record<StatusStage, string> = {
  rewriting: 'Rewriting your question…',
  retrieving: 'Retrieving passages…',
  thinking: 'Thinking…',
}

function reducer(state: StreamState, action: Action): StreamState {
  switch (action.type) {
    case 'send':
      return { ...INITIAL_STREAM, phase: 'connecting', chatId: action.chatId, question: action.question }
    case 'status':
      return { ...state, phase: state.phase === 'streaming' ? 'streaming' : 'status', stage: action.stage }
    case 'token':
      return { ...state, phase: 'streaming', text: state.text + action.text }
    case 'citations':
      return { ...state, citations: action.citations }
    case 'usage':
      return { ...state, usage: action.usage }
    case 'error':
      return { ...state, phase: 'error', error: action.message, errorCode: action.code }
    case 'reset':
      return INITIAL_STREAM
  }
}

function parseData(raw: string): unknown {
  try {
    return JSON.parse(raw)
  } catch {
    return raw
  }
}

/** Streams one answer at a time and writes the finished exchange into the chat cache. */
export function useChatStream() {
  const queryClient = useQueryClient()
  const [state, dispatch] = useReducer(reducer, INITIAL_STREAM)
  const controller = useRef<AbortController | null>(null)

  const stop = useCallback(() => controller.current?.abort(), [])
  useEffect(() => () => controller.current?.abort(), [])

  const send = useCallback(
    async (chatId: string, content: string) => {
      controller.current?.abort()
      const ac = new AbortController()
      controller.current = ac
      dispatch({ type: 'send', chatId, question: content })
      let text = ''
      let citations: Citation[] = []
      let usage: Usage | null = null
      try {
        const res = await streamMessage(chatId, content, ac.signal)
        for await (const event of readSse(res, ac.signal)) {
          const data = parseData(event.data)
          switch (event.event) {
            case 'status':
              dispatch({ type: 'status', stage: (data as SseEventMap['status']).stage })
              break
            case 'token': {
              const piece = typeof data === 'string' ? data : (data as SseEventMap['token']).text
              text += piece
              dispatch({ type: 'token', text: piece })
              break
            }
            case 'citations':
              citations = data as Citation[]
              dispatch({ type: 'citations', citations })
              break
            case 'usage':
              usage = data as Usage
              dispatch({ type: 'usage', usage })
              break
            case 'done': {
              const done = data as SseEventMap['done']
              const now = new Date().toISOString()
              const user: Message = {
                id: done.user_message_id,
                role: 'user',
                content,
                citations: [],
                usage: null,
                rewritten_query: done.rewritten_query,
                created_at: now,
              }
              const assistant: Message = {
                id: done.message_id,
                role: 'assistant',
                content: text,
                citations,
                usage,
                rewritten_query: null,
                created_at: now,
              }
              queryClient.setQueryData<Chat>(['chat', chatId], (old) =>
                old
                  ? { ...old, messages: [...old.messages, user, assistant], message_count: old.message_count + 2 }
                  : old,
              )
              dispatch({ type: 'reset' })
              void queryClient.invalidateQueries({ queryKey: ['chats'] })
              void queryClient.invalidateQueries({ queryKey: ['chat', chatId] })
              return
            }
            case 'error': {
              const error = data as SseEventMap['error']
              dispatch({ type: 'error', message: error.message, code: error.code })
              return
            }
            default:
              break
          }
        }
        dispatch({ type: 'error', message: 'The stream ended before the answer was complete.', code: null })
      } catch (err) {
        if (ac.signal.aborted || (err instanceof DOMException && err.name === 'AbortError')) {
          dispatch({ type: 'error', message: 'Stopped', code: null })
        } else {
          dispatch({ type: 'error', message: err instanceof Error ? err.message : String(err), code: null })
        }
      } finally {
        if (controller.current === ac) controller.current = null
      }
    },
    [queryClient],
  )

  return { state, send, stop }
}
