import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import type { Citation } from '../api/types'

export interface ActiveCitation {
  document_id: string
  filename: string
  page: number
  quote: string
  /** Changes on every open() so re-clicking the same chip re-centres the page. */
  nonce: number
}

interface ViewerContextValue {
  active: ActiveCitation | null
  open: (citation: Pick<Citation, 'document_id' | 'filename' | 'page' | 'quote'>) => void
  close: () => void
}

const ViewerContext = createContext<ViewerContextValue | null>(null)

export function ViewerProvider({ children }: { children: ReactNode }) {
  const [active, setActive] = useState<ActiveCitation | null>(null)
  const open = useCallback<ViewerContextValue['open']>((c) => {
    setActive({
      document_id: c.document_id,
      filename: c.filename,
      page: c.page,
      quote: c.quote,
      nonce: Date.now() + Math.random(),
    })
  }, [])
  const close = useCallback(() => setActive(null), [])
  const value = useMemo(() => ({ active, open, close }), [active, open, close])
  return <ViewerContext.Provider value={value}>{children}</ViewerContext.Provider>
}

export function useViewer(): ViewerContextValue {
  const ctx = useContext(ViewerContext)
  if (!ctx) throw new Error('useViewer must be used inside ViewerProvider')
  return ctx
}
