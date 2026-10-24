import { useEffect, useState } from 'react'
import type { ErrorCode } from '../../api/types'
import { useChatStream } from '../../hooks/useChatStream'
import { useChat, useChats, useCreateChat, useDeleteChat } from '../../hooks/useChats'
import { useDocuments } from '../../hooks/useDocuments'
import { ChatSwitcher } from './ChatSwitcher'
import { Composer } from './Composer'
import { MessageList } from './Messages'

function ErrorNotice({ message, code }: { message: string | null; code: ErrorCode | null }) {
  return (
    <div role="alert" className="mx-3 mb-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      {message}
      {code === 'no_documents' && ' Upload a PDF and wait for the ready badge.'}
    </div>
  )
}

interface Props {
  activeChatId: string | null
  onSelectChat: (id: string | null) => void
  pendingScope: string[]
}

export function ChatPanel({ activeChatId, onSelectChat, pendingScope }: Props) {
  const chats = useChats()
  const chat = useChat(activeChatId)
  const documents = useDocuments()
  const createChat = useCreateChat()
  const deleteChat = useDeleteChat()
  const { state, send, stop } = useChatStream()
  const [draft, setDraft] = useState('')

  const hasReady = (documents.data ?? []).some((d) => d.status === 'ready')
  const busy = state.phase !== 'idle' && state.phase !== 'error'

  useEffect(() => {
    if (state.phase === 'error' && state.question) setDraft(state.question)
  }, [state.phase, state.question])

  const submit = async () => {
    const content = draft.trim()
    if (!content || busy || !hasReady) return
    let chatId = activeChatId
    if (!chatId) {
      try {
        const created = await createChat.mutateAsync({ document_ids: pendingScope })
        chatId = created.id
        onSelectChat(chatId)
      } catch {
        return
      }
    }
    setDraft('')
    void send(chatId, content)
  }

  const showStream = state.chatId === activeChatId || (activeChatId === null && state.phase !== 'idle')
  const messages = chat.data?.messages ?? []

  return (
    <div className="flex h-full min-h-0 flex-col">
      <ChatSwitcher
        chats={chats.data ?? []}
        activeChatId={activeChatId}
        onSelect={onSelectChat}
        onDelete={(id) =>
          deleteChat.mutate(id, {
            onSuccess: () => {
              if (id === activeChatId) onSelectChat(null)
            },
          })
        }
      />
      <MessageList messages={messages} stream={showStream ? state : { ...state, phase: 'idle' }} />
      {state.phase === 'error' && <ErrorNotice message={state.error} code={state.errorCode} />}
      {createChat.error && <ErrorNotice message={createChat.error.message} code={null} />}
      <Composer
        value={draft}
        onChange={setDraft}
        onSubmit={() => void submit()}
        onStop={stop}
        busy={busy}
        disabled={!hasReady}
      />
    </div>
  )
}
