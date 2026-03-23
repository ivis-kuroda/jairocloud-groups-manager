export const useSystemAdminVisibility = () => {
  const route = useRoute()
  const router = useRouter()

  const systemAdminVisible = computed({
    get: () => route.query.systemAdmin === 'true',
    set: (value: boolean) => {
      router.replace({
        query: {
          ...route.query,
          systemAdmin: value ? 'true' : 'false',
        },
      })
    },
  })

  return {
    systemAdminVisible,
  }
}
