/**
 * Composable for managing cache groups.
 */
import { UCheckbox, ULink } from '#components'

import type { Row, Table } from '@tanstack/table-core'
import type { DropdownMenuItem, SelectItem, TableColumn } from '@nuxt/ui'

const useCacheGroups = () => {
  const route = useRoute()
  const router = useRouter()

  const { t: $t } = useI18n()

  /** Reactive query object */
  const query = computed<CacheGroupsSearchQuery>(() => normalizeCacheGroupsQuery(route.query))
  /** Update query parameters and push to router */
  const updateQuery = (newQuery: Partial<CacheGroupsSearchQuery>) => {
    router.push({
      query: {
        ...route.query,
        ...newQuery,
      },
    })
  }

  const searchTerm = ref(query.value.q)
  const filter = ref(query.value.f)
  const pageNumber = ref(query.value.p)
  const pageSize = ref(query.value.l)

  const searchIdentityKey = computed(() => {
    const { p, l, ...filters } = query.value
    return JSON.stringify(filters)
  })

  const selectedMap = useState<Record<string, RepositorySummary | undefined>>(
    `selection-group-caches:${searchIdentityKey.value}`, () => ({}),
  )

  const selectedCount = computed(() => {
    return Object.values(selectedMap.value).filter(value => value !== undefined).length
  })
  const toggleSelection = (event: Event | undefined, row: Row<RepositoryCache>) => {
    selectedMap.value[row.original.id]
      = selectedMap.value[row.original.id] ? undefined : row.original
  }
  const toggleAllPageRows = (table: Table<RepositoryCache>) => {
    const pageRows = table.getRowModel().rows
    const allSelected = pageRows.every(row => selectedMap.value[row.original.id] !== undefined)

    if (allSelected) {
      for (const row of pageRows) {
        selectedMap.value[row.original.id] = undefined
      }
    }
    else {
      for (const row of pageRows) {
        selectedMap.value[row.original.id] = row.original
      }
    }
  }
  const isAllPageRowsSelected = (table: Table<RepositoryCache>) => {
    const pageRows = table.getRowModel().rows
    return pageRows.length > 0 && pageRows.every(
      row => selectedMap.value[row.original.id] !== undefined,
    )
  }
  const isSomePageRowsSelected = (table: Table<RepositoryCache>) => {
    const pageRows = table.getRowModel().rows
    const selectedRows = pageRows.filter(row => selectedMap.value[row.original.id] !== undefined)
    return selectedRows.length > 0 && selectedRows.length < pageRows.length
  }

  const getSelected = (): { id: string, serviceName: string, serviceUrl: string }[] => {
    return Object.entries(selectedMap.value)
      .filter(([_, service]) => service !== undefined)
      .map(([id, service]) => ({
        id, serviceName: service!.serviceName, serviceUrl: service!.serviceUrl,
      }))
  }
  const clearSelection = () => {
    selectedMap.value = {}
  }

  const modals = reactive<Record<GroupCacheUpdateAction, boolean>>({
    'all': false,
    'id-specified': false,
  })
  const isUpdating = ref(false)

  /** Column names with translations */
  const columnNames = computed(() => ({
    id: '#',
    serviceName: $t('group-caches.table.column.repository-name'),
    serviceUrl: $t('group-caches.table.column.repository-url'),
    updated: $t('group-caches.table.column.repository-updated-at'),
  }))

  const filterItems = computed<SelectItem[]>(() => [
    {
      label: $t('group-caches.status.cached'),
      value: 'e' as GroupCacheStatus,
    },
    {
      label: $t('group-caches.status.no-cached'),
      value: 'n' as GroupCacheStatus,
    },
  ])

  const selectedRepositoriesAction = computed<[DropdownMenuItem, ...DropdownMenuItem[]]>(() => [
    {
      type: 'label' as const,
      label: $t('repositories.all-repositories-actions'),
    },
    {
      icon: 'i-lucide-refresh-cw',
      label: $t('group-caches.button.update-all-repositories'),
      onSelect: () => modals.all = true,
    },
    {
      type: 'separator' as const,
    },
    {
      type: 'label' as const,
      label: $t('repositories.selected-repositories-actions'),
    },
    {
      icon: 'i-lucide-refresh-cw',
      label: $t('group-caches.button.update-selected-repositories'),
      onSelect: () => modals['id-specified'] = true,
      disabled: selectedCount.value === 0,
    },
  ])

  type CacheGroupsTableColumn = TableColumn<RepositoryCache>
  const columns = computed<CacheGroupsTableColumn[]>(() => [
    {
      id: 'select',
      header: ({ table }) =>
        h(UCheckbox, {
          'modelValue': isSomePageRowsSelected(table)
            ? 'indeterminate'
            : isAllPageRowsSelected(table),
          'onUpdate:modelValue': () => toggleAllPageRows(table),
          'ui': { root: 'py-0.5' },
          'disabled': isUpdating.value,
          'aria-label': 'Select all',
        }),
      cell: ({ row }) =>
        h(UCheckbox, {
          'modelValue': selectedMap.value[row.original.id] !== undefined,
          'onUpdate:modelValue': () => toggleSelection(undefined, row),
          'disabled': isUpdating.value,
          'aria-label': 'Select row',
        }),
      enableHiding: false,
    },
    {
      accessorKey: 'serviceName',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' }, columnNames.value.serviceName,
      ),
      cell: ({ row }) => h(
        ULink, {
          to: `/repositories/${row.original.id}`,
          class: 'font-bold hover:underline inline-flex items-center',
        }, () => [
          h('span', row.original.serviceName),
        ],

      ),
    },
    {
      accessorKey: 'url',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' }, columnNames.value.serviceUrl,
      ),
    },
    {
      accessorKey: 'updated',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' }, columnNames.value.updated,
      ),
      cell: ({ row }) =>
        row.original.updated
          ? datetimeFormatter.format(new Date(row.original.updated))
          : $t('group-caches.status.no-cached'),
    },
  ])

  const makePageInfo = (result: Ref<GroupCachesSearchResult | undefined>) => {
    return computed(() => {
      const start = result.value?.offset ?? 1
      const total = result.value?.total ?? 0
      const end = Math.min(start + pageSize.value!, total)
      const count = selectedCount.value

      if (count > 0)
        return `${start} - ${end} / ${total} (${$t('table.selected')} ${count})`
      return `${start} - ${end} / ${total}`
    })
  }

  return {
    /** Computed reference for the current query */
    query,
    /** Update query parameters and push to router */
    updateQuery,
    /** Criteria for filtering and sorting repositories */
    criteria: {
      /** Reactive object for the search term */
      searchTerm,
      /** Reactive object for the filter */
      filter,
      /** Reactive object for the current page number */
      pageNumber,
      /** Reactive object for the page size */
      pageSize,
    },
    /** Flag indicating if the data is being updated */
    isUpdating,
    /** Reactive object for the selected repositories */
    selectedMap,
    /** Computed reference for the count of selected repositories */
    selectedCount,
    /** Toggle the selection of a repository */
    toggleSelection,
    /** Get the selected repositories */
    getSelected,
    /** Clear all selection */
    clearSelection,
    /** Dropdown items of actions for the selected repositories */
    selectedRepositoriesAction,
    /** Items for filtering the repositories */
    filterItems,
    /** Column definitions for the table with translations */
    columns,
    /** Make indicator for the page information */
    makePageInfo,
    /** Reactive object for the state of modals */
    modals,
  }
}

export { useCacheGroups }
