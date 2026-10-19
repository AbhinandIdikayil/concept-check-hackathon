/**
 * Minimal history-based router. The app only needs two shapes:
 *
 *   /                → case picker
 *   /chat/:chatId    → chat history (a bare /:chatId is also accepted)
 *
 * Deep links work because Vite serves index.html for unknown paths in dev
 * and the SPA fallback can be configured the same way in production.
 */
const CHAT_ROUTE = /^\/(?:chat\/)?([^/]+)\/?$/

/** Extract the chat id from a pathname, or null when this is the case list. */
export function chatIdFromPath(
  path: string = window.location.pathname,
): string | null {
  const match = CHAT_ROUTE.exec(path)
  if (!match) return null
  try {
    return decodeURIComponent(match[1])
  } catch {
    return match[1]
  }
}

/** Canonical URL for a chat. */
export function chatPath(chatId: string): string {
  return `/chat/${encodeURIComponent(chatId)}`
}

/** Push a new history entry (no-op when already on that path). */
export function navigate(path: string): void {
  const current = window.location.pathname + window.location.search
  if (current === path) return
  window.history.pushState({}, '', path)
}

/** Replace the current history entry, e.g. to clean up an invalid chat URL. */
export function replace(path: string): void {
  window.history.replaceState({}, '', path)
}
