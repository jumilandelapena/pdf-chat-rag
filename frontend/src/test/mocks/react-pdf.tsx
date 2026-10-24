import { useEffect, type ReactNode, type RefObject } from 'react'
import { FIXTURE_ITEMS } from '../fixtures'

export const pdfjs = { GlobalWorkerOptions: { workerSrc: '' }, version: '5.4.296' }

interface DocumentProps {
  file?: unknown
  children?: ReactNode
  onLoadSuccess?: (doc: { numPages: number }) => void
  onLoadError?: (error: Error) => void
  loading?: ReactNode
  error?: ReactNode
  options?: unknown
  onItemClick?: unknown
}

export function Document({ file, children, onLoadSuccess, onLoadError }: DocumentProps) {
  const url = typeof file === 'string' ? file : ''
  useEffect(() => {
    if (url.includes('missing')) onLoadError?.(new Error('missing'))
    else onLoadSuccess?.({ numPages: 10 })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url])
  return (
    <div data-testid="pdf-document" data-file={url}>
      {children}
    </div>
  )
}

interface PageProps {
  pageNumber: number
  width?: number
  customTextRenderer?: (props: { str: string; itemIndex: number; pageIndex: number; pageNumber: number }) => string
  onGetTextSuccess?: (content: { items: unknown[]; styles: object }) => void
  onRenderTextLayerSuccess?: () => void
  inputRef?: RefObject<HTMLDivElement>
  renderAnnotationLayer?: boolean
}

export function Page({ pageNumber, width, customTextRenderer, onGetTextSuccess, onRenderTextLayerSuccess, inputRef }: PageProps) {
  useEffect(() => {
    onGetTextSuccess?.({ items: FIXTURE_ITEMS, styles: {} })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageNumber])
  const html = FIXTURE_ITEMS.map((item, i) => {
    const inner = customTextRenderer
      ? customTextRenderer({ str: item.str, itemIndex: i, pageIndex: pageNumber - 1, pageNumber })
      : item.str
    return `<span>${inner}</span>`
  }).join('')
  useEffect(() => {
    onRenderTextLayerSuccess?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [html, customTextRenderer])
  return (
    <div ref={inputRef} data-testid="pdf-page" data-page-number={pageNumber} style={{ width }}>
      <div className="react-pdf__Page__textContent" dangerouslySetInnerHTML={{ __html: html }} />
    </div>
  )
}
