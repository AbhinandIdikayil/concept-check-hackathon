import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ArrowUp,
  ArrowUpRight,
  Bookmark,
  FileText,
  History,
  Inbox,
  Loader2,
  PanelLeftClose,
  Plus,
  RotateCcw,
  Search,
} from 'lucide-react'
import {
  createChat,
  createMessage,
  listChats,
  listMessages,
} from '../api/chatApi'
import { fetchCases } from '../api/caseApi'
import { apiErrorMessage } from '../api/client'
import type { Case, ChatSummary, Message } from '../api/types'
import { getUserId, storeUserId } from '../lib/userId'
import { chatIdFromPath, chatPath, navigate, replace } from '../lib/router'

/** Id prefix for a message shown optimistically, before the API replies. */
const PENDING_ID_PREFIX = 'pending-'

/**
 * A chat is closed once its latest learner answer was graded: the backend
 * sets `status` ('passed' | 'failed') on that user message when the case
 * ends, while in-progress messages keep status null.
 */
function isChatClosed(history: Message[]): boolean {
  for (let i = history.length - 1; i >= 0; i--) {
    if (history[i].role === 'user') return history[i].status !== null
  }
  return false
}

/**
 * The closing assistant turn carries the reference answer: the lead-in on the
 * first line, the answer below it. `correct_answer` only travels with the
 * response of the turn that was just answered, so the stored message is the
 * fallback when a closed chat is reopened from history.
 */
function splitClosingMessage(text: string): { leadIn: string; answer: string } {
  const newline = text.indexOf('\n')
  if (newline === -1) return { leadIn: text.trim(), answer: '' }
  return {
    leadIn: text.slice(0, newline).trim(),
    answer: text.slice(newline + 1).trim(),
  }
}

/**
 * Single responsive CasePilot screen, merged from the three Flowstep variants
 * (desktop / iPhone / iPad). Layout responds to its container width:
 * - < 48rem (mobile): no sidebar, tab bar
 * - >= 48rem (tablet/desktop): sidebar + workspace
 * Case cards are row-style (icon left, text, arrow right) and two per line.
 *
 * Data comes from the FastAPI backend (see api.md):
 *   GET  /api/case/all
 *   POST /api/chat/create
 *   POST /api/chat/{chat_id}/message/create
 *   GET  /api/chat/{chat_id}/message/all
 */
export default function CasePilot() {
  const [userId, setUserId] = useState(() => getUserId())

  const [cases, setCases] = useState<Case[]>([])
  const [casesLoading, setCasesLoading] = useState(true)
  const [casesError, setCasesError] = useState<string | null>(null)

  const [recentChats, setRecentChats] = useState<ChatSummary[]>([])
  const [recentChatsLoading, setRecentChatsLoading] = useState(true)

  const [chatId, setChatId] = useState<string | null>(null)
  const [chatTitle, setChatTitle] = useState<string | null>(null)
  const [activeCase, setActiveCase] = useState<Case | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [ended, setEnded] = useState(false)
  const [nextCase, setNextCase] = useState<Case | null>(null)
  const [correctAnswer, setCorrectAnswer] = useState<string | null>(null)

  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [chatError, setChatError] = useState<string | null>(null)

  const transcriptEndRef = useRef<HTMLDivElement | null>(null)
  const inputRef = useRef<HTMLTextAreaElement | null>(null)

  /** Grow the composer with the text, up to a cap, then scroll inside it. */
  const resizeInput = useCallback(() => {
    const el = inputRef.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${Math.min(Math.max(el.scrollHeight, 80), 200)}px`
  }, [])

  useEffect(() => {
    resizeInput()
  }, [draft, resizeInput])

  const loadCases = useCallback(async () => {
    setCasesLoading(true)
    setCasesError(null)
    try {
      setCases(await fetchCases())
    } catch (error) {
      setCasesError(apiErrorMessage(error, 'Could not load the cases.'))
    } finally {
      setCasesLoading(false)
    }
  }, [])

  const loadChats = useCallback(
    async (owner: string = userId) => {
      try {
        setRecentChats(await listChats(owner))
      } catch {
        // The sidebar is non-critical; leave it empty if it fails.
        setRecentChats([])
      } finally {
        setRecentChatsLoading(false)
      }
    },
    [userId],
  )

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadCases()
  }, [loadCases])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadChats()
  }, [loadChats])

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const startCase = useCallback(
    async (target: Case) => {
      setBusy(true)
      setChatError(null)
      setDraft('')
      setEnded(false)
      setNextCase(null)
      setCorrectAnswer(null)
      setChatTitle(null)
      try {
        const chat = await createChat(target.id, userId)
        // The backend issues the canonical per-browser user id; persist it
        // so every later request body carries the same id.
        storeUserId(chat.user_id)
        setUserId(chat.user_id)
        setChatId(chat.chat_id)
        setActiveCase(chat.case)
        setMessages(await listMessages(chat.chat_id))
        navigate(chatPath(chat.chat_id))
        void loadChats(chat.user_id)
      } catch (error) {
        setChatError(apiErrorMessage(error, 'Could not start the case.'))
      } finally {
        setBusy(false)
      }
    },
    [loadChats, userId],
  )

  const resetChat = useCallback(() => {
    setChatId(null)
    setChatTitle(null)
    setActiveCase(null)
    setMessages([])
    setEnded(false)
    setNextCase(null)
    setCorrectAnswer(null)
    setDraft('')
    setChatError(null)
  }, [])

  const openChatById = useCallback(
    async (id: string, title: string | null = null) => {
      setBusy(true)
      setChatError(null)
      setDraft('')
      setEnded(false)
      setNextCase(null)
      setCorrectAnswer(null)
      try {
        const history = await listMessages(id)
        setChatId(id)
        setChatTitle(title)
        setActiveCase(null)
        setMessages(history)
        // Restore the closed state from history so a finished case cannot
        // be answered again when reopened from the sidebar or a deep link.
        setEnded(isChatClosed(history))
        navigate(chatPath(id))
      } catch (error) {
        resetChat()
        replace('/')
        setChatError(apiErrorMessage(error, 'Could not open the chat.'))
      } finally {
        setBusy(false)
      }
    },
    [resetChat],
  )

  const openChat = useCallback(
    (summary: ChatSummary) => {
      if (busy) return
      void openChatById(summary.chat_id, summary.text)
    },
    [busy, openChatById],
  )

  const sendMessage = useCallback(async () => {
    if (!chatId) return
    const text = draft
    if (!text.trim()) return

    // Optimistic update: the learner's answer is shown the moment it is
    // submitted. When the reply lands, this placeholder is swapped for the
    // server's copy (real id, created_at and grading status).
    const pendingId = `${PENDING_ID_PREFIX}${Date.now()}`
    const pendingMessage: Message = {
      id: pendingId,
      role: 'user',
      message: text,
      status: null,
      created_at: new Date().toISOString(),
    }

    setBusy(true)
    setChatError(null)
    setDraft('')
    setMessages((prev) => [...prev, pendingMessage])

    try {
      const result = await createMessage(chatId, userId, text)
      setMessages((prev) => [
        ...prev.filter((message) => message.id !== pendingId),
        result.user_message,
        result.message,
      ])
      setEnded(result.ended)
      setNextCase(result.new_case)
      setCorrectAnswer(result.correct_answer)
    } catch (error) {
      // Roll the optimistic message back and let the learner retry it.
      setMessages((prev) => prev.filter((message) => message.id !== pendingId))
      setDraft(text)
      setChatError(apiErrorMessage(error, 'Could not send the message.'))
    } finally {
      setBusy(false)
    }
  }, [chatId, draft, userId])

  const backToCases = useCallback(() => {
    resetChat()
    navigate('/')
  }, [resetChat])

  // Keep the view in sync with the URL: deep links (e.g. /chat/<id>) and
  // the browser back/forward buttons.
  useEffect(() => {
    const syncFromRoute = () => {
      const routeChatId = chatIdFromPath()
      if (routeChatId) {
        void openChatById(routeChatId)
      } else {
        resetChat()
      }
    }

    syncFromRoute()
    window.addEventListener('popstate', syncFromRoute)
    return () => window.removeEventListener('popstate', syncFromRoute)
  }, [openChatById, resetChat])


  // The case prompt. The backend usually stores it as the first assistant
  // message, so only show it separately when the transcript doesn't have it.
  const questionText = activeCase?.text ?? chatTitle ?? null
  const question =
    questionText &&
    !messages.some((message) => message.message.trim() === questionText.trim())
      ? questionText
      : null

  return (
    <div className="@container bg-background text-foreground w-full h-full">
      <div className="flex w-full h-full overflow-hidden">
        <aside className="bg-sidebar border-y-sidebar-border border-r border-r-sidebar-border border-l-sidebar-border w-1/4 flex pt-5 pr-4 pb-5 pl-4 flex-col shrink-0 @3xl:flex">
          <div className="flex justify-between items-center">
            <div className="font-semibold text-sidebar-foreground text-base flex items-center gap-2">
              <span className="rounded-full bg-primary size-2.5" />
              <span>CasePilot</span>
            </div>
            <div className="flex items-center gap-1">
              <button
                aria-label="Search"
                className="rounded-md text-sidebar-foreground/70 flex justify-center items-center size-8 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              >
                <Search className="size-4" />
              </button>
              <button
                aria-label="Collapse sidebar"
                className="rounded-md text-sidebar-foreground/70 flex justify-center items-center size-8 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
              >
                <PanelLeftClose className="size-4" />
              </button>
            </div>
          </div>
          <div className="flex flex-col flex-1 min-h-0">
            <input
              placeholder="Search cases"
              className="rounded-md bg-sidebar-accent text-sidebar-foreground text-sm border-t border-t-sidebar-border border-r border-r-sidebar-border border-b border-b-sidebar-border border-l border-l-sidebar-border outline-none hidden mt-5 pr-3 pl-3 h-9 placeholder:text-sidebar-foreground/50 focus:ring-2 focus:ring-sidebar-ring"
              defaultValue=""
            />
            <button
              onClick={backToCases}
              className="font-medium rounded-md bg-sidebar-primary text-sidebar-primary-foreground text-sm flex mt-5 pr-3 pl-3 items-center gap-2 h-10 hover:opacity-90"
            >
              <Plus className="size-4" />
              <span>New case</span>
            </button>

            <div className="mt-6 flex-1 min-h-0 overflow-y-auto">
              <p className="font-medium uppercase text-sidebar-foreground/50 text-xs tracking-wide mb-2 pr-2 pl-2">
                Recent chats
              </p>
              <div>
                {recentChatsLoading ? (
                  Array.from({ length: 4 }).map((_, index) => (
                    <div
                      key={index}
                      className="h-8 rounded-md bg-sidebar-accent/60 animate-pulse mb-1"
                    />
                  ))
                ) : recentChats.length === 0 ? (
                  <p className="text-sidebar-foreground/50 text-xs pr-2 pl-2 py-1">
                    No chats yet.
                  </p>
                ) : (
                  recentChats.map((chat) => (
                    <button
                      key={chat.chat_id}
                      onClick={() => void openChat(chat)}
                      disabled={busy}
                      title={chat.text}
                      className={`text-left rounded-md text-sm border-l-2 flex mb-1 pt-2 pr-2 pb-2 pl-2 items-center w-full truncate transition-colors disabled:opacity-60 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground ${
                        chatId === chat.chat_id
                          ? 'border-l-primary bg-sidebar-accent text-sidebar-foreground'
                          : 'border-l-sidebar-border text-sidebar-foreground/80'
                      }`}
                    >
                      <span className="truncate">{chat.text}</span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </div>
        </aside>
        <main className="bg-background flex flex-col flex-1 min-w-0 min-h-0">
          <div
            className={`pt-5 pr-4 pb-4 pl-4 @3xl:pt-6 @3xl:pr-8 @3xl:pb-6 flex flex-1 justify-center ${chatId ? '' : 'items-center'} min-h-0 w-full overflow-y-auto`}
          >
            {chatId ? (
              /* ---------- Active chat ---------- */
              <div className="flex w-full flex-col gap-3 @3xl:gap-4 px-4 pt-4 pb-4 @md:px-8 @md:pt-6 @md:pb-6 @3xl:px-28 @3xl:pt-14 @3xl:pb-14">
              

                {chatError && (
                  <p className="text-destructive text-sm border border-destructive/40 bg-destructive/10 rounded-lg px-3 py-2">
                    {chatError}
                  </p>
                )}

                {question && (
                  <div className="flex justify-end">
                    <div className="max-w-[85%] rounded-xl rounded-br-sm bg-card border border-border px-3 py-2 text-md">
                      <p className="whitespace-pre-wrap">{question}</p>
                    </div>
                  </div>
                )}

                {messages.map((message, index) => {
                  // The last assistant turn of a closed chat is the answer, so
                  // it gets its own block instead of an ordinary bubble.
                  const closing =
                    ended &&
                    message.role === 'assistant' &&
                    index === messages.length - 1
                  const { leadIn, answer } = closing
                    ? splitClosingMessage(message.message)
                    : { leadIn: '', answer: '' }
                  // Shown optimistically while the API is still answering.
                  const pending = message.id.startsWith(PENDING_ID_PREFIX)
                  const bubbleClass =
                    message.role === 'user'
                      ? 'max-w-[85%] rounded-xl rounded-bl-sm bg-primary/15 border border-primary/30 px-3 py-2 text-md'
                      : closing
                        ? 'max-w-[85%] rounded-xl rounded-br-sm bg-accent border border-border px-3 py-2 text-md'
                        : 'max-w-[85%] rounded-xl rounded-br-sm bg-card border border-border px-3 py-2 text-md'

                  return (
                    <div
                      key={message.id}
                      className={
                        message.role === 'user'
                          ? 'flex justify-start'
                          : 'flex justify-end'
                      }
                    >
                      <div
                        className={`${bubbleClass} ${pending ? 'opacity-60' : ''}`}
                      >
                        {closing ? (
                          <>
                            {leadIn && (
                              <p className="whitespace-pre-wrap">{leadIn}</p>
                            )}
                            {(correctAnswer || answer) && (
                              <p className="mt-2 whitespace-pre-wrap border-t border-border pt-2">
                                {correctAnswer || answer}
                              </p>
                            )}
                          </>
                        ) : (
                          <p className="whitespace-pre-wrap">
                            {message.message}
                          </p>
                        )}
                      
                      </div>
                    </div>
                  )
                })}

        

                {ended && (
                  <div className="rounded-lg border border-border bg-card px-4 py-3 flex items-center justify-between gap-3">
                    <p className="text-md">
                      This case is closed
                      {nextCase ? '. Ready for the next one?' : '.'}
                    </p>
                    {nextCase && (
                      <button
                        onClick={() => void startCase(nextCase)}
                        disabled={busy}
                        className="font-medium rounded-md bg-primary text-primary-foreground text-md flex items-center gap-2 px-3 h-9 hover:opacity-90 disabled:opacity-60"
                      >
                        {busy ? (
                          <Loader2 className="size-4 animate-spin" />
                        ) : (
                          <ArrowUpRight className="size-4" />
                        )}
                        <span>Next case</span>
                      </button>
                    )}
                  </div>
                )}

                <div ref={transcriptEndRef} />
              </div>
            ) : (
              /* ---------- Case picker ---------- */
              <div className="my-auto flex w-full flex-col mx-auto @3xl:max-w-4xl">
                {chatError && (
                  <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3">
                    <p className="text-sm">{chatError}</p>
                  </div>
                )}

                {casesError && (
                  <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 flex items-center justify-between gap-3 @3xl:max-w-4xl">
                    <p className="text-sm">{casesError}</p>
                    <button
                      onClick={() => void loadCases()}
                      className="text-sm font-medium flex items-center gap-1.5 shrink-0"
                    >
                      <RotateCcw className="size-4" />
                      Retry
                    </button>
                  </div>
                )}

                {casesLoading ? (
                  <div className="grid gap-3 @3xl:gap-4 grid-cols-1 @md:grid-cols-2 @md:max-w-4xl mx-auto w-full">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <div
                        key={index}
                        className="h-18.5 rounded-lg border border-border bg-card/40 animate-pulse"
                      />
                    ))}
                  </div>
                ) : (
                  <div className="grid gap-3 @3xl:gap-4 grid-cols-1 @md:grid-cols-2 @md:max-w-4xl mx-auto w-full">
                    {cases.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => startCase(item)}
                        disabled={busy}
                        className="group hover:cursor-pointer text-left transition-colors rounded-lg border-t border-r border-b border-l pt-3 pr-4 pb-3 pl-4 @3xl:pt-4 @3xl:pb-4 flex items-center gap-3 @3xl:gap-4 w-full disabled:opacity-60"
                      >
                        <div className="shrink-0 rounded-md flex justify-center items-center size-9 @3xl:size-10 bg-primary/15 text-primary">
                          <FileText className="size-5" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-xs text-primary">
                            Case {item.id}
                          </p>
                          <h2 className="font-semibold text-base mt-0.5 line-clamp-2">
                            {item.text}
                          </h2>
                        </div>
                        <div className="flex items-center gap-1 shrink-0 self-center">
                          <span className="font-medium text-muted-foreground text-xs @max-md:hidden group-hover:text-foreground transition-colors">
                            Start case
                          </span>
                          <ArrowUpRight className="text-muted-foreground group-hover:text-foreground transition-colors size-4" />
                        </div>
                      </button>
                    ))}
                  </div>
                )}

                {!casesLoading && !casesError && cases.length === 0 && (
                  <p className="text-muted-foreground text-sm">
                    No cases are available yet.
                  </p>
                )}
              </div>
            )}
          </div>
          <div className="bg-background border-x-border border-t border-t-border pt-3 pr-4 pb-3 pl-4 @3xl:pr-8 @3xl:pl-8 shrink-0 sticky bottom-15 @3xl:bottom-0 z-20">
            <div className="w-full @3xl:max-w-3xl mx-auto">
              <div
                className={`rounded-2xl bg-card border-t border-t-input border-r border-r-input border-b border-b-input border-l border-l-input flex flex-col justify-between gap-2 min-h-35 p-3 @3xl:p-4 ${
                  chatId && !ended ? '' : 'opacity-60'
                }`}
              >
                <textarea
                  ref={inputRef}
                  rows={1}
                  value={draft}
                  onChange={(event) => {
                    setDraft(event.target.value)
                    resizeInput()
                  }}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' && !event.shiftKey) {
                      event.preventDefault()
                      void sendMessage()
                    }
                  }}
                  disabled={!chatId || ended || busy}
                  placeholder={
                    chatId
                      ? 'Answer the case…'
                      : 'Select a case to start answering…'
                  }
                  className="bg-transparent text-md outline-none w-full min-w-0 shrink-0 resize-none max-h-50 overflow-y-auto leading-6 placeholder:text-muted-foreground disabled:opacity-50 disabled:cursor-not-allowed cursor-text"
                />
                <div className="flex items-end justify-between gap-3">
                  <p className="text-muted-foreground text-md pb-1">
                    {chatId
                      ? ended
                        ? 'This session is closed. Start the next case to keep going.'
                        : 'Keep it simple. There is no perfect wording.'
                      : 'Your conversation will appear here after you select a case'}
                  </p>
                  <div className="flex flex-col items-end gap-1">
                    
                    <button
                      aria-label="Send"
                      onClick={() => void sendMessage()}
                      disabled={!chatId || ended || busy || !draft.trim()}
                      className="rounded-xl bg-primary text-primary-foreground flex justify-center items-center size-9 @3xl:size-10 hover:opacity-90 disabled:opacity-40"
                    >
                      {busy ? (
                        <Loader2 className="size-4 animate-spin" />
                      ) : (
                        <ArrowUp className="size-5" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
              <p className="text-muted-foreground text-xs text-center mt-2">
                ↵ Enter to send · Shift + Enter for a new line
              </p>
            </div>
          </div>
          {/* Mobile bottom tab bar */}
          <nav className="@3xl:hidden bg-card border-x-border border-t border-t-border flex pt-2 pr-4 pb-3 pl-4 justify-around shrink-0 sticky bottom-0 z-10">
            <button
              onClick={backToCases}
              className="text-xs flex flex-col items-center gap-1"
            >
              <Inbox className="size-5" />
              <span>Cases</span>
            </button>
            <button className="text-xs flex flex-col items-center gap-1">
              <Bookmark className="size-5" />
              <span>Saved</span>
            </button>
            <button className="text-xs flex flex-col items-center gap-1">
              <History className="size-5" />
              <span>Recent</span>
            </button>
          </nav>
        </main>
      </div>
    </div>
  )
}
