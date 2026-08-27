/*
 * Copyright (C) 2026 National Institute of Informatics.
 */

import type { RouteLocationNormalizedGeneric } from 'vue-router'

/**
 * Composable for managing authentication state and actions
 */
export function useAuth() {
  const { $api } = useNuxtApp()
  const { publicRoutes, loginRoute, loggedinRedirectRoute } = useAppConfig()

  const authStore = useAuthStore()
  const { isAuthenticated, authChecked, currentUser } = storeToRefs(authStore)

  const checkin = async ({
    to,
    from,
  }: {
    to: RouteLocationNormalizedGeneric
    from: RouteLocationNormalizedGeneric

  }) => {
    const next = encodeURIComponent(to.fullPath.replace(/\/$/, ''))
    const toPath = to.path.replace(/\/$/, '')
    const fromPath = from.path.replace(/\/$/, '')

    if (publicRoutes.has(toPath)) {
      return
    }

    if (!authChecked.value || fromPath === loginRoute) {
      try {
        const user = await $api<LoginUser>('/api/auth/check', { method: 'GET' })
        if (user.eppn) {
          authStore.setUser(user)
        }
        else {
          authStore.unsetUser()
        }
      }
      catch {
        authStore.unsetUser()
      }
    }

    if (isAuthenticated.value) {
      let { next: nextTo } = to.query
      if (Array.isArray(nextTo)) {
        nextTo = nextTo[0]
      }

      if (nextTo && !publicRoutes.has(nextTo as string)) {
        return navigateTo((decodeURIComponent(nextTo)) as string)
      }

      if (!toPath) {
        return navigateTo(loggedinRedirectRoute)
      }

      return
    }

    return navigateTo({ path: loginRoute, query: next ? { next } : {} })
  }

  const checkout = async ({ next }: { next?: string } = {}) => {
    authStore.unsetUser()
    return await navigateTo({ path: loginRoute, query: next ? { next } : {} })
  }

  const logout = async () => {
    try {
      await $api('/api/auth/logout', { method: 'GET' })
    }
    catch {
      // ignore errors
    }
    finally {
      await checkout()
    }
  }

  return {
    /** Indicates whether the user is authenticated */
    isAuthenticated,
    /** Indicates whether the authentication check has been completed */
    authChecked,
    /** Current user information */
    currentUser,
    /** Checks the authentication status and navigates accordingly */
    checkin,
    /** Clears the authentication state */
    checkout,
    /** Logs out the user and redirects to the login page */
    logout,
  }
}
