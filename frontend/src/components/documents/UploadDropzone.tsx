import { useState } from 'react'
import { cx } from '../../lib/cx'

interface Props {
  onFiles: (files: File[]) => void
  busy: boolean
}

export function UploadDropzone({ onFiles, busy }: Props) {
  const [dragging, setDragging] = useState(false)
  return (
    <div>
      <label
        htmlFor="pdf-upload"
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          onFiles([...e.dataTransfer.files])
        }}
        className={cx(
          'block cursor-pointer rounded-lg border-2 border-dashed px-3 py-4 text-center text-sm font-medium',
          dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 hover:border-blue-400',
          busy && 'opacity-60',
        )}
      >
        Upload PDFs
        <input
          id="pdf-upload"
          type="file"
          accept="application/pdf,.pdf"
          multiple
          disabled={busy}
          className="sr-only"
          onChange={(e) => {
            onFiles([...(e.target.files ?? [])])
            e.target.value = ''
          }}
        />
      </label>
      <p className="mt-1 text-xs text-slate-500">Drop files or click to choose. Max 50 MiB each, 5 per upload.</p>
    </div>
  )
}
