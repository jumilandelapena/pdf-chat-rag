import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Page } from 'react-pdf'
import { findQuoteRanges, renderItemHtml, type TextItemLike } from '../../lib/quote'

export type LayerState = 'pending' | 'hit' | 'miss'

interface Props {
  pageNumber: number
  quote: string
  width: number
  nonce: number
  onLayerReady: (state: LayerState) => void
}

const isTextItem = (item: unknown): item is TextItemLike =>
  typeof item === 'object' && item !== null && typeof (item as { str?: unknown }).str === 'string'

function scrollToHit(root: HTMLElement | null) {
  root?.querySelector('mark.quote-hit')?.scrollIntoView({ block: 'center' })
}

/** One PDF page whose text layer wraps every occurrence of the quote in `<mark>`. */
export function HighlightedPage({ pageNumber, quote, width, nonce, onLayerReady }: Props) {
  const [items, setItems] = useState<TextItemLike[]>([])
  const pageRef = useRef<HTMLDivElement>(null)
  const ranges = useMemo(() => findQuoteRanges(items, quote), [items, quote])

  const customTextRenderer = useCallback(
    ({ str, itemIndex }: { str: string; itemIndex: number }) => renderItemHtml(str, ranges.get(itemIndex)),
    [ranges],
  )
  const onGetTextSuccess = useCallback((content: { items: unknown[] }) => {
    setItems(content.items.filter(isTextItem))
  }, [])
  const onRenderTextLayerSuccess = useCallback(() => {
    scrollToHit(pageRef.current)
    onLayerReady(items.length === 0 ? 'pending' : ranges.size > 0 ? 'hit' : 'miss')
  }, [items.length, ranges, onLayerReady])

  useEffect(() => {
    scrollToHit(pageRef.current)
  }, [nonce])

  return (
    <Page
      inputRef={pageRef}
      pageNumber={pageNumber}
      width={width}
      customTextRenderer={customTextRenderer}
      onGetTextSuccess={onGetTextSuccess}
      onRenderTextLayerSuccess={onRenderTextLayerSuccess}
      renderAnnotationLayer={false}
    />
  )
}
