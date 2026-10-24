import { useState } from 'react'
import type { Chat } from '../../api/types'
import { usePatchScope } from '../../hooks/useChats'
import { useDeleteDocument, useDocuments, useUploadDocuments } from '../../hooks/useDocuments'
import { DocumentRow } from './DocumentRow'
import { UploadDropzone } from './UploadDropzone'

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024
export const MAX_UPLOAD_FILES = 5

interface Props {
  chat: Chat | null
  pendingScope: string[]
  onPendingScopeChange: (ids: string[]) => void
}

export function DocumentsPanel({ chat, pendingScope, onPendingScopeChange }: Props) {
  const docs = useDocuments()
  const upload = useUploadDocuments()
  const remove = useDeleteDocument()
  const patchScope = usePatchScope(chat?.id ?? '')
  const [clientError, setClientError] = useState<string | null>(null)

  const documents = docs.data ?? []
  const readyIds = documents.filter((d) => d.status === 'ready').map((d) => d.id)
  const scope = chat ? chat.document_ids : pendingScope
  const isChecked = (id: string) => scope.length === 0 || scope.includes(id)
  const checkedReady = readyIds.filter(isChecked)

  const toggle = (id: string, checked: boolean) => {
    const next = checked ? [...new Set([...checkedReady, id])] : checkedReady.filter((x) => x !== id)
    const all = next.length === readyIds.length && readyIds.every((x) => next.includes(x))
    const payload = all ? [] : next
    if (chat) patchScope.mutate(payload)
    else onPendingScopeChange(payload)
  }

  const onFiles = (files: File[]) => {
    setClientError(null)
    if (files.length === 0) return
    if (files.length > MAX_UPLOAD_FILES) {
      setClientError(`Upload at most ${MAX_UPLOAD_FILES} files at a time`)
      return
    }
    for (const file of files) {
      if (!file.name.toLowerCase().endsWith('.pdf') && file.type !== 'application/pdf') {
        setClientError(`${file.name} is not a PDF`)
        return
      }
      if (file.size > MAX_UPLOAD_BYTES) {
        setClientError(`${file.name} exceeds 50 MiB`)
        return
      }
    }
    upload.mutate(files)
  }

  const error = clientError ?? upload.error?.message ?? remove.error?.message ?? null

  return (
    <div className="p-3">
      <h2 className="mb-2 text-sm font-semibold">
        Documents <span className="font-normal text-slate-500">({documents.length})</span>
      </h2>
      <UploadDropzone onFiles={onFiles} busy={upload.isPending} />
      {error && (
        <p role="alert" className="mt-2 text-xs text-red-700">
          {error}
        </p>
      )}
      <ul className="mt-2">
        {documents.map((doc) => (
          <DocumentRow
            key={doc.id}
            doc={doc}
            checked={isChecked(doc.id)}
            lockChecked={checkedReady.length === 1}
            onToggle={(checked) => toggle(doc.id, checked)}
            onDelete={() => remove.mutate(doc.id)}
          />
        ))}
      </ul>
      {documents.length === 0 && docs.isSuccess && (
        <p className="mt-3 text-xs text-slate-500">No documents yet. Upload a PDF to start.</p>
      )}
      {documents.length > 0 && (
        <p className="mt-2 text-[11px] text-slate-400">Checked documents are searched in the current chat.</p>
      )}
    </div>
  )
}
