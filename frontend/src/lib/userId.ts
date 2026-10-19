const STORAGE_KEY = 'casepilot.user_id'

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'

/**
 * Minimal ULID generator: 10 chars of timestamp + 16 chars of randomness,
 * Crockford base32 (26 chars total). The backend treats the id as opaque, it
 * only needs to be stable for the lifetime of a browser session.
 */
export function newUlid(): string {
  let time = Date.now()
  const timePart: string[] = []
  for (let i = 9; i >= 0; i--) {
    timePart[i] = CROCKFORD[time % 32]
    time = Math.floor(time / 32)
  }

  const random = new Uint8Array(16)
  crypto.getRandomValues(random)
  const randomPart = Array.from(random, (byte) => CROCKFORD[byte % 32]).join('')

  return timePart.join('') + randomPart
}

let cachedUserId: string | null = null

/** Stable per-browser user id, persisted in localStorage. */
export function getUserId(): string {
  if (cachedUserId) return cachedUserId

  const existing = localStorage.getItem(STORAGE_KEY)
  if (existing) {
    cachedUserId = existing
    return existing
  }

  const created = newUlid()
  localStorage.setItem(STORAGE_KEY, created)
  cachedUserId = created
  return created
}

/**
 * Persist the backend-issued user id (from the chat create response).
 * It replaces any locally generated id so every later request uses
 * the id the backend knows this browser by.
 */
export function storeUserId(id: string): void {
  if (!id) return
  cachedUserId = id
  localStorage.setItem(STORAGE_KEY, id)
}
