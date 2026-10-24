import type { Chat, Citation, Document, Message, Usage } from '../api/types'

/** Two pdf.js text items; the quote below spans both of them. */
export const FIXTURE_ITEMS = [
  { str: 'Any attempt to brew coffee with a teapot should result in the', hasEOL: true },
  { str: 'error code "418 I’m a teapot".', hasEOL: false },
]

export const QUOTE = 'Any attempt to brew coffee with a teapot should result in the error code "418 I\'m a teapot".'

export const citation = (overrides: Partial<Citation> = {}): Citation => ({
  n: 1,
  document_id: 'd1',
  filename: 'rfc2324-htcpcp.pdf',
  page: 5,
  quote: QUOTE,
  text_start: 0,
  text_end: 20,
  chunk_id: 'd1:00004',
  page_char_start: 100,
  page_char_end: 190,
  ...overrides,
})

export const usage = (overrides: Partial<Usage> = {}): Usage => ({
  input_tokens: 1000,
  output_tokens: 20,
  cache_read_input_tokens: 0,
  cache_creation_input_tokens: 900,
  thinking_tokens: 0,
  model: 'claude-haiku-5-5',
  cost_usd: 0.0002,
  ...overrides,
})

export const document = (overrides: Partial<Document> = {}): Document => ({
  id: 'd1',
  filename: 'rfc2324-htcpcp.pdf',
  status: 'ready',
  error: null,
  page_count: 10,
  chunk_count: 12,
  scanned_pages: 0,
  size_bytes: 13928,
  created_at: '2026-10-24T10:00:00Z',
  ...overrides,
})

export const message = (overrides: Partial<Message> = {}): Message => ({
  id: 'm1',
  role: 'assistant',
  content: 'The pot returns 418. Done.',
  citations: [],
  usage: null,
  rewritten_query: null,
  created_at: '2026-10-24T10:01:00Z',
  ...overrides,
})

export const chat = (overrides: Partial<Chat> = {}): Chat => ({
  id: 'c1',
  title: 'Teapots',
  document_ids: [],
  created_at: '2026-10-24T10:00:00Z',
  updated_at: '2026-10-24T10:01:00Z',
  message_count: 0,
  messages: [],
  ...overrides,
})
