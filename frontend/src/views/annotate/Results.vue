<template>
  <div class="page-shell annotate-results">
    <section class="section-card results-top">
      <div class="results-top__left">
        <el-button text @click="$router.push('/annotate')"><el-icon><ArrowLeft /></el-icon>返回任务列表</el-button>
        <h1>{{ results?.task?.name || `标注任务 #${taskId}` }}</h1>
        <p class="muted">共 {{ results?.task?.total ?? 0 }} 条样本，{{ (results?.coders || []).length }} 位编码者。</p>
      </div>
      <div class="results-top__right">
        <el-button @click="$router.push(`/annotate/${taskId}`)">进入标注</el-button>
        <el-button type="primary" @click="exportExcel"><el-icon><Download /></el-icon>导出 Excel</el-button>
      </div>
    </section>

    <StatusState v-if="loading" type="loading" title="正在计算结果" />
    <StatusState
      v-else-if="loadError"
      type="error"
      title="结果加载失败"
      :description="loadError"
      action-label="重新加载"
      @action="loadResults"
    />
    <template v-else>
      <section class="section-card">
        <div class="section-card__header">
          <div>
            <h2>编码者完成数</h2>
            <p>任务内各编码者已提交的条目数。</p>
          </div>
        </div>
        <div v-if="!coders.length" class="muted">尚无编码记录。</div>
        <div v-else class="results-coders">
          <div v-for="item in coders" :key="item.coder" class="results-coder">
            <span>{{ item.coder }}</span>
            <el-progress :percentage="percent(item.done, results.task.total)" :stroke-width="10" />
            <strong>{{ item.done }}/{{ results.task.total }}</strong>
          </div>
        </div>
      </section>

      <section class="section-card">
        <div class="section-card__header">
          <div>
            <h2>两两一致性</h2>
            <p>一致率 = 双方均非空配对中编码相同的比例；Cohen's Kappa 按 A–G 边际频率计算。</p>
          </div>
        </div>
        <el-table :data="results.pairwise" size="small" border class="results-table">
          <el-table-column label="对比方 A" min-width="140">
            <template #default="{ row }">{{ sourceLabel(row.a) }}</template>
          </el-table-column>
          <el-table-column label="对比方 B" min-width="140">
            <template #default="{ row }">{{ sourceLabel(row.b) }}</template>
          </el-table-column>
          <el-table-column prop="n" label="有效配对" width="100" align="center" />
          <el-table-column prop="agree" label="一致数" width="90" align="center" />
          <el-table-column label="一致率" width="110" align="center">
            <template #default="{ row }">{{ row.agree_rate.toFixed(3) }}</template>
          </el-table-column>
          <el-table-column label="Cohen's Kappa" width="150" align="center">
            <template #default="{ row }">
              <span :class="kappaClass(row.kappa)">{{ row.kappa.toFixed(3) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </section>

      <section class="section-card">
        <div class="section-card__header">
          <div>
            <h2>分歧清单</h2>
            <p>该条目所有非空编码（平台、智能体、各人工）不全部相同即入分歧（{{ disagreements.length }} 条）。</p>
          </div>
        </div>
        <StatusState v-if="!disagreements.length" type="empty" title="无分歧条目" description="所有非空编码在各来源间完全一致。" />
        <el-table v-else :data="disagreements" size="small" border class="results-table">
          <el-table-column prop="sid" label="样本编号" width="100" />
          <el-table-column label="照片" width="96">
            <template #default="{ row }">
              <el-image
                :src="row.photo_url"
                :preview-src-list="[row.photo_url]"
                preview-teleported
                fit="cover"
                class="results-thumb"
              />
            </template>
          </el-table-column>
          <el-table-column label="平台" width="70" align="center">
            <template #default="{ row }">{{ row.platform || '—' }}</template>
          </el-table-column>
          <el-table-column label="智能体" width="80" align="center">
            <template #default="{ row }">{{ row.ai || '—' }}</template>
          </el-table-column>
          <el-table-column v-for="coder in results.coders" :key="coder" :label="coder" width="90" align="center">
            <template #default="{ row }">{{ row.human?.[coder] || '—' }}</template>
          </el-table-column>
          <el-table-column label="备注" min-width="160">
            <template #default="{ row }">{{ noteText(row.notes) || '—' }}</template>
          </el-table-column>
          <el-table-column prop="caption" label="图注" min-width="220" show-overflow-tooltip />
        </el-table>
      </section>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import StatusState from '@/components/common/StatusState.vue'
import { annotationExportUrl, getAnnotationResults, listAnnotationTasks } from '@/utils/annotateApi'

const route = useRoute()
const taskId = Number(route.params.id)

const results = ref(null)
const taskCounts = ref([])
const loading = ref(true)
const loadError = ref('')

const coders = computed(() => taskCounts.value)
const disagreements = computed(() => results.value?.disagreements || [])

onMounted(loadResults)

async function loadResults() {
  loading.value = true
  loadError.value = ''
  try {
    const [resultData, listData] = await Promise.all([
      getAnnotationResults(taskId),
      listAnnotationTasks().catch(() => ({ items: [] })),
    ])
    results.value = resultData
    const task = (listData.items || []).find((item) => item.id === taskId)
    taskCounts.value = task?.coders || (resultData.coders || []).map((coder) => ({ coder, done: 0 }))
  } catch (error) {
    loadError.value = error.response?.data?.detail || '请检查后端服务后重试。'
  } finally {
    loading.value = false
  }
}

function percent(done, total) {
  if (!total) return 0
  return Math.min(100, Math.round((done / total) * 100))
}

function sourceLabel(key) {
  if (key === 'platform') return '平台分类'
  if (key === 'ai') return '智能体'
  return key
}

function kappaClass(kappa) {
  if (kappa >= 0.6) return 'kappa kappa--good'
  if (kappa >= 0.4) return 'kappa kappa--mid'
  return 'kappa kappa--low'
}

function noteText(notes) {
  if (!notes) return ''
  return Object.entries(notes)
    .map(([coder, note]) => `${coder}:${note}`)
    .join('；')
}

function exportExcel() {
  const url = annotationExportUrl(taskId)
  if (!url) {
    ElMessage.error('导出地址无效')
    return
  }
  window.open(url, '_blank')
}
</script>

<style scoped>
.results-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}
.results-top__left h1 {
  margin: 6px 0 4px;
  font-size: 20px;
  color: var(--text-primary);
}
.results-top__left p {
  margin: 0;
}
.results-top__right {
  display: flex;
  gap: 10px;
}
.results-coders {
  display: grid;
  gap: 12px;
  margin-top: 6px;
}
.results-coder {
  display: grid;
  grid-template-columns: 90px 1fr 80px;
  align-items: center;
  gap: 12px;
}
.results-coder strong {
  color: var(--brand-600);
  text-align: right;
}
.results-table {
  margin-top: 8px;
}
.results-thumb {
  width: 64px;
  height: 48px;
  border-radius: 6px;
}
.kappa--good {
  color: #16a34a;
  font-weight: 600;
}
.kappa--mid {
  color: #d97706;
  font-weight: 600;
}
.kappa--low {
  color: #dc2626;
}
</style>
