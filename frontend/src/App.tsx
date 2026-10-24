import { useEffect, useState } from 'react'
import { API_BASE } from './api/base'
import { AppLayout } from './components/AppLayout'
import { useBackendHealth } from './hooks/useBackendHealth'
import { useChats } from './hooks/useChats'
import { cx } from './lib/cx'

export const ACTIVE_CHAT_KEY = 'pdfchat.activeChat'

function readStoredChatId(): string | undefined {
  try {
    return localStorage.getItem(ACTIVE_CHAT_KEY) ?? undefined
  } catch {
    return undefined
  }
}

export default function App() {
  const { health, showBanner } = useBackendHealth()
  const chats = useChats()
  // undefined = nothing chosen yet (fall back to the newest chat); null = explicit "New chat"
  const [activeChatId, setActiveChatId] = useState<string | null | undefined>(readStoredChatId)

  useEffect(() => {
    try {
      if (activeChatId) localStorage.setItem(ACTIVE_CHAT_KEY, activeChatId)
      else if (activeChatId === null) localStorage.removeItem(ACTIVE_CHAT_KEY)
    } catch {
      /* storage unavailable */
    }
  }, [activeChatId])

  useEffect(() => {
    if (!chats.data || activeChatId === null) return
    if (activeChatId === undefined || !chats.data.some((c) => c.id === activeChatId)) {
      setActiveChatId(chats.data[0]?.id ?? null)
    }
  }, [chats.data, activeChatId])

  return (
    <div className="flex min-h-dvh flex-col bg-slate-50 text-slate-900 lg:h-dvh">
      <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-2">
        <h1 className="text-base font-semibold">Chat with your PDFs</h1>
        {health && (
          <span
            data-testid="provider-badge"
            className={cx(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              health.llm_provider === 'anthropic'
                ? 'bg-green-100 text-green-900'
                : 'bg-amber-100 text-amber-900',
            )}
          >
            provider: {health.llm_provider}
            {health.llm_provider === 'anthropic' ? ` · ${health.answer_model}` : ''}
          </span>
        )}
        <a
          href={`${API_BASE}/docs`}
          target="_blank"
          rel="noreferrer"
          className="ml-auto text-xs text-blue-700 hover:underline"
        >
          API docs
        </a>
      </header>
      {showBanner && (
        <div role="status" className="bg-amber-100 px-4 py-2 text-sm text-amber-900">
          Waking up the server… free-tier hosts need about a minute.
        </div>
      )}
      <AppLayout activeChatId={activeChatId ?? null} onSelectChat={setActiveChatId} />
    </div>
  )
}
