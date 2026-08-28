import { useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { GeneratedResponse, Prompt } from '../api/types'

const MODELS = ['claude-opus-5', 'claude-sonnet-5', 'claude-haiku-4-5']

function PromptCard({ prompt }: { prompt: Prompt }) {
  const [responses, setResponses] = useState<GeneratedResponse[] | null>(null)
  const [open, setOpen] = useState(false)
  const [model, setModel] = useState(MODELS[0])
  const [generating, setGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open || responses !== null) return
    api
      .listResponses(prompt.id)
      .then(setResponses)
      .catch((e: ApiError) => setError(e.message))
  }, [open, responses, prompt.id])

  async function generate() {
    setGenerating(true)
    setError(null)
    try {
      const created = await api.generate({ prompt_id: prompt.id, model })
      setResponses((prev) => [created, ...(prev ?? [])])
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div className="card">
      <h3>{prompt.title || <span className="muted">Untitled</span>}</h3>
      <p className="small muted" style={{ margin: '0 0 0.5rem' }}>
        #{prompt.id} · {new Date(prompt.created_at).toLocaleString()}
      </p>
      <div style={{ whiteSpace: 'pre-wrap' }}>{prompt.content}</div>

      <div className="divider" />
      {error && <div className="error">{error}</div>}

      <div className="row">
        <div className="narrow" style={{ flex: '0 0 12rem' }}>
          <label htmlFor={`model-${prompt.id}`}>Model</label>
          <select
            id={`model-${prompt.id}`}
            value={model}
            onChange={(e) => setModel(e.target.value)}
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        <div style={{ flex: '0 0 auto' }}>
          <button onClick={generate} disabled={generating}>
            {generating ? 'Generating…' : 'Generate response'}
          </button>
        </div>
        <div style={{ flex: '0 0 auto' }}>
          <button className="secondary" onClick={() => setOpen((v) => !v)}>
            {open ? 'Hide responses' : 'Show responses'}
          </button>
        </div>
      </div>

      {generating && (
        <p className="small muted">
          This call is synchronous, so it blocks until the model replies.
        </p>
      )}

      {open && responses !== null && (
        <div style={{ marginTop: '0.75rem' }}>
          {responses.length === 0 ? (
            <p className="small muted">No responses generated yet.</p>
          ) : (
            responses.map((r) => (
              <div key={r.id} style={{ marginTop: '0.75rem' }}>
                <span className="pill">
                  #{r.id} · {r.model}
                </span>
                <pre className="response-body">{r.content}</pre>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<Prompt[] | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listPrompts()
      .then(setPrompts)
      .catch((e: ApiError) => setError(e.message))
  }, [])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const created = await api.createPrompt({
        title: title.trim() || null,
        content,
      })
      setPrompts((prev) => [created, ...(prev ?? [])])
      setTitle('')
      setContent('')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <>
      <div className="card">
        <h2>New prompt</h2>
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="title">Title (optional)</label>
            <input
              id="title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Capital city"
            />
          </div>
          <div className="field">
            <label htmlFor="content">Prompt</label>
            <textarea
              id="content"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="What is the capital of France?"
              required
            />
          </div>
          <button disabled={saving || !content.trim()}>
            {saving ? 'Saving…' : 'Add prompt'}
          </button>
        </form>
      </div>

      <h2 style={{ fontSize: '1rem' }}>Prompts</h2>
      {prompts === null && <p className="muted">Loading…</p>}
      {prompts?.length === 0 && (
        <p className="muted">No prompts yet. Add one above.</p>
      )}
      {prompts?.map((p) => (
        <PromptCard key={p.id} prompt={p} />
      ))}
    </>
  )
}
