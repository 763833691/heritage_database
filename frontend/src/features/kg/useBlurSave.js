import { onScopeDispose, ref, unref } from 'vue'

/**
 * Vue 版 `useBlurSave`。
 *
 * 在表单字段失焦或防抖到期时保存，并提供可直接绑定到 AutoSaveIndicator 的状态。
 *
 * @param {object} options
 * @param {boolean|import('vue').Ref<boolean>|(() => boolean)} [options.ready=true] 表单初始化完成后才允许保存
 * @param {() => boolean} options.hasChanges 返回 true 时才触发保存
 * @param {() => Promise<void>} options.save 实际保存逻辑，抛出的错误会交给 onError
 * @param {(error: unknown) => void} [options.onError]
 * @param {number} [options.debounceMs=300]
 * @returns {{ status: import('vue').Ref<'idle'|'saving'|'saved'|'error'>, saving: import('vue').Ref<boolean>, onBlurSave: () => void, scheduleSave: () => void, runSave: () => Promise<void> }}
 */
export function useBlurSave({ ready = true, hasChanges, save, onError, debounceMs = 300 } = {}) {
  const status = ref('idle')
  const saving = ref(false)

  let debounceTimer = null
  let fadeTimer = null
  let savingNow = false

  function clearTimers() {
    if (debounceTimer !== null) {
      clearTimeout(debounceTimer)
      debounceTimer = null
    }
    if (fadeTimer !== null) {
      clearTimeout(fadeTimer)
      fadeTimer = null
    }
  }

  onScopeDispose(clearTimers)

  function isReady() {
    if (typeof ready === 'function') return Boolean(ready())
    return Boolean(unref(ready))
  }

  async function runSave() {
    if (!isReady() || savingNow) return
    if (!hasChanges()) return

    savingNow = true
    saving.value = true
    status.value = 'saving'
    try {
      await save()
      status.value = 'saved'
      if (fadeTimer !== null) clearTimeout(fadeTimer)
      fadeTimer = setTimeout(() => {
        status.value = 'idle'
      }, 2500)
    } catch (error) {
      status.value = 'error'
      if (onError) onError(error)
    } finally {
      savingNow = false
      saving.value = false
    }
  }

  function onBlurSave() {
    void runSave()
  }

  function scheduleSave() {
    if (debounceTimer !== null) clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => {
      void runSave()
    }, debounceMs)
  }

  return { status, saving, onBlurSave, scheduleSave, runSave }
}
