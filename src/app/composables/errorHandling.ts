import type { FetchResponse } from 'ofetch'

export const createFetchErrorHandler = (
  $t: ReturnType<typeof useI18n>['t'],
) => {
  const route = useRoute()
  const toast = useToast()

  const { publicRoutes } = useAppConfig()
  const { checkout } = useAuth()

  return async ({ response }: { response: FetchResponse<unknown> }) => {
    const errorId = `error-${response.status}`
    if (toast.toasts.value.some(t => t.id === errorId)) return

    const baseToast = {
      id: errorId,
      color: 'error' as const,
      icon: 'i-lucide-circle-x',
    }

    switch (response.status) {
      case 400: {
        toast.add({
          ...baseToast,
          title: $t('toast.error.bad-request.title'),
          description: $t('toast.error.bad-request.description'),
        })
        break
      }
      case 401: {
        toast.add({
          ...baseToast,
          title: $t('toast.error.unauthorized.title'),
          description: $t('toast.error.unauthorized.description'),
        })
        if (!publicRoutes.has(route.path.replace(/\/$/, ''))) {
          const next = encodeURIComponent(route.fullPath.replace(/\/$/, ''))
          await checkout({ next })
        }
        break
      }
      case 403: {
        toast.add({
          ...baseToast,
          title: $t('toast.error.forbidden.title'),
          description: $t('toast.error.forbidden.description'),
        })
        break
      }
      case 404: {
        toast.add({
          ...baseToast,
          title: $t('toast.error.not-found.title'),
          description: $t('toast.error.not-found.description'),
        })
        break
      }
      case 502: {
        toast.add({
          ...baseToast,
          title: $t('toast.error.bad-gateway.title'),
          description: $t('toast.error.bad-gateway.description'),
        })
        break
      }
      case 503: {
        toast.add({
          ...baseToast,
          title: $t('toast.error.service-unavailable.title'),
          description: $t('toast.error.service-unavailable.description'),
        })
        break
      }
      default: {
        const defaultId = 'error-default'
        if (toast.toasts.value.some(t => t.id === defaultId)) return
        toast.add({
          ...baseToast,
          id: defaultId,
          title: $t('toast.error.server.title'),
          description: $t('toast.error.server.description'),
        })
        break
      }
    }
  }
}

const useErrorHandling = () => {
  const { t: $t } = useI18n()

  const handleFetchError = createFetchErrorHandler($t)

  return { handleFetchError }
}

export { useErrorHandling }
