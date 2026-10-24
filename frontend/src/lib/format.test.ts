import { describe, expect, it } from 'vitest'
import { usage } from '../test/fixtures'
import { formatBytes, formatCost, pageLabel } from './format'

describe('formatCost', () => {
  it('lists tokens, cache segments only when non-zero, cost and model', () => {
    expect(formatCost(usage({ input_tokens: 6410, output_tokens: 92, cache_creation_input_tokens: 6300, cost_usd: 0.0339 }))).toBe(
      '6,410 in · 92 out · 6,300 cache write · $0.0339 · claude-haiku-5-5',
    )
    expect(formatCost(usage({ cache_creation_input_tokens: 0, cache_read_input_tokens: 500, cost_usd: 0.00005 }))).toBe(
      '1,000 in · 20 out · 500 cache read · <$0.0001 · claude-haiku-5-5',
    )
    expect(formatCost(usage({ cache_creation_input_tokens: 0, cost_usd: 0 }))).toBe('1,000 in · 20 out · $0.0000 · claude-haiku-5-5')
  })

  it('marks mock usage and renders nothing for null', () => {
    expect(formatCost(usage({ input_tokens: 0, output_tokens: 0, cache_creation_input_tokens: 0, model: 'mock', cost_usd: 0 }))).toBe(
      '0 in · 0 out · $0.0000 (mock)',
    )
    expect(formatCost(null)).toBe('')
  })
})

describe('helpers', () => {
  it('formats bytes and page labels', () => {
    expect(formatBytes(500)).toBe('500 B')
    expect(formatBytes(13928)).toBe('14 KB')
    expect(formatBytes(1981801)).toBe('1.9 MB')
    expect(pageLabel({ filename: 'rfc2324-htcpcp.pdf', page: 5 })).toBe('rfc2324-htcpcp.pdf p.5')
  })
})
