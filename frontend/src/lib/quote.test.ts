import { describe, expect, it } from 'vitest'
import { FIXTURE_ITEMS, QUOTE } from '../test/fixtures'
import { findQuoteRanges, foldText, renderItemHtml } from './quote'

describe('findQuoteRanges', () => {
  it('finds a quote spanning two items', () => {
    const items = [{ str: 'The quick brown', hasEOL: true }, { str: 'fox jumps', hasEOL: false }]
    const ranges = findQuoteRanges(items, 'brown fox')
    expect([...ranges.entries()]).toEqual([
      [0, [[10, 15]]],
      [1, [[0, 3]]],
    ])
  })

  it('matches the fixture quote across the pdf.js items', () => {
    const ranges = findQuoteRanges(FIXTURE_ITEMS, QUOTE)
    expect(ranges.get(0)).toEqual([[0, FIXTURE_ITEMS[0]!.str.length]])
    expect(ranges.get(1)).toEqual([[0, FIXTURE_ITEMS[1]!.str.length]])
  })

  it('folds curly quotes, dashes, ligatures, case and whitespace runs', () => {
    expect(foldText('“Fiﬁ’s  — Test”')).toBe('"fifi\'s - test"')
    const items = [{ str: 'a  “fiﬁne”   day' }]
    expect(findQuoteRanges(items, 'A "fifine" day').get(0)).toEqual([[0, 16]])
  })

  it('returns an empty map when nothing matches and falls back to the first 12 words', () => {
    expect(findQuoteRanges(FIXTURE_ITEMS, 'completely unrelated words here').size).toBe(0)
    const longQuote = `${QUOTE} plus some words that are not on the page at all`
    expect(findQuoteRanges(FIXTURE_ITEMS, longQuote).size).toBeGreaterThan(0)
    expect(findQuoteRanges(FIXTURE_ITEMS, '').size).toBe(0)
  })
})

describe('renderItemHtml', () => {
  it('escapes html and wraps ranges in mark elements', () => {
    expect(renderItemHtml('a<b', undefined)).toBe('a&lt;b')
    expect(renderItemHtml('a<b & c', [[0, 1], [4, 5]])).toBe(
      '<mark class="quote-hit">a</mark>&lt;b <mark class="quote-hit">&amp;</mark> c',
    )
  })
})
