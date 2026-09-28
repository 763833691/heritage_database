<template>
  <div class="page-shell model-routing">
    <PageHero
      title="模型路由"
      description="注册可调用的模型（厂商 / 端点 / 上游模型 / 加密 Key），并把每个任务路由到合适的模型。API Key 加密落库，不会明文回显。"
      :image="portalHero"
      compact
    >
      <template #actions>
        <el-button @click="loadAll"><el-icon><Refresh /></el-icon>刷新</el-button>
        <el-button type="primary" @click="openCreate"><el-icon><Plus /></el-icon>新建模型</el-button>
      </template>
    </PageHero>

    <!-- 任务路由 -->
    <section class="section-card">
      <div class="section-card__header">
        <div>
          <h2>任务路由</h2>
          <p>解析优先级：数据库路由 → .env 的 MODEL_ROUTES → 旧配置。把任务清空即可回退到 .env 配置。</p>
        </div>
        <div class="muted">
          已解析 {{ statusSummary.resolved }}/{{ statusSummary.total }}
          <el-tag v-if="statusSummary.errors" type="danger" size="small" effect="plain">{{ statusSummary.errors }} 个问题</el-tag>
        </div>
      </div>

      <el-table :data="routes" row-key="task" class="routing-table">
        <el-table-column label="任务" min-width="220">
          <template #default="{ row }">
            <strong>{{ row.label }}</strong>
            <div class="muted mono">{{ row.task }}</div>
          </template>
        </el-table-column>
        <el-table-column label="所需能力" width="120">
          <template #default="{ row }"><el-tag size="small" effect="plain">{{ row.capability }}</el-tag></template>
        </el-table-column>
        <el-table-column label="路由到模型" min-width="260">
          <template #default="{ row }">
            <el-select
              :model-value="row.model_id"
              clearable
              placeholder="未配置（回退 .env）"
              style="width: 100%"
              @change="(value) => changeRoute(row, value)"
            >
              <el-option
                v-for="model in selectableModels(row.capability)"
                :key="model.id"
                :value="model.id"
                :label="`${model.display_name}（${model.alias}）`"
                :disabled="!model.enabled || !model.key_ready"
              >
                <span>{{ model.display_name }}（{{ model.alias }}）</span>
                <span class="option-flags">
                  <el-tag v-if="!model.enabled" size="small" type="info" effect="plain">停用</el-tag>
                  <el-tag v-else-if="!model.key_ready" size="small" type="warning" effect="plain">缺 Key</el-tag>
                </span>
              </el-option>
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="解析状态" min-width="260">
          <template #default="{ row }">
            <template v-if="row.error">
              <el-tag type="danger" size="small" effect="plain">不可用</el-tag>
              <span class="muted status-text">{{ row.error }}</span>
            </template>
            <template v-else-if="row.resolved">
              <el-tag type="success" size="small" effect="plain">{{ row.resolved.source === 'db' ? '数据库' : '.env' }}</el-tag>
              <span class="muted status-text">{{ row.resolved.alias }} · {{ row.resolved.model }}</span>
            </template>
            <span v-else class="muted">未配置</span>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 模型注册表 -->
    <section class="section-card">
      <div class="section-card__header">
        <div>
          <h2>模型注册表</h2>
          <p>共 {{ models.length }} 个模型，其中启用 {{ enabledCount }} 个。预置模型来自短剧项目的 providers 清单，默认停用且不带 Key。</p>
        </div>
        <el-button size="small" :loading="seeding" @click="importPresets">导入预置模型</el-button>
      </div>

      <StatusState v-if="loading" type="loading" title="正在加载模型" />
      <StatusState v-else-if="loadError" type="error" title="加载失败" :description="loadError" action-label="重新加载" @action="loadAll" />
      <StatusState v-else-if="!models.length" type="empty" title="暂无模型" description="点击「导入预置模型」或「新建模型」开始配置。" />
      <el-table v-else :data="models" row-key="id">
        <el-table-column label="模型" min-width="220">
          <template #default="{ row }">
            <strong>{{ row.display_name }}</strong>
            <el-tag v-if="row.is_preset" size="small" effect="plain" class="preset-tag">预置</el-tag>
            <div class="muted mono">{{ row.alias }}</div>
          </template>
        </el-table-column>
        <el-table-column label="厂商 / 类型" width="180">
          <template #default="{ row }">
            <div>{{ providerLabel(row.provider_type) }}</div>
            <el-tag size="small" effect="plain">{{ row.capability }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="端点 / 模型" min-width="280">
          <template #default="{ row }">
            <div class="mono ellipsis" :title="row.base_url">{{ row.base_url }}</div>
            <div class="muted mono">{{ row.model }}</div>
          </template>
        </el-table-column>
        <el-table-column label="API Key" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.has_api_key" type="success" size="small" effect="plain">{{ row.api_key_hint }}</el-tag>
            <el-tag v-else-if="row.env_key_available" type="success" size="small" effect="plain">env: {{ row.api_key_env }}</el-tag>
            <el-tag v-else-if="row.api_key_env" type="warning" size="small" effect="plain">env 未设置: {{ row.api_key_env }}</el-tag>
            <el-tag v-else type="warning" size="small" effect="plain">未配置</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="启用" width="80" align="center">
          <template #default="{ row }">
            <el-switch v-model="row.enabled" @change="(value) => toggleEnabled(row, value)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" :loading="testingId === row.id" @click="runTest(row)">测试</el-button>
            <el-button size="small" text @click="openEdit(row)">编辑</el-button>
            <el-button size="small" text type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 新建 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="form.id ? '编辑模型' : '新建模型'" width="min(680px, 94vw)">
      <el-form label-width="110px" label-position="right">
        <el-form-item label="别名" required>
          <el-input v-model="form.alias" placeholder="如 dashscope-qwen-vl-max（路由引用它，需唯一）" />
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" placeholder="界面展示用名称" />
        </el-form-item>
        <el-form-item label="厂商类型">
          <el-select v-model="form.provider_type" style="width: 100%">
            <el-option v-for="item in PROVIDER_TYPES" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型能力">
          <el-select v-model="form.capability" style="width: 100%">
            <el-option v-for="item in CAPABILITIES" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="端点 base_url" required>
          <el-input v-model="form.base_url" placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1" />
        </el-form-item>
        <el-form-item label="上游模型 id" required>
          <el-input v-model="form.model" placeholder="qwen-vl-max" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input
            v-model="form.api_key"
            type="password"
            show-password
            :placeholder="form.id && form.has_api_key ? '已配置（留空保持不变）' : 'sk-...'"
          />
          <div class="muted form-hint">加密存储（Fernet），接口只回显末 4 位；留空表示不修改。</div>
        </el-form-item>
        <el-form-item label="Key 环境变量">
          <el-input v-model="form.api_key_env" placeholder="可选：DASHSCOPE_API_KEY（显式 Key 优先）" />
        </el-form-item>
        <el-form-item label="输入模态">
          <el-select v-model="form.input_modalities" multiple style="width: 100%">
            <el-option v-for="item in MODALITIES" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="输出模态">
          <el-select v-model="form.output_modalities" multiple style="width: 100%">
            <el-option v-for="item in MODALITIES" :key="item" :label="item" :value="item" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
          <span class="muted form-hint">未启用的模型不可被任务路由选中。</span>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <!-- 测试结果 -->
    <el-dialog v-model="testVisible" title="连通性测试" width="min(560px, 92vw)">
      <el-alert
        v-if="testResult"
        :type="testResult.ok ? 'success' : (testResult.supported ? 'error' : 'info')"
        :closable="false"
        :title="testResult.ok ? '连接正常' : (testResult.supported ? '连接失败' : '未测试')"
        :description="testResult.message"
      />
      <p v-if="testResult?.latency_ms" class="muted">耗时 {{ testResult.latency_ms }} ms</p>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'
import {
  CAPABILITIES,
  MODALITIES,
  PROVIDER_TYPES,
  capabilityMatches,
  createAiModel,
  deleteAiModel,
  getAiRouterStatus,
  listAiModels,
  listAiRoutes,
  seedAiModels,
  setAiRoute,
  testAiModel,
  updateAiModel,
} from '@/utils/aiModelApi'

const models = ref([])
const routes = ref([])
const statusItems = ref([])
const loading = ref(false)
const loadError = ref('')
const saving = ref(false)
const seeding = ref(false)
const testingId = ref(null)
const dialogVisible = ref(false)
const testVisible = ref(false)
const testResult = ref(null)

const emptyForm = () => ({
  id: null,
  alias: '',
  display_name: '',
  provider_type: 'openai_compatible',
  capability: 'text',
  base_url: '',
  model: '',
  api_key: '',
  api_key_env: '',
  input_modalities: ['text'],
  output_modalities: ['text'],
  enabled: false,
  note: '',
  has_api_key: false,
})
const form = reactive(emptyForm())

const enabledCount = computed(() => models.value.filter((item) => item.enabled).length)
const statusSummary = computed(() => ({
  total: routes.value.length,
  resolved: statusItems.value.filter((item) => item.alias).length,
  errors: statusItems.value.filter((item) => item.error).length,
}))

onMounted(loadAll)

async function loadAll() {
  loading.value = true
  loadError.value = ''
  try {
    const [modelData, routeData, statusData] = await Promise.all([
      listAiModels(),
      listAiRoutes(),
      getAiRouterStatus(),
    ])
    models.value = modelData.items || []
    routes.value = routeData.items || []
    statusItems.value = statusData.items || []
  } catch (error) {
    loadError.value = error.response?.data?.detail || '请检查后端服务后重试。'
  } finally {
    loading.value = false
  }
}

function providerLabel(value) {
  return PROVIDER_TYPES.find((item) => item.value === value)?.label || value || '—'
}

function selectableModels(taskCapability) {
  return models.value.filter((model) => capabilityMatches(taskCapability, model.capability))
}

async function changeRoute(row, modelId) {
  try {
    const data = await setAiRoute(row.task, modelId ?? null)
    routes.value = data.items || []
    statusItems.value = (await getAiRouterStatus()).items || []
    ElMessage.success(modelId ? '路由已更新' : '已清除路由（回退 .env 配置）')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '路由更新失败')
    await loadAll()
  }
}

function openCreate() {
  Object.assign(form, emptyForm())
  dialogVisible.value = true
}

function openEdit(row) {
  Object.assign(form, emptyForm(), {
    id: row.id,
    alias: row.alias,
    display_name: row.display_name,
    provider_type: row.provider_type,
    capability: row.capability,
    base_url: row.base_url,
    model: row.model,
    api_key: '',
    api_key_env: row.api_key_env || '',
    input_modalities: [...(row.input_modalities || [])],
    output_modalities: [...(row.output_modalities || [])],
    enabled: row.enabled,
    note: row.note || '',
    has_api_key: row.has_api_key,
  })
  dialogVisible.value = true
}

async function save() {
  if (!form.alias.trim() || !form.base_url.trim() || !form.model.trim()) {
    ElMessage.warning('别名、端点与上游模型 id 为必填项')
    return
  }
  saving.value = true
  const payload = {
    alias: form.alias.trim(),
    display_name: form.display_name,
    provider_type: form.provider_type,
    capability: form.capability,
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key_env: form.api_key_env,
    input_modalities: form.input_modalities,
    output_modalities: form.output_modalities,
    enabled: form.enabled,
    note: form.note,
  }
  if (form.api_key) payload.api_key = form.api_key
  try {
    if (form.id) {
      const updated = await updateAiModel(form.id, payload)
      const index = models.value.findIndex((item) => item.id === form.id)
      if (index >= 0) models.value[index] = updated
    } else {
      models.value.push(await createAiModel(payload))
    }
    dialogVisible.value = false
    ElMessage.success('已保存')
    routes.value = (await listAiRoutes()).items || []
    statusItems.value = (await getAiRouterStatus()).items || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

async function toggleEnabled(row, value) {
  try {
    const updated = await updateAiModel(row.id, { enabled: value })
    Object.assign(row, updated)
    routes.value = (await listAiRoutes()).items || []
    statusItems.value = (await getAiRouterStatus()).items || []
  } catch (error) {
    row.enabled = !value
    ElMessage.error(error.response?.data?.detail || '更新失败')
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm(`确定删除模型「${row.display_name}」？引用它的任务路由会被清空。`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await deleteAiModel(row.id)
    models.value = models.value.filter((item) => item.id !== row.id)
    routes.value = (await listAiRoutes()).items || []
    statusItems.value = (await getAiRouterStatus()).items || []
    ElMessage.success('已删除')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

async function runTest(row) {
  testingId.value = row.id
  testResult.value = null
  try {
    testResult.value = await testAiModel(row.id)
    testVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '测试失败')
  } finally {
    testingId.value = null
  }
}

async function importPresets() {
  seeding.value = true
  try {
    const data = await seedAiModels()
    models.value = data.items || []
    ElMessage.success(data.created ? `已导入 ${data.created} 个预置模型` : '预置模型已存在')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '导入失败')
  } finally {
    seeding.value = false
  }
}
</script>

<style scoped>
.routing-table {
  margin-top: 12px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.muted {
  color: var(--text-secondary);
}
.status-text {
  margin-left: 8px;
  font-size: 12px;
  word-break: break-all;
}
.option-flags {
  margin-left: 8px;
}
.preset-tag {
  margin-left: 6px;
}
.ellipsis {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-hint {
  margin-left: 8px;
  font-size: 12px;
}
.section-card__header .muted {
  font-size: 13px;
}
</style>
