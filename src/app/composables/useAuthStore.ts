/*
 * Copyright (C) 2026 National Institute of Informatics.
 */

import { defineStore } from 'pinia'

/**
 * Interface representing a logged-in user
 */
export interface LoginUser {
  id: string
  eppn: string
  userName: string
  isSystemAdmin: boolean
}

/**
 * Pinia store for managing authentication state
 */
export const useAuthStore = defineStore('auth', () => {
  const _isAuthenticated = ref(false)
  const _authChecked = ref(false)
  const _user = ref<LoginUser | undefined>(undefined)

  const isAuthenticated = computed(() => _isAuthenticated.value)
  const authChecked = computed(() => _authChecked.value)
  const currentUser = computed(() => _user.value as Readonly<LoginUser | undefined>)

  function setAuthenticated(status: boolean) {
    _isAuthenticated.value = status
  }

  function setUser(user?: LoginUser) {
    _user.value = user
    _isAuthenticated.value = !!user
    _authChecked.value = true
  }

  function setAuthChecked(checked: boolean) {
    _authChecked.value = checked
  }

  function unsetUser() {
    _user.value = undefined
    _isAuthenticated.value = false
    _authChecked.value = true
  }

  return {
    isAuthenticated,
    authChecked,
    currentUser,
    setAuthenticated,
    setUser,
    setAuthChecked,
    unsetUser,
  }
})
