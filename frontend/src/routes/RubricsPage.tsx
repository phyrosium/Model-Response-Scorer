import { useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { NewCriterion, Rubric } from '../api/types'

interface DraftCriterion {
  name: string
  description: string
  max_score: string
  weight: string
}

const blank = (): DraftCriterion => ({
  name: '',
  description: '',
  max_score: '5',
  weight: '1',
})

export default function RubricsPage() {
  const [rubrics, setRubrics] = useState<Rubric[] | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [criteria, setCriteria] = useState<DraftCriterion[]>([blank()])
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api
      .listRubrics()
      .then(setRubrics)
      .catch((e: ApiError) => setError(e.message))
  }, [])

  function update(index: number, patch: Partial<DraftCriterion>) {
    setCriteria((prev) =>
      prev.map((c, i) => (i === index ? { ...c, ...patch } : c)),
    )
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      const payload: NewCriterion[] = criteria.map((c) => ({
        name: c.name.trim(),
        description: c.description.trim() || null,
        max_score: Number(c.max_score),
        weight: Number(c.weight),
      }))
      const created = await api.createRubric({
        name: name.trim(),
        description: description.trim() || null,
        criteria: payload,
      })
      setRubrics((prev) => [created, ...(prev ?? [])])
      setName('')
      setDescription('')
      setCriteria([blank()])
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err))
    } finally {
      setSaving(false)
    }
  }

  const canSubmit =
    name.trim() !== '' && criteria.every((c) => c.name.trim() !== '')

  return (
    <>
      <div className="card">
        <h2>New rubric</h2>
        {error && <div className="error">{error}</div>}
        <form onSubmit={submit}>
          <div className="field">
            <label htmlFor="rubric-name">Name</label>
            <input
              id="rubric-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Answer quality"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="rubric-desc">Description (optional)</label>
            <input
              id="rubric-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="divider" />
          <label>Criteria (order here is the order they appear when scoring)</label>

          <div className="stack">
            {criteria.map((c, i) => (
              <div key={i} className="row">
                <div>
                  <label htmlFor={`c-name-${i}`}>Name</label>
                  <input
                    id={`c-name-${i}`}
                    value={c.name}
                    onChange={(e) => update(i, { name: e.target.value })}
                    placeholder="Accuracy"
                  />
                </div>
                <div>
                  <label htmlFor={`c-desc-${i}`}>Description</label>
                  <input
                    id={`c-desc-${i}`}
                    value={c.description}
                    onChange={(e) => update(i, { description: e.target.value })}
                  />
                </div>
                <div className="narrow">
                  <label htmlFor={`c-max-${i}`}>Max</label>
                  <input
                    id={`c-max-${i}`}
                    type="number"
                    min={1}
                    value={c.max_score}
                    onChange={(e) => update(i, { max_score: e.target.value })}
                  />
                </div>
                <div className="narrow">
                  <label htmlFor={`c-weight-${i}`}>Weight</label>
                  <input
                    id={`c-weight-${i}`}
                    type="number"
                    min={0}
                    step="0.5"
                    value={c.weight}
                    onChange={(e) => update(i, { weight: e.target.value })}
                  />
                </div>
                <div style={{ flex: '0 0 auto' }}>
                  <button
                    type="button"
                    className="secondary"
                    disabled={criteria.length === 1}
                    onClick={() =>
                      setCriteria((prev) => prev.filter((_, j) => j !== i))
                    }
                    title={
                      criteria.length === 1
                        ? 'A rubric needs at least one criterion'
                        : 'Remove'
                    }
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>

          <p style={{ margin: '0.75rem 0' }}>
            <button
              type="button"
              className="link"
              onClick={() => setCriteria((prev) => [...prev, blank()])}
            >
              + Add criterion
            </button>
          </p>

          <button disabled={saving || !canSubmit}>
            {saving ? 'Saving…' : 'Create rubric'}
          </button>
        </form>
      </div>

      <h2 style={{ fontSize: '1rem' }}>Rubrics</h2>
      {rubrics === null && <p className="muted">Loading…</p>}
      {rubrics?.length === 0 && <p className="muted">No rubrics yet.</p>}
      {rubrics?.map((r) => (
        <div className="card" key={r.id}>
          <h3>{r.name}</h3>
          {r.description && <p className="small muted">{r.description}</p>}
          <ul style={{ margin: '0.5rem 0 0', paddingLeft: '1.1rem' }}>
            {r.criteria.map((c) => (
              <li key={c.id}>
                {c.name}{' '}
                <span className="muted small">
                  (max {c.max_score}, weight {c.weight})
                </span>
                {c.description && (
                  <div className="small muted">{c.description}</div>
                )}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </>
  )
}
