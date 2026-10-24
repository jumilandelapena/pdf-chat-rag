import { Fragment, useEffect, useRef } from 'react'
import type { Citation, Message, StatusStage, Usage } from '../../api/types'
import { STAGE_TEXT, type StreamPhase, type StreamState } from '../../hooks/useChatStream'
import { splitAnswer, uniqueCitations } from '../../lib/citations'
import { formatCost, pageLabel } from '../../lib/format'
import { useViewer } from '../../state/viewer'

export function UserMessage({ content }: { content: string }) {
  return (
    <div className="ml-auto max-w-[85%] rounded-lg bg-blue-600 px-3 py-2 text-sm whitespace-pre-wrap text-white">
      {content}
    </div>
  )
}

export function CitationChip({ citation }: { citation: Citation }) {
  const viewer = useViewer()
  return (
    <button
      type="button"
      data-testid="citation-chip"
      data-n={citation.n}
      data-page={citation.page}
      data-document-id={citation.document_id}
      aria-label={`Citation ${citation.n}: ${citation.filename} page ${citation.page}`}
      title={citation.quote}
      onClick={() => viewer.open(citation)}
      className="mx-0.5 inline-flex rounded bg-blue-100 px-1 align-baseline text-xs font-medium text-blue-900 hover:bg-blue-200"
    >
      [{citation.n}]
    </button>
  )
}

export function AnswerText({ text, citations, caret = false }: { text: string; citations: Citation[]; caret?: boolean }) {
  const segments = splitAnswer(text, citations)
  return (
    <p className="leading-relaxed whitespace-pre-wrap">
      {segments.map((segment, i) =>
        segment.kind === 'text' ? (
          <Fragment key={i}>{segment.value}</Fragment>
        ) : (
          <CitationChip key={i} citation={segment.citation} />
        ),
      )}
      {caret && <span className="ml-0.5 animate-pulse text-blue-600">▍</span>}
    </p>
  )
}

export function CitationList({ citations }: { citations: Citation[] }) {
  const viewer = useViewer()
  const unique = uniqueCitations(citations)
  if (unique.length === 0) return null
  return (
    <ol aria-label="Sources" className="mt-2 space-y-0.5 text-xs">
      {unique.map((c) => (
        <li key={c.n}>
          <button
            type="button"
            className="text-blue-800 hover:underline"
            title={c.quote}
            onClick={() => viewer.open(c)}
          >
            [{c.n}] {pageLabel(c)}
          </button>
        </li>
      ))}
    </ol>
  )
}

export function CostLine({ usage }: { usage: Usage | null }) {
  if (!usage) return null
  return (
    <p data-testid="cost-line" className="mt-2 text-[11px] text-slate-500">
      {formatCost(usage)}
    </p>
  )
}

export function StreamingIndicator({ stage }: { stage: StatusStage | null }) {
  return (
    <p className="flex items-center gap-2 text-xs text-slate-500" data-testid="streaming-indicator">
      <span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
      {stage ? STAGE_TEXT[stage] : 'Connecting…'}
    </p>
  )
}

interface AssistantProps {
  content: string
  citations: Citation[]
  usage: Usage | null
  phase?: StreamPhase
  stage?: StatusStage | null
}

export function AssistantMessage({ content, citations, usage, phase = 'idle', stage = null }: AssistantProps) {
  const waiting = phase === 'connecting' || phase === 'status'
  return (
    <div data-testid="assistant-message" className="rounded-lg border border-slate-200 bg-white p-3 text-sm">
      {waiting && <StreamingIndicator stage={stage} />}
      {(content || !waiting) && <AnswerText text={content} citations={citations} caret={phase === 'streaming'} />}
      <CitationList citations={citations} />
      <CostLine usage={usage} />
    </div>
  )
}

export function MessageList({ messages, stream }: { messages: Message[]; stream: StreamState }) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const live = stream.phase !== 'idle' && stream.phase !== 'error'
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ block: 'end' })
  }, [messages.length, stream.text.length, stream.phase])
  return (
    <div role="log" aria-live="polite" className="flex flex-1 flex-col gap-3 overflow-y-auto p-3">
      {messages.length === 0 && !live && (
        <p className="text-sm text-slate-500">
          Ask a question about your documents. Every answer cites the exact page, and clicking a
          citation opens it in the viewer.
        </p>
      )}
      {messages.map((m) =>
        m.role === 'user' ? (
          <UserMessage key={m.id} content={m.content} />
        ) : (
          <AssistantMessage key={m.id} content={m.content} citations={m.citations} usage={m.usage} />
        ),
      )}
      {live && (
        <>
          <UserMessage content={stream.question} />
          <AssistantMessage
            content={stream.text}
            citations={stream.citations}
            usage={stream.usage}
            phase={stream.phase}
            stage={stream.stage}
          />
        </>
      )}
      <div ref={bottomRef} />
    </div>
  )
}
