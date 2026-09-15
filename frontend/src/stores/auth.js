import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'
import { AUTH_ENABLED } from '@/config/app'

const GUEST_USER = { username: 'guest', full_name: '访客', role: 'admin' }

export const useAuthStore = defineStore('auth', () => {
  const token = ref(AUTH_ENABLED ? localStorage.getItem('token') || '' : 'bypass')
  const user = ref(
    AUTH_ENABLED
      ? JSON.parse(localStorage.getItem('user') || 'null')
      : GUEST_USER
  )

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username, password) {
    const res = await api.post('/auth/login', { username, password })
    token.value = res.data.access_token
    user.value = res.data.user
    localStorage.setItem('token', token.value)
    localStorage.setItem('user', JSON.stringify(user.value))
    return res.data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, isAdmin, login, logout }
})
