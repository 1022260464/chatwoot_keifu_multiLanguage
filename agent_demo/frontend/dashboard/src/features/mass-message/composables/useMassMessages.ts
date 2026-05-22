import { computed, readonly, shallowRef } from 'vue'
import type { MassMessagePayload, MassMessageResponse } from '../types'

interface UseMassMessagesOptions {
  endpoint?: string
}

export function useMassMessages(options: UseMassMessagesOptions = {}) {
  const endpoint = options.endpoint ?? '/dashboard/mass-messages'
  const isSubmitting = shallowRef(false)
  const errorMessage = shallowRef('')
  const response = shallowRef<MassMessageResponse | null>(null)

  const hasResponse = computed(() => response.value !== null)
  const resultType = computed<'success' | 'warning' | 'info'>(() => {
    if (!response.value) {
      return 'info'
    }
    return response.value.failed > 0 ? 'warning' : 'success'
  })

  async function sendMassMessages(payload: MassMessagePayload, dashboardToken: string) {
    isSubmitting.value = true
    errorMessage.value = ''
    response.value = null

    try {
      const result = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Dashboard-Token': dashboardToken,
        },
        body: JSON.stringify(payload),
      })

      const body = await result.json().catch(() => null)
      if (!result.ok) {
        throw new Error(String(body?.detail ?? `请求失败：HTTP ${result.status}`))
      }

      response.value = body as MassMessageResponse
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '发送失败'
    } finally {
      isSubmitting.value = false
    }
  }

  function resetResult() {
    errorMessage.value = ''
    response.value = null
  }

  return {
    isSubmitting: readonly(isSubmitting),
    errorMessage: readonly(errorMessage),
    response: readonly(response),
    hasResponse,
    resultType,
    sendMassMessages,
    resetResult,
  }
}
