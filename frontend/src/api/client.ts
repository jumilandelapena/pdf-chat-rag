import { API_BASE } from './base'
import type { Chat, ChatSummary, Document, Health } from './types'

export class ApiError extends Error {
  readonly status: number
  readonly detail: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** Build an ApiError from a failed response: JSON `detail`, else the text body, else the status. */
export async function parseError(res: Response): Promise<ApiError> {
  const text = await res.text().catch(() => '')
  let detail = ''
  if (text) {
    try {
      const body = JSON.parse(text) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (body.detail !== undefined) detail = JSON.stringify(body.detail)
      else detail = text.trim()
    } catch {
      detail = text.trim()
    }
  }
  return new ApiError(res.status, detail || res.statusText || `HTTP ${res.status}`)
}

const JSON_HEADERS = { 'Content-Type': 'application/json' }

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) throw await parseError(res)
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

function normaliseChat(chat: Chat): Chat {
  return {
    ...chat,
    document_ids: chat.document_ids ?? [],
    messages: (chat.messages ?? []).map((m) => ({ ...m, citations: m.citations ?? [] })),
  }
}

export const getHealth = (signal?: AbortSignal) => request<Health>('/health', { signal })

export const listDocuments = () => request<Document[]>('/documents')

export function uploadDocuments(files: File[]): Promise<Document[]> {
  const form = new FormData()
  for (const file of files) form.append('files', file, file.name)
  return request<Document[]>('/documents', { method: 'POST', body: form })
}

export const deleteDocument = (id: string) => request<void>(`/documents/${id}`, { method: 'DELETE' })

export const documentFileUrl = (id: string) => `${API_BASE}/documents/${id}/file`

export const listChats = () => request<ChatSummary[]>('/chats')

export const createChat = (body: { document_ids: string[]; title?: string }) =>
  request<Chat>('/chats', { method: 'POST', headers: JSON_HEADERS, body: JSON.stringify(body) }).then(
    normaliseChat,
  )

export const getChat = (id: string) => request<Chat>(`/chats/${id}`).then(normaliseChat)

export const patchChat = (id: string, body: { document_ids?: string[]; title?: string }) =>
  request<Chat>(`/chats/${id}`, {
    method: 'PATCH',
    headers: JSON_HEADERS,
    body: JSON.stringify(body),
  }).then(normaliseChat)

export const deleteChat = (id: string) => request<void>(`/chats/${id}`, { method: 'DELETE' })

/** Start a streamed answer. The caller reads the SSE body with `readSse`. */
export function streamMessage(chatId: string, content: string, signal: AbortSignal): Promise<Response> {
  return fetch(`${API_BASE}/chats/${chatId}/messages`, {
    method: 'POST',
    headers: { ...JSON_HEADERS, Accept: 'text/event-stream' },
    body: JSON.stringify({ content }),
    signal,
  })
}
