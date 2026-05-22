<script setup lang="ts">
import { computed, shallowRef } from 'vue'
import ConversationPicker from './components/ConversationPicker.vue'
import MassMessageForm from './components/MassMessageForm.vue'
import MassMessageResultTable from './components/MassMessageResultTable.vue'
import { useMassMessages } from './composables/useMassMessages'
import type { MassMessageDraft } from './types'

const { isSubmitting, errorMessage, response, resultType, sendMassMessages, resetResult } = useMassMessages()
const dashboardToken = __DASHBOARD_API_TOKEN__.trim()
const selectedConversationIds = shallowRef<string[]>([])

const tokenReady = computed(() => dashboardToken.length > 0)

async function handleSubmit(draft: MassMessageDraft) {
  const conversationIds = Array.from(new Set([...selectedConversationIds.value, ...draft.manualConversationIds]))
  await sendMassMessages(
    {
      conversation_ids: conversationIds,
      content: draft.content,
      private: draft.private,
      delay_seconds: draft.delaySeconds,
      translate_before_send: draft.translateBeforeSend,
      target_language: draft.targetLanguage,
    },
    dashboardToken,
  )
}
</script>

<template>
  <main class="mass-message-view">
    <header class="mass-message-view__header">
      <div>
        <p class="mass-message-view__eyebrow">运营仪表盘</p>
        <h1 class="mass-message-view__title">Chatwoot 群发助手</h1>
      </div>
      <ElTag type="success" effect="plain">自动识别会话 ID</ElTag>
    </header>

    <ElAlert
      v-if="!tokenReady"
      class="mass-message-view__alert"
      type="error"
      title="未配置 DASHBOARD_API_TOKEN，请检查 agent_demo/.env 后重启前端服务。"
      show-icon
      :closable="false"
    />

    <section class="mass-message-view__panel">
      <h2 class="mass-message-view__section-title">第一步：选择要发送的会话</h2>
      <ConversationPicker v-model:selected-ids="selectedConversationIds" :dashboard-token="dashboardToken" />
    </section>

    <section class="mass-message-view__panel">
      <h2 class="mass-message-view__section-title">第二步：填写消息并发送</h2>
      <MassMessageForm
        :loading="isSubmitting"
        :selected-count="selectedConversationIds.length"
        :token-ready="tokenReady"
        @submit="handleSubmit"
        @clear="resetResult"
      />
    </section>

    <MassMessageResultTable :response="response" :error-message="errorMessage" :result-type="resultType" />
  </main>
</template>

<style scoped>
.mass-message-view {
  width: min(1080px, 100%);
  margin: 0 auto;
  padding: 24px;
}

.mass-message-view__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.mass-message-view__eyebrow {
  margin: 0 0 4px;
  color: #667085;
  font-size: 13px;
  line-height: 1.4;
}

.mass-message-view__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
  line-height: 1.2;
  letter-spacing: 0;
}

.mass-message-view__panel {
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #ffffff;
}

.mass-message-view__alert {
  margin-bottom: 20px;
}

.mass-message-view__section-title {
  margin: 0 0 16px;
  color: #111827;
  font-size: 18px;
  font-weight: 650;
  line-height: 1.3;
  letter-spacing: 0;
}

@media (max-width: 720px) {
  .mass-message-view {
    padding: 16px;
  }

  .mass-message-view__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .mass-message-view__title {
    font-size: 24px;
  }
}
</style>
