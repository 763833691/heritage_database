<template>
  <span class="status-badge" :class="`status-badge--${display.tone}`">{{ display.label }}</span>
</template>

<script setup>
import { computed } from 'vue'
import { getWorkflowDisplayStatus } from '@/features/kg/constants'

const props = defineProps({
  status: { type: String, required: true },
  processStatus: { type: Object, default: null },
})

const display = computed(() => getWorkflowDisplayStatus(props.status, props.processStatus))
</script>

<style scoped lang="scss">
.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.6;
  white-space: nowrap;
  box-shadow: inset 0 0 0 1px rgba(15, 23, 42, .05);
}

.status-badge--processing {
  color: var(--brand-600);
  background: var(--brand-50);
}

.status-badge--failed {
  color: var(--red-500);
  background: #fef2f2;
}

.status-badge--success {
  color: #15803d;
  background: #ecfdf5;
}

.status-badge--neutral {
  color: var(--text-secondary);
  background: var(--surface-soft);
}

.status-badge--violet {
  color: var(--violet-500);
  background: #f5f3ff;
}

.status-badge--cyan {
  color: #0e7490;
  background: #ecfeff;
}

.status-badge--warning {
  color: #b45309;
  background: #fffbeb;
}
</style>
