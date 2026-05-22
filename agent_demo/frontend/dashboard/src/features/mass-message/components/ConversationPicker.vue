<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useDashboardConversations } from '../composables/useDashboardConversations'

interface Props {
  dashboardToken: string
  selectedIds: string[]
}

interface Emits {
  'update:selectedIds': [ids: string[]]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const filters = reactive({
  status: 'open',
  query: '',
})

const { conversations, isLoading, errorMessage, hasConversations, loadConversations } = useDashboardConversations()

const canLoad = computed(() => props.dashboardToken.trim().length > 0)

function loadCurrentConversations() {
  if (!canLoad.value) {
    return
  }

  void loadConversations({
    dashboardToken: props.dashboardToken.trim(),
    status: filters.status,
    query: filters.query.trim(),
  })
}

function handleSelectionChange(rows: Array<{ id: string }>) {
  emit(
    'update:selectedIds',
    rows.map((row) => row.id),
  )
}
</script>

<template>
  <section class="conversation-picker">
    <div class="conversation-picker__toolbar">
      <ElSelect v-model="filters.status" class="conversation-picker__status" placeholder="会话状态">
        <ElOption label="打开中" value="open" />
        <ElOption label="待处理" value="pending" />
        <ElOption label="已解决" value="resolved" />
        <ElOption label="全部" value="" />
      </ElSelect>

      <ElInput
        v-model="filters.query"
        class="conversation-picker__search"
        clearable
        placeholder="按客户姓名、邮箱或关键词搜索"
        @keyup.enter="loadCurrentConversations"
      />

      <ElButton type="primary" :disabled="!canLoad" :loading="isLoading" @click="loadCurrentConversations">
        刷新会话
      </ElButton>
    </div>

    <ElAlert
      v-if="!canLoad"
      type="info"
      title="未配置 Dashboard Token，请检查 agent_demo/.env 中的 DASHBOARD_API_TOKEN 并重启前端服务。"
      show-icon
      :closable="false"
    />

    <ElAlert v-if="errorMessage" type="error" :title="errorMessage" show-icon :closable="false" />

    <ElTable
      v-if="hasConversations"
      :data="conversations"
      class="conversation-picker__table"
      border
      height="360"
      @selection-change="handleSelectionChange"
    >
      <ElTableColumn type="selection" width="48" />
      <ElTableColumn prop="id" label="会话 ID" width="100" />
      <ElTableColumn prop="display_name" label="客户" min-width="160" />
      <ElTableColumn prop="email" label="邮箱" min-width="200" />
      <ElTableColumn prop="status" label="状态" width="100" />
      <ElTableColumn prop="assignee_name" label="负责人" width="140" />
    </ElTable>

    <p class="conversation-picker__hint">已选择 {{ props.selectedIds.length }} 个会话。</p>
  </section>
</template>

<style scoped>
.conversation-picker {
  display: grid;
  gap: 12px;
}

.conversation-picker__toolbar {
  display: grid;
  grid-template-columns: 140px minmax(220px, 1fr) auto;
  gap: 12px;
}

.conversation-picker__status,
.conversation-picker__search,
.conversation-picker__table {
  width: 100%;
}

.conversation-picker__hint {
  margin: 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

@media (max-width: 820px) {
  .conversation-picker__toolbar {
    grid-template-columns: 1fr;
  }
}
</style>
