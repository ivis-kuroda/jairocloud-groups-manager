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
 * Interface representing the authentication state
 */
interface AuthState {
  _isAuthenticated: boolean
  _authChecked: boolean
  _user?: LoginUser | undefined
}

/**
 * Pinia store for managing authentication state
 */
export const useAuthStore = defineStore('auth', {
  state: (): AuthState => ({
    _isAuthenticated: false,
    _authChecked: false,
    _user: undefined,
  }),

  getters: {
    isAuthenticated: state => computed(() => state._isAuthenticated),
    authChecked: state => computed(() => state._authChecked),
    currentUser: state => readonly(computed(() => state._user)),
  },

  actions: {
    setAuthenticated(status: boolean) {
      this._isAuthenticated = status
    },

    setUser(user?: LoginUser) {
      this._user = user
      this._isAuthenticated = !!user
      this._authChecked = true
    },

    setAuthChecked(checked: boolean) {
      this._authChecked = checked
    },

    unsetUser() {
      this._user = undefined
      this._isAuthenticated = false
      this._authChecked = true
    },
  },
})
