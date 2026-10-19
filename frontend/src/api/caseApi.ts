import { api } from './client'
import type { Case, HealthResponse } from './types'

/** GET /api/health */
export async function fetchHealth(): Promise<HealthResponse> {
  const { data } = await api.get<HealthResponse>('/api/health')
  return data
}

/** GET /api/case/all — every seeded case, ordered by id. */
export async function fetchCases(): Promise<Case[]> {
  const { data } = await api.get<Case[]>('/api/case/all')
  return data
}
