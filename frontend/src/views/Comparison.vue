<template>
  <div class="page-shell comparison-page">
    <PageHero title="对比分析" description="支持最多 5 个遗址公园开展多维综合比较，从保护管理、科研价值与公共服务等真实指标中发现差异。" :image="portalHero" compact>
      <template #actions><el-button plain :disabled="!comparisonData.length" @click="exportNotice"><el-icon><Download /></el-icon> 导出说明</el-button></template>
    </PageHero>

    <section class="section-card compare-selector">
      <div class="compare-selector__control"><h2>选择对比公园</h2><el-select v-model="selectedParks" multiple filterable collapse-tags :max-collapse-tags="2" placeholder="选择 2—5 个遗址公园" :multiple-limit="5"><el-option v-for="park in allParks" :key="park.id" :label="park.short_name||park.name" :value="park.id" /></el-select><el-button type="primary" :disabled="selectedParks.length<2" :loading="loading" @click="loadComparison">开始对比</el-button></div>
      <div class="selected-parks"><span v-if="!selectedParkObjects.length" class="selected-parks__empty">还没有选择对比对象</span><article v-for="park in selectedParkObjects" :key="park.id"><img :src="parkCover" :alt="`${park.short_name||park.name}主题封面`"/><div><strong>{{ park.short_name||park.name }}</strong><span>{{ park.province }} · {{ park.park_type }}</span></div><button type="button" :aria-label="`移除${park.short_name||park.name}`" @click="removePark(park.id)"><el-icon><Close /></el-icon></button></article><button v-if="selectedParks.length<5" type="button" class="add-card" @click="focusSelect"><el-icon><Plus /></el-icon><span>最多可选 5 个</span></button></div>
    </section>

    <StatusState v-if="error" type="error" title="对比数据加载失败" :description="error" action-label="重新加载" @action="loadComparison" />
    <StatusState v-else-if="!comparisonData.length" type="empty" title="请选择至少两个公园" description="对比结果将使用当前平台的真实评分记录生成。" />
    <template v-else>
      <section class="compare-tabs"><el-tabs v-model="activeTab"><el-tab-pane label="维度对比" name="dimension"/><el-tab-pane label="指标对比" name="indicator"/><el-tab-pane label="数据表格" name="table"/></el-tabs></section>
      <section v-show="activeTab==='dimension'" class="compare-main-grid"><div class="chart-card"><div class="section-card__header"><div><h2>维度雷达对比</h2><p>各维度得分均值，满分 100。</p></div></div><div ref="radarRef" class="chart-canvas tall"></div></div><div class="chart-card chart-card--wide"><div class="section-card__header"><div><h2>核心维度对比</h2><p>同一维度下比较不同公园表现。</p></div></div><div ref="barRef" class="chart-canvas tall"></div></div><aside class="section-card insight-panel"><div class="section-card__header"><div><h2>对比洞察</h2><p>由当前真实数据直接计算。</p></div></div><div v-for="insight in insights" :key="insight.title" class="insight-item"><span><el-icon><TrendCharts /></el-icon></span><div><strong>{{ insight.title }}</strong><p>{{ insight.text }}</p></div></div></aside></section>
      <section v-show="activeTab==='indicator'" class="chart-card"><div class="section-card__header"><div><h2>全部指标对比</h2><p>指标较多时可横向滚动查看。</p></div></div><div ref="indicatorRef" class="chart-canvas tall"></div></section>
      <section v-show="activeTab==='table'" class="section-card compare-table"><div class="section-card__header"><div><h2>维度得分总览</h2><p>表格中的数值均由已录入指标计算。</p></div></div><div class="table-scroll"><table><thead><tr><th>遗址公园</th><th v-for="dim in dimensions" :key="dim">{{ dim }}</th><th>综合均值</th></tr></thead><tbody><tr v-for="park in tableRows" :key="park.name"><td>{{ park.name }}</td><td v-for="dim in dimensions" :key="dim">{{ park.dimensions[dim]??'—' }}</td><td><strong>{{ park.average }}</strong></td></tr></tbody></table></div></section>
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import api from '@/utils/api'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'
import parkCover from '@/assets/images/park-cover-fallback.webp'
const route=useRoute();const router=useRouter();const allParks=ref([]);const selectedParks=ref([]);const comparisonData=ref([]);const loading=ref(false);const error=ref('');const activeTab=ref('dimension');const radarRef=ref();const barRef=ref();const indicatorRef=ref();const charts=[];const chartColors=['#2563eb','#22c55e','#7c3aed','#f59e0b','#06b6d4'];let observer;let radarChart;let barChart;let indicatorChart
const selectedParkObjects = computed(() => selectedParks.value.map(id => allParks.value.find(park => park.id === id)).filter(Boolean))
const dimensions = computed(() => [...new Set(comparisonData.value.flatMap(item => Object.values(item.scores || {}).map(score => score.dimension)))])
const tableRows = computed(() => comparisonData.value.map(item => {
  const values = {}
  dimensions.value.forEach(dim => {
    const scores = Object.values(item.scores || {}).filter(score => score.dimension === dim).map(score => Number(score.score)).filter(Number.isFinite)
    values[dim] = scores.length ? Number((scores.reduce((sum, value) => sum + value, 0) / scores.length).toFixed(1)) : null
  })
  const valid = Object.values(item.scores || {}).map(score => Number(score.score)).filter(Number.isFinite)
  return { name: item.park_name, dimensions: values, average: valid.length ? (valid.reduce((sum, value) => sum + value, 0) / valid.length).toFixed(1) : '—' }
}))
const insights = computed(() => {
  if (!tableRows.value.length) return []
  const best = [...tableRows.value].sort((a, b) => Number(b.average || 0) - Number(a.average || 0))[0]
  return [
    { title: `综合表现：${best.name}`, text: `当前已录入指标综合均值为 ${best.average}，在本组中最高。` },
    ...dimensions.value.slice(0, 3).map(dim => {
      const item = [...tableRows.value].filter(row => row.dimensions[dim] != null).sort((a, b) => b.dimensions[dim] - a.dimensions[dim])[0]
      return { title: `${dim}优势`, text: item ? `${item.name} 在该维度均值为 ${item.dimensions[dim]}。` : '该维度暂无可比较数据。' }
    }),
  ]
})
onMounted(async()=>{const res=await api.get('/parks',{params:{page_size:100},silent:true});allParks.value=res.data.items||[];const initial=String(route.query.park_ids||'').split(',').map(Number).filter(Boolean).slice(0,5);selectedParks.value=initial.filter(id=>allParks.value.some(p=>p.id===id));if(selectedParks.value.length>=2)loadComparison()});onBeforeUnmount(()=>{observer?.disconnect();charts.forEach(chart=>chart.dispose())});watch(activeTab,async()=>{await nextTick();renderActiveCharts();resizeActiveCharts()})
async function loadComparison(){if(selectedParks.value.length<2)return;loading.value=true;error.value='';try{const res=await api.get('/statistics/comparison',{params:{park_ids:selectedParks.value.join(',')},silent:true});comparisonData.value=res.data||[];router.replace({query:{park_ids:selectedParks.value.join(',')}});await nextTick();renderCharts()}catch(e){error.value=e.response?.data?.detail||'请检查后端服务或登录状态。'}finally{loading.value=false}}
function makeChart(el){if(!el)return null;const chart=echarts.init(el);charts.push(chart);observer||=new ResizeObserver(resizeActiveCharts);observer.observe(el);return chart}
function renderCharts(){charts.splice(0).forEach(chart=>chart.dispose());radarChart=null;barChart=null;indicatorChart=null;renderActiveCharts()}
function renderActiveCharts(){
  if(activeTab.value==='dimension'&&!radarChart&&radarRef.value&&barRef.value){
    radarChart=makeChart(radarRef.value);barChart=makeChart(barRef.value)
    radarChart.setOption({color:chartColors,tooltip:{},legend:{top:0},radar:{indicator:dimensions.value.map(name=>({name,max:100})),splitArea:{areaStyle:{color:['#fff','#f8fbff']}},splitLine:{lineStyle:{color:'#dbe5f2'}}},series:[{type:'radar',data:tableRows.value.map(row=>({name:row.name,value:dimensions.value.map(dim=>row.dimensions[dim]||0),areaStyle:{opacity:.06}}))}]})
    barChart.setOption({color:chartColors,tooltip:{trigger:'axis'},legend:{top:0},grid:{top:54,right:20,bottom:36,left:42},xAxis:{type:'category',data:dimensions.value},yAxis:{type:'value',max:100,splitLine:{lineStyle:{color:'#eef1f5'}}},series:tableRows.value.map(row=>({name:row.name,type:'bar',barMaxWidth:22,data:dimensions.value.map(dim=>row.dimensions[dim]||0)}))})
  }
  if(activeTab.value==='indicator'&&!indicatorChart&&indicatorRef.value){
    const indicators=[...new Set(comparisonData.value.flatMap(item=>Object.keys(item.scores||{})))]
    indicatorChart=makeChart(indicatorRef.value)
    indicatorChart.setOption({color:chartColors,tooltip:{trigger:'axis'},legend:{top:0},grid:{top:54,right:20,bottom:90,left:42},dataZoom:[{type:'inside'},{type:'slider',bottom:10}],xAxis:{type:'category',data:indicators,axisLabel:{rotate:40,fontSize:10}},yAxis:{type:'value',max:100},series:comparisonData.value.map(item=>({name:item.park_name,type:'bar',data:indicators.map(code=>item.scores?.[code]?.score||0)}))})
  }
}
function resizeActiveCharts(){if(activeTab.value==='dimension'){radarChart?.resize();barChart?.resize()}else if(activeTab.value==='indicator'){indicatorChart?.resize()}}
function removePark(id){selectedParks.value=selectedParks.value.filter(item=>item!==id);if(selectedParks.value.length<2)comparisonData.value=[]}function focusSelect(){document.querySelector('.compare-selector .el-select__wrapper')?.click()}function exportNotice(){ElMessage.info('当前后端尚未提供对比报告导出接口。')} 
</script>

<style scoped lang="scss">
.compare-selector{display:grid;grid-template-columns:340px 1fr;overflow:hidden}.compare-selector__control{padding:24px;display:grid;gap:14px;border-right:1px solid var(--border)}.compare-selector__control h2{margin:0;font-size:18px}.selected-parks{padding:20px;display:flex;align-items:center;gap:10px;overflow-x:auto}.selected-parks article{min-width:230px;padding:9px;display:grid;grid-template-columns:54px 1fr auto;align-items:center;gap:10px;border:1px solid var(--border);border-radius:12px}.selected-parks article img{width:54px;height:54px;object-fit:cover;border-radius:9px}.selected-parks article div{min-width:0;display:grid}.selected-parks strong{font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.selected-parks article span{margin-top:5px;color:var(--text-tertiary);font-size:10px}.selected-parks article button{border:0;background:none;color:var(--text-tertiary);cursor:pointer}.selected-parks__empty{color:var(--text-tertiary);font-size:13px}.add-card{min-width:112px;height:74px;display:grid;place-items:center;border:1px dashed var(--brand-100);border-radius:12px;color:var(--brand-600);background:var(--brand-50);cursor:pointer}.add-card span{font-size:10px}.compare-tabs{padding:0 16px;border:1px solid var(--border);border-radius:14px;background:#fff}.compare-main-grid{display:grid;grid-template-columns:1fr 1.35fr .8fr;gap:16px}.insight-panel,.compare-table{padding:22px}.insight-item{display:flex;gap:10px;padding:14px 0;border-bottom:1px solid var(--border)}.insight-item>span{width:34px;height:34px;display:grid;place-items:center;flex:0 0 auto;border-radius:10px;color:var(--brand-600);background:var(--brand-50)}.insight-item strong{font-size:12px}.insight-item p{margin:5px 0 0;color:var(--text-secondary);font-size:11px;line-height:1.6}.table-scroll{overflow-x:auto}.compare-table table{width:100%;border-collapse:collapse;font-size:12px}.compare-table th,.compare-table td{padding:13px;border:1px solid var(--border);text-align:center}.compare-table th{background:var(--surface-soft);color:var(--text-secondary)}.compare-table td:first-child{text-align:left;font-weight:600}.compare-table td strong{color:var(--brand-600)}@media(max-width:1150px){.compare-main-grid{grid-template-columns:1fr 1fr}.insight-panel{grid-column:1/-1}.compare-selector{grid-template-columns:300px 1fr}}@media(max-width:760px){.compare-selector{grid-template-columns:1fr}.compare-selector__control{border-right:0;border-bottom:1px solid var(--border)}.selected-parks article{min-width:210px}.compare-main-grid{grid-template-columns:1fr}.insight-panel{grid-column:auto}}
</style>
