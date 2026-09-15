<template>
  <div :class="['portal-layout', { 'portal-layout--fixed': route.meta.flush }]">
    <PortalHeader />
    <main :class="['portal-main', { 'portal-main--flush': route.meta.flush, 'portal-main--wide': route.meta.wide }]">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <PortalFooter v-if="!route.meta.hideFooter" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, watch } from 'vue'
import { useRoute } from 'vue-router'
import PortalHeader from '@/components/portal/PortalHeader.vue'
import PortalFooter from '@/components/portal/PortalFooter.vue'

const route = useRoute()

function syncViewportLock(fixed) {
  document.documentElement.classList.toggle('portal-viewport-lock', fixed)
}

watch(() => route.meta.flush, (fixed) => syncViewportLock(Boolean(fixed)), { immediate: true })
onBeforeUnmount(() => syncViewportLock(false))
</script>

<style scoped>
.portal-layout { min-height: 100%; background: var(--page-bg); }
.portal-layout--fixed {
  height: 100%;
  max-height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  overscroll-behavior: none;
}
.portal-layout--fixed :deep(.portal-header) {
  flex-shrink: 0;
}
.portal-main { width: min(100% - 40px, 1440px); min-height: calc(100vh - var(--portal-header-height)); margin: 0 auto; padding: 28px 0 0; }
.portal-main--wide { width: min(100% - 32px, 1600px); }
.portal-main--flush {
  width: 100%;
  padding: 0;
  margin: 0;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}
.portal-main--flush :deep(> *) {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: block;
}
.portal-main--flush :deep(.map-page) {
  height: 100%;
  overflow: hidden;
  overscroll-behavior: none;
}
@media (max-width: 760px) {
  .portal-main, .portal-main--wide { width: calc(100% - 24px); padding-top: 18px; }
  .portal-main--flush { width: 100%; padding: 0; }
}
</style>
