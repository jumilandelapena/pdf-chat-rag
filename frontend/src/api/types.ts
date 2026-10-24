// Mirrors backend/app/api/schemas.py. Keep the two in sync.

export type DocumentStatus = 'processing' | 'ready' | 'failed'

export interface Document {
  id: string
  filename: string
  status: DocumentStatus
  error: string | null
  page_count: number | null
  chunk_count: number | null
  scanned_pages: number
  size_bytes: number
  created_at: string
}

export interface Citation {
  n: number
  document_id: string
  filename: string
  page: number
  quote: string
  /** UTF-16 offsets into the answer text (JavaScript string indices). */
  text_start: number
  text_end: number
  chunk_id: string
  page_char_start: number
  page_char_end: number
}

export interface Usage {
  input_tokens: number
  output_tokens: number
  cache_read_input_tokens: number
  cache_creation_input_tokens: number
  thinking_tokens: number
  model: string
  cost_usd: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations: Citation[]
  usage: Usage | null
  rewritten_query: string | null
  created_at: string
}

export interface ChatSummary {
  id: string
  title: string
  /** Empty array = all ready documents. */
  document_ids: string[]
  created_at: string
  updated_at: string
  message_count: number
}

export interface Chat extends ChatSummary {
  messages: Message[]
}

export interface Health {
  status: string
  llm_provider: 'anthropic' | 'mock'
  embeddings_provider: 'local' | 'fake'
  answer_model: string
  documents: number
}

export type StatusStage = 'rewriting' | 'retrieving' | 'thinking'

export type ErrorCode =
  | 'no_documents'
  | 'no_results'
  | 'provider_error'
  | 'max_tokens'
  | 'refusal'
  | 'context_window'

export interface SseEventMap {
  status: { stage: StatusStage }
  token: { text: string }
  citations: Citation[]
  usage: Usage
  done: { message_id: string; user_message_id: string; rewritten_query: string | null }
  error: { code: ErrorCode; message: string }
}
