<template>
  <div :class="['status-state', `status-state--${type}`]" role="status">
    <span class="status-state__icon"><el-icon><component :is="iconComponent" /></el-icon></span>
    <h3>{{ title }}</h3>
    <p v-if="description">{{ description }}</p>
    <el-button v-if="actionLabel" type="primary" plain @click="$emit('action')">{{ actionLabel }}</el-button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Loading, Warning, Lock, FolderOpened } from '@element-plus/icons-vue'

const props = defineProps({
  type: { type: String, default: 'empty' },
  title: { type: String, required: true },
  description: { type: String, default: '' },
  actionLabel: { type: String, default: '' },
})
defineEmits(['action'])

const iconComponent = computed(() => ({ loading: Loading, error: Warning, forbidden: Lock, empty: FolderOpened }[props.type] || FolderOpened))
</script>

<style scoped lang="scss">
.status-state { min-height: 220px; padding: 36px; display: grid; place-items: center; align-content: center; gap: 10px; text-align: center; border: 1px dashed var(--border-strong); border-radius: var(--radius-lg); background: rgba(255, 255, 255, .76); }
.status-state__icon { width: 52px; height: 52px; display: grid; place-items: center; border-radius: 16px; color: var(--brand-600); background: var(--brand-50); font-size: 24px; }
.status-state h3 { margin: 4px 0 0; color: var(--text-primary); font-size: 17px; }
.status-state p { max-width: 480px; margin: 0; color: var(--text-secondary); line-height: 1.7; font-size: 13px; }
.status-state--loading .status-state__icon { animation: spin 1.2s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .status-state--loading .status-state__icon { animation: none; } }
</style>
