/**
 * Composable for global search operations
 */

import type { CommandPaletteGroup, CommandPaletteItem } from '@nuxt/ui'

const useGlobalSearch = () => {
  const { t: $t } = useI18n()
  const { header: { globalSearch } } = useAppConfig()

  const searchTerm = ref('')
  const previousSearchTerm = ref('')
  const query = computed(() =>
    previousSearchTerm.value ? { q: previousSearchTerm.value, l: globalSearch.limit } : undefined,
  )

  const makeResultGroups = (result: GlobalSearchResults): CommandPaletteGroup[] => [
    {
      id: 'repositories',
      label: $t('header.global-search.matching', {
        searchTerm: previousSearchTerm.value,
        category: $t('repositories.title'),
      }),
      items: result.find(item => item.type === 'repositories')?.resources
        .map<CommandPaletteItem>(item => ({
          id: `repository-${item.id}`,
          label: item.serviceName,
          suffix: item.serviceUrl,
          icon: 'i-lucide-folder',
          to: `/repositories/${item.id}`,
        })) || [],
      ignoreFilter: true,
    },
    {
      id: 'groups',
      label: $t('header.global-search.matching', {
        searchTerm: previousSearchTerm.value,
        category: $t('groups.title'),
      }),
      items: result.find(item => item.type === 'groups')?.resources
        .map<CommandPaletteItem>(item => ({
          id: `group-${item.id}`,
          label: item.displayName,
          suffix: item.usersCount ? `${item.usersCount} users` : undefined,
          icon: 'i-lucide-users',
          to: `/groups/${item.id}`,
        })) || [],
      ignoreFilter: true,
    },
    {
      id: 'users',
      label: $t('header.global-search.matching', {
        searchTerm: previousSearchTerm.value,
        category: $t('users.title'),
      }),
      items: result.find(item => item.type === 'users')?.resources
        .map<CommandPaletteItem>(item => ({
          id: `user-${item.id}`,
          label: item.userName,
          description: item.eppns?.[0],
          icon: 'i-lucide-user',
          to: `/users/${item.id}`,
        })) || [],
      ignoreFilter: true,
    },
  ]

  return {
    searchTerm,
    previousSearchTerm,
    query,
    makeResultGroups,
  }
}

export { useGlobalSearch }
