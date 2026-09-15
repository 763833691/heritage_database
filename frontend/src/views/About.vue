<template>
  <div class="page-shell about-page">
    <PageHero eyebrow="ABOUT THE PLATFORM" title="关于我们" description="以真实数据、可靠知识与智能工具连接遗址公园保护、研究和管理，让分散的信息形成可持续使用的研究基础设施。" :image="portalHero">
      <template #actions><el-button type="primary" @click="$router.push('/parks')">探索遗址公园</el-button><el-button plain @click="$router.push('/library')">进入知识库</el-button></template>
    </PageHero>
    <section class="about-grid">
      <article v-for="item in capabilities" :key="item.title" class="section-card about-card"><span><el-icon><component :is="item.icon" /></el-icon></span><h2>{{ item.title }}</h2><p>{{ item.description }}</p></article>
    </section>
    <section class="section-card about-section"><div><span class="eyebrow">RESEARCH BACKGROUND</span><h2>面向文化遗产保护的研究门户</h2></div><div><p>平台围绕国家考古遗址公园的保护管理、科研价值、展示利用与公共服务组织数据和知识，服务研究人员、管理机构与合作单位。</p><p>本轮门户化改造保留现有真实接口、数据库与业务操作，不以演示数据替代生产事实。页面中没有来源的数据会展示明确空状态。</p></div></section>
    <section class="section-card source-section"><div class="section-card__header"><div><span class="eyebrow">DATA & TECHNOLOGY</span><h2>数据与技术说明</h2><p>透明说明平台当前能力和边界。</p></div></div><div class="source-grid"><div><strong>数据来源</strong><p>现有遗址公园数据库、评价指标与评分、知识库文献、知识图谱和相关业务接口。</p></div><div><strong>技术架构</strong><p>Vue 3 门户前端、FastAPI 服务、SQLite 数据库、ECharts 可视化与高德地图适配层。</p></div><div><strong>地图说明</strong><p>地图采用高德 JavaScript API 2.0 与 Loca 2.0，地图 Key 通过环境变量配置，版权信息保留。</p></div><div><strong>合作联系</strong><p>如需开展数据共建、专题研究或系统合作，请联系 heritage@example.com。</p></div></div></section>
    <section class="about-note"><el-icon><Warning /></el-icon><p>平台数据用于研究与辅助决策，具体保护、规划与管理结论应结合权威文件和专业论证。</p></section>
  </div>
</template>
<script setup>
import { DataAnalysis, MapLocation, Share, ChatDotRound } from '@element-plus/icons-vue'
import PageHero from '@/components/portal/PageHero.vue'
import portalHero from '@/assets/images/portal-hero.webp'
const capabilities=[{title:'数据研究',description:'整合公园、遗址点和评价指标，形成可查询、可比较的研究数据。',icon:DataAnalysis},{title:'空间洞察',description:'以专题地图理解遗址公园的空间分布和区域特征。',icon:MapLocation},{title:'知识关联',description:'通过知识图谱与文献资源追踪实体关系和研究脉络。',icon:Share},{title:'智能辅助',description:'以现有知识和数据为基础，支持研究问答与内容分析。',icon:ChatDotRound}]
</script>
<style scoped lang="scss">
.about-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:14px}.about-card{padding:24px}.about-card>span{width:44px;height:44px;display:grid;place-items:center;border-radius:14px;color:var(--brand-600);background:var(--brand-50);font-size:21px}.about-card h2{margin:18px 0 8px;font-size:17px}.about-card p,.about-section p,.source-grid p{color:var(--text-secondary);font-size:13px;line-height:1.8}.about-section{padding:34px;display:grid;grid-template-columns:.75fr 1.25fr;gap:48px}.about-section h2{margin:9px 0 0;font-size:28px}.about-section p+p{margin-top:14px}.source-section{padding:30px}.source-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}.source-grid>div{padding:20px;border:1px solid var(--border);border-radius:14px;background:var(--surface-soft)}.source-grid p{margin:8px 0 0}.about-note{padding:18px 22px;display:flex;align-items:flex-start;gap:10px;border-radius:14px;color:#92400e;background:#fffbeb}.about-note p{margin:0;font-size:13px;line-height:1.7}@media(max-width:900px){.about-grid{grid-template-columns:repeat(2,1fr)}.about-section{grid-template-columns:1fr;gap:20px}}@media(max-width:600px){.about-grid,.source-grid{grid-template-columns:1fr}.about-section{padding:24px}}
</style>
