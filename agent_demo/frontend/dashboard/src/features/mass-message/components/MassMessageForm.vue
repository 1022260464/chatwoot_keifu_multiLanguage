<script setup lang="ts">
import { computed, reactive } from 'vue'
import type { MassMessageDraft } from '../types'

interface Props {
  loading?: boolean
  selectedCount?: number
  tokenReady?: boolean
}

interface Emits {
  submit: [draft: MassMessageDraft]
  clear: []
}

const props = withDefaults(defineProps<Props>(), {
  loading: false,
  selectedCount: 0,
  tokenReady: false,
})

const emit = defineEmits<Emits>()

const form = reactive({
  targetText: '',
  content: '',
  private: false,
  delaySeconds: 0.5,
  translateBeforeSend: false,
  targetLanguage: 'en',
})

const conversationIds = computed(() =>
  form.targetText
    .split(/[\s,，]+/)
    .map((item) => item.trim())
    .filter(Boolean),
)

const targetCount = computed(() => conversationIds.value.length + props.selectedCount)

const canSubmit = computed(
  () => targetCount.value > 0 && form.content.trim().length > 0 && props.tokenReady,
)

function handleSubmit() {
  if (!canSubmit.value) {
    return
  }

  emit('submit', {
    manualConversationIds: conversationIds.value,
    content: form.content.trim(),
    private: form.private,
    delaySeconds: form.delaySeconds,
    translateBeforeSend: form.translateBeforeSend,
    targetLanguage: form.targetLanguage,
  })
}

function clearForm() {
  form.targetText = ''
  form.content = ''
  form.private = false
  form.delaySeconds = 0.5
  form.translateBeforeSend = false
  form.targetLanguage = 'en'
  emit('clear')
}
</script>

<template>
  <ElForm class="mass-message-form" label-position="top" @submit.prevent="handleSubmit">
    <ElFormItem label="高级备用：手动补充会话 ID">
      <ElInput
        v-model="form.targetText"
        class="mass-message-form__textarea"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 6 }"
        placeholder="一般不用填写。只有自动列表里找不到时，再输入：1, 2, 3 或每行一个 ID"
      />
      <p class="mass-message-form__hint">
        自动选择 {{ props.selectedCount }} 个，手动补充 {{ conversationIds.length }} 个，共 {{ targetCount }} 个。
      </p>
    </ElFormItem>

    <ElFormItem label="群发内容">
      <ElInput
        v-model="form.content"
        class="mass-message-form__textarea"
        type="textarea"
        maxlength="4000"
        show-word-limit
        :autosize="{ minRows: 6, maxRows: 14 }"
        placeholder="输入要发送给客户或写入内部备注的内容"
      />
    </ElFormItem>

    <div class="mass-message-form__options">
      <ElFormItem label="消息类型">
        <ElSwitch
          v-model="form.private"
          active-text="内部备注"
          inactive-text="客户可见"
          inline-prompt
        />
      </ElFormItem>

      <ElFormItem label="发送前翻译">
        <ElSwitch
          v-model="form.translateBeforeSend"
          active-text="开启"
          inactive-text="关闭"
          inline-prompt
        />
        <p class="mass-message-form__hint">
          关闭时会原文发送；开启后会先翻译成下方选择的语言再发送。
        </p>
      </ElFormItem>

      <ElFormItem v-if="form.translateBeforeSend" label="目标语言">
        <ElSelect v-model="form.targetLanguage" class="mass-message-form__select" placeholder="选择目标语言">
          <ElOption label="英文 English" value="en" />
          <ElOption label="越南语 Tiếng Việt" value="vi" />
          <ElOption label="日语 日本語" value="ja" />
          <ElOption label="韩语 한국어" value="ko" />
          <ElOption label="泰语 ไทย" value="th" />
          <ElOption label="西班牙语 Español" value="es" />
          <ElOption label="法语 Français" value="fr" />
          <ElOption label="俄语 Русский" value="ru" />
          <ElOption label="阿拉伯语 العربية" value="ar" />
        </ElSelect>
      </ElFormItem>

      <ElFormItem label="发送间隔（秒）">
        <ElInputNumber
          v-model="form.delaySeconds"
          :min="0"
          :max="10"
          :step="0.5"
          controls-position="right"
        />
      </ElFormItem>
    </div>

    <div class="mass-message-form__actions">
      <ElButton native-type="button" @click="clearForm">清空内容</ElButton>
      <ElButton type="primary" native-type="submit" :disabled="!canSubmit" :loading="props.loading">
        开始群发
      </ElButton>
    </div>
  </ElForm>
</template>

<style scoped>
.mass-message-form {
  display: grid;
  gap: 16px;
}

.mass-message-form__input,
.mass-message-form__textarea,
.mass-message-form__select {
  width: 100%;
}

.mass-message-form__hint {
  margin: 8px 0 0;
  color: #667085;
  font-size: 13px;
  line-height: 1.5;
}

.mass-message-form__options {
  display: grid;
  grid-template-columns: repeat(4, minmax(160px, 1fr));
  gap: 16px;
}

.mass-message-form__actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

@media (max-width: 720px) {
  .mass-message-form__options {
    grid-template-columns: 1fr;
  }

  .mass-message-form__actions {
    justify-content: stretch;
  }

  .mass-message-form__actions :deep(.el-button) {
    flex: 1;
  }
}
</style>
