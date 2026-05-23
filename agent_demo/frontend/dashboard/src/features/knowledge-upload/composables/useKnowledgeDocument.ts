import { computed, readonly, shallowRef } from 'vue'
import type { KnowledgeDocumentPayload, KnowledgeDocumentResponse } from '../types'

interface UseKnowledgeDocumentOptions {
  endpoint?: string
}

export function useKnowledgeDocument(options: UseKnowledgeDocumentOptions = {}) {
  const endpoint = options.endpoint ?? '/dashboard/knowledge/chunk-document'
  const isSubmitting = shallowRef(false)
  const errorMessage = shallowRef('')
  const response = shallowRef<KnowledgeDocumentResponse | null>(null)

  const hasChunks = computed(() => (response.value?.chunks.length ?? 0) > 0)
  const importedCount = computed(() => response.value?.import_result?.upserted_ids.length ?? 0)
  const deactivatedCount = computed(() =>
    Object.values(response.value?.import_result?.deactivated ?? {}).reduce((total, count) => total + count, 0),
  )

  async function submitDocument(payload: KnowledgeDocumentPayload, dashboardToken: string) {
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

      response.value = body as KnowledgeDocumentResponse
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : '知识库文档处理失败'
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
    hasChunks,
    importedCount,
    deactivatedCount,
    submitDocument,
    resetResult,
  }
}
