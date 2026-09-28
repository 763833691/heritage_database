<template>
  <header class="portal-header">
    <div class="portal-header__inner">
      <router-link class="portal-brand" to="/" aria-label="返回首页">
        <span class="portal-brand__mark"><el-icon><OfficeBuilding /></el-icon></span>
        <span class="portal-brand__copy">
          <strong>遗址公园研究平台</strong>
          <small>HERITAGE PARK RESEARCH PLATFORM</small>
        </span>
      </router-link>

      <nav class="portal-nav" aria-label="主导航">
        <router-link
          v-for="item in portalNavigation"
          :key="item.path"
          :to="item.path"
          :class="['portal-nav__item', { active: isNavigationActive(item, route.path) }]"
          :aria-current="isNavigationActive(item, route.path) ? 'page' : undefined"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="portal-header__actions">
        <button class="header-icon-button header-search-button" type="button" aria-label="打开全站搜索" @click="searchOpen = true">
          <el-icon><Search /></el-icon>
        </button>

        <template v-if="auth.isLoggedIn">
          <el-dropdown trigger="click" @command="handleCommand">
            <button type="button" class="user-button" aria-label="打开用户菜单">
              <el-avatar :size="30" icon="UserFilled" />
              <span>{{ auth.user?.full_name || auth.user?.username || '访客' }}</span>
              <el-icon><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-if="auth.isAdmin" command="admin">
                  <el-icon><Setting /></el-icon>数据管理
                </el-dropdown-item>
                <el-dropdown-item v-if="AUTH_ENABLED" command="logout" divided>
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </template>
        <router-link v-else class="portal-login-button" to="/login">登录 / 注册</router-link>

        <button class="header-icon-button mobile-menu-button" type="button" aria-label="打开移动导航" @click="mobileOpen = true">
          <el-icon><Menu /></el-icon>
        </button>
      </div>
    </div>

    <el-dialog v-model="searchOpen" class="global-search-dialog" title="全站搜索" width="min(640px, 92vw)" append-to-body @closed="resetSearch">
      <el-input
        v-model="searchText"
        size="large"
        autofocus
        clearable
        placeholder="搜索遗址公园、文献或指标"
        @keyup.enter="submitSearch"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
        <template #append><el-button :loading="searching" @click="submitSearch">搜索</el-button></template>
      </el-input>
      <div class="global-search-dialog__hints">
        <button v-for="term in searchSuggestions" :key="term" type="button" @click="searchText = term; submitSearch()">{{ term }}</button>
      </div>

      <div v-if="searching" class="global-search-status">正在检索遗址公园与文献…</div>
      <div v-else-if="searchError" class="global-search-status global-search-status--error">{{ searchError }}</div>
      <div v-else-if="searched" class="global-search-results">
        <section v-if="parkResults.length">
          <h4>遗址公园（{{ parkResults.length }}）</h4>
          <button v-for="park in parkResults" :key="park.id" type="button" @click="goPark(park)">
            <strong>{{ park.short_name || park.name }}</strong>
            <small>{{ park.province }} {{ park.city }} · {{ park.park_type || '类型未录入' }}</small>
          </button>
        </section>
        <section v-if="litResults.length">
          <h4>文献（{{ litResults.length }}）</h4>
          <button v-for="lit in litResults" :key="lit.id" type="button" @click="goLiterature(lit)">
            <strong>{{ lit.title }}</strong>
            <small>{{ lit.year || '年份未知' }} · {{ lit.journal || '来源未录入' }}</small>
          </button>
        </section>
        <p v-if="!parkResults.length && !litResults.length" class="global-search-status">未找到与“{{ lastKeyword }}”相关的结果。</p>
      </div>
    </el-dialog>

    <el-drawer v-model="mobileOpen" direction="rtl" size="min(360px, 88vw)" class="mobile-nav-drawer" append-to-body>
      <template #header>
        <div class="mobile-nav-title">
          <span class="portal-brand__mark"><el-icon><OfficeBuilding /></el-icon></span>
          <strong>遗址公园研究平台</strong>
        </div>
      </template>
      <nav class="mobile-nav" aria-label="移动端主导航">
        <router-link
          v-for="item in portalNavigation"
          :key="item.path"
          :to="item.path"
          :class="{ active: isNavigationActive(item, route.path) }"
          @click="mobileOpen = false"
        >
          <span>{{ item.label }}</span><el-icon><ArrowRight /></el-icon>
        </router-link>
        <router-link v-if="auth.isAdmin" to="/data-management" @click="mobileOpen = false">
          <span>数据管理</span><el-icon><ArrowRight /></el-icon>
        </router-link>
      </nav>
    </el-drawer>
  </header>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import { AUTH_ENABLED } from '@/config/app'
import { portalNavigation, isNavigationActive } from '@/config/navigation'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const searchOpen = ref(false)
const mobileOpen = ref(false)
const searchText = ref('')
const searchSuggestions = ['圆明园', '保护利用', '文化传播', '大明宫']
const searching = ref(false)
const searched = ref(false)
const searchError = ref('')
const lastKeyword = ref('')
const parkResults = ref([])
const litResults = ref([])

async function submitSearch() {
  const keyword = searchText.value.trim()
  if (!keyword) return
  searching.value = true
  searched.value = true
  searchError.value = ''
  lastKeyword.value = keyword
  try {
    const [parkRes, litRes] = await Promise.allSettled([
      api.get('/parks', { params: { keyword, page_size: 5 }, silent: true }),
      api.get('/knowledge/search', { params: { q: keyword, limit: 6 }, silent: true }),
    ])
    parkResults.value = parkRes.status === 'fulfilled' ? (parkRes.value.data.items || []) : []
    litResults.value = litRes.status === 'fulfilled' ? (litRes.value.data.results || []) : []
    if (parkRes.status === 'rejected' && litRes.status === 'rejected') {
      searchError.value = '搜索服务暂不可用，请稍后重试。'
    }
  } catch (error) {
    searchError.value = error.response?.data?.detail || '搜索失败，请稍后重试。'
    parkResults.value = []
    litResults.value = []
  } finally {
    searching.value = false
  }
}

function resetSearch() {
  searched.value = false
  searchError.value = ''
  lastKeyword.value = ''
  parkResults.value = []
  litResults.value = []
}

function goPark(park) {
  searchOpen.value = false
  router.push(`/parks/${park.id}`)
}

function goLiterature(lit) {
  searchOpen.value = false
  router.push({ path: '/library', query: { lit: lit.id } })
}

function handleCommand(command) {
  if (command === 'admin') router.push('/data-management')
  if (command === 'logout' && AUTH_ENABLED) {
    auth.logout()
    router.push('/login')
  }
}
</script>

<style scoped lang="scss">
.portal-header {
  position: sticky;
  inset: 0 0 auto;
  z-index: 1000;
  height: var(--portal-header-height);
  background: rgba(255, 255, 255, 0.96);
  border-bottom: 1px solid var(--border);
  backdrop-filter: blur(18px);
}

.portal-header__inner {
  width: 100%;
  height: 100%;
  padding: 0 16px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto;
  align-items: center;
  gap: 20px;
}

.portal-brand {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  color: var(--text-primary);
  text-decoration: none;
  justify-self: start;
}

.portal-brand__mark {
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #fff;
  background: var(--brand-600);
  box-shadow: 0 8px 20px rgba(37, 99, 235, 0.22);
  font-size: 22px;
}

.portal-brand__copy { display: grid; line-height: 1.1; }
.portal-brand__copy strong { font-size: 17px; letter-spacing: 0.01em; }
.portal-brand__copy small { margin-top: 5px; font-size: 7px; color: var(--text-tertiary); letter-spacing: 0.05em; }

.portal-nav { height: 100%; display: flex; align-items: stretch; justify-content: center; min-width: 0; justify-self: center; }
.portal-nav__item {
  min-width: max-content;
  padding: 0 13px;
  display: grid;
  place-items: center;
  position: relative;
  color: #344054;
  font-size: 14px;
  text-decoration: none;
  transition: color .2s ease;
}
.portal-nav__item::after {
  content: '';
  position: absolute;
  left: 50%;
  right: 50%;
  bottom: -1px;
  height: 2px;
  background: var(--brand-600);
  transition: left .2s ease, right .2s ease;
}
.portal-nav__item:hover, .portal-nav__item.active { color: var(--brand-600); }
.portal-nav__item.active::after { left: 14px; right: 14px; }

.portal-header__actions { display: flex; align-items: center; gap: 8px; justify-self: end; }
.header-icon-button, .user-button {
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text-secondary);
  cursor: pointer;
}
.header-icon-button { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; font-size: 18px; }
.header-icon-button:hover { color: var(--brand-600); border-color: var(--brand-100); background: #f8fbff; }
.user-button { height: 40px; border-radius: 12px; padding: 0 10px 0 5px; display: inline-flex; align-items: center; gap: 7px; font: inherit; font-size: 13px; }
.portal-login-button { padding: 10px 18px; border-radius: 11px; background: var(--brand-600); color: #fff; text-decoration: none; font-size: 13px; }
.mobile-menu-button { display: none; }

@media (max-width: 1320px) {
  .portal-header__inner { padding: 0 14px; gap: 12px; }
  .portal-nav__item { padding: 0 9px; font-size: 13px; }
  .portal-brand__copy small { display: none; }
}
@media (max-width: 1120px) {
  .portal-header__inner { grid-template-columns: auto 1fr auto; }
  .portal-nav { display: none; }
  .mobile-menu-button { display: grid; }
}
@media (max-width: 640px) {
  .portal-header__inner { padding: 0 12px; }
  .portal-brand__copy strong { font-size: 15px; }
  .user-button span, .user-button > .el-icon, .header-search-button { display: none; }
  .user-button { width: 40px; padding: 4px; }
}
</style>

<style lang="scss">
.global-search-dialog__hints { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }
.global-search-dialog__hints button { border: 1px solid var(--border); background: var(--surface-soft); color: var(--text-secondary); padding: 7px 12px; border-radius: 999px; cursor: pointer; }
.global-search-status { margin-top: 16px; color: var(--text-secondary); font-size: 13px; }
.global-search-status--error { color: #dc2626; }
.global-search-results { margin-top: 18px; display: grid; gap: 16px; max-height: 52vh; overflow-y: auto; }
.global-search-results h4 { margin: 0 0 8px; color: var(--text-tertiary); font-size: 12px; font-weight: 600; }
.global-search-results section { display: grid; gap: 6px; }
.global-search-results button { display: grid; gap: 3px; padding: 11px 13px; text-align: left; border: 1px solid var(--border); border-radius: 11px; background: #fff; cursor: pointer; transition: border-color .2s ease; }
.global-search-results button:hover { border-color: var(--brand-200); background: var(--brand-50); }
.global-search-results button strong { color: var(--text-primary); font-size: 13px; }
.global-search-results button small { color: var(--text-tertiary); font-size: 11px; }
.mobile-nav-title { display: flex; align-items: center; gap: 10px; color: var(--text-primary); }
.mobile-nav { display: grid; gap: 6px; }
.mobile-nav a { display: flex; align-items: center; justify-content: space-between; padding: 14px 12px; color: var(--text-primary); text-decoration: none; border-radius: 12px; }
.mobile-nav a:hover, .mobile-nav a.active { color: var(--brand-600); background: var(--brand-50); }
</style>
