import { api } from './client'
import type {
  ChatCreateResponse,
  ChatSummary,
  Message,
  MessageCreateResponse,
} from './types'

/** GET /api/chat/all?user_id=… — every chat belonging to this browser. */
export async function listChats(
  userId?: string | null,
): Promise<ChatSummary[]> {
  const { data } = await api.get<ChatSummary[]>('/api/chat/all', {
    params: { user_id: userId ?? undefined },
  })
  return data
}

/** POST /api/chat/create — open a chat on a case. */
export async function createChat(
  caseId: string,
  userId?: string | null,
): Promise<ChatCreateResponse> {
  const { data } = await api.post<ChatCreateResponse>('/api/chat/create', {
    case_id: caseId,
    user_id: userId ?? undefined,
  })
  return data
}

/** GET /api/chat/{chat_id}/message/all — full transcript, oldest first. */
export async function listMessages(chatId: string): Promise<Message[]> {
  const { data } = await api.get<Message[]>(`/api/chat/${chatId}/message/all`)
  return data
}

/** POST /api/chat/{chat_id}/message/create — send one learner turn. */
export async function createMessage(
  chatId: string,
  userId: string,
  message: string,
): Promise<MessageCreateResponse> {
  const { data } = await api.post<MessageCreateResponse>(
    `/api/chat/${chatId}/message/create`,
    { user_id: userId, message },
  )
  return data
}
