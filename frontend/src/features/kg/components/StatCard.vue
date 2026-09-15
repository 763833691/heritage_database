<template>
  <div class="stat-card">
    <div class="stat-card__copy">
      <div class="stat-card__label">{{ label }}</div>
      <div class="stat-card__value">{{ value }}</div>
      <div v-if="delta" class="stat-card__delta">较上次 <span>{{ delta }}</span></div>
    </div>
    <span class="stat-card__icon" :class="`stat-card__icon--${tone}`">
      <el-icon><component :is="icon" /></el-icon>
    </span>
  </div>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  delta: { type: String, default: '' },
  tone: { type: String, default: 'blue' },
  icon: { type: [String, Object, Function], default: '' },
})
</script>

<style scoped lang="scss">
.stat-card {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.stat-card__label {
  color: var(--text-secondary);
  font-size: 12px;
}

.stat-card__value {
  margin-top: 6px;
  color: var(--text-primary);
  font-size: 26px;
  font-weight: 750;
  line-height: 1.1;
}

.stat-card__delta {
  margin-top: 4px;
  color: var(--text-tertiary);
  font-size: 11px;
}

.stat-card__delta span {
  color: var(--green-500);
}

.stat-card__icon {
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  flex: 0 0 auto;
  border-radius: var(--radius-lg);
  font-size: 22px;
}

.stat-card__icon--blue {
  color: var(--brand-600);
  background: var(--brand-50);
}

.stat-card__icon--green {
  color: #15803d;
  background: #ecfdf5;
}

.stat-card__icon--violet {
  color: var(--violet-500);
  background: #f5f3ff;
}

.stat-card__icon--orange {
  color: var(--orange-500);
  background: #fffbeb;
}
</style>
