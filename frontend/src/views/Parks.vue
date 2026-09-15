<template>
  <div class="page-shell parks-page">
    <PageHero title="遗址公园" description="全面展示平台已收录遗址公园的建设与发展信息，支持按类型、区域和批次检索真实数据。" :image="portalHero" compact />

    <section class="filter-surface parks-filter" aria-label="遗址公园筛选">
      <div class="parks-filter__grid">
        <label><span>类型</span><el-select v-model="filters.park_type" clearable placeholder="全部类型"><el-option v-for="type in parkTypes" :key="type" :label="type" :value="type" /></el-select></label>
        <label><span>省份</span><el-select v-model="filters.province" clearable filterable placeholder="全部省份"><el-option v-for="province in provinces" :key="province" :label="province" :value="province" /></el-select></label>
        <label><span>批次</span><el-select v-model="filters.batch" clearable placeholder="全部批次"><el-option v-for="batch in batches" :key="batch" :label="`第${batch}批`" :value="batch" /></el-select></label>
        <label class="parks-filter__search"><span>关键词</span><el-input v-model="filters.keyword" clearable placeholder="搜索公园名称、地点" @keyup.enter="applyFilters"><template #prefix><el-icon><Search /></el-icon></template></el-input></label>
        <div class="parks-filter__actions">
          <el-button type="primary" @click="applyFilters">查询公园</el-button>
          <el-button @click="resetFilters">重置</el-button>
          <el-button v-if="auth.isAdmin" type="success" @click="showCreateDialog"><el-icon><Plus /></el-icon> 新增遗址公园</el-button>
        </div>
      </div>
    </section>

    <section v-if="featured" class="featured-park section-card">
      <div class="featured-park__image"><img :src="parkCover" :alt="`${featured.short_name || featured.name}主题封面`" /><span>当前数据推荐</span></div>
      <div class="featured-park__content"><span class="eyebrow">FEATURED HERITAGE PARK</span><h2>{{ featured.short_name || featured.name }}</h2><p class="featured-park__meta"><el-icon><Location /></el-icon>{{ featured.province }} {{ featured.city }}<i></i>第{{ featured.batch || '—' }}批<i></i>{{ featured.park_type || '类型未录入' }}</p><p>{{ featured.description || '当前公园尚未录入简介，可进入详情查看已有指标和基础信息。' }}</p><el-button type="primary" plain @click="goDetail(featured.id)">查看详情 <el-icon><ArrowRight /></el-icon></el-button></div>
      <div class="featured-park__scores"><div class="featured-score"><span>综合均分</span><strong>{{ averageScore(featured) }}</strong><small>按已录入评价指标计算</small></div><div v-for="score in featured.scores?.slice(0, 4)" :key="score.indicator_code" class="score-line"><div><span>{{ score.indicator_name }}</span><strong>{{ score.score ?? '—' }}</strong></div><el-progress :percentage="score.score || 0" :show-text="false" :stroke-width="6" /></div></div>
    </section>

    <section class="parks-results">
      <div class="section-heading"><div><h2>共 {{ total }} 个遗址公园</h2><p>所有数据均来自当前平台真实接口。</p></div><div class="results-tools"><el-select v-model="sortMode" size="small" style="width:120px"><el-option label="默认排序" value="default"/><el-option label="评分优先" value="score"/><el-option label="批次优先" value="batch"/></el-select><el-radio-group v-model="viewMode" size="small"><el-radio-button value="grid"><el-icon><Grid /></el-icon> 卡片</el-radio-button><el-radio-button value="list"><el-icon><List /></el-icon> 列表</el-radio-button></el-radio-group></div></div>
      <StatusState v-if="loading" type="loading" title="正在加载遗址公园" />
      <StatusState v-else-if="error" type="error" title="遗址公园加载失败" :description="error" action-label="重新加载" @action="loadParks" />
      <StatusState v-else-if="!sortedParks.length" type="empty" title="未找到符合条件的公园" description="可以清空筛选条件后重新查询。" action-label="清空筛选" @action="resetFilters" />
      <div v-else :class="['park-grid', { 'park-grid--list': viewMode === 'list' }]">
        <article v-for="park in sortedParks" :key="park.id" class="park-card">
          <button class="park-card__image" type="button" @click="goDetail(park.id)"><img :src="parkCover" :alt="`${park.short_name || park.name}主题封面`" loading="lazy"/><span v-if="park.batch">第{{ park.batch }}批</span></button>
          <div class="park-card__body"><div class="park-card__heading"><div><h3>{{ park.short_name || park.name }}</h3><p><el-icon><Location /></el-icon>{{ park.province }} {{ park.city }}</p></div><strong>{{ averageScore(park) }}</strong></div><div class="park-card__tags"><span>{{ park.park_type || '类型未录入' }}</span><span v-if="park.world_heritage">世界遗产</span><span v-if="park.aaa_level">{{ park.aaa_level }}级景区</span></div><div v-if="park.scores?.length" class="park-card__metrics"><div v-for="score in park.scores.slice(0, 4)" :key="score.indicator_code"><span>{{ shortMetric(score.indicator_name) }}</span><strong>{{ score.score ?? '—' }}</strong></div></div><p class="park-card__description">{{ park.description || '当前公园暂无简介，已有基础档案与评价指标可供查看。' }}</p><div class="park-card__actions"><el-button type="primary" plain @click="goDetail(park.id)">查看详情</el-button><el-button text @click="addToCompare(park.id)">加入对比</el-button></div></div>
        </article>
      </div>
      <div v-if="total > pageSize" class="pagination"><el-pagination v-model:current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="loadParks" /></div>
    </section>

    <ParkFormDialog v-model="createDialogVisible" @saved="handleParkCreated" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/utils/api'
import { useAuthStore } from '@/stores/auth'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import ParkFormDialog from '@/components/park/ParkFormDialog.vue'
import portalHero from '@/assets/images/portal-hero.webp'
import parkCover from '@/assets/images/park-cover-fallback.webp'

const auth=useAuthStore();const route=useRoute();const router=useRouter();const parks=ref([]);const total=ref(0);const page=ref(1);const pageSize=ref(8);const provinces=ref([]);const batches=ref([]);const parkTypes=ref([]);const loading=ref(true);const error=ref('');const sortMode=ref('default');const viewMode=ref('grid');const createDialogVisible=ref(false)
const filters=ref({park_type:'',province:'',batch:'',keyword:String(route.query.keyword||'')})
const featured=computed(()=>sortedParks.value[0]||null)
const sortedParks=computed(()=>{const items=[...parks.value];if(sortMode.value==='score')items.sort((a,b)=>Number(averageScore(b))-Number(averageScore(a)));if(sortMode.value==='batch')items.sort((a,b)=>(a.batch||99)-(b.batch||99));return items})

onMounted(async()=>{await loadOptions();await loadParks()})
async function loadOptions(){try{const res=await api.get('/statistics/overview',{silent:true});provinces.value=Object.keys(res.data.by_province||{}).filter(Boolean);batches.value=Object.keys(res.data.by_batch||{}).filter(Boolean).map(Number).sort((a,b)=>a-b);parkTypes.value=Object.keys(res.data.by_type||{}).filter(Boolean)}catch{}}
async function loadParks(){loading.value=true;error.value='';try{const res=await api.get('/parks',{params:{page:page.value,page_size:pageSize.value,park_type:filters.value.park_type||undefined,province:filters.value.province||undefined,batch:filters.value.batch||undefined,keyword:filters.value.keyword||undefined},silent:true});parks.value=res.data.items||[];total.value=res.data.total||0}catch(e){error.value=e.response?.data?.detail||'请检查后端服务后重试。'}finally{loading.value=false}}
function applyFilters(){page.value=1;router.replace({query:filters.value.keyword?{keyword:filters.value.keyword}:undefined});loadParks()}
function resetFilters(){filters.value={park_type:'',province:'',batch:'',keyword:''};page.value=1;router.replace({query:undefined});loadParks()}
function goDetail(id){router.push(`/parks/${id}`)}
function addToCompare(id){router.push({path:'/compare',query:{park_ids:String(id)}})}
function averageScore(park){const values=(park.scores||[]).map(s=>Number(s.score)).filter(Number.isFinite);return values.length?(values.reduce((sum,value)=>sum+value,0)/values.length).toFixed(1):'—'}
function shortMetric(name){return String(name||'指标').replace(/[（(].*$/,'').slice(0,6)}
function showCreateDialog(){createDialogVisible.value=true}
async function handleParkCreated(){page.value=1;await loadOptions();await loadParks()}
</script>

<style scoped lang="scss">
.parks-filter__grid{display:grid;grid-template-columns:160px 180px 150px minmax(240px,1fr) auto;gap:12px;align-items:end}.parks-filter label{display:grid;gap:7px}.parks-filter label>span{color:var(--text-secondary);font-size:12px}.parks-filter__actions{display:flex;gap:8px;flex-wrap:wrap}.featured-park{min-height:255px;overflow:hidden;display:grid;grid-template-columns:1.05fr 1.15fr .9fr}.featured-park__image{position:relative;min-height:255px}.featured-park__image img{width:100%;height:100%;object-fit:cover}.featured-park__image>span{position:absolute;left:18px;top:18px;padding:7px 11px;border-radius:999px;color:#fff;background:rgba(23,32,51,.72);font-size:11px}.featured-park__content{padding:30px}.featured-park__content h2{margin:8px 0 10px;font-size:25px}.featured-park__meta{display:flex;align-items:center;gap:8px;color:var(--text-secondary)!important}.featured-park__meta i{width:1px;height:12px;background:var(--border-strong)}.featured-park__content>p{margin:0 0 20px;color:var(--text-secondary);font-size:13px;line-height:1.8}.featured-park__scores{padding:28px;border-left:1px solid var(--border);background:var(--surface-soft)}.featured-score{display:grid;margin-bottom:18px}.featured-score span,.score-line span{color:var(--text-secondary);font-size:12px}.featured-score strong{font-size:30px}.featured-score small{color:var(--text-tertiary)}.score-line{margin-top:12px}.score-line>div{display:flex;justify-content:space-between;margin-bottom:5px}.score-line strong{font-size:12px}.parks-results{display:grid;gap:18px}.results-tools{display:flex;align-items:center;gap:10px}.park-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.park-card{overflow:hidden;border:1px solid var(--border);border-radius:var(--radius-lg);background:#fff;box-shadow:var(--shadow-soft)}.park-card__image{width:100%;height:180px;padding:0;position:relative;overflow:hidden;border:0;background:#edf2f8;cursor:pointer}.park-card__image img{width:100%;height:100%;object-fit:cover;transition:transform .3s ease}.park-card:hover .park-card__image img{transform:scale(1.025)}.park-card__image span{position:absolute;right:12px;top:12px;padding:5px 9px;border-radius:999px;color:#fff;background:rgba(37,99,235,.9);font-size:11px}.park-card__body{padding:16px}.park-card__heading{display:flex;justify-content:space-between;gap:10px}.park-card h3{margin:0;font-size:16px;line-height:1.4}.park-card__heading p{margin:7px 0 0;display:flex;align-items:center;gap:4px;color:var(--text-secondary);font-size:11px}.park-card__heading>strong{color:var(--brand-600);font-size:20px}.park-card__tags{display:flex;gap:6px;flex-wrap:wrap;margin:13px 0}.park-card__tags span{padding:5px 8px;border-radius:999px;color:var(--text-secondary);background:var(--surface-soft);font-size:10px}.park-card__metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}.park-card__metrics>div{padding:8px 4px;text-align:center;border-radius:9px;background:#f8fafc}.park-card__metrics span{display:block;color:var(--text-tertiary);font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.park-card__metrics strong{display:block;margin-top:3px;font-size:13px}.park-card__description{margin:13px 0;color:var(--text-secondary);font-size:11px;line-height:1.7;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.park-card__actions{display:flex;align-items:center;justify-content:space-between}.park-grid--list{grid-template-columns:1fr}.park-grid--list .park-card{display:grid;grid-template-columns:300px 1fr}.park-grid--list .park-card__image{height:100%;min-height:230px}.pagination{display:flex;justify-content:center;padding-top:8px}
@media(max-width:1200px){.parks-filter__grid{grid-template-columns:repeat(3,1fr)}.parks-filter__search{grid-column:span 2}.park-grid{grid-template-columns:repeat(3,1fr)}}@media(max-width:900px){.featured-park{grid-template-columns:1fr 1fr}.featured-park__scores{grid-column:1/-1;border-left:0;border-top:1px solid var(--border)}.park-grid{grid-template-columns:repeat(2,1fr)}}@media(max-width:640px){.parks-filter__grid{grid-template-columns:1fr}.parks-filter__search{grid-column:auto}.parks-filter__actions>*{flex:1}.featured-park{grid-template-columns:1fr}.featured-park__image{min-height:210px}.featured-park__scores{grid-column:auto}.section-heading{display:grid}.results-tools{justify-content:space-between}.park-grid,.park-grid--list{grid-template-columns:1fr}.park-grid--list .park-card{display:block}.park-card__image{height:200px}}
</style>
