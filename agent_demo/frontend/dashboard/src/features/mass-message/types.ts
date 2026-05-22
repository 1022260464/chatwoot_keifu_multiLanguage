export interface MassMessageDraft {
  manualConversationIds: string[]
  content: string
  private: boolean
  delaySeconds: number
  translateBeforeSend: boolean
  targetLanguage: string
}

export interface MassMessagePayload {
  conversation_ids: string[]
  content: string
  private: boolean
  delay_seconds: number
  translate_before_send: boolean
  target_language: string
}

export interface MassMessageItemResult {
  conversation_id: string
  ok: boolean
  error: string
}

export interface MassMessageResponse {
  total: number
  success: number
  failed: number
  translated: boolean
  target_language: string
  sent_content_preview: string
  results: MassMessageItemResult[]
}

export interface DashboardConversation {
  id: string
  display_name: string
  email: string
  status: string
  inbox_id: string
  last_activity_at: string
  assignee_name: string
}

export interface DashboardConversationResponse {
  total: number
  conversations: DashboardConversation[]
}
