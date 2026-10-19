import axios from 'axios'

/**
 * Base URL of the FastAPI backend.
 * `.env` holds `VITE_API=http://localhost:8000` (or `API=…`); both are
 * inlined at build time by the `define` block in vite.config.ts.
 */
export const API_BASE_URL = (
  process.env.API ?? 'http://localhost:8000'
).replace(/\/+$/, '')

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60_000,
})

/** Best-effort human readable error message from an axios failure. */
export function apiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)
      ?.detail
    if (detail) return detail
    if (error.code === 'ECONNABORTED') return 'The request timed out.'
    if (!error.response) {
      return `Cannot reach the API at ${API_BASE_URL}. Is the backend running?`
    }
    return error.message
  }
  return fallback
}
