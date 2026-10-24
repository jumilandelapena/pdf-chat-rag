import { describe, expect, it } from 'vitest'
import { citation } from '../test/fixtures'
import { splitAnswer, uniqueCitations } from './citations'

describe('splitAnswer', () => {
  it('places a chip at text_end', () => {
    const segments = splitAnswer('The pot returns 418. Done.', [citation({ text_end: 20 })])
    expect(segments).toEqual([
      { kind: 'text', value: 'The pot returns 418.' },
      { kind: 'chip', citation: citation({ text_end: 20 }) },
      { kind: 'text', value: ' Done.' },
    ])
  })

  it('keeps n order for chips at the same offset and clamps out-of-range offsets', () => {
    const segments = splitAnswer('abc', [citation({ n: 2, text_end: 99 }), citation({ n: 1, text_end: 99 })])
    expect(segments.map((s) => (s.kind === 'chip' ? s.citation.n : s.value))).toEqual(['abc', 1, 2])
    expect(splitAnswer('abc', [])).toEqual([{ kind: 'text', value: 'abc' }])
    expect(splitAnswer('', [])).toEqual([{ kind: 'text', value: '' }])
  })

  it('uses UTF-16 offsets (an emoji counts as two units)', () => {
    const segments = splitAnswer('Hi \u{1F600} there. Done.', [citation({ text_end: 12 })])
    expect(segments[0]).toEqual({ kind: 'text', value: 'Hi \u{1F600} there.' })
  })
})

describe('uniqueCitations', () => {
  it('keeps one entry per n in numeric order', () => {
    const list = uniqueCitations([citation({ n: 2, text_end: 5 }), citation({ n: 1 }), citation({ n: 2, text_end: 9 })])
    expect(list.map((c) => [c.n, c.text_end])).toEqual([
      [1, 20],
      [2, 5],
    ])
  })
})
