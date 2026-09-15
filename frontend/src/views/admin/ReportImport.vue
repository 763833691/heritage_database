<template>
  <div class="report-import">
    <!-- 上传区 -->
    <div v-if="!parsed" class="upload-section">
      <el-upload
        ref="uploadRef"
        class="upload-box"
        drag
        :auto-upload="false"
        :limit="1"
        accept=".docx,.doc,.txt"
        :on-change="handleFileChange"
        :on-exceed="() => ElMessage.warning('只能上传一个文件')"
      >
        <el-icon class="upload-icon"><UploadFilled /></el-icon>
        <div class="upload-text">
          <p><strong>拖拽或点击上传调研报告</strong></p>
          <p class="upload-hint">支持 .docx / .doc 格式，最大 50MB</p>
        </div>
      </el-upload>

      <div v-if="uploadFile" class="upload-info">
        <el-tag type="info" size="large">{{ uploadFile.name }}</el-tag>
        <el-button
          type="primary"
          :loading="parsing"
          @click="startParse"
          style="margin-left:12px"
        >
          {{ parsing ? 'AI 解析中...' : '开始解析' }}
        </el-button>
      </div>

      <div v-if="parsing" class="parse-progress">
        <el-progress :percentage="parseProgress" :stroke-width="16" :text-inside="true" />
        <p class="progress-text">{{ parseStatus }}</p>
      </div>
    </div>

    <!-- 解析结果预览 -->
    <div v-if="parsed" class="result-section">
      <div class="result-header">
        <h3>解析结果预览</h3>
        <div>
          <el-tag type="success">{{ parsed.parks?.length || 0 }} 个公园</el-tag>
          <el-tag type="warning" style="margin-left:8px">{{ parsed.scores?.length || 0 }} 条评分</el-tag>
          <el-tag type="info" style="margin-left:8px">{{ parsed.surveys?.length || 0 }} 条问卷</el-tag>
        </div>
      </div>

      <!-- 公园列表 -->
      <el-card header="遗址公园" shadow="never" style="margin-top:16px">
        <el-table :data="parsed.parks" stripe border max-height="400">
          <el-table-column prop="name" label="名称" min-width="200" />
          <el-table-column prop="short_name" label="简称" width="120" />
          <el-table-column prop="park_type" label="类型" width="80" />
          <el-table-column prop="province" label="省份" width="80" />
          <el-table-column prop="city" label="城市" width="100" />
          <el-table-column label="操作" width="80">
            <template #default="{ $index }">
              <el-button size="small" type="danger" text @click="removePark($index)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!parsed.parks?.length" description="未识别到公园数据" />
      </el-card>

      <!-- 评分列表 -->
      <el-card header="评估评分" shadow="never" style="margin-top:16px">
        <el-table :data="parsed.scores" stripe border max-height="400">
          <el-table-column prop="park_name" label="公园" width="120" />
          <el-table-column prop="indicator_code" label="编号" width="80" />
          <el-table-column prop="indicator_name" label="指标" min-width="160" />
          <el-table-column prop="score" label="得分" width="80">
            <template #default="{ row }">
              <el-tag :type="row.score >= 80 ? 'success' : row.score >= 60 ? 'primary' : row.score >= 40 ? 'warning' : 'danger'">
                {{ row.score }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="dimension" label="维度" width="140" />
          <el-table-column label="操作" width="80">
            <template #default="{ $index }">
              <el-button size="small" type="danger" text @click="removeScore($index)">移除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!parsed.scores?.length" description="未识别到评分数据" />
      </el-card>

      <!-- 问卷列表 -->
      <el-card v-if="parsed.surveys?.length" header="调研问卷" shadow="never" style="margin-top:16px">
        <el-table :data="parsed.surveys" stripe border>
          <el-table-column prop="park_name" label="公园" width="120" />
          <el-table-column prop="total_distributed" label="发放" width="80" />
          <el-table-column prop="total_collected" label="回收" width="80" />
          <el-table-column prop="valid_count" label="有效" width="80" />
          <el-table-column prop="sampling_method" label="抽样方法" />
        </el-table>
      </el-card>

      <!-- 操作按钮 -->
      <div class="result-actions">
        <el-button @click="reset">重新上传</el-button>
        <el-button type="primary" :loading="importing" @click="confirmImport">
          {{ importing ? '导入中...' : '确认导入' }}
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '@/utils/api'

const uploadRef = ref(null)
const uploadFile = ref(null)
const parsing = ref(false)
const importing = ref(false)
const parsed = ref(null)
const parseProgress = ref(0)
const parseStatus = ref('')

function handleFileChange(file) {
  uploadFile.value = file.raw
}

async function startParse() {
  if (!uploadFile.value) return

  parsing.value = true
  parseProgress.value = 30
  parseStatus.value = '正在提取文档文本...'

  try {
    const formData = new FormData()
    formData.append('file', uploadFile.value)

    parseProgress.value = 60
    parseStatus.value = 'AI 正在解析文档内容...'

    const res = await api.post('/admin/upload/report', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 180000,
    })

    parseProgress.value = 100
    parseStatus.value = '解析完成！'
    parsed.value = res.data.parsed

    setTimeout(() => {
      if (parsed.value) {
        ElMessage.success(
          `解析完成：${res.data.parsed.parks.length} 个公园，${res.data.parsed.scores.length} 条评分`
        )
      }
    }, 300)
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '解析失败')
  } finally {
    parsing.value = false
  }
}

function removePark(idx) {
  parsed.value.parks.splice(idx, 1)
}

function removeScore(idx) {
  parsed.value.scores.splice(idx, 1)
}

async function confirmImport() {
  try {
    await ElMessageBox.confirm(
      `确认导入 ${parsed.value.parks.length} 个公园、${parsed.value.scores.length} 条评分、${parsed.value.surveys.length} 条问卷？`,
      '确认导入'
    )
  } catch {
    return
  }

  importing.value = true
  try {
    const res = await api.post('/admin/upload/report/confirm', parsed.value)
    const imp = res.data.imported
    ElMessage.success(`导入完成：${imp.parks} 个公园，${imp.scores} 条评分，${imp.surveys} 条问卷`)
    parsed.value = null
    uploadFile.value = null
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '导入失败')
  } finally {
    importing.value = false
  }
}

function reset() {
  parsed.value = null
  uploadFile.value = null
}
</script>

<style scoped>
.upload-section {
  text-align: center;
  padding: 40px 0;
}

.upload-box {
  width: 100%;
}

.upload-icon {
  font-size: 56px;
  color: #409eff;
}

.upload-text p {
  margin: 8px 0;
  font-size: 16px;
}

.upload-hint {
  color: #999;
  font-size: 13px;
}

.upload-info {
  margin-top: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.parse-progress {
  margin-top: 24px;
  text-align: center;
}

.progress-text {
  color: #999;
  margin-top: 8px;
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-actions {
  margin-top: 24px;
  text-align: center;
}
</style>
