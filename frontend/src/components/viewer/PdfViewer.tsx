import { useEffect, useMemo, useState } from 'react'
import { Document, pdfjs } from 'react-pdf'
import 'react-pdf/dist/Page/TextLayer.css'
import 'react-pdf/dist/Page/AnnotationLayer.css'
import './PdfViewer.css'
import { documentFileUrl } from '../../api/client'
import { useContainerWidth } from '../../hooks/useContainerWidth'
import { useDocuments } from '../../hooks/useDocuments'
import { useViewer, type ActiveCitation } from '../../state/viewer'
import { HighlightedPage, type LayerState } from './HighlightedPage'
import { CitedPassage, ViewerToolbar } from './ViewerToolbar'

pdfjs.GlobalWorkerOptions.workerSrc = new URL(
  'pdfjs-dist/build/pdf.worker.min.mjs',
  import.meta.url,
).toString()

const documentOptions = {}

export function PdfViewer() {
  const { active } = useViewer()
  const documents = useDocuments()
  if (!active) {
    return <p className="p-4 text-sm text-slate-500">Click a citation to open the cited page here.</p>
  }
  if (documents.data && !documents.data.some((d) => d.id === active.document_id)) {
    return (
      <p role="alert" className="p-4 text-sm text-slate-700">
        This document was deleted.
      </p>
    )
  }
  return <ViewerBody key={active.document_id} active={active} />
}

function ViewerBody({ active }: { active: ActiveCitation }) {
  const [numPages, setNumPages] = useState<number | null>(null)
  const [page, setPage] = useState(active.page)
  const [layer, setLayer] = useState<LayerState>('pending')
  const [containerRef, containerWidth] = useContainerWidth<HTMLDivElement>(640)

  useEffect(() => {
    setPage(active.page)
    setLayer('pending')
  }, [active.nonce, active.page])

  const total = numPages ?? Math.max(active.page, 1)
  const current = Math.min(Math.max(page, 1), total)
  const width = Math.max(320, Math.min(containerWidth - 16, 1200))
  const file = useMemo(() => documentFileUrl(active.document_id), [active.document_id])

  return (
    <div ref={containerRef} className="flex flex-col gap-2 p-2">
      <ViewerToolbar filename={active.filename} page={current} numPages={numPages} onPage={setPage} fileUrl={file} />
      <CitedPassage quote={active.quote} notFound={layer === 'miss'} />
      <Document
        file={file}
        options={documentOptions}
        loading={<p className="p-4 text-sm text-slate-500">Loading PDF…</p>}
        error={
          <p role="alert" className="p-4 text-sm text-red-700">
            Failed to load the PDF (it may have been deleted).
          </p>
        }
        onLoadSuccess={({ numPages: n }) => setNumPages(n)}
        onItemClick={({ pageNumber }) => setPage(pageNumber)}
      >
        {numPages !== null && (
          <HighlightedPage
            key={`${active.document_id}:${current}`}
            pageNumber={current}
            quote={active.quote}
            width={width}
            nonce={active.nonce}
            onLayerReady={setLayer}
          />
        )}
      </Document>
    </div>
  )
}
