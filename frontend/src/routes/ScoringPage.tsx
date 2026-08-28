import { useEffect, useMemo, useState } from 'react'

import { ApiError, api } from '../api/client'
import type {
  Criterion,
  GeneratedResponse,
  Prompt,
  Rubric,
  Score,
} from '../api/types'

function CriterionRow({
  criterion,
  responseId,
  existing,
  onSaved,
}: {
  criterion: Criterion
  responseId: number
  existing: Score | undefined
  onSaved: (score: Score) => void
}) {
  const [value, setValue] = useState('')
  const [rationale, setRationale] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [justSaved, setJustSaved] = useState(false)

  // re-seed whenever we switch response, or a saved score comes back
  useEffect(() => {
    setValue(existing ? String(existing.value) : '')
    setRationale(existing?.rationale ?? '')
    setError(null)
    setJustSaved(false)
  }, [existing, responseId])

  async function save() {
    setSaving(true)
    setError(null)
    try {
      const saved = await api.saveScore({
        response_id: responseId,
        criterion_id: criterion.id,
        value: Number(value),
        rationale: rationale.trim() || null,
      })
      onSaved(saved)
      setJustSaved(true)
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setSaving(false)
    }
  }

  const numeric = Number(value)
  const outOfRange =
    value !== '' &&
    (Number.isNaN(numeric) || numeric < 0 || numeric > criterion.max_score)

  return (
    <div style={{ marginBottom: '1rem' }}>
      <div className="row">
        <div>
          <label htmlFor={`v-${criterion.id}`}>
            {criterion.name}{' '}
            <span className="muted">
              (0-{criterion.max_score}, weight {criterion.weight})
            </span>
          </label>
          {criterion.description && (
            <p className="small muted" style={{ margin: '0 0 0.3rem' }}>
              {criterion.description}
            </p>
          )}
          <input
            id={`v-${criterion.id}`}
            type="number"
            min={0}
            max={criterion.max_score}
            step="0.5"
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setJustSaved(false)
            }}
            placeholder={`0-${criterion.max_score}`}
          />
        </div>
        <div style={{ flex: 2 }}>
          <label htmlFor={`r-${criterion.id}`}>Rationale (optional)</label>
          <input
            id={`r-${criterion.id}`}
            value={rationale}
            onChange={(e) => {
              setRationale(e.target.value)
              setJustSaved(false)
            }}
          />
        </div>
        <div style={{ flex: '0 0 auto' }}>
          <button onClick={save} disabled={saving || value === '' || outOfRange}>
            {saving ? 'Saving...' : existing ? 'Update' : 'Save'}
          </button>
        </div>
      </div>
      {outOfRange && (
        <p
          className="small"
          style={{ color: 'var(--danger)', margin: '0.25rem 0 0' }}
        >
          Must be between 0 and {criterion.max_score}.
        </p>
      )}
      {error && (
        <div className="error" style={{ marginTop: '0.4rem' }}>
          {error}
        </div>
      )}
      {justSaved && (
        <p className="saved" style={{ margin: '0.25rem 0 0' }}>
          Saved.
        </p>
      )}
    </div>
  )
}

export default function ScoringPage() {
  const [prompts, setPrompts] = useState<Prompt[]>([])
  const [rubrics, setRubrics] = useState<Rubric[]>([])
  // null means 'not loaded yet' -- distinct from [] meaning 'none exist', so
  // an in-flight fetch doesn't render as 'No responses generated yet'
  const [responses, setResponses] = useState<GeneratedResponse[] | null>(null)
  const [scores, setScores] = useState<Score[]>([])

  const [promptId, setPromptId] = useState('')
  const [responseId, setResponseId] = useState('')
  const [rubricId, setRubricId] = useState('')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.all([api.listPrompts(), api.listRubrics()])
      .then(([p, r]) => {
        setPrompts(p)
        setRubrics(r)
      })
      .catch((e: ApiError) => setError(e.message))
  }, [])

  useEffect(() => {
    setResponseId('')
    setResponses(null)
    if (!promptId) return
    api
      .listResponses(Number(promptId))
      .then(setResponses)
      .catch((e: ApiError) => setError(e.message))
  }, [promptId])

  useEffect(() => {
    setScores([])
    if (!responseId) return
    api
      .listScores(Number(responseId))
      .then(setScores)
      .catch((e: ApiError) => setError(e.message))
  }, [responseId])

  const response = (responses ?? []).find((r) => String(r.id) === responseId)
  const rubric = rubrics.find((r) => String(r.id) === rubricId)

  // only manual scores prefill the form; auto scores will be shown alongside
  // once auto-scoring exists
  const manualByCriterion = useMemo(() => {
    const map = new Map<number, Score>()
    for (const s of scores) {
      if (s.source === 'manual') map.set(s.criterion.id, s)
    }
    return map
  }, [scores])

  function recordSaved(saved: Score) {
    setScores((prev) => [...prev.filter((s) => s.id !== saved.id), saved])
  }

  const weighted = useMemo(() => {
    if (!rubric) return null
    const scored = rubric.criteria
      .map((c) => ({ criterion: c, score: manualByCriterion.get(c.id) }))
      .filter((x) => x.score !== undefined)
    if (scored.length === 0) return null
    const totalWeight = scored.reduce((sum, x) => sum + x.criterion.weight, 0)
    // every scored criterion could legitimately carry weight 0
    if (totalWeight === 0) return null
    const fraction = scored.reduce(
      (sum, x) =>
        sum + (x.score!.value / x.criterion.max_score) * x.criterion.weight,
      0,
    )
    return {
      pct: Math.round((fraction / totalWeight) * 1000) / 10,
      done: scored.length,
      total: rubric.criteria.length,
    }
  }, [rubric, manualByCriterion])

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>What are you scoring?</h2>
        <div className="row">
          <div>
            <label htmlFor="prompt-select">Prompt</label>
            <select
              id="prompt-select"
              value={promptId}
              onChange={(e) => setPromptId(e.target.value)}
            >
              <option value="">Choose a prompt...</option>
              {prompts.map((p) => (
                <option key={p.id} value={p.id}>
                  #{p.id} {p.title || p.content.slice(0, 40)}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="response-select">Response</label>
            <select
              id="response-select"
              value={responseId}
              onChange={(e) => setResponseId(e.target.value)}
              disabled={!promptId}
            >
              <option value="">
                {!promptId
                  ? 'Choose a response...'
                  : responses === null
                    ? 'Loading...'
                    : responses.length === 0
                      ? 'No responses generated yet'
                      : 'Choose a response...'}
              </option>
              {(responses ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  #{r.id} - {r.model}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="rubric-select">Rubric</label>
            <select
              id="rubric-select"
              value={rubricId}
              onChange={(e) => setRubricId(e.target.value)}
            >
              <option value="">Choose a rubric...</option>
              {rubrics.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {response && (
        <div className="card">
          <h2>
            Response #{response.id}{' '}
            <span className="pill">{response.model}</span>
          </h2>
          <pre className="response-body">{response.content}</pre>
        </div>
      )}

      {response && rubric && (
        <div className="card">
          <h2>{rubric.name}</h2>
          {weighted && (
            <p className="small muted">
              {weighted.done} of {weighted.total} criteria scored - weighted{' '}
              <strong>{weighted.pct}%</strong>
            </p>
          )}
          <div className="divider" />
          {rubric.criteria.map((c) => (
            <CriterionRow
              key={c.id}
              criterion={c}
              responseId={response.id}
              existing={manualByCriterion.get(c.id)}
              onSaved={recordSaved}
            />
          ))}
        </div>
      )}

      {!response && (
        <p className="muted">
          Pick a prompt and one of its responses to start scoring. Generate
          responses on the Prompts page first.
        </p>
      )}
    </>
  )
}
