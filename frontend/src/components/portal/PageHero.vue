<template>
  <section :class="['page-context', { 'has-actions': $slots.actions }]">
    <h1 class="page-context__title">{{ title }}<span v-if="accent"> / {{ accent }}</span></h1>
    <div v-if="$slots.actions" class="page-context__actions" aria-label="页面操作"><slot name="actions" /></div>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  accent: { type: String, default: '' },
  description: { type: String, default: '' },
  eyebrow: { type: String, default: '' },
  image: { type: String, default: '' },
  compact: { type: Boolean, default: false },
})
</script>

<style scoped lang="scss">
.page-context { display: contents; }
.page-context.has-actions { min-height: 40px; display: flex; align-items: center; justify-content: flex-end; }
.page-context__title { width: 1px; height: 1px; padding: 0; position: absolute; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
.page-context__actions { display: flex; gap: 8px; flex-wrap: wrap; }
@media (max-width: 760px) { .page-context.has-actions { justify-content: flex-start; } }
</style>
