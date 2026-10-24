import { useState } from 'react'
import type { ChatSummary } from '../../api/types'

interface Props {
  chats: ChatSummary[]
  activeChatId: string | null
  onSelect: (id: string | null) => void
  onDelete: (id: string) => void
}

export function ChatSwitcher({ chats, activeChatId, onSelect, onDelete }: Props) {
  const [confirming, setConfirming] = useState(false)
  const buttonClass = 'rounded border border-slate-300 px-2 py-1 text-xs hover:bg-slate-50'
  return (
    <div className="flex items-center gap-2 border-b border-slate-200 bg-white p-2">
      <select
        aria-label="Chat"
        value={activeChatId ?? ''}
        onChange={(e) => onSelect(e.target.value || null)}
        className="min-w-0 flex-1 rounded border border-slate-300 px-2 py-1 text-sm"
      >
        <option value="">New chat</option>
        {chats.map((c) => (
          <option key={c.id} value={c.id}>
            {c.title || 'Untitled chat'} ({Math.floor(c.message_count / 2)})
          </option>
        ))}
      </select>
      <button type="button" className={buttonClass} onClick={() => onSelect(null)}>
        New chat
      </button>
      {activeChatId &&
        (confirming ? (
          <>
            <button
              type="button"
              aria-label="Confirm delete chat"
              className="rounded bg-red-600 px-2 py-1 text-xs text-white"
              onClick={() => {
                setConfirming(false)
                onDelete(activeChatId)
              }}
            >
              Confirm
            </button>
            <button type="button" className={buttonClass} onClick={() => setConfirming(false)}>
              Cancel
            </button>
          </>
        ) : (
          <button type="button" aria-label="Delete chat" className={buttonClass} onClick={() => setConfirming(true)}>
            Delete
          </button>
        ))}
    </div>
  )
}
