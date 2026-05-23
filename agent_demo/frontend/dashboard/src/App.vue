<script setup lang="ts">
import { shallowRef } from 'vue'
import KnowledgeUploadView from './features/knowledge-upload/KnowledgeUploadView.vue'
import MassMessageView from './features/mass-message/MassMessageView.vue'

const activeView = shallowRef<'mass-message' | 'knowledge-upload'>('mass-message')
</script>

<template>
  <div class="app-shell">
    <nav class="app-shell__nav">
      <ElSegmented
        v-model="activeView"
        :options="[
          { label: '群发助手', value: 'mass-message' },
          { label: '知识库入库', value: 'knowledge-upload' },
        ]"
      />
    </nav>

    <MassMessageView v-if="activeView === 'mass-message'" />
    <KnowledgeUploadView v-else />
  </div>
</template>

<style scoped>
.app-shell__nav {
  display: flex;
  justify-content: center;
  padding: 20px 16px 0;
}
</style>
