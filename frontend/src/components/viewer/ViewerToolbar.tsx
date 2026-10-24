interface ToolbarProps {
  filename: string
  page: number
  numPages: number | null
  onPage: (page: number) => void
  fileUrl: string
}

const BUTTON = 'rounded border border-slate-300 bg-white px-2 py-0.5 text-sm hover:bg-slate-50 disabled:opacity-40'

export function ViewerToolbar({ filename, page, numPages, onPage, fileUrl }: ToolbarProps) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      <span className="max-w-[40%] truncate font-medium" title={filename}>
        {filename}
      </span>
      <button type="button" aria-label="Previous page" className={BUTTON} disabled={page <= 1} onClick={() => onPage(page - 1)}>
        ‹
      </button>
      <label className="flex items-center gap-1 text-xs">
        Page
        <input
          type="number"
          aria-label="Page number"
          min={1}
          max={numPages ?? undefined}
          value={page}
          onChange={(e) => {
            const value = Number(e.target.value)
            if (Number.isFinite(value) && value > 0) onPage(value)
          }}
          className="w-14 rounded border border-slate-300 px-1 py-0.5 text-sm"
        />
      </label>
      <span data-testid="viewer-page-indicator" className="text-xs text-slate-600">
        Page {page} of {numPages ?? '…'}
      </span>
      <button
        type="button"
        aria-label="Next page"
        className={BUTTON}
        disabled={numPages !== null && page >= numPages}
        onClick={() => onPage(page + 1)}
      >
        ›
      </button>
      <a href={fileUrl} target="_blank" rel="noreferrer" className="ml-auto text-xs text-blue-700 hover:underline">
        Open PDF
      </a>
    </div>
  )
}

export function CitedPassage({ quote, notFound }: { quote: string; notFound: boolean }) {
  return (
    <blockquote
      data-testid="cited-passage"
      className="rounded border-l-4 border-yellow-400 bg-yellow-50 px-3 py-2 text-xs text-slate-700"
    >
      <span className="font-medium">Cited passage: </span>“{quote.trim()}”
      {notFound && (
        <span className="mt-1 block text-slate-500">
          Exact text not found on this page; showing the cited passage.
        </span>
      )}
    </blockquote>
  )
}
