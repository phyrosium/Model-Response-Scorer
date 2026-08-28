import { useEffect, useMemo, useState } from 'react'

import { ApiError, api } from '../api/client'
import type {
  Criterion,
  GeneratedResponse,
  Prompt,
  Rubric,
  Score,
} from '../api/types'

const JUDGE_MODELS = ['claude-opus-5', 'claude-sonnet-5', 'claude-haiku-4-5']

interface Row {
  criterion: Criterion
  manual?: Score
  auto?: Score
  /** auto minus manual, only when both sides scored this criterion */
  delta?: number
}

/** Weighted percentage over whichever criteria that source actually scored. */
function weightedPct(rows: Row[], pick: (row: Row) => Score | undefined) {
  const scored = rows.filter((r) => pick(r) !== undefined)
  if (scored.length === 0) return null
  const totalWeight = scored.reduce((sum, r) => sum + r.criterion.weight, 0)
  if (totalWeight === 0) return null
  const fraction = scored.reduce(
    (sum, r) =>
      sum + (pick(r)!.value / r.criterion.max_score) * r.criterion.weight,
    0,
  )
  return Math.round((fraction / totalWeight) * 1000) / 10
}

function DeltaCell({ delta }: { delta: number | undefined }) {
  if (delta === undefined) return <span className="muted">n/a</span>
  if (delta === 0) return <span style={{ color: 'var(--ok)' }}>0</span>
  const sign = delta > 0 ? '+' : ''
  return (
    <strong style={{ color: 'var(--danger)' }}>
      {sign}
      {delta}
    </strong>
  )
}

export default function ComparisonPage() {
  const [prompts, setPrompts] = useState<Prompt[]>([])
  const [rubrics, setRubrics] = useState<Rubric[]>([])
  const [responses, setResponses] = useState<GeneratedResponse[] | null>(null)
  const [scores, setScores] = useState<Score[]>([])

  const [promptId, setPromptId] = useState('')
  const [responseId, setResponseId] = useState('')
  const [rubricId, setRubricId] = useState('')
  const [judgeModel, setJudgeModel] = useState(JUDGE_MODELS[0])

  const [judging, setJudging] = useState(false)
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

  const rows: Row[] = useMemo(() => {
    if (!rubric) return []
    return rubric.criteria.map((criterion) => {
      const forCriterion = scores.filter((s) => s.criterion.id === criterion.id)
      const manual = forCriterion.find((s) => s.source === 'manual')
      const auto = forCriterion.find((s) => s.source === 'auto')
      return {
        criterion,
        manual,
        auto,
        delta:
          manual && auto
            ? Math.round((auto.value - manual.value) * 100) / 100
            : undefined,
      }
    })
  }, [rubric, scores])

  const summary = useMemo(() => {
    const both = rows.filter((r) => r.delta !== undefined)
    if (both.length === 0) return null
    const agreed = both.filter((r) => r.delta === 0).length
    const meanAbs =
      both.reduce((sum, r) => sum + Math.abs(r.delta!), 0) / both.length
    return {
      comparable: both.length,
      agreed,
      meanAbs: Math.round(meanAbs * 100) / 100,
      manualPct: weightedPct(rows, (r) => r.manual),
      autoPct: weightedPct(rows, (r) => r.auto),
    }
  }, [rows])

  async function runJudge() {
    if (!response || !rubric) return
    setJudging(true)
    setError(null)
    try {
      await api.autoScore({
        response_id: response.id,
        rubric_id: rubric.id,
        model: judgeModel,
      })
      // re-read rather than merging: the endpoint may have replaced an earlier
      // auto run, and the listing is the source of truth for both sources
      setScores(await api.listScores(response.id))
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e))
    } finally {
      setJudging(false)
    }
  }

  const missingManual = rows.filter((r) => !r.manual).length

  return (
    <>
      {error && <div className="error">{error}</div>}

      <div className="card">
        <h2>Compare manual and automated scoring</h2>
        <div className="row">
          <div>
            <label htmlFor="cmp-prompt">Prompt</label>
            <select
              id="cmp-prompt"
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
            <label htmlFor="cmp-response">Response</label>
            <select
              id="cmp-response"
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
            <label htmlFor="cmp-rubric">Rubric</label>
            <select
              id="cmp-rubric"
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

          <div className="row" style={{ marginBottom: '0.75rem' }}>
            <div style={{ flex: '0 0 14rem' }}>
              <label htmlFor="judge-model">Judge model</label>
              <select
                id="judge-model"
                value={judgeModel}
                onChange={(e) => setJudgeModel(e.target.value)}
              >
                {JUDGE_MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
            <div style={{ flex: '0 0 auto' }}>
              <button onClick={runJudge} disabled={judging}>
                {judging ? 'Judging...' : 'Auto-score with Claude'}
              </button>
            </div>
          </div>

          {judging && (
            <p className="small muted">
              The judge is not shown your manual scores, so the two sides stay
              independent.
            </p>
          )}

          {missingManual > 0 && (
            <p className="small muted">
              {missingManual} of {rows.length} criteria have no manual score yet.
              Score them on the Scoring page to compare.
            </p>
          )}

          <div style={{ overflowX: 'auto' }}>
            <table className="compare">
              <thead>
                <tr>
                  <th>Criterion</th>
                  <th>Manual</th>
                  <th>Auto</th>
                  <th>Delta</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.criterion.id}>
                    <td>
                      {row.criterion.name}
                      <div className="small muted">
                        out of {row.criterion.max_score}, weight{' '}
                        {row.criterion.weight}
                      </div>
                    </td>
                    <td>
                      {row.manual ? (
                        <>
                          <strong>{row.manual.value}</strong>
                          {row.manual.rationale && (
                            <div className="small muted">
                              {row.manual.rationale}
                            </div>
                          )}
                        </>
                      ) : (
                        <span className="muted">not scored</span>
                      )}
                    </td>
                    <td>
                      {row.auto ? (
                        <>
                          <strong>{row.auto.value}</strong>
                          {row.auto.rationale && (
                            <div className="small muted">
                              {row.auto.rationale}
                            </div>
                          )}
                        </>
                      ) : (
                        <span className="muted">not scored</span>
                      )}
                    </td>
                    <td>
                      <DeltaCell delta={row.delta} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {summary && (
            <>
              <div className="divider" />
              <p className="small">
                Agreed exactly on <strong>{summary.agreed}</strong> of{' '}
                {summary.comparable} comparable criteria · mean absolute
                difference <strong>{summary.meanAbs}</strong>
              </p>
              <p className="small">
                Weighted total: manual <strong>{summary.manualPct}%</strong> ·
                auto <strong>{summary.autoPct}%</strong>
              </p>
            </>
          )}
        </div>
      )}

      {!response && (
        <p className="muted">
          Pick a response and a rubric. Manual scores come from the Scoring page;
          the automated ones are generated here.
        </p>
      )}
    </>
  )
}
