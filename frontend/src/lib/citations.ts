import type { Citation } from '../api/types'

export type Segment = { kind: 'text'; value: string } | { kind: 'chip'; citation: Citation }

/** Split the answer into text runs and citation chips placed at each citation's `text_end`. */
export function splitAnswer(text: string, citations: Citation[]): Segment[] {
  const sorted = [...citations].sort((a, b) => a.text_end - b.text_end || a.n - b.n)
  const segments: Segment[] = []
  let pos = 0
  for (const citation of sorted) {
    const end = Math.min(Math.max(citation.text_end, 0), text.length)
    if (end > pos) {
      segments.push({ kind: 'text', value: text.slice(pos, end) })
      pos = end
    }
    segments.push({ kind: 'chip', citation })
  }
  if (pos < text.length || segments.length === 0) {
    segments.push({ kind: 'text', value: text.slice(pos) })
  }
  return segments
}

/** One entry per citation number, in order of first appearance. */
export function uniqueCitations(citations: Citation[]): Citation[] {
  const seen = new Map<number, Citation>()
  for (const c of [...citations].sort((a, b) => a.n - b.n)) {
    if (!seen.has(c.n)) seen.set(c.n, c)
  }
  return [...seen.values()]
}
