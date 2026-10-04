<template>
  <div class="page-shell annotate-tasks">
    <PageHero
      title="数据标注"
      description="照片语义标注工作台：盲标、多人独立编码与人机一致性（Cohen's Kappa）检验；标注任务由样本 JSON 通过接口导入。"
      :image="portalHero"
      compact
    >
      <template #actions>
        <el-button @click="loadTasks"><el-icon><Refresh /></el-icon>刷新</el-button>
      </template>
    </PageHero>

    <section class="section-card">
      <div class="section-card__header">
        <div>
          <h2>标注任务</h2>
          <p>共 {{ tasks.length }} 个任务。</p>
        </div>
      </div>

      <StatusState v-if="loading" type="loading" title="正在加载标注任务" />
      <StatusState
        v-else-if="loadError"
        type="error"
        title="标注任务加载失败"
        :description="loadError"
        action-label="重新加载"
        @action="loadTasks"
      />
      <StatusState
        v-else-if="!tasks.length"
        type="empty"
        title="暂无标注任务"
        description="可通过 POST /api/annotate/tasks/import 导入 backend/data/annotation/sample_v1.json 创建任务。"
      />
      <div v-else class="annotate-grid">
        <article v-for="task in tasks" :key="task.id" class="annotate-card">
          <header class="annotate-card__head">
            <h3>{{ task.name }}</h3>
            <el-tag size="small" :type="task.status === 'closed' ? 'info' : 'success'">
              {{ task.status === 'closed' ? '已关闭' : '开放中' }}
            </el-tag>
          </header>
          <p class="annotate-card__meta">
            条目总数 <strong>{{ task.total }}</strong> · 编码手册 {{ task.codebook_version }}
          </p>

          <div class="annotate-card__coders">
            <div v-if="!task.coders.length" class="annotate-card__empty muted">尚无编码记录</div>
            <div v-for="item in task.coders" :key="item.coder" class="annotate-coder">
              <span class="annotate-coder__name">{{ item.coder }}</span>
              <el-progress
                :percentage="percent(item.done, task.total)"
                :stroke-width="8"
                :text-inside="false"
                class="annotate-coder__bar"
              />
              <span class="annotate-coder__count">{{ item.done }}/{{ task.total }}</span>
            </div>
          </div>

          <footer class="annotate-card__foot">
            <el-button type="primary" size="small" @click="openWorkbench(task.id)">
              {{ task.coders.length ? '继续标注' : '开始标注' }}
            </el-button>
            <el-button size="small" @click="openResults(task.id)">查看结果</el-button>
          </footer>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'
import { listAnnotationTasks } from '@/utils/annotateApi'

const router = useRouter()
const tasks = ref([])
const loading = ref(false)
const loadError = ref('')

onMounted(loadTasks)

async function loadTasks() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await listAnnotationTasks()
    tasks.value = data.items || []
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

function openWorkbench(taskId) {
  router.push(`/annotate/${taskId}`)
}

function openResults(taskId) {
  router.push(`/annotate/${taskId}/results`)
}
</script>

<style scoped>
.annotate-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
  margin-top: 12px;
}
.annotate-card {
  display: grid;
  gap: 12px;
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
  background: var(--surface);
}
.annotate-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.annotate-card__head h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}
.annotate-card__meta {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}
.annotate-card__meta strong {
  color: var(--brand-600);
}
.annotate-card__coders {
  display: grid;
  gap: 8px;
}
.annotate-card__empty {
  font-size: 13px;
}
.annotate-coder {
  display: grid;
  grid-template-columns: 70px 1fr 56px;
  align-items: center;
  gap: 10px;
}
.annotate-coder__name {
  font-size: 13px;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.annotate-coder__count {
  font-size: 12px;
  color: var(--text-tertiary);
  text-align: right;
}
.annotate-card__foot {
  display: flex;
  gap: 10px;
  padding-top: 4px;
}
</style>
