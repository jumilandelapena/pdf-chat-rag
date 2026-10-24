interface Props {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onStop: () => void
  busy: boolean
  disabled: boolean
}

export function Composer({ value, onChange, onSubmit, onStop, busy, disabled }: Props) {
  return (
    <form
      className="border-t border-slate-200 bg-white p-3"
      onSubmit={(e) => {
        e.preventDefault()
        onSubmit()
      }}
    >
      <textarea
        aria-label="Ask a question"
        rows={2}
        value={value}
        disabled={disabled || busy}
        placeholder={disabled ? 'Upload a PDF first' : 'Ask a question about your documents…'}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            onSubmit()
          }
        }}
        className="w-full resize-none rounded border border-slate-300 p-2 text-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-50"
      />
      <div className="mt-2 flex items-center gap-2">
        <button
          type="submit"
          disabled={disabled || busy || !value.trim()}
          className="rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Send
        </button>
        {busy && (
          <button
            type="button"
            onClick={onStop}
            className="rounded border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50"
          >
            Stop
          </button>
        )}
        <span className="text-xs text-slate-400">Enter to send · Shift+Enter for a new line</span>
      </div>
    </form>
  )
}
