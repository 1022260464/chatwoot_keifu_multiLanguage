import { computed, readonly, shallowRef } from 'vue'
import type { DashboardConversation, DashboardConversationResponse } from '../types'

export function useDashboardConversations() {
  const conversations = shallowRef<DashboardConversation[]>([])
  const isLoading = shallowRef(false)
  const errorMessage = shallowRef('')

  const hasConversations = computed(() => conversations.value.length > 0)

  async function loadConversations(options: {
    dashboardToken: string
    status: string
    query: string
    page?: number
  }) {
    isLoading.value = true
    errorMessage.value = ''

    try {
      const params = new URLSearchParams({
        status: options.status,
        q: options.query,
        page: String(options.page ?? 1),
      })
      const result = await fetch(`/dashboard/conversations?${params.toString()}`, {
        headers: {
          'X-Dashboard-Token': options.dashboardToken,
        },
      })
      const body = await result.json().catch(() => null)

      if (!result.ok) {
        throw new Error(String(body?.detail ?? `请求失败：HTTP ${result.status}`))
      }

      conversations.value = (body as DashboardConversationResponse).conversations
    } catch (error) {
      conversations.value = []
      errorMessage.value = error instanceof Error ? error.message : '会话加载失败'
    } finally {
      isLoading.value = false
    }
  }

  function clearConversations() {
    conversations.value = []
    errorMessage.value = ''
  }

  return {
    conversations: readonly(conversations),
    isLoading: readonly(isLoading),
    errorMessage: readonly(errorMessage),
    hasConversations,
    loadConversations,
    clearConversations,
  }
}
