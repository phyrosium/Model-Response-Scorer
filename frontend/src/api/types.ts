// Mirrors the Pydantic response models in backend/schemas.py.

export interface Prompt {
  id: number
  title: string | null
  content: string
  created_at: string
}

export interface GeneratedResponse {
  id: number
  prompt_id: number
  model: string
  content: string
  created_at: string
}

export interface Criterion {
  id: number
  name: string
  description: string | null
  max_score: number
  weight: number
  position: number
}

export interface Rubric {
  id: number
  name: string
  description: string | null
  created_at: string
  criteria: Criterion[]
}

/** The trimmed criterion embedded in a score, so a panel can render in one call. */
export interface ScoreCriterion {
  id: number
  name: string
  max_score: number
  weight: number
}

export type ScoreSource = 'manual' | 'auto'

export interface Score {
  id: number
  response_id: number
  source: ScoreSource
  value: number
  rationale: string | null
  created_at: string
  criterion: ScoreCriterion
}

export interface NewCriterion {
  name: string
  description?: string | null
  max_score?: number
  weight?: number
}
