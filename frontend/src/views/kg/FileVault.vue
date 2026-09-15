<template>
  <div class="page-shell vault-page">
    <div class="vault-layout">
      <!-- 左侧：文件分类 -->
      <aside class="vault-sidebar">
        <div class="vault-sidebar__header">
          <div class="vault-sidebar__title">文件分类</div>
          <el-button text type="primary" size="small" @click="promptCreateFolder">
            <el-icon><Plus /></el-icon>
            新建分类
          </el-button>
        </div>

        <div class="vault-sidebar__search">
          <el-input v-model="folderSearch" size="small" clearable placeholder="搜索分类名称">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>

        <div ref="sidebarListRef" class="vault-sidebar__list">
          <button
            type="button"
            class="folder-row"
            :class="{ 'folder-row--active': activeFolderKey === VAULT_ALL_KEY }"
            @click="selectFolder(VAULT_ALL_KEY)"
          >
            <span class="folder-row__icon">📁</span>
            <span class="folder-row__label">全部资料</span>
            <span class="folder-row__count">{{ vaultFiles.length }}</span>
          </button>

          <button
            type="button"
            class="folder-row"
            :class="{ 'folder-row--active': activeFolderKey === VAULT_UNCATEGORIZED_KEY }"
            @click="selectFolder(VAULT_UNCATEGORIZED_KEY)"
          >
            <span class="folder-row__icon">🗂️</span>
            <span class="folder-row__label">未分类</span>
            <span class="folder-row__count">{{ countFilesInFolder(vaultFiles, VAULT_UNCATEGORIZED_KEY) }}</span>
          </button>

          <div
            v-for="folder in filteredFolders"
            :key="folder.id"
            class="folder-row-wrap"
            :class="{ 'folder-row-wrap--active': activeFolderKey === folder.id }"
          >
            <template v-if="editingFolderId !== folder.id">
              <button
                type="button"
                class="folder-row"
                :class="{ 'folder-row--active': activeFolderKey === folder.id }"
                @click="selectFolder(folder.id)"
                @dblclick="startRename(folder)"
              >
                <span class="folder-row__icon">{{ folderIcon(folder.name) }}</span>
                <span class="folder-row__label">{{ folder.name }}</span>
                <span class="folder-row__count">{{ countFilesInFolder(vaultFiles, folder.id) }}</span>
              </button>
            </template>
            <div v-else class="folder-row folder-row--editing">
              <input
                v-model="folderRenameDraft"
                class="folder-row__input"
                @blur="onFolderRenameBlur"
                @keydown.enter="onFolderRenameEnter"
                @keydown.esc="cancelRename"
              />
              <AutoSaveIndicator :status="renameSaveStatus" />
            </div>
            <span class="folder-row__tools">
              <el-button text size="small" title="重命名" @click.stop="startRename(folder)">
                <el-icon><EditPen /></el-icon>
              </el-button>
              <el-button text size="small" title="删除分类" @click.stop="promptDeleteFolder(folder)">
                <el-icon><Delete /></el-icon>
              </el-button>
            </span>
          </div>

          <p v-if="folderError" class="vault-sidebar__error">{{ folderError }}</p>
        </div>

        <div class="vault-sidebar__tags">
          <button type="button" class="vault-sidebar__toggle" @click="showTagCloud = !showTagCloud">
            <el-icon :class="{ 'is-open': showTagCloud }"><ArrowRight /></el-icon>
            标签云
          </button>
          <div v-if="showTagCloud" class="tag-cloud">
            <button v-for="tag in topTags" :key="tag.name" type="button" class="tag-chip" @click="applyTag(tag.name)">
              {{ tag.name }} ({{ tag.count }})
            </button>
            <span v-if="!topTags.length" class="muted">暂无标签</span>
          </div>
        </div>
      </aside>

      <!-- 中间：工具栏与文件列表 -->
      <section class="vault-main">
        <header class="vault-main__header">
          <div class="vault-main__titles">
            <h1>文件库</h1>
            <p class="muted">{{ vaultBreadcrumb(activeFolderKey, folders) }} · 管理与浏览您的研究资料</p>
          </div>
          <div class="toolbar-row vault-main__toolbar">
            <el-input
              v-model="query"
              class="vault-search"
              clearable
              placeholder="搜索文件名、内容、标签或实体..."
              @blur="persistQuery"
            >
              <template #prefix><el-icon><Search /></el-icon></template>
            </el-input>
            <AudioTranscribeDialog @saved="handleTranscribeSaved" />
            <el-button :disabled="!selectedIds.length" :loading="deleting" @click="deleteSelected">
              <el-icon><Delete /></el-icon>
              批量删除
            </el-button>
            <el-button type="primary" :loading="busy" @click="openFilePicker">
              <el-icon><Upload /></el-icon>
              上传文件
            </el-button>
            <input ref="fileInputRef" type="file" multiple hidden @change="onFileInput" />
          </div>
        </header>

        <div class="vault-folder-tabs">
          <button
            v-for="tab in folderTabCounts"
            :key="tab.key"
            type="button"
            class="folder-tab"
            :class="{ 'folder-tab--active': activeFolderKey === tab.key }"
            @click="selectFolder(tab.key)"
          >
            <el-icon><FolderOpened /></el-icon>
            {{ tab.label }}
            <span class="folder-tab__count">{{ tab.count }}</span>
          </button>
        </div>

        <div class="vault-listbar">
          <span class="muted">共 {{ filtered.length }} 个文件</span>
          <el-radio-group v-model="viewMode" size="small">
            <el-radio-button value="list"><el-icon><List /></el-icon></el-radio-button>
            <el-radio-button value="grid"><el-icon><Grid /></el-icon></el-radio-button>
          </el-radio-group>
        </div>

        <div
          class="vault-dropzone"
          :class="{ 'vault-dropzone--active': dragging }"
          @dragenter="onDragEnter"
          @dragleave="onDragLeave"
          @dragover="onDragOver"
          @drop="onDrop"
        >
          <div v-if="dragging" class="vault-dropzone__mask">{{ dropHint }}</div>

          <StatusState v-if="loading" type="loading" title="正在加载文件" />
          <StatusState
            v-else-if="loadError"
            type="error"
            title="文件列表加载失败"
            :description="loadError"
            action-label="重新加载"
            @action="loadAll"
          />
          <StatusState
            v-else-if="!filtered.length"
            type="empty"
            :title="vaultFiles.length ? '当前目录暂无文件' : '还没有文献'"
            :description="dropHint"
            action-label="上传文件"
            @action="openFilePicker"
          />

          <template v-else>
            <el-table
              v-if="viewMode === 'list'"
              :data="paginatedFiles"
              row-key="id"
              highlight-current-row
              :current-row-key="currentFile?.id"
              class="vault-table"
              @row-click="onRowClick"
              @selection-change="onSelectionChange"
            >
              <el-table-column type="selection" width="46" reserve-selection />
              <el-table-column label="文件名称" min-width="240">
                <template #default="{ row }">
                  <div class="file-cell">
                    <span class="file-icon" :class="`file-icon--${fileTypeVariant(row.type)}`">{{ fileIconLabel(row.type) }}</span>
                    <span class="file-cell__name">{{ row.name }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="类型" width="88">
                <template #default="{ row }">{{ String(row.type || '').toUpperCase() }}</template>
              </el-table-column>
              <el-table-column label="分类" width="130">
                <template #default="{ row }">
                  <span class="folder-badge">{{ folderNameById(folders, row.folder_id) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="标签" min-width="180">
                <template #default="{ row }">
                  <div class="tag-cell">
                    <span v-for="tag in (row.tags || []).slice(0, 3)" :key="tag" class="tag-cell__item">{{ tag }}</span>
                    <span v-if="(row.tags || []).length > 3" class="tag-cell__more">+{{ row.tags.length - 3 }}</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column label="上传时间" width="120">
                <template #default="{ row }">{{ String(row.upload_time || '').slice(0, 10) }}</template>
              </el-table-column>
              <el-table-column label="状态" width="130">
                <template #default="{ row }">
                  <el-tag :type="statusTagType(row.status)" size="small">
                    <el-icon :class="{ 'is-spin': row.status === 'processing' }">
                      <component :is="statusIconName(row.status)" />
                    </el-icon>
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="150" align="right">
                <template #default="{ row }">
                  <div class="row-actions" @click.stop>
                    <el-button text size="small" title="处理" @click="handleStart(row)">
                      <el-icon><VideoPlay /></el-icon>
                    </el-button>
                    <el-button text size="small" title="详情" @click="selectFileById(row.id)">
                      <el-icon><View /></el-icon>
                    </el-button>
                    <el-button text size="small" type="danger" title="删除" @click="handleDelete([row])">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>

            <div v-else class="vault-grid">
              <article
                v-for="file in paginatedFiles"
                :key="file.id"
                class="vault-card"
                :class="{ 'vault-card--active': currentFile?.id === file.id }"
                @click="selectFileById(file.id)"
              >
                <div class="vault-card__top">
                  <span class="file-icon" :class="`file-icon--${fileTypeVariant(file.type)}`">{{ fileIconLabel(file.type) }}</span>
                  <span class="vault-card__name">{{ file.name }}</span>
                </div>
                <div class="vault-card__meta">
                  <el-tag :type="statusTagType(file.status)" size="small">{{ statusLabel(file.status) }}</el-tag>
                  <span class="muted">{{ String(file.type || '').toUpperCase() }}</span>
                </div>
                <div class="vault-card__footer">
                  <span class="muted">{{ folderNameById(folders, file.folder_id) }}</span>
                  <div class="row-actions" @click.stop>
                    <el-button text size="small" title="处理" @click="handleStart(file)">
                      <el-icon><VideoPlay /></el-icon>
                    </el-button>
                    <el-button text size="small" type="danger" title="删除" @click="handleDelete([file])">
                      <el-icon><Delete /></el-icon>
                    </el-button>
                  </div>
                </div>
              </article>
            </div>
          </template>
        </div>

        <footer class="vault-pagination">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :total="filtered.length"
            :page-sizes="[10, 20, 50]"
            background
            layout="total, sizes, prev, pager, next"
          />
        </footer>
      </section>

      <!-- 右侧：文件详情 -->
      <aside class="vault-detail">
        <template v-if="currentFile">
          <div class="vault-detail__header">
            <span class="file-icon file-icon--lg" :class="`file-icon--${fileTypeVariant(currentFile.type)}`">
              {{ fileIconLabel(currentFile.type) }}
            </span>
            <div class="vault-detail__titles">
              <div class="vault-detail__name">{{ currentFile.name }}</div>
              <div class="muted">{{ formatSize(currentFile.size) }}</div>
            </div>
            <el-button text size="small" title="关闭" @click="closeDetail">
              <el-icon><Close /></el-icon>
            </el-button>
          </div>

          <div class="vault-detail__actions">
            <el-button size="small" @click="handleStart(currentFile)">
              <el-icon><VideoPlay /></el-icon>
              处理
            </el-button>
            <el-button size="small" @click="openPreview">
              <el-icon><View /></el-icon>
              预览
            </el-button>
            <el-button size="small" @click="handleDownload">
              <el-icon><Download /></el-icon>
              下载
            </el-button>
          </div>

          <div class="vault-detail__body">
            <dl class="detail-list">
              <div class="detail-list__row">
                <dt>类型</dt>
                <dd>{{ String(currentFile.type || '').toUpperCase() }}</dd>
              </div>
              <div class="detail-list__row">
                <dt>分类</dt>
                <dd class="detail-list__folder">
                  <el-select v-model="folderDraft" size="small" placeholder="未分类" @change="scheduleFolderSave" @blur="onFolderBlurSave">
                    <el-option label="未分类" value="" />
                    <el-option v-for="folder in folders" :key="folder.id" :label="folder.name" :value="folder.id" />
                  </el-select>
                  <AutoSaveIndicator :status="folderSaveStatus" />
                </dd>
              </div>
              <div class="detail-list__row">
                <dt>上传时间</dt>
                <dd>{{ formatTime(currentFile.upload_time) }}</dd>
              </div>
              <div class="detail-list__row">
                <dt>上传者</dt>
                <dd>admin</dd>
              </div>
              <div class="detail-list__row">
                <dt>摘要</dt>
                <dd class="detail-list__summary">{{ currentFile.summary || '暂无摘要' }}</dd>
              </div>
            </dl>

            <div class="detail-section">
              <h3>标签</h3>
              <div class="detail-tags">
                <span v-for="tag in currentFile.tags || []" :key="tag" class="detail-tag">{{ tag }}</span>
                <span v-if="!(currentFile.tags || []).length" class="muted">暂无标签</span>
              </div>
            </div>

            <div class="detail-section">
              <h3>处理状态</h3>
              <StatusBadge :status="currentFile.status" :process-status="currentFile.process_status" />
            </div>

            <div v-if="detailEntities.length" class="detail-section">
              <h3>识别实体（{{ detailEntities.length }}）</h3>
              <div class="entity-list">
                <span
                  v-for="entity in detailEntities"
                  :key="entity.id"
                  class="entity-chip"
                  :class="`entity-chip--${entityTone(entity.type)}`"
                  :title="ENTITY_TYPE_LABELS[entity.type] || entity.type"
                >
                  <el-icon><component :is="entityIconName(entity.type)" /></el-icon>
                  {{ entity.name }}
                </span>
              </div>
            </div>

            <div v-if="detailRelations.length" class="detail-section">
              <h3>识别关系（{{ detailRelations.length }}）</h3>
              <div class="relation-list">
                <div v-for="(relation, index) in detailRelations" :key="index" class="relation-item">
                  <span class="entity-chip" :class="`entity-chip--${entityTone(relation.sourceType)}`">
                    {{ relation.sourceName }}
                  </span>
                  <span class="relation-item__label">→ {{ relation.relation }}</span>
                  <span class="entity-chip" :class="`entity-chip--${entityTone(relation.targetType)}`">
                    {{ relation.targetName }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </template>

        <div v-else class="vault-detail__placeholder">选择文件查看详情</div>
      </aside>
    </div>

    <el-dialog v-model="previewVisible" :title="previewTitle" width="min(860px, 94vw)">
      <el-input v-model="previewText" type="textarea" :rows="16" readonly placeholder="暂无预览内容" />
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createKgFolder,
  deleteKgFile,
  deleteKgFolder,
  getKgFolders,
  getKgTextPreview,
  updateKgFile,
  updateKgFolder,
} from '@/utils/kgApi'
import { useKgStore } from '@/stores/kg'
import StatusState from '@/components/common/StatusState.vue'
import AutoSaveIndicator from '@/features/kg/components/AutoSaveIndicator.vue'
import AudioTranscribeDialog from '@/features/kg/components/AudioTranscribeDialog.vue'
import StatusBadge from '@/features/kg/components/StatusBadge.vue'
import { useBlurSave } from '@/features/kg/useBlurSave'
import {
  ENTITY_TYPE_LABELS,
  VAULT_ALL_KEY,
  VAULT_UNCATEGORIZED_KEY,
  countFilesInFolder,
  entityIconName,
  entityTone,
  fileIconLabel,
  fileTypeVariant,
  folderIcon,
  folderNameById,
  formatSize,
  matchesVaultFolder,
  statusIconName,
  statusLabel,
  statusTagType,
  uploadFolderIdFromKey,
  vaultBreadcrumb,
} from '@/features/kg/constants'

const router = useRouter()
const store = useKgStore()

const folders = ref([])
const folderError = ref('')
const loadError = ref('')
const booting = ref(true)
const busy = ref(false)
const deleting = ref(false)
const dragging = ref(false)
const fileInputRef = ref(null)
const selectedIds = ref([])
const viewMode = ref('list')
const currentPage = ref(1)
const pageSize = ref(10)
const folderSearch = ref('')
const showTagCloud = ref(true)
const previewVisible = ref(false)
const previewText = ref('')

const activeFolderKey = ref(localStorage.getItem('kg-file-vault-folder') || VAULT_ALL_KEY)
const query = ref(localStorage.getItem('kg-file-vault-query') || '')

const folderDraft = ref('')
const folderSnapshot = ref('')

const editingFolderId = ref('')
const folderRenameDraft = ref('')
const renameSnapshot = ref('')
const sidebarListRef = ref(null)

let dragDepth = 0

const files = computed(() => store.files)
const currentFile = computed(() => store.currentFile)
const loading = computed(() => booting.value || (store.loading && !files.value.length))

const vaultFiles = computed(() =>
  files.value.filter(
    (file) => file.status !== 'created' && file.source !== '任务创建' && file.source !== '文件库载入',
  ),
)

const filtered = computed(() => {
  const keyword = query.value.trim().toLowerCase()
  return vaultFiles.value.filter((file) => {
    if (!matchesVaultFolder(file, activeFolderKey.value)) return false
    if (!keyword) return true
    const folderName = folderNameById(folders.value, file.folder_id)
    return [file.name, file.type, file.source, file.summary, folderName, ...(file.tags || [])]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const paginatedFiles = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filtered.value.slice(start, start + pageSize.value)
})

const filteredFolders = computed(() => {
  if (!folderSearch.value) return folders.value
  const keyword = folderSearch.value.toLowerCase()
  return folders.value.filter((folder) => folder.name.toLowerCase().includes(keyword))
})

const folderTabCounts = computed(() => {
  const tabs = [
    { key: VAULT_ALL_KEY, label: '全部资料', count: vaultFiles.value.length },
    { key: VAULT_UNCATEGORIZED_KEY, label: '未分类', count: countFilesInFolder(vaultFiles.value, VAULT_UNCATEGORIZED_KEY) },
  ]
  folders.value.forEach((folder) => {
    tabs.push({ key: folder.id, label: folder.name, count: countFilesInFolder(vaultFiles.value, folder.id) })
  })
  return tabs
})

const topTags = computed(() => {
  const counts = new Map()
  vaultFiles.value.forEach((file) => {
    ;(file.tags || []).forEach((tag) => counts.set(tag, (counts.get(tag) || 0) + 1))
  })
  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12)
    .map(([name, count]) => ({ name, count }))
})

const dropHint = computed(() =>
  isFolderKey(activeFolderKey.value)
    ? `拖拽文件到此处，将导入到「${folderNameById(folders.value, activeFolderKey.value)}」（单文件最大 200 MB）`
    : '拖拽 PDF / MD / TXT 到此处上传（单文件最大 200 MB）',
)

const previewTitle = computed(() => (currentFile.value ? `预览 · ${currentFile.value.name}` : '文件预览'))

const detailEntities = computed(() => currentFile.value?.process_result?.entities?.slice(0, 6) ?? [])

const detailRelations = computed(() => {
  const relations = currentFile.value?.process_result?.relations ?? []
  const entities = currentFile.value?.process_result?.entities ?? []
  return relations.slice(0, 4).map((relation) => {
    const source = entities.find((entity) => entity.id === relation.source)
    const target = entities.find((entity) => entity.id === relation.target)
    return {
      relation: relation.relation,
      sourceName: source?.name || relation.source,
      targetName: target?.name || relation.target,
      sourceType: source?.type,
      targetType: target?.type,
    }
  })
})

const {
  status: folderSaveStatus,
  onBlurSave: onFolderBlurSave,
  scheduleSave: scheduleFolderSave,
} = useBlurSave({
  ready: () => Boolean(currentFile.value),
  hasChanges: () => folderDraft.value !== folderSnapshot.value,
  save: async () => {
    const file = currentFile.value
    if (!file) return
    await updateKgFile(file.id, { folder_id: folderDraft.value })
    folderSnapshot.value = folderDraft.value
    await Promise.all([loadFiles(), loadFolders()])
  },
  onError: (error) => ElMessage.error(error?.message || '保存分类失败'),
})

const { status: renameSaveStatus, onBlurSave: onRenameBlurSave } = useBlurSave({
  ready: () => Boolean(editingFolderId.value),
  hasChanges: () => folderRenameDraft.value.trim() !== renameSnapshot.value,
  save: async () => {
    const folderId = editingFolderId.value
    const next = folderRenameDraft.value.trim()
    if (!folderId || !next) return
    await updateKgFolder(folderId, next)
    renameSnapshot.value = next
    editingFolderId.value = ''
    await Promise.all([loadFolders(), loadFiles()])
  },
  onError: (error) => ElMessage.error(error?.message || '重命名失败'),
})

function isFolderKey(key) {
  return key !== VAULT_ALL_KEY && key !== VAULT_UNCATEGORIZED_KEY
}

function formatTime(value) {
  return String(value || '').slice(0, 16).replace('T', ' ')
}

async function loadFiles(options) {
  try {
    await store.loadFiles(options)
    loadError.value = ''
  } catch (error) {
    loadError.value = error?.message || '文件列表加载失败'
  }
}

async function loadFolders() {
  try {
    const data = await getKgFolders()
    folders.value = data?.folders || []
    folderError.value = ''
  } catch (error) {
    folderError.value = error?.message || '分类加载失败'
  }
}

async function loadAll() {
  booting.value = true
  await Promise.all([loadFiles(), loadFolders()])
  booting.value = false
}

function persistQuery() {
  localStorage.setItem('kg-file-vault-query', query.value)
}

function selectFolder(key) {
  activeFolderKey.value = key
  localStorage.setItem('kg-file-vault-folder', key)
}

function applyTag(tag) {
  query.value = tag
  currentPage.value = 1
}

function selectFileById(fileId) {
  store.selectFile(fileId)
}

function closeDetail() {
  store.selectFile('')
}

function onRowClick(row) {
  selectFileById(row.id)
}

function onSelectionChange(rows) {
  selectedIds.value = rows.map((row) => row.id)
}

function openFilePicker() {
  fileInputRef.value?.click()
}

function onFileInput(event) {
  handleUploadFiles(event.target.files)
  event.target.value = ''
}

function onDragEnter(event) {
  event.preventDefault()
  dragDepth += 1
  dragging.value = true
}

function onDragLeave(event) {
  event.preventDefault()
  dragDepth = Math.max(0, dragDepth - 1)
  if (!dragDepth) dragging.value = false
}

function onDragOver(event) {
  event.preventDefault()
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy'
}

function onDrop(event) {
  event.preventDefault()
  dragDepth = 0
  dragging.value = false
  handleUploadFiles(event.dataTransfer?.files)
}

async function handleUploadFiles(fileList) {
  const uploads = fileList ? Array.from(fileList) : []
  if (!uploads.length || busy.value) return
  busy.value = true
  try {
    let lastItem
    for (const file of uploads) {
      lastItem = await store.upload(file, uploadFolderIdFromKey(activeFolderKey.value))
    }
    if (lastItem) store.selectFile(lastItem.id)
    await loadFolders()
    ElMessage.success(`已上传 ${uploads.length} 个文件`)
  } catch (error) {
    ElMessage.error(error?.message || '上传失败')
  } finally {
    busy.value = false
  }
}

async function handleStart(file) {
  if (!file) return
  busy.value = true
  try {
    await store.process(file.id)
    router.push(`/kg/processing/${file.id}`)
  } catch (error) {
    ElMessage.error(error?.message || '启动处理失败')
  } finally {
    busy.value = false
  }
}

async function handleDelete(targets) {
  if (!targets.length || deleting.value) return
  const label = targets.length === 1 ? `确定删除「${targets[0].name}」吗？` : `确定删除选中的 ${targets.length} 个文件吗？`
  try {
    await ElMessageBox.confirm(label, '删除确认', { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' })
  } catch {
    return
  }
  deleting.value = true
  try {
    await Promise.all(targets.map((file) => deleteKgFile(file.id)))
    const removed = new Set(targets.map((file) => file.id))
    selectedIds.value = selectedIds.value.filter((id) => !removed.has(id))
    await loadFiles()
    if (currentFile.value && removed.has(currentFile.value.id)) closeDetail()
    ElMessage.success('删除成功')
  } catch (error) {
    ElMessage.error(error?.message || '删除失败')
  } finally {
    deleting.value = false
  }
}

function deleteSelected() {
  const targets = vaultFiles.value.filter((file) => selectedIds.value.includes(file.id))
  return handleDelete(targets)
}

async function promptCreateFolder() {
  try {
    const { value } = await ElMessageBox.prompt('请输入分类名称', '新建分类', {
      confirmButtonText: '创建',
      cancelButtonText: '取消',
      inputValidator: (input) => (input && input.trim() ? true : '分类名称不能为空'),
    })
    const name = String(value || '').trim()
    if (!name) return
    const data = await createKgFolder(name)
    await loadFolders()
    if (data?.folder?.id) selectFolder(data.folder.id)
    ElMessage.success('分类已创建')
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(error?.message || '创建分类失败')
  }
}

async function promptDeleteFolder(folder) {
  try {
    await ElMessageBox.confirm(`确定删除目录「${folder.name}」吗？目录内文件将移至未分类。`, '删除分类', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteKgFolder(folder.id)
    if (activeFolderKey.value === folder.id) selectFolder(VAULT_ALL_KEY)
    await Promise.all([loadFolders(), loadFiles()])
    ElMessage.success('分类已删除')
  } catch (error) {
    ElMessage.error(error?.message || '删除分类失败')
  }
}

function startRename(folder) {
  if (!folder) return
  editingFolderId.value = folder.id
  folderRenameDraft.value = folder.name
  renameSnapshot.value = folder.name
  nextTick(() => {
    const input = sidebarListRef.value?.querySelector('.folder-row__input')
    input?.focus()
    input?.select()
  })
}

function cancelRename() {
  folderRenameDraft.value = renameSnapshot.value
  editingFolderId.value = ''
}

function onFolderRenameBlur() {
  onRenameBlurSave()
  editingFolderId.value = ''
}

function onFolderRenameEnter(event) {
  event.target.blur()
}

async function openPreview() {
  const file = currentFile.value
  if (!file) return
  previewVisible.value = true
  previewText.value = ''
  try {
    const data = await getKgTextPreview(file.id)
    previewText.value = data?.text_preview || '暂无文本预览'
  } catch (error) {
    previewText.value = `预览加载失败：${error?.message || '未知错误'}`
  }
}

function handleDownload() {
  ElMessage.info('该文件暂不支持直接下载，可在处理完成后前往图谱展示查看成果。')
}

function handleTranscribeSaved() {
  loadFiles()
}

watch([activeFolderKey, query], () => {
  currentPage.value = 1
})

watch(pageSize, () => {
  currentPage.value = 1
})

watch(
  () => filtered.value.length,
  (length) => {
    const maxPage = Math.max(1, Math.ceil(length / pageSize.value))
    if (currentPage.value > maxPage) currentPage.value = maxPage
  },
)

watch(
  () => [currentFile.value?.id, currentFile.value?.folder_id],
  () => {
    const value = currentFile.value?.folder_id ?? ''
    folderDraft.value = value
    folderSnapshot.value = value
  },
  { immediate: true },
)

onMounted(loadAll)
</script>

<style scoped lang="scss">
.vault-page {
  width: 100%;
}

.vault-layout {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr) 320px;
  gap: 18px;
  align-items: start;
}

/* ===== 左侧分类面板 ===== */
.vault-sidebar {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
}

.vault-sidebar__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.vault-sidebar__title {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.vault-sidebar__list {
  display: grid;
  gap: 2px;
  max-height: 340px;
  overflow: auto;
}

.vault-sidebar__error {
  margin: 6px 0 0;
  color: var(--red-500);
  font-size: 11px;
}

.folder-row-wrap {
  display: flex;
  align-items: center;
  gap: 2px;
  border-radius: var(--radius-lg);
}

.folder-row-wrap--active {
  background: var(--brand-50);
}

.folder-row {
  display: flex;
  flex: 1;
  align-items: center;
  gap: 8px;
  min-width: 0;
  padding: 7px 10px;
  border: 0;
  border-radius: var(--radius-lg);
  background: transparent;
  color: var(--text-secondary);
  font-size: 13px;
  text-align: left;
  cursor: pointer;
}

.folder-row:hover {
  background: var(--surface-soft);
}

.folder-row--active {
  color: var(--brand-600);
  font-weight: 650;
}

.folder-row__icon {
  flex: 0 0 auto;
}

.folder-row__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.folder-row__count {
  flex: 0 0 auto;
  padding: 1px 8px;
  border-radius: 999px;
  background: #eef1f5;
  color: var(--text-secondary);
  font-size: 11px;
}

.folder-row-wrap--active .folder-row__count {
  background: var(--brand-100);
  color: var(--brand-600);
}

.folder-row__tools {
  display: flex;
  flex: 0 0 auto;
  gap: 0;
}

.folder-row--editing {
  align-items: center;
  gap: 8px;
  cursor: default;
}

.folder-row__input {
  flex: 1;
  height: 28px;
  min-width: 0;
  padding: 0 8px;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  font-size: 12px;
  outline: none;
}

.folder-row__input:focus {
  border-color: var(--brand-500);
}

.vault-sidebar__tags {
  padding-top: 12px;
  border-top: 1px solid var(--border);
}

.vault-sidebar__toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  border: 0;
  background: none;
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.vault-sidebar__toggle .is-open {
  transform: rotate(90deg);
}

.tag-cloud {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.tag-chip {
  padding: 2px 9px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 11px;
  cursor: pointer;
  transition: border-color .2s ease, color .2s ease;
}

.tag-chip:hover {
  border-color: var(--brand-100);
  color: var(--brand-600);
}

/* ===== 中间主区 ===== */
.vault-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.vault-main__header {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
}

.vault-main__titles h1 {
  margin: 0;
  font-size: 20px;
}

.vault-main__titles p {
  margin: 4px 0 0;
  font-size: 13px;
}

.vault-main__toolbar {
  justify-content: flex-end;
}

.vault-search {
  width: 280px;
}

.vault-folder-tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.folder-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border: 0;
  border-radius: var(--radius-lg);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}

.folder-tab--active {
  background: #1f2937;
  color: #fff;
}

.folder-tab__count {
  padding: 0 6px;
  border-radius: 999px;
  background: rgba(148, 163, 184, .2);
  font-size: 11px;
}

.folder-tab--active .folder-tab__count {
  background: rgba(255, 255, 255, .22);
}

.vault-listbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.vault-dropzone {
  position: relative;
  min-height: 320px;
  padding: 4px;
  border: 1px dashed var(--border);
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, .6);
}

.vault-dropzone--active {
  border-color: var(--orange-500);
  background: #fffbeb;
}

.vault-dropzone__mask {
  position: absolute;
  inset: 8px;
  z-index: 5;
  display: grid;
  place-items: center;
  border: 2px dashed var(--orange-500);
  border-radius: var(--radius-lg);
  background: rgba(255, 251, 235, .94);
  color: #b45309;
  font-size: 13px;
  font-weight: 650;
  text-align: center;
  pointer-events: none;
}

.vault-table {
  width: 100%;
}

.file-cell {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.file-cell__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-weight: 550;
}

.file-icon {
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  border-radius: var(--radius-lg);
  font-size: 11px;
  font-weight: 700;
}

.file-icon--lg {
  width: 40px;
  height: 40px;
  font-size: 12px;
}

.file-icon--pdf { color: var(--red-500); background: #fef2f2; }
.file-icon--doc { color: var(--brand-600); background: var(--brand-50); }
.file-icon--md { color: #b45309; background: #fffbeb; }
.file-icon--txt { color: var(--violet-500); background: #f5f3ff; }
.file-icon--image { color: #15803d; background: #ecfdf5; }
.file-icon--zip { color: #a16207; background: #fefce8; }
.file-icon--other { color: var(--text-secondary); background: var(--surface-soft); }

.folder-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-md);
  background: #fffbeb;
  color: #b45309;
  font-size: 11px;
  font-weight: 600;
}

.tag-cell {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag-cell__item,
.tag-cell__more {
  padding: 1px 7px;
  border-radius: var(--radius-md);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 11px;
}

.tag-cell__more {
  color: var(--text-tertiary);
}

.row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0;
}

.vault-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 12px;
  padding: 8px;
}

.vault-card {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  cursor: pointer;
  transition: border-color .2s ease, transform .2s ease;
}

.vault-card:hover {
  transform: translateY(-2px);
  border-color: var(--brand-100);
}

.vault-card--active {
  border-color: var(--brand-500);
  background: var(--brand-50);
}

.vault-card__top {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.vault-card__name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}

.vault-card__meta,
.vault-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-size: 11px;
}

.vault-pagination {
  display: flex;
  justify-content: flex-end;
}

/* ===== 右侧详情 ===== */
.vault-detail {
  display: flex;
  flex-direction: column;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  background: var(--surface);
  box-shadow: var(--shadow-soft);
  overflow: hidden;
}

.vault-detail__header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--border);
}

.vault-detail__titles {
  flex: 1;
  min-width: 0;
}

.vault-detail__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
}

.vault-detail__actions {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
}

.vault-detail__body {
  padding: 16px;
  display: grid;
  gap: 18px;
}

.vault-detail__placeholder {
  display: grid;
  place-items: center;
  min-height: 260px;
  padding: 24px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.detail-list {
  display: grid;
  gap: 12px;
}

.detail-list__row {
  display: grid;
  grid-template-columns: 60px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
}

.detail-list__row dt {
  color: var(--text-tertiary);
  font-size: 12px;
}

.detail-list__row dd {
  margin: 0;
  color: var(--text-primary);
  font-size: 13px;
}

.detail-list__folder {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-list__summary {
  color: var(--text-secondary) !important;
  line-height: 1.7;
}

.detail-section h3 {
  margin: 0 0 8px;
  color: var(--text-tertiary);
  font-size: 12px;
  font-weight: 650;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.detail-tag {
  padding: 2px 9px;
  border-radius: var(--radius-md);
  background: var(--surface-soft);
  color: var(--text-secondary);
  font-size: 11px;
}

.entity-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.entity-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: var(--radius-lg);
  font-size: 11px;
  font-weight: 600;
}

.entity-chip--green { color: #15803d; background: #ecfdf5; }
.entity-chip--blue { color: var(--brand-600); background: var(--brand-50); }
.entity-chip--violet { color: var(--violet-500); background: #f5f3ff; }
.entity-chip--orange { color: #b45309; background: #fffbeb; }
.entity-chip--slate { color: var(--text-secondary); background: var(--surface-soft); }

.relation-list {
  display: grid;
  gap: 8px;
}

.relation-item {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
}

.relation-item__label {
  color: var(--text-tertiary);
  font-size: 11px;
}

.is-spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@media (max-width: 1280px) {
  .vault-layout {
    grid-template-columns: 200px minmax(0, 1fr);
  }

  .vault-detail {
    grid-column: 1 / -1;
  }
}

@media (max-width: 900px) {
  .vault-layout {
    grid-template-columns: 1fr;
  }

  .vault-search {
    width: 100%;
  }
}
</style>
