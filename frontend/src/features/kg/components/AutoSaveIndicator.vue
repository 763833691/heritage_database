<template>
  <span v-if="visible" class="auto-save-indicator" :class="`auto-save-indicator--${tone}`">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: { type: String, default: 'idle' },
  saving: { type: Boolean, default: false },
})

const visible = computed(() => props.status !== 'idle' || props.saving)

const label = computed(() => {
  if (props.status === 'saving' || props.saving) return '正在保存...'
  if (props.status === 'saved') return '已自动保存'
  if (props.status === 'error') return '保存失败'
  return ''
})

const tone = computed(() => {
  if (props.status === 'error') return 'error'
  if (props.status === 'saved') return 'saved'
  return 'neutral'
})
</script>

<style scoped lang="scss">
.auto-save-indicator {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border: 1px solid transparent;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  white-space: nowrap;
}

.auto-save-indicator--neutral {
  color: var(--text-secondary);
  border-color: var(--border);
  background: var(--surface-soft);
}

.auto-save-indicator--saved {
  color: #15803d;
  border-color: #bbf7d0;
  background: #ecfdf5;
}

.auto-save-indicator--error {
  color: var(--red-500);
  border-color: #fecaca;
  background: #fef2f2;
}
</style>
