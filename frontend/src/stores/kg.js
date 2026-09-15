import { defineStore } from 'pinia'
import {
  getKgFiles,
  getKgFullGraph,
  getKgProcessResult,
  getKgProcessStatus,
  startKgProcess,
  uploadKgFile,
} from '@/utils/kgApi'

/** 知识图谱子系统共享状态：文件库、当前文件、图谱数据与处理状态。 */
export const useKgStore = defineStore('kg', {
  state: () => ({
    files: [],
    currentFile: undefined,
    graph: { nodes: [], edges: [] },
    processResult: undefined,
    processStatus: undefined,
    loading: false,
  }),
  getters: {
    filesWithContent: (state) => state.files.filter((file) => file.content_path && file.status !== 'created'),
    graphNodeCount: (state) => state.graph.nodes.length,
    graphEdgeCount: (state) => state.graph.edges.length,
  },
  actions: {
    async loadFiles({ silent = false } = {}) {
      if (!silent) this.loading = true
      try {
        const data = await getKgFiles()
        this.files = data?.files || []
        if (this.currentFile) {
          this.currentFile = this.files.find((item) => item.id === this.currentFile.id) || this.files[0]
        }
        return this.files
      } finally {
        if (!silent) this.loading = false
      }
    },
    selectFile(fileId) {
      if (!fileId) {
        this.currentFile = undefined
        return
      }
      this.currentFile = this.files.find((item) => item.id === fileId)
    },
    async upload(file, folderId = '') {
      const data = await uploadKgFile(file, folderId)
      await this.loadFiles()
      this.currentFile = this.files.find((item) => item.id === data.file_id)
      return this.currentFile
    },
    async process(fileId) {
      await startKgProcess(fileId)
      await this.refreshProcess(fileId)
      await this.loadFiles({ silent: true })
    },
    async refreshProcess(fileId, { silent = false } = {}) {
      const [status, result] = await Promise.all([
        getKgProcessStatus(fileId).catch((error) => {
          if (!silent) throw error
          return undefined
        }),
        getKgProcessResult(fileId).catch((error) => {
          if (!silent) throw error
          return undefined
        }),
      ])
      this.processStatus = status
      this.processResult = result
      return { status, result }
    },
    async loadGraph() {
      this.graph = (await getKgFullGraph()) || { nodes: [], edges: [] }
      return this.graph
    },
  },
})
