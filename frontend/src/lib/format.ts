import type { Citation, Usage } from '../api/types'

export const formatInt = (n: number) => n.toLocaleString('en-US')

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}

export const pageLabel = (c: Pick<Citation, 'filename' | 'page'>) => `${c.filename} p.${c.page}`

export function formatCostValue(cost: number): string {
  if (cost === 0) return '$0.0000'
  if (cost < 0.0001) return '<$0.0001'
  return `$${cost.toFixed(4)}`
}

/** e.g. "6,410 in · 92 out · 6,300 cache write · $0.0339 · claude-haiku-5-5" */
export function formatCost(usage: Usage | null): string {
  if (!usage) return ''
  const parts = [`${formatInt(usage.input_tokens)} in`, `${formatInt(usage.output_tokens)} out`]
  if (usage.cache_read_input_tokens > 0) parts.push(`${formatInt(usage.cache_read_input_tokens)} cache read`)
  if (usage.cache_creation_input_tokens > 0) {
    parts.push(`${formatInt(usage.cache_creation_input_tokens)} cache write`)
  }
  if (usage.model === 'mock') parts.push('$0.0000 (mock)')
  else parts.push(formatCostValue(usage.cost_usd), usage.model)
  return parts.join(' · ')
}
