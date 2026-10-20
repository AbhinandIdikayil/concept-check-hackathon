/** Shared API types, mirroring the FastAPI schemas in backend/app/validators.py. */

export interface Case {
  id: string
  text: string
}

export type MessageRole = 'user' | 'assistant'
export type MessageStatus = 'passed' | 'failed' | null

export interface Message {
  id: string
  role: MessageRole
  message: string
  status: MessageStatus
  created_at: string
}

export interface HealthResponse {
  status: string
}

export interface ChatSummary {
  chat_id: string
  text: string
}

export interface ChatCreateResponse {
  chat_id: string
  user_id: string
  case: Case
}

export interface MessageCreateResponse {
  status: MessageStatus
  reply: string
  ended: boolean
  gap_sentence: string | null
  correct_answer: string | null
  new_case: Case | null
  user_message: Message
  message: Message
}
