import type { Collections, ContentNavigationItem } from '@nuxt/content'

export const useNavigation = async () => {
  const route = useRoute()
  const { systemAdminVisible } = useSystemAdminVisibility()

  const collection = computed(() => {
    return route.path.split('/')
      .find(segment => segment.length > 0) as Exclude<keyof Collections, 'index'>
  })

  const { data: navigation } = await useAsyncData(
    `navigation-${collection.value}`,
    async () => {
      const navData = await queryCollectionNavigation(collection.value)
      const pages = navData?.find(item => item.path === `/${collection.value}`)?.children
        || navData || []

      if (collection.value !== 'manual') {
        return pages
      }

      const allPages = await queryCollection(collection.value).all()
      const pageMap = new Map(allPages.map(page => [page.path, page]))

      const enrichAndFilterPages = (items: ContentNavigationItem[]): ContentNavigationItem[] => {
        return items
          .map((navItem) => {
            const itemPath = (navItem._path as string) || navItem.path
            const pageData = pageMap.get(itemPath)
            const navFile = pageMap.get(`${itemPath}/.navigation`)
            const systemAdminOnly = pageData?.['system-admin-only']
              || navFile?.['system-admin-only']

            return {
              ...navItem,
              'system-admin-only': systemAdminOnly,
              'children': navItem.children ? enrichAndFilterPages(navItem.children) : undefined,
            }
          })
          .filter((page) => {
            if (page['system-admin-only'] && !systemAdminVisible.value) {
              return false
            }
            return true
          })
      }

      return enrichAndFilterPages(pages)
    },
    {
      watch: [collection, () => route.query.systemAdmin],
    },
  )

  return {
    collection,
    navigation,
  }
}
