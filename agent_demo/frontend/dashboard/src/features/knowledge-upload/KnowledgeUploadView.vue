<script setup lang="ts">
import { computed, reactive, shallowRef } from 'vue'
import { useKnowledgeDocument } from './composables/useKnowledgeDocument'
import type { KnowledgeDocumentPayload } from './types'

const dashboardToken = __DASHBOARD_API_TOKEN__.trim()
const tokenReady = computed(() => dashboardToken.length > 0)
const selectedFileName = shallowRef('')
const fileError = shallowRef('')
const metadataText = shallowRef('{\n  "category": "faq"\n}')
const documentText = shallowRef('')
const generatedSourceDocId = `doc_${Date.now()}`

const form = reactive({
  sourceDocId: generatedSourceDocId,
  sourceName: '',
  sourceType: 'text',
  sourceUrl: '',
  language: 'zh-CN',
  userLevel: 'all',
  tagsText: '',
  maxChars: 900,
  overlapChars: 120,
  importToDb: true,
  deactivateExisting: false,
})

const {
  isSubmitting,
  errorMessage,
  response,
  hasChunks,
  importedCount,
  deactivatedCount,
  submitDocument,
  resetResult,
} = useKnowledgeDocument()

const tags = computed(() =>
  form.tagsText
    .split(/[\s,，]+/)
    .map((item) => item.trim())
    .filter(Boolean),
)

const contentLength = computed(() => documentText.value.trim().length)

const canSubmit = computed(
  () =>
    tokenReady.value &&
    form.sourceDocId.trim().length > 0 &&
    documentText.value.trim().length > 0 &&
    form.overlapChars < form.maxChars,
)

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }

  fileError.value = ''
  selectedFileName.value = file.name
  if (!form.sourceName) {
    form.sourceName = file.name
  }

  try {
    documentText.value = await file.text()
    resetResult()
  } catch {
    fileError.value = '文件读取失败'
  }
}

async function handleSubmit() {
  if (!canSubmit.value) {
    return
  }

  let metadata: Record<string, unknown>
  try {
    metadata = JSON.parse(metadataText.value || '{}') as Record<string, unknown>
  } catch {
    fileError.value = 'metadata 必须是合法 JSON'
    return
  }

  fileError.value = ''
  const payload: KnowledgeDocumentPayload = {
    source_doc_id: form.sourceDocId.trim(),
    source_name: form.sourceName.trim(),
    source_type: form.sourceType,
    source_url: form.sourceUrl.trim(),
    content: documentText.value,
    language: form.language,
    user_level: form.userLevel,
    tags: tags.value,
    metadata,
    options: {
      max_chars: form.maxChars,
      overlap_chars: form.overlapChars,
    },
    import_to_db: form.importToDb,
    deactivate_existing: form.deactivateExisting,
    include_chunks: true,
  }

  await submitDocument(payload, dashboardToken)
}

function clearForm() {
  selectedFileName.value = ''
  fileError.value = ''
  documentText.value = ''
  metadataText.value = '{\n  "category": "faq"\n}'
  form.sourceDocId = `doc_${Date.now()}`
  form.sourceName = ''
  form.sourceType = 'text'
  form.sourceUrl = ''
  form.language = 'zh-CN'
  form.userLevel = 'all'
  form.tagsText = ''
  form.maxChars = 900
  form.overlapChars = 120
  form.importToDb = true
  form.deactivateExisting = false
  resetResult()
}
</script>

<template>
  <main class="knowledge-upload-view">
    <header class="knowledge-upload-view__header">
      <div>
        <p class="knowledge-upload-view__eyebrow">知识库管理</p>
        <h1 class="knowledge-upload-view__title">文档切分与入库</h1>
      </div>
      <ElTag type="primary" effect="plain">RAG</ElTag>
    </header>

    <ElAlert
      v-if="!tokenReady"
      class="knowledge-upload-view__alert"
      type="error"
      title="未配置 DASHBOARD_API_TOKEN，请检查 agent_demo/.env 后重启前端服务。"
      show-icon
      :closable="false"
    />

    <section class="knowledge-upload-view__panel">
      <h2 class="knowledge-upload-view__section-title">文档来源</h2>
      <ElForm class="knowledge-upload-form" label-position="top" @submit.prevent="handleSubmit">
        <div class="knowledge-upload-form__grid">
          <ElFormItem label="选择文本文档">
            <label class="knowledge-upload-form__file-button">
              <input
                class="knowledge-upload-form__file-input"
                type="file"
                accept=".txt,.md,.markdown,.csv,.json,.log,text/plain,text/markdown,application/json"
                @change="handleFileChange"
              />
              <span>{{ selectedFileName || '上传文档' }}</span>
            </label>
          </ElFormItem>

          <ElFormItem label="文档 ID">
            <ElInput v-model="form.sourceDocId" placeholder="自动生成，可手动调整" />
          </ElFormItem>

          <ElFormItem label="文档名称">
            <ElInput v-model="form.sourceName" placeholder="贷款 FAQ" />
          </ElFormItem>

          <ElFormItem label="文档类型">
            <ElSelect v-model="form.sourceType">
              <ElOption label="Text" value="text" />
              <ElOption label="Markdown" value="markdown" />
              <ElOption label="FAQ" value="faq" />
              <ElOption label="JSON" value="json" />
            </ElSelect>
          </ElFormItem>

          <ElFormItem label="语言">
            <ElSelect v-model="form.language">
              <ElOption label="中文" value="zh-CN" />
              <ElOption label="English" value="en" />
              <ElOption label="Tiếng Việt" value="vi" />
            </ElSelect>
          </ElFormItem>

          <ElFormItem label="用户层级">
            <ElSelect v-model="form.userLevel">
              <ElOption label="全部用户" value="all" />
              <ElOption label="新用户" value="new_user" />
              <ElOption label="普通用户" value="normal_user" />
              <ElOption label="优质用户" value="vip" />
              <ElOption label="内部知识" value="internal" />
            </ElSelect>
          </ElFormItem>

          <ElFormItem label="标签">
            <ElInput v-model="form.tagsText" placeholder="faq, loan, credit_limit" />
          </ElFormItem>

          <ElFormItem label="来源 URL">
            <ElInput v-model="form.sourceUrl" placeholder="https://..." />
          </ElFormItem>
        </div>

        <ElFormItem label="文档内容">
          <ElInput
            v-model="documentText"
            type="textarea"
            maxlength="200000"
            show-word-limit
            :autosize="{ minRows: 8, maxRows: 18 }"
            placeholder="上传文件后会自动填充，也可以直接粘贴文本"
          />
          <p class="knowledge-upload-form__hint">当前 {{ contentLength }} 个字符。</p>
        </ElFormItem>

        <div class="knowledge-upload-form__settings">
          <ElFormItem label="单段最大字符">
            <ElInputNumber v-model="form.maxChars" :min="200" :max="4000" :step="100" controls-position="right" />
          </ElFormItem>

          <ElFormItem label="相邻片段保留上下文">
            <ElInputNumber v-model="form.overlapChars" :min="0" :max="1000" :step="20" controls-position="right" />
            <p class="knowledge-upload-form__hint">
              每段开头保留上一段末尾的一小段文字，避免答案被切断。常用 80-150。
            </p>
          </ElFormItem>

          <ElFormItem label="写入数据库">
            <ElSwitch v-model="form.importToDb" active-text="写入" inactive-text="预览" inline-prompt />
          </ElFormItem>

          <ElFormItem label="替换同文档旧数据">
            <ElSwitch v-model="form.deactivateExisting" active-text="替换" inactive-text="保留" inline-prompt />
          </ElFormItem>
        </div>

        <ElFormItem label="Metadata JSON">
          <ElInput
            v-model="metadataText"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 8 }"
            placeholder='{"category":"faq","user_level":"all"}'
          />
        </ElFormItem>

        <ElAlert
          v-if="fileError || errorMessage"
          class="knowledge-upload-view__alert"
          type="error"
          :title="fileError || errorMessage"
          show-icon
          :closable="false"
        />

        <div class="knowledge-upload-form__actions">
          <ElButton native-type="button" @click="clearForm">清空</ElButton>
          <ElButton type="primary" native-type="submit" :disabled="!canSubmit" :loading="isSubmitting">
            {{ form.importToDb ? '切分并写入' : '预览切分' }}
          </ElButton>
        </div>
      </ElForm>
    </section>

    <section v-if="response" class="knowledge-upload-view__panel">
      <div class="knowledge-upload-result__summary">
        <ElStatistic title="切分段数" :value="response.chunk_count" />
        <ElStatistic title="写入段数" :value="importedCount" />
        <ElStatistic title="停用旧段数" :value="deactivatedCount" />
      </div>

      <ElTable v-if="hasChunks" class="knowledge-upload-result__table" :data="response.chunks" border>
        <ElTableColumn prop="chunk_index" label="#" width="72" />
        <ElTableColumn prop="char_count" label="字符" width="90" />
        <ElTableColumn prop="token_count" label="Token" width="90" />
        <ElTableColumn label="内容">
          <template #default="{ row }">
            <p class="knowledge-upload-result__chunk">{{ row.chunk_text }}</p>
          </template>
        </ElTableColumn>
      </ElTable>
    </section>
  </main>
</template>

<style scoped>
.knowledge-upload-view {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 24px;
}

.knowledge-upload-view__header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

.knowledge-upload-view__eyebrow {
  margin: 0 0 4px;
  color: #667085;
  font-size: 13px;
  line-height: 1.4;
}

.knowledge-upload-view__title {
  margin: 0;
  font-size: 28px;
  font-weight: 650;
  line-height: 1.2;
  letter-spacing: 0;
}

.knowledge-upload-view__panel {
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid #e4e7ec;
  border-radius: 8px;
  background: #ffffff;
}

.knowledge-upload-view__alert {
  margin-bottom: 20px;
}

.knowledge-upload-view__section-title {
  margin: 0 0 16px;
  color: #111827;
  font-size: 18px;
  font-weight: 650;
  line-height: 1.3;
  letter-spacing: 0;
}

.knowledge-upload-form {
  display: grid;
  gap: 16px;
}

.knowledge-upload-form__grid,
.knowledge-upload-form__settings {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 16px;
}

.knowledge-upload-form__file-button {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  min-height: 32px;
  padding: 0 12px;
  border: 1px solid #409eff;
  border-radius: 4px;
  color: #ffffff;
  background: #409eff;
  cursor: pointer;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.knowledge-upload-form__file-button:hover {
  border-color: #66b1ff;
  background: #66b1ff;
}

.knowledge-upload-form__file-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.knowledge-upload-form__hint {
  margin: 8px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.knowledge-upload-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.knowledge-upload-result__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(160px, 1fr));
  gap: 16px;
  margin-bottom: 18px;
}

.knowledge-upload-result__table {
  width: 100%;
}

.knowledge-upload-result__chunk {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: #344054;
  line-height: 1.5;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
}

@media (max-width: 860px) {
  .knowledge-upload-form__grid,
  .knowledge-upload-form__settings,
  .knowledge-upload-result__summary {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .knowledge-upload-view {
    padding: 16px;
  }

  .knowledge-upload-view__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .knowledge-upload-view__title {
    font-size: 24px;
  }

  .knowledge-upload-form__actions {
    justify-content: stretch;
  }

  .knowledge-upload-form__actions :deep(.el-button) {
    flex: 1;
  }
}
</style>
