<template>
  <div class="home-page">
    <section class="home-hero">
      <img :src="portalHero" alt="蓝白数字孪生风格的中国传统宫殿建筑" class="home-hero__art" />
      <div class="home-hero__content">
        <span class="home-hero__badge">国家考古遗址公园 · 数字研究门户</span>
        <h1>探索遗址公园<br /><em>数据 · 知识 · 智能</em></h1>
        <p>整合全国遗址公园数据、评价体系与知识资源，为文化遗产保护、科学研究与管理决策提供可信支持。</p>
        <div class="home-hero__actions">
          <el-button type="primary" size="large" @click="$router.push('/parks')">开始探索 <el-icon><ArrowRight /></el-icon></el-button>
          <el-button size="large" plain @click="$router.push('/about')">了解平台</el-button>
        </div>
      </div>
    </section>

    <section class="home-stats" aria-label="平台核心数据">
      <article v-for="item in statItems" :key="item.label" class="home-stat">
        <span :class="['home-stat__icon', item.tone]"><el-icon><component :is="item.icon" /></el-icon></span>
        <div><span>{{ item.label }}</span><strong>{{ item.value }}</strong><small>{{ item.meta }}</small></div>
      </article>
    </section>

    <section class="home-section">
      <div class="section-heading">
        <div><span class="eyebrow">RESEARCH TOOLKIT</span><h2>从数据到洞察，一站式展开遗址研究</h2></div>
      </div>
      <div class="feature-grid">
        <router-link v-for="feature in features" :key="feature.path" :to="feature.path" class="feature-card">
          <span :class="['feature-card__icon', feature.tone]"><el-icon><component :is="feature.icon" /></el-icon></span>
          <div><h3>{{ feature.title }}</h3><p>{{ feature.description }}</p></div>
          <el-icon class="feature-card__arrow"><ArrowRight /></el-icon>
        </router-link>
      </div>
    </section>

    <section class="home-content-grid">
      <div class="section-card research-panel">
        <div class="section-card__header">
          <div><span class="eyebrow">LATEST RESEARCH</span><h2>最新研究动态</h2><p>来自平台知识库的真实文献与研究成果。</p></div>
          <router-link to="/library" class="section-heading__link">查看全部 <el-icon><ArrowRight /></el-icon></router-link>
        </div>
        <StatusState v-if="researchLoading" type="loading" title="正在读取研究成果" />
        <StatusState v-else-if="!researchItems.length" type="empty" title="暂无公开研究成果" description="知识库有新内容后会自动显示在这里。" />
        <div v-else class="research-list">
          <article v-for="item in researchItems" :key="item.id" class="research-item">
            <span class="research-item__type">{{ item.doc_type || '文献' }}</span>
            <div><h3>{{ item.title }}</h3><p>{{ authorText(item) }} · {{ item.year || '年份未知' }}</p></div>
            <el-icon><ArrowRight /></el-icon>
          </article>
        </div>
      </div>

      <div class="section-card platform-panel">
        <div class="section-card__header"><div><span class="eyebrow">PLATFORM VALUE</span><h2>平台亮点</h2></div></div>
        <div class="value-list">
          <div v-for="value in values" :key="value.title">
            <span :class="['value-list__icon', value.tone]"><el-icon><component :is="value.icon" /></el-icon></span>
            <div><h3>{{ value.title }}</h3><p>{{ value.description }}</p></div>
          </div>
        </div>
      </div>
    </section>

    <section class="home-section">
      <div class="section-heading">
        <div><span class="eyebrow">HERITAGE PARKS</span><h2>遗址公园精选</h2><p>浏览平台当前收录的真实遗址公园数据。</p></div>
        <router-link to="/parks" class="section-heading__link">全部公园 <el-icon><ArrowRight /></el-icon></router-link>
      </div>
      <StatusState v-if="parksLoading" type="loading" title="正在读取公园数据" />
      <StatusState v-else-if="!parks.length" type="empty" title="暂无遗址公园数据" />
      <div v-else class="park-preview-grid">
        <router-link v-for="park in parks" :key="park.id" :to="`/parks/${park.id}`" class="park-preview-card">
          <img :src="parkCover" :alt="`${park.short_name || park.name}主题封面`" />
          <div class="park-preview-card__body">
            <span>第{{ park.batch || '—' }}批 · {{ park.park_type || '类型未录入' }}</span>
            <h3>{{ park.short_name || park.name }}</h3>
            <p><el-icon><Location /></el-icon>{{ park.province }} {{ park.city }}</p>
          </div>
        </router-link>
      </div>
    </section>

    <section class="home-callout">
      <div><span class="eyebrow">RESEARCH WITH EVIDENCE</span><h2>让数据赋能文化遗产保护，让知识驱动未来研究</h2></div>
      <el-button type="primary" size="large" @click="$router.push('/research-data')">查看研究数据</el-button>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  OfficeBuilding, Location, DataAnalysis, PieChart, MapLocation, TrendCharts,
  Share, ChatDotRound, Collection, Document, Search, Connection, CircleCheck,
} from '@element-plus/icons-vue'
import api from '@/utils/api'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'
import parkCover from '@/assets/images/park-cover-fallback.webp'

const stats = ref({})
const parks = ref([])
const researchItems = ref([])
const parksLoading = ref(true)
const researchLoading = ref(true)

const statItems = computed(() => [
  { label: '遗址公园数量', value: formatNumber(stats.value.total_parks), meta: `覆盖 ${Object.keys(stats.value.by_province || {}).length} 个省级区域`, icon: OfficeBuilding, tone: 'blue' },
  { label: '遗址地点', value: formatNumber(stats.value.total_sites), meta: stats.value.total_sites ? '已录入遗址点数据' : '当前暂无遗址点记录', icon: Location, tone: 'green' },
  { label: '评价指标', value: formatNumber(stats.value.total_indicators), meta: '多维度评价体系', icon: DataAnalysis, tone: 'violet' },
  { label: '公园批次', value: `${Object.keys(stats.value.by_batch || {}).length}`, meta: '当前数据中的评定批次', icon: PieChart, tone: 'orange' },
])

const features = [
  { title: '研究数据', description: '真实统计数据与多维可视化', path: '/research-data', icon: DataAnalysis, tone: 'blue' },
  { title: '遗址公园', description: '浏览公园档案与评价指标', path: '/parks', icon: OfficeBuilding, tone: 'sand' },
  { title: '地图浏览', description: '探索空间分布与区域特征', path: '/map', icon: MapLocation, tone: 'green' },
  { title: '对比分析', description: '多公园综合指标横向比较', path: '/compare', icon: TrendCharts, tone: 'blue' },
  { title: '知识图谱', description: '发现实体关系与研究脉络', path: '/knowledge-graph', icon: Share, tone: 'violet' },
  { title: 'AI助手', description: '以数据与知识辅助研究', path: '/assistant', icon: ChatDotRound, tone: 'cyan' },
  { title: '知识库', description: '文献、报告与知识资源', path: '/library', icon: Collection, tone: 'indigo' },
  { title: '文献计量', description: '洞察研究趋势与热点', path: '/bibliometrics', icon: Document, tone: 'orange' },
]

const values = [
  { title: '权威数据整合', description: '统一汇聚真实公园、指标与研究数据。', icon: CircleCheck, tone: 'blue' },
  { title: '多维研究工具', description: '从空间、评价到文献的完整分析链路。', icon: Search, tone: 'green' },
  { title: '知识智能联动', description: '知识图谱与 AI 助手连接研究线索。', icon: Connection, tone: 'violet' },
]

onMounted(() => {
  loadOverview()
  loadParks()
  loadResearch()
})

async function loadOverview() {
  try { stats.value = (await api.get('/statistics/overview', { silent: true })).data } catch { stats.value = {} }
}
async function loadParks() {
  try { parks.value = (await api.get('/parks', { params: { page_size: 4 }, silent: true })).data.items || [] } finally { parksLoading.value = false }
}
async function loadResearch() {
  try { researchItems.value = (await api.get('/knowledge/list', { params: { page: 1, page_size: 4 }, silent: true })).data.items || [] } finally { researchLoading.value = false }
}
function formatNumber(value) { return Number(value || 0).toLocaleString('zh-CN') }
function authorText(item) { return (item.authors || []).slice(0, 2).map((author) => author.name).filter(Boolean).join('、') || '作者未录入' }
</script>

<style scoped lang="scss">
.home-page { display: grid; gap: 30px; }
.home-hero { min-height: 470px; position: relative; overflow: hidden; border: 0; border-radius: 0; background: #f9fbff; box-shadow: none; }
.home-hero__art { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: center; }
.home-hero__content { width: 50%; min-height: 470px; padding: 68px 0 64px 64px; position: relative; z-index: 2; display: flex; flex-direction: column; justify-content: center; }
.home-hero__badge { width: fit-content; margin-bottom: 18px; padding: 0 0 8px; border: 0; border-bottom: 1px solid var(--brand-600); border-radius: 0; color: var(--brand-600); background: transparent; font-size: 12px; font-weight: 650; }
.home-hero h1 { margin: 0; font-size: clamp(42px, 4.4vw, 64px); line-height: 1.12; letter-spacing: -.045em; }
.home-hero h1 em { color: var(--brand-600); font-style: normal; }
.home-hero p { max-width: 600px; margin: 24px 0 0; color: #536078; font-size: 16px; line-height: 1.9; }
.home-hero__actions { display: flex; gap: 12px; margin-top: 30px; }
.home-stats { margin-top: -42px; padding: 0 32px; position: relative; z-index: 3; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); background: rgba(255,255,255,.94); border-top: 1px solid var(--border); border-bottom: 1px solid var(--border); }
.home-stat { min-height: 104px; padding: 20px 24px; display: flex; align-items: center; gap: 14px; border: 0; border-right: 1px solid var(--border); background: transparent; box-shadow: none; }
.home-stat:first-child { border-radius: 0; }
.home-stat:last-child { border-right: 0; border-radius: 0; }
.home-stat__icon, .feature-card__icon, .value-list__icon, .home-stat__icon.green, .home-stat__icon.violet, .home-stat__icon.orange, .feature-card__icon.green, .feature-card__icon.violet, .feature-card__icon.cyan, .feature-card__icon.orange, .feature-card__icon.sand, .feature-card__icon.indigo, .value-list__icon.green, .value-list__icon.violet { display: grid; place-items: center; flex: 0 0 auto; color: var(--brand-600); background: transparent; }
.home-stat__icon { width: 34px; height: 34px; border-radius: 0; font-size: 22px; }
.home-stat div { min-width: 0; display: grid; }.home-stat span { color: var(--text-secondary); font-size: 12px; }.home-stat strong { margin-top: 2px; font-size: 25px; }.home-stat small { margin-top: 4px; color: var(--text-tertiary); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.home-section { display: grid; gap: 18px; padding-top: 12px; }
.feature-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; border-top: 1px solid var(--border); }
.feature-card { min-height: 110px; padding: 24px 12px; display: grid; grid-template-columns: auto 1fr auto; align-items: start; gap: 14px; color: inherit; text-decoration: none; border: 0; border-bottom: 1px solid var(--border); border-radius: 0; background: transparent; box-shadow: none; transition: color .2s ease, background-color .2s ease; }
.feature-card:hover { color: var(--brand-700); background: #f8fafc; }
.feature-card__icon { width: 30px; height: 30px; border-radius: 0; font-size: 23px; }
.feature-card h3 { margin: 3px 0 7px; font-size: 16px; }.feature-card p { color: var(--text-secondary); font-size: 12px; line-height: 1.6; }.feature-card__arrow { margin-top: 4px; color: var(--text-tertiary); }
.home-content-grid { display: grid; grid-template-columns: 1.35fr .8fr; gap: 0; padding-top: 24px; border-top: 1px solid var(--border); }.research-panel,.platform-panel{padding:0 24px 0 0}.platform-panel{padding:0 0 0 32px;border-left:1px solid var(--border)}.research-list{display:grid}.research-item{min-height:76px;display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:14px;border-bottom:1px solid var(--border)}.research-item:last-child{border-bottom:0}.research-item__type{padding:6px 9px;border-radius:4px;color:var(--brand-600);background:var(--brand-50);font-size:11px}.research-item h3{margin:0;font-size:14px;line-height:1.5}.research-item p{margin:5px 0 0;color:var(--text-tertiary);font-size:11px}.research-item>.el-icon{color:var(--text-tertiary)}
.value-list{display:grid;gap:20px}.value-list>div{display:flex;gap:13px}.value-list__icon{width:30px;height:30px;border-radius:0;font-size:19px}.value-list h3{margin:1px 0 5px;font-size:14px}.value-list p{color:var(--text-secondary);font-size:12px;line-height:1.6}
.park-preview-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:24px}.park-preview-card{overflow:hidden;color:inherit;text-decoration:none;border:0;border-radius:0;background:transparent;box-shadow:none}.park-preview-card>img{width:100%;height:180px;object-fit:cover;border-radius:4px;transition:transform .3s ease}.park-preview-card:hover>img{transform:scale(1.025)}.park-preview-card__body{padding:14px 0 0}.park-preview-card__body span{color:var(--brand-600);font-size:11px}.park-preview-card h3{margin:7px 0 10px;font-size:16px}.park-preview-card p{display:flex;align-items:center;gap:5px;color:var(--text-secondary);font-size:12px}
.home-callout{min-height:160px;padding:36px 42px;display:flex;align-items:center;justify-content:space-between;gap:24px;border-radius:var(--radius-xl);color:#fff;background:#162b57}.home-callout .eyebrow{color:#8fb4ff}.home-callout h2{max-width:780px;margin:8px 0 0;font-size:25px;line-height:1.4}
@media (max-width:1080px){.home-hero__content{width:62%;padding-left:44px}.home-stats{grid-template-columns:repeat(2,1fr);margin-top:-40px}.home-stat:nth-child(2){border-right:0;border-radius:0}.home-stat:nth-child(3){border-radius:0}.feature-grid,.park-preview-grid{grid-template-columns:repeat(2,1fr)}}
@media (max-width:760px){.home-page{gap:22px}.home-hero{min-height:520px}.home-hero__art{object-position:64% center;opacity:.38}.home-hero__content{width:100%;min-height:520px;padding:44px 24px;justify-content:flex-end}.home-hero h1{font-size:42px}.home-hero p{font-size:14px}.home-stats{margin-top:-26px;padding:0 12px;display:flex;overflow-x:auto}.home-stat{min-width:235px;border-right:1px solid var(--border);border-radius:0!important}.home-stat:last-child{border-right:0}.feature-grid,.park-preview-grid,.home-content-grid{grid-template-columns:1fr}.feature-card{min-height:100px}.platform-panel{padding:24px 0 0;border-left:0;border-top:1px solid var(--border)}.park-preview-card>img{height:190px}.home-callout{align-items:flex-start;flex-direction:column;padding:28px}.home-callout h2{font-size:21px}}
</style>
