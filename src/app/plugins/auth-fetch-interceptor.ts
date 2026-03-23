/*
 * Copyright (C) 2026 National Institute of Informatics.
 */

/**
 * Nuxt plugin to intercept fetch requests for authentication handling
 */
export default defineNuxtPlugin(() => {
  const { $i18n } = useNuxtApp()
  const $t = $i18n.t.bind($i18n)

  const handleFetchError = createFetchErrorHandler($t)

  const { baseURL } = useAppConfig()
  const api = $fetch.create({
    baseURL,
    credentials: 'include',
    onResponseError: ({ response }) => handleFetchError({ response }),
  })

  return {
    provide: {
      api,
    },
  }
})
