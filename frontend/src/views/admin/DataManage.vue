<template>
  <div class="page-shell data-manage">
    <StatusState v-if="!auth.isAdmin" type="forbidden" title="没有数据管理权限" description="当前账号无法访问管理功能，请使用管理员账号登录。" action-label="返回首页" @action="$router.push('/')" />
    <template v-else>
    <PageHero title="数据管理" description="统一管理遗址公园、遗址点、评价数据、用户与报告导入，保持数据完整性和规范性。" :image="portalHero" compact />
    <div class="portal-stat-grid admin-stats">
      <div class="portal-stat-card"><span class="portal-stat-card__icon"><el-icon><OfficeBuilding /></el-icon></span><div><div class="portal-stat-card__label">遗址公园</div><div class="portal-stat-card__value">{{ parks.length }}</div><div class="portal-stat-card__meta">当前管理接口记录</div></div></div>
      <div class="portal-stat-card"><span class="portal-stat-card__icon green"><el-icon><Location /></el-icon></span><div><div class="portal-stat-card__label">遗址点</div><div class="portal-stat-card__value">{{ sites.length }}</div><div class="portal-stat-card__meta">选择公园后显示</div></div></div>
      <div class="portal-stat-card"><span class="portal-stat-card__icon violet"><el-icon><DataAnalysis /></el-icon></span><div><div class="portal-stat-card__label">评分记录</div><div class="portal-stat-card__value">{{ scores.length }}</div><div class="portal-stat-card__meta">当前评分接口记录</div></div></div>
      <div class="portal-stat-card"><span class="portal-stat-card__icon orange"><el-icon><User /></el-icon></span><div><div class="portal-stat-card__label">用户</div><div class="portal-stat-card__value">{{ users.length }}</div><div class="portal-stat-card__meta">当前用户记录</div></div></div>
    </div>
    <section class="section-card admin-tabs-card">
    <el-tabs v-model="activeTab">
      <!-- 遗址公园管理 -->
      <el-tab-pane label="遗址公园" name="parks">
        <div class="toolbar">
          <el-button type="primary" @click="showParkDialog()">新增公园</el-button>
          <el-upload
            action="/api/admin/import/parks"
            :headers="uploadHeaders"
            :on-success="handleImportSuccess"
            :show-file-list="false"
            accept=".xlsx,.xls"
          >
            <el-button>Excel导入</el-button>
          </el-upload>
          <a href="/templates/parks_template.xlsx" download>
            <el-button text>下载模板</el-button>
          </a>
        </div>
        <el-table :data="parks" stripe border>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="名称" />
          <el-table-column prop="park_type" label="类型" width="80" />
          <el-table-column prop="province" label="省份" width="80" />
          <el-table-column prop="city" label="城市" width="80" />
          <el-table-column prop="batch" label="批次" width="60" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="showParkDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deletePark(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 遗址点管理 -->
      <el-tab-pane label="遗址点" name="sites">
        <div class="toolbar">
          <el-select v-model="siteFilterParkId" placeholder="选择公园" clearable @change="loadSites">
            <el-option v-for="p in parks" :key="p.id" :label="p.short_name || p.name" :value="p.id" />
          </el-select>
          <el-button type="primary" @click="showSiteDialog()">新增遗址点</el-button>
          <el-upload
            action="/api/admin/import/sites"
            :headers="uploadHeaders"
            :on-success="handleImportSuccess"
            :show-file-list="false"
            accept=".xlsx,.xls"
          >
            <el-button>Excel导入</el-button>
          </el-upload>
        </div>
        <el-table :data="sites" stripe border>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="site_name" label="名称" />
          <el-table-column prop="site_type" label="类型" width="100" />
          <el-table-column prop="period" label="时期" width="100" />
          <el-table-column prop="integrity_score" label="完整性" width="80" />
          <el-table-column prop="safety_score" label="安全性" width="80" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="showSiteDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteSite(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 评分管理 -->
      <el-tab-pane label="评估评分" name="scores">
        <div class="toolbar">
          <el-select v-model="scoreFilterParkId" placeholder="选择公园" clearable @change="loadScores">
            <el-option v-for="p in parks" :key="p.id" :label="p.short_name || p.name" :value="p.id" />
          </el-select>
          <el-button type="primary" @click="showScoreDialog()">新增评分</el-button>
          <el-upload
            action="/api/admin/import/scores"
            :headers="uploadHeaders"
            :on-success="handleImportSuccess"
            :show-file-list="false"
            accept=".xlsx,.xls"
          >
            <el-button>Excel导入</el-button>
          </el-upload>
        </div>
        <el-table :data="scores" stripe border>
          <el-table-column prop="park_name" label="公园" width="150" />
          <el-table-column prop="indicator_code" label="编号" width="80" />
          <el-table-column prop="indicator_name" label="指标" width="180" />
          <el-table-column prop="dimension" label="维度" width="120" />
          <el-table-column prop="normalized_score" label="得分" width="80" />
          <el-table-column prop="grade" label="等级" width="80" />
          <el-table-column prop="evidence" label="依据" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="showScoreDialog(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="deleteScore(row.id)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 用户管理 -->
      <el-tab-pane label="用户管理" name="users">
        <el-table :data="users" stripe border>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="username" label="用户名" />
          <el-table-column prop="email" label="邮箱" />
          <el-table-column prop="full_name" label="姓名" />
          <el-table-column prop="role" label="角色" width="100">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'primary'">{{ row.role }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="is_active" label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="row.is_active ? 'success' : 'info'">
                {{ row.is_active ? '启用' : '禁用' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="200">
            <template #default="{ row }">
              <el-select v-model="row.role" size="small" @change="updateRole(row.id, row.role)" style="width:80px">
                <el-option label="admin" value="admin" />
                <el-option label="researcher" value="researcher" />
                <el-option label="guest" value="guest" />
              </el-select>
              <el-button size="small" @click="toggleStatus(row.id)">
                {{ row.is_active ? '禁用' : '启用' }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <!-- 报告导入 -->
      <el-tab-pane label="报告导入" name="report">
        <ReportImport />
      </el-tab-pane>
    </el-tabs>
    </section>

    <!-- 公园编辑弹窗 -->
    <el-dialog v-model="parkDialogVisible" :title="parkForm.id ? '编辑公园' : '新增公园'" width="600px">
      <el-form :model="parkForm" label-width="100px">
        <el-form-item label="名称" required>
          <el-input v-model="parkForm.name" />
        </el-form-item>
        <el-form-item label="简称">
          <el-input v-model="parkForm.short_name" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="parkForm.park_type">
            <el-option label="城市型" value="城市型" />
            <el-option label="城郊型" value="城郊型" />
            <el-option label="乡村型" value="乡村型" />
          </el-select>
        </el-form-item>
        <el-form-item label="批次">
          <el-input-number v-model="parkForm.batch" :min="1" :max="5" />
        </el-form-item>
        <el-form-item label="省份">
          <el-input v-model="parkForm.province" />
        </el-form-item>
        <el-form-item label="城市">
          <el-input v-model="parkForm.city" />
        </el-form-item>
        <el-form-item label="经度">
          <el-input-number v-model="parkForm.longitude" :precision="4" />
        </el-form-item>
        <el-form-item label="纬度">
          <el-input-number v-model="parkForm.latitude" :precision="4" />
        </el-form-item>
        <el-form-item label="面积(km²)">
          <el-input-number v-model="parkForm.total_area" :precision="2" />
        </el-form-item>
        <el-form-item label="景区等级">
          <el-select v-model="parkForm.aaa_level" clearable>
            <el-option label="5A" value="5A" />
            <el-option label="4A" value="4A" />
            <el-option label="3A" value="3A" />
          </el-select>
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="parkForm.description" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="parkDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="savePark">保存</el-button>
      </template>
    </el-dialog>

    <!-- 评分编辑弹窗 -->
    <el-dialog v-model="scoreDialogVisible" :title="scoreForm.id ? '编辑评分' : '新增评分'" width="500px">
      <el-form :model="scoreForm" label-width="80px">
        <el-form-item label="公园" required>
          <el-select v-model="scoreForm.park_id" filterable>
            <el-option v-for="p in parks" :key="p.id" :label="p.short_name || p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="指标" required>
          <el-select v-model="scoreForm.indicator_id" filterable>
            <el-option v-for="ind in indicators" :key="ind.id" :label="`${ind.code} ${ind.name}`" :value="ind.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="得分" required>
          <el-select v-model="scoreForm.normalized_score">
            <el-option :label="100" :value="100" />
            <el-option :label="80" :value="80" />
            <el-option :label="60" :value="60" />
            <el-option :label="40" :value="40" />
            <el-option :label="20" :value="20" />
          </el-select>
        </el-form-item>
        <el-form-item label="依据">
          <el-input v-model="scoreForm.evidence" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="年份">
          <el-input-number v-model="scoreForm.data_year" :min="2020" :max="2030" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scoreDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveScore">保存</el-button>
      </template>
    </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'
import ReportImport from './ReportImport.vue'
import { useAuthStore } from '@/stores/auth'
import PageHero from '@/components/portal/PageHero.vue'
import StatusState from '@/components/common/StatusState.vue'
import portalHero from '@/assets/images/portal-hero.webp'

const auth = useAuthStore()
const activeTab = ref('parks')

// 数据
const parks = ref([])
const sites = ref([])
const scores = ref([])
const users = ref([])
const indicators = ref([])

// 筛选
const siteFilterParkId = ref()
const scoreFilterParkId = ref()

// 弹窗
const parkDialogVisible = ref(false)
const scoreDialogVisible = ref(false)

// 表单
const parkForm = ref({})
const scoreForm = ref({})

// 上传头
const uploadHeaders = computed(() => ({
  Authorization: `Bearer ${localStorage.getItem('token')}`
}))

onMounted(() => {
  if (!auth.isAdmin) return
  loadParks()
  loadIndicators()
  loadUsers()
  loadScores()
})

// ==================== 加载数据 ====================

async function loadParks() {
  const res = await api.get('/admin/parks')
  parks.value = res.data
}

async function loadSites() {
  if (!siteFilterParkId.value) {
    sites.value = []
    return
  }
  const res = await api.get(`/admin/parks/${siteFilterParkId.value}/sites`)
  sites.value = res.data
}

async function loadScores() {
  const params = scoreFilterParkId.value ? { park_id: scoreFilterParkId.value } : {}
  const res = await api.get('/admin/scores', { params })
  scores.value = res.data
}

async function loadIndicators() {
  try {
    const res = await api.get('/admin/indicators')
    indicators.value = res.data
  } catch (e) {
    console.error('加载指标列表失败', e)
  }
}

async function loadUsers() {
  const res = await api.get('/admin/users')
  users.value = res.data
}

// ==================== 公园操作 ====================

function showParkDialog(row = null) {
  parkForm.value = row ? { ...row } : {
    name: '', short_name: '', park_type: '', batch: 1,
    province: '', city: '', longitude: null, latitude: null,
    total_area: null, aaa_level: '', description: ''
  }
  parkDialogVisible.value = true
}

async function savePark() {
  try {
    if (parkForm.value.id) {
      await api.put(`/admin/parks/${parkForm.value.id}`, parkForm.value)
    } else {
      await api.post('/admin/parks', parkForm.value)
    }
    ElMessage.success('保存成功')
    parkDialogVisible.value = false
    loadParks()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function deletePark(id) {
  await ElMessageBox.confirm('确定删除此公园？关联数据将一并删除。', '确认')
  await api.delete(`/admin/parks/${id}`)
  ElMessage.success('删除成功')
  loadParks()
}

// ==================== 遗址点操作 ====================

function showSiteDialog(_row = null) {
  // 简化处理
  ElMessage.info('请使用Excel导入遗址点数据')
}

async function deleteSite(id) {
  await ElMessageBox.confirm('确定删除？', '确认')
  await api.delete(`/admin/sites/${id}`)
  ElMessage.success('删除成功')
  loadSites()
}

// ==================== 评分操作 ====================

function showScoreDialog(row = null) {
  scoreForm.value = row ? { ...row } : {
    park_id: null, indicator_id: null,
    normalized_score: 60, evidence: '', data_year: 2025
  }
  scoreDialogVisible.value = true
}

async function saveScore() {
  try {
    if (scoreForm.value.id) {
      await api.put(`/admin/scores/${scoreForm.value.id}`, scoreForm.value)
    } else {
      await api.post('/admin/scores', scoreForm.value)
    }
    ElMessage.success('保存成功')
    scoreDialogVisible.value = false
    loadScores()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '保存失败')
  }
}

async function deleteScore(id) {
  await ElMessageBox.confirm('确定删除？', '确认')
  await api.delete(`/admin/scores/${id}`)
  ElMessage.success('删除成功')
  loadScores()
}

// ==================== 用户操作 ====================

async function updateRole(userId, role) {
  await api.put(`/admin/users/${userId}/role`, null, { params: { role } })
  ElMessage.success('角色已更新')
}

async function toggleStatus(userId) {
  await api.put(`/admin/users/${userId}/status`)
  ElMessage.success('状态已更新')
  loadUsers()
}

// ==================== 导入回调 ====================

function handleImportSuccess(res) {
  if (res.success) {
    ElMessage.success(`导入成功: ${res.success}条`)
    loadParks()
    loadScores()
    loadSites()
  }
  if (res.errors?.length) {
    ElMessage.warning(`${res.errors.length}条导入失败`)
  }
}
</script>

<style scoped lang="scss">
.admin-tabs-card {
  padding: 0 22px 22px;
  overflow: hidden;
}

.admin-tabs-card :deep(.el-tabs__header) {
  margin-bottom: 20px;
}

.admin-tabs-card :deep(.el-tabs__nav-wrap) {
  padding: 0 6px;
}

.toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.toolbar a { text-decoration: none; }

@media (max-width: 760px) {
  .admin-tabs-card { padding-inline: 12px; }
  .toolbar { align-items: stretch; }
  .toolbar .el-select { width: 100%; }
}
</style>
