/*
 * Copyright (C) 2026 National Institute of Informatics.
 */

const useApiFetch = createUseFetch((currentOptions) => {
  const { baseURL } = useAppConfig()
  const { handleFetchError } = useErrorHandling()
  return {
    ...currentOptions,
    baseURL,
    onResponseError: ({ response }) => handleFetchError({ response }),
    credentials: 'include',
    server: false,
  }
})

export { useApiFetch }
