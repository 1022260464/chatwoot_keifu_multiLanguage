<script setup lang="ts">
import { computed } from 'vue'
import type { MassMessageResponse } from '../types'

interface Props {
  response: MassMessageResponse | null
  errorMessage?: string
  resultType?: 'success' | 'warning' | 'info'
}

const props = withDefaults(defineProps<Props>(), {
  errorMessage: '',
  resultType: 'info',
})

const tableData = computed(() => props.response?.results ?? [])
</script>

<template>
  <section class="mass-message-results">
    <ElAlert
      v-if="props.errorMessage"
      class="mass-message-results__alert"
      type="error"
      :title="props.errorMessage"
      show-icon
      :closable="false"
    />

    <ElAlert
      v-if="props.response"
      class="mass-message-results__alert"
      :type="props.resultType"
      :title="`共 ${props.response.total} 个，成功 ${props.response.success} 个，失败 ${props.response.failed} 个`"
      show-icon
      :closable="false"
    />

    <ElAlert
      v-if="props.response"
      class="mass-message-results__alert"
      :type="props.response.translated ? 'success' : 'info'"
      :title="props.response.translated ? `已在发送前翻译为 ${props.response.target_language}` : '本次未执行发送前翻译，已按原文发送'"
      :description="props.response.sent_content_preview ? `实际发送内容预览：${props.response.sent_content_preview}` : ''"
      show-icon
      :closable="false"
    />

    <ElTable v-if="props.response" :data="tableData" class="mass-message-results__table" border>
      <ElTableColumn prop="conversation_id" label="会话 ID" width="180" />
      <ElTableColumn label="状态" width="120">
        <template #default="{ row }">
          <ElTag :type="row.ok ? 'success' : 'danger'">
            {{ row.ok ? '已发送' : '失败' }}
          </ElTag>
        </template>
      </ElTableColumn>
      <ElTableColumn prop="error" label="错误原因" min-width="240" />
    </ElTable>
  </section>
</template>

<style scoped>
.mass-message-results {
  display: grid;
  gap: 12px;
}

.mass-message-results__alert {
  border-radius: 6px;
}

.mass-message-results__table {
  width: 100%;
}
</style>
