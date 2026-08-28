import type {
  GeneratedResponse,
  NewCriterion,
  Prompt,
  Rubric,
  Score,
} from './types'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

/** FastAPI sends `detail` as a string for HTTPException and as an array of
 *  field errors for a 422. Without flattening the array the UI would render
 *  "[object Object]" for every validation failure. */
function readDetail(body: unknown, fallback: string): string {
  if (typeof body !== 'object' || body === null) return fallback
  const detail = (body as { detail?: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const { loc, msg } = item as { loc?: unknown[]; msg?: string }
        const field = Array.isArray(loc)
          ? loc.filter((p) => p !== 'body').join('.')
          : ''
        return field ? `${field}: ${msg}` : (msg ?? '')
      })
      .filter(Boolean)
      .join('; ')
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: globalThis.Response
  try {
    res = await fetch(`${API_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    })
  } catch {
    // fetch only rejects on network failure, never on a 4xx/5xx
    throw new ApiError(0, `Could not reach the API at ${API_URL}`)
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(res.status, readDetail(body, res.statusText))
  }
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T)
}

const post = <T,>(path: string, body: unknown) =>
  request<T>(path, { method: 'POST', body: JSON.stringify(body) })

export const api = {
  health: () => request<{ status: string; database: string }>('/health'),

  listPrompts: () => request<Prompt[]>('/prompts'),
  createPrompt: (input: { title: string | null; content: string }) =>
    post<Prompt>('/prompts', input),

  listResponses: (promptId: number) =>
    request<GeneratedResponse[]>(`/prompts/${promptId}/responses`),
  generate: (input: { prompt_id: number; model?: string }) =>
    post<GeneratedResponse>('/generate', input),

  listRubrics: () => request<Rubric[]>('/rubrics'),
  createRubric: (input: {
    name: string
    description: string | null
    criteria: NewCriterion[]
  }) => post<Rubric>('/rubrics', input),

  listScores: (responseId: number) =>
    request<Score[]>(`/responses/${responseId}/scores`),
  saveScore: (input: {
    response_id: number
    criterion_id: number
    value: number
    rationale: string | null
  }) => post<Score>('/scores', input),
}
