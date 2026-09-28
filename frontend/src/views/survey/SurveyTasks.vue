<template>
  <div class="page-shell survey-tasks">
    <PageHero
      title="田野调研"
      description="上传两步路 KML 轨迹，自动下载照片、逆地理编码与多模态语义描述，组织为调研事件并生成报告「调研过程」章节。"
      :image="portalHero"
      compact
    >
      <template #actions>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建调研任务</el-button>
        <el-button @click="loadTasks"><el-icon><Refresh /></el-icon>刷新</el-button>
      </template>
    </PageHero>

    <section class="section-card">
      <div class="section-card__header">
        <div>
          <h2>调研任务</h2>
          <p>共 {{ tasks.length }} 个任务，点击卡片进入三步工作台。</p>
        </div>
      </div>

      <StatusState v-if="loading" type="loading" title="正在加载调研任务" />
      <StatusState
        v-else-if="loadError"
        type="error"
        title="调研任务加载失败"
        :description="loadError"
        action-label="重新加载"
        @action="loadTasks"
      />
      <StatusState
        v-else-if="!tasks.length"
        type="empty"
        title="暂无调研任务"
        description="点击「新建调研任务」，然后在工作台上传 KML 轨迹文件。"
      />
      <div v-else class="task-grid">
        <article v-for="task in tasks" :key="task.id" class="task-card" @click="openWorkbench(task.id)">
          <header class="task-card__head">
            <h3>{{ task.title }}</h3>
            <el-tag size="small" :type="taskTagType(task)">{{ taskTagLabel(task) }}</el-tag>
          </header>
          <p class="task-card__meta">调研日期：{{ task.survey_date || '未设置' }}</p>
          <div class="task-card__counts">
            <span>照片 <strong>{{ task.photo_count }}</strong></span>
            <span>事件 <strong>{{ task.event_count }}</strong></span>
            <span>可用于报告 <strong>{{ task.usable_event_count }}</strong></span>
          </div>
          <footer class="task-card__foot">
            <span>报告：{{ reportLabel(task.report_status) }}<template v-if="task.report_version">（v{{ task.report_version }}）</template></span>
            <el-button text type="danger" size="small" @click.stop="removeTask(task)">删除</el-button>
          </footer>
        </article>
      </div>
    </section>

    <el-dialog v-model="createVisible" title="新建调研任务" width="min(520px, 92vw)">
      <el-form label-width="88px">
        <el-form-item label="任务标题" required>
          <el-input v-model="form.title" maxlength="200" placeholder="如：2026-09-08 刘贺主墓调研" />
        </el-form-item>
        <el-form-item label="调研日期">
          <el-date-picker v-model="form.survey_date" type="date" value-format="YYYY-MM-DD" placeholder="选择日期" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建并进入工作台</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'
import { createSurveyTask, deleteSurveyTask, listSurveyTasks } from '@/utils/surveyApi'

const router = useRouter()
const tasks = ref([])
const loading = ref(false)
const loadError = ref('')
const createVisible = ref(false)
const creating = ref(false)
const form = reactive({ title: '', survey_date: '' })

onMounted(loadTasks)

async function loadTasks() {
  loading.value = true
  loadError.value = ''
  try {
    const data = await listSurveyTasks()
    tasks.value = data.items || []
  } catch (error) {
    loadError.value = error.response?.data?.detail || '请检查后端服务后重试。'
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.title = ''
  form.survey_date = ''
  createVisible.value = true
}

async function submitCreate() {
  if (!form.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  creating.value = true
  try {
    const task = await createSurveyTask({ title: form.title.trim(), survey_date: form.survey_date || null })
    ElMessage.success('调研任务已创建')
    createVisible.value = false
    router.push(`/survey/${task.id}`)
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

function openWorkbench(taskId) {
  router.push(`/survey/${taskId}`)
}

async function removeTask(task) {
  try {
    await ElMessageBox.confirm(`确定删除调研任务「${task.title}」？关联的事件与报告将一并删除。`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteSurveyTask(task.id)
    ElMessage.success('已删除')
    loadTasks()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

function taskTagType(task) {
  if (task.status === 'ready') return 'success'
  if (task.status === 'processing') return 'warning'
  return 'info'
}

function taskTagLabel(task) {
  return { draft: '草稿', processing: '处理中', ready: '可生成报告' }[task.status] || task.status
}

function reportLabel(status) {
  return { empty: '未生成', draft: '未生成', generating: '生成中', done: '已生成', failed: '生成失败' }[status] || status
}
</script>

<style scoped>
.task-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  margin-top: 12px;
}
.task-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px;
  background: var(--surface);
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}
.task-card:hover {
  border-color: var(--brand-100);
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.1);
  transform: translateY(-2px);
}
.task-card__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}
.task-card__head h3 {
  margin: 0;
  font-size: 16px;
  color: var(--text-primary);
}
.task-card__meta {
  margin: 8px 0 12px;
  font-size: 13px;
  color: var(--text-secondary);
}
.task-card__counts {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
  font-size: 13px;
  color: var(--text-secondary);
}
.task-card__counts strong {
  color: var(--brand-600);
}
.task-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px dashed var(--border);
  font-size: 13px;
  color: var(--text-tertiary);
}
</style>
