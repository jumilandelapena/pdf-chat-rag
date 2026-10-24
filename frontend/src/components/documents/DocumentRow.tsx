import { useEffect, useState } from 'react'
import type { Document, DocumentStatus } from '../../api/types'
import { cx } from '../../lib/cx'
import { formatBytes } from '../../lib/format'

const BADGE: Record<DocumentStatus, string> = {
  processing: 'bg-amber-100 text-amber-900',
  ready: 'bg-green-100 text-green-900',
  failed: 'bg-red-100 text-red-900',
}

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      data-testid="doc-status"
      data-status={status}
      role="status"
      className={cx('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium', BADGE[status])}
    >
      {status === 'processing' && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-600" />}
      {status}
    </span>
  )
}

interface Props {
  doc: Document
  checked: boolean
  lockChecked: boolean
  onToggle: (checked: boolean) => void
  onDelete: () => void
}

export function DocumentRow({ doc, checked, lockChecked, onToggle, onDelete }: Props) {
  const [confirming, setConfirming] = useState(false)
  useEffect(() => {
    if (!confirming) return undefined
    const timer = setTimeout(() => setConfirming(false), 4000)
    return () => clearTimeout(timer)
  }, [confirming])
  const locked = checked && lockChecked
  const scanned = doc.scanned_pages > 0 ? ` · ${doc.scanned_pages} scanned page${doc.scanned_pages > 1 ? 's' : ''}` : ''
  const details =
    doc.status === 'ready'
      ? `${doc.page_count ?? 0} pages · ${doc.chunk_count ?? 0} chunks${scanned}`
      : formatBytes(doc.size_bytes)
  return (
    <li data-testid="doc-row" className="flex items-start gap-2 border-b border-slate-100 py-2">
      <input
        type="checkbox"
        aria-label={`Include ${doc.filename} in chat scope`}
        className="mt-1"
        checked={checked}
        disabled={doc.status !== 'ready' || locked}
        title={locked ? 'At least one document must stay in scope' : undefined}
        onChange={(e) => onToggle(e.target.checked)}
      />
      <div className="min-w-0 flex-1">
        <div className="truncate text-sm font-medium" title={doc.filename}>
          {doc.filename}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <StatusBadge status={doc.status} />
          <span>{details}</span>
        </div>
        {doc.status === 'failed' && doc.error && <p className="mt-1 text-xs text-red-700">{doc.error}</p>}
      </div>
      {confirming ? (
        <span className="flex shrink-0 gap-1">
          <button
            type="button"
            aria-label={`Confirm delete ${doc.filename}`}
            className="rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white"
            onClick={() => {
              setConfirming(false)
              onDelete()
            }}
          >
            Confirm delete
          </button>
          <button
            type="button"
            className="rounded border border-slate-300 px-2 py-0.5 text-xs"
            onClick={() => setConfirming(false)}
          >
            Cancel
          </button>
        </span>
      ) : (
        <button
          type="button"
          aria-label={`Delete ${doc.filename}`}
          className="shrink-0 rounded px-2 py-0.5 text-xs text-slate-500 hover:bg-slate-100 hover:text-red-700"
          onClick={() => setConfirming(true)}
        >
          Delete
        </button>
      )}
    </li>
  )
}
