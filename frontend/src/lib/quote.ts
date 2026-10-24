/** Locate a cited quote inside the pdf.js text layer items, tolerant to whitespace and glyph differences. */

export interface TextItemLike {
  str: string
  hasEOL?: boolean
}

export type ItemRanges = Map<number, [number, number][]>

interface Origin {
  item: number
  start: number
  end: number
}

function foldChar(ch: string): string {
  return ch
    .normalize('NFKC')
    .replace(/[‘’‚‛′]/g, "'")
    .replace(/[“”„‟″]/g, '"')
    .replace(/[‐-―−­]/g, '-')
    .toLowerCase()
}

export function foldText(text: string): string {
  let out = ''
  for (const ch of text) {
    const folded = foldChar(ch)
    for (const f of folded) {
      if (/\s/.test(f)) {
        if (!out.endsWith(' ')) out += ' '
      } else out += f
    }
  }
  return out.trim()
}

function buildHaystack(items: TextItemLike[]): { text: string; origins: (Origin | null)[] } {
  let text = ''
  const origins: (Origin | null)[] = []
  const pushSpace = () => {
    if (text.endsWith(' ') || text === '') return
    text += ' '
    origins.push(null)
  }
  items.forEach((item, itemIndex) => {
    let offset = 0
    for (const ch of item.str) {
      const start = offset
      offset += ch.length
      for (const f of foldChar(ch)) {
        if (/\s/.test(f)) pushSpace()
        else {
          text += f
          origins.push({ item: itemIndex, start, end: offset })
        }
      }
    }
    if (item.hasEOL) pushSpace()
  })
  return { text, origins }
}

function mergeRanges(ranges: [number, number][]): [number, number][] {
  const sorted = [...ranges].sort((a, b) => a[0] - b[0])
  const out: [number, number][] = []
  for (const [s, e] of sorted) {
    const last = out[out.length - 1]
    if (last && s <= last[1]) last[1] = Math.max(last[1], e)
    else out.push([s, e])
  }
  return out
}

function locate(haystack: string, origins: (Origin | null)[], needle: string): ItemRanges {
  const result: ItemRanges = new Map()
  if (!needle) return result
  let from = 0
  for (;;) {
    const at = haystack.indexOf(needle, from)
    if (at === -1) break
    for (let i = at; i < at + needle.length; i++) {
      const origin = origins[i]
      if (!origin) continue
      const list = result.get(origin.item) ?? []
      list.push([origin.start, origin.end])
      result.set(origin.item, list)
    }
    from = at + Math.max(needle.length, 1)
  }
  for (const [item, ranges] of result) result.set(item, mergeRanges(ranges))
  return result
}

/** Ranges (per text item, in code units of `item.str`) covering every occurrence of `quote`. */
export function findQuoteRanges(items: TextItemLike[], quote: string): ItemRanges {
  const needle = foldText(quote)
  if (!needle) return new Map()
  const { text, origins } = buildHaystack(items)
  const full = locate(text, origins, needle)
  if (full.size > 0) return full
  const words = needle.split(' ')
  if (words.length <= 12) return full
  return locate(text, origins, words.slice(0, 12).join(' '))
}

export function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/** HTML for one text-layer item with `<mark>` around the given ranges. */
export function renderItemHtml(str: string, ranges: [number, number][] | undefined): string {
  if (!ranges || ranges.length === 0) return escapeHtml(str)
  let html = ''
  let pos = 0
  for (const [s, e] of ranges) {
    html += escapeHtml(str.slice(pos, s))
    html += `<mark class="quote-hit">${escapeHtml(str.slice(s, e))}</mark>`
    pos = e
  }
  return html + escapeHtml(str.slice(pos))
}
