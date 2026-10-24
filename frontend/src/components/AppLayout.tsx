import { useEffect, useRef, useState } from 'react'
import { useChat } from '../hooks/useChats'
import { useViewer } from '../state/viewer'
import { ChatPanel } from './chat/ChatPanel'
import { DocumentsPanel } from './documents/DocumentsPanel'
import { PdfViewer } from './viewer/PdfViewer'

interface Props {
  activeChatId: string | null
  onSelectChat: (id: string | null) => void
}

export function AppLayout({ activeChatId, onSelectChat }: Props) {
  const { active } = useViewer()
  const viewerRef = useRef<HTMLElement>(null)
  const chat = useChat(activeChatId)
  // scope chosen before the first message creates the chat ([] = all ready documents)
  const [pendingScope, setPendingScope] = useState<string[]>([])

  useEffect(() => {
    if (!active) return
    if (typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 1023px)').matches) {
      viewerRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [active])

  return (
    <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[300px_minmax(0,1fr)_minmax(380px,42%)] lg:overflow-hidden">
      <section
        aria-label="Documents"
        className="min-w-0 border-b border-slate-200 bg-white lg:border-r lg:border-b-0 lg:overflow-y-auto"
      >
        <DocumentsPanel
          chat={chat.data ?? null}
          pendingScope={pendingScope}
          onPendingScopeChange={setPendingScope}
        />
      </section>
      <section aria-label="Chat" className="flex min-h-[60dvh] min-w-0 flex-col lg:min-h-0 lg:overflow-hidden">
        <ChatPanel activeChatId={activeChatId} onSelectChat={onSelectChat} pendingScope={pendingScope} />
      </section>
      <section
        ref={viewerRef}
        aria-label="PDF viewer"
        className="min-w-0 border-t border-slate-200 bg-slate-100 lg:border-l lg:border-t-0 lg:overflow-y-auto"
      >
        <PdfViewer />
      </section>
    </div>
  )
}
