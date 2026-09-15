<template>
  <el-dialog
    v-model="visible"
    :title="isEdit ? '编辑遗址公园' : '新增遗址公园'"
    width="min(720px, 94vw)"
    destroy-on-close
    @closed="resetForm"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="110px" class="park-form">
      <div v-if="locationPicked && !isEdit" class="park-form__location-notice">
        <el-icon><LocationFilled /></el-icon>
        <div>
          <strong>已从地图选定公园位置</strong>
          <span>经度 {{ formatCoordinate(form.longitude) }}，纬度 {{ formatCoordinate(form.latitude) }}</span>
        </div>
      </div>
      <div class="park-form__section">
        <h3>基本信息</h3>
        <div class="park-form__grid">
          <el-form-item label="公园名称" prop="name">
            <el-input v-model="form.name" placeholder="如：圆明园国家考古遗址公园" />
          </el-form-item>
          <el-form-item label="简称">
            <el-input v-model="form.short_name" placeholder="如：圆明园" />
          </el-form-item>
          <el-form-item label="公园类型" prop="park_type">
            <el-select v-model="form.park_type" placeholder="选择类型">
              <el-option label="城市型" value="城市型" />
              <el-option label="城郊型" value="城郊型" />
              <el-option label="乡村型" value="乡村型" />
            </el-select>
          </el-form-item>
          <el-form-item label="评定批次">
            <el-input-number v-model="form.batch" :min="1" :max="5" />
          </el-form-item>
          <el-form-item label="省份" prop="province">
            <el-input v-model="form.province" placeholder="如：北京" />
          </el-form-item>
          <el-form-item label="城市" prop="city">
            <el-input v-model="form.city" placeholder="如：北京" />
          </el-form-item>
          <el-form-item label="经度">
            <el-input-number v-model="form.longitude" :precision="4" :step="0.0001" />
          </el-form-item>
          <el-form-item label="纬度">
            <el-input-number v-model="form.latitude" :precision="4" :step="0.0001" />
          </el-form-item>
          <el-form-item label="面积(km²)">
            <el-input-number v-model="form.total_area" :precision="2" :min="0" />
          </el-form-item>
          <el-form-item label="景区等级">
            <el-select v-model="form.aaa_level" clearable placeholder="可选">
              <el-option label="5A" value="5A" />
              <el-option label="4A" value="4A" />
              <el-option label="3A" value="3A" />
            </el-select>
          </el-form-item>
          <el-form-item label="世界遗产">
            <el-switch v-model="form.world_heritage" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </div>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="公园简介、历史背景等" />
        </el-form-item>
        <p v-if="!isEdit" class="park-form__hint">评价指标将根据遗址点、调研数据等自动计算，无需手动填写。</p>
      </div>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">{{ isEdit ? '保存修改' : '创建公园' }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '@/utils/api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  park: { type: Object, default: null },
  initialValues: { type: Object, default: null },
  locationPicked: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'saved'])

const formRef = ref()
const saving = ref(false)

const defaultForm = () => ({
  name: '',
  short_name: '',
  park_type: '',
  batch: 1,
  province: '',
  city: '',
  longitude: null,
  latitude: null,
  total_area: null,
  aaa_level: '',
  world_heritage: 0,
  description: '',
})

const form = ref(defaultForm())

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})

const isEdit = computed(() => Boolean(form.value.id))

const rules = {
  name: [{ required: true, message: '请输入公园名称', trigger: 'blur' }],
  park_type: [{ required: true, message: '请选择公园类型', trigger: 'change' }],
  province: [{ required: true, message: '请输入省份', trigger: 'blur' }],
  city: [{ required: true, message: '请输入城市', trigger: 'blur' }],
}

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    form.value = props.park
      ? { ...defaultForm(), ...props.park }
      : { ...defaultForm(), ...(props.initialValues || {}) }
  }
)

function resetForm() {
  form.value = defaultForm()
  formRef.value?.resetFields()
}

async function handleSave() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  saving.value = true
  try {
    if (isEdit.value) {
      await api.put(`/admin/parks/${form.value.id}`, form.value)
    } else {
      const response = await api.post('/admin/parks', form.value)
      ElMessage.success('新增成功')
      visible.value = false
      emit('saved', response.data)
      return
    }
    ElMessage.success('更新成功')
    visible.value = false
    emit('saved', { id: form.value.id })
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    saving.value = false
  }
}

function formatCoordinate(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(6) : '—'
}
</script>

<style scoped lang="scss">
.park-form__section h3 {
  margin: 0 0 14px;
  font-size: 15px;
}

.park-form__location-notice {
  margin: 0 0 18px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid var(--brand-100);
  border-radius: 10px;
  color: var(--brand-700);
  background: var(--brand-50);
}

.park-form__location-notice .el-icon {
  font-size: 22px;
}

.park-form__location-notice div {
  display: grid;
  gap: 3px;
}

.park-form__location-notice span {
  color: var(--text-secondary);
  font-size: 12px;
}

.park-form__hint {
  margin: 4px 0 0;
  color: var(--text-secondary);
  font-size: 12px;
  line-height: 1.6;
}

.park-form__grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}

@media (max-width: 640px) {
  .park-form__grid {
    grid-template-columns: 1fr;
  }
}
</style>
