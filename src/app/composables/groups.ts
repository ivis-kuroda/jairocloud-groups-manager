/**
 * Composable for group-related operations
 */

import { UButton, UCheckbox, UDropdownMenu, ULink } from '#components'

import type { Row, Table } from '@tanstack/table-core'
import type { ButtonProps, DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'

/** Composable for managing groups table */
const useGroupsTable = () => {
  const route = useRoute()

  const toast = useToast()
  const { t: $t } = useI18n()
  const { copy } = useClipboard()

  const {
    table: { pageSize: pageSizeConfig },
    features: { groups: { 'sort-columns': sortColumns },
      repositories: { 'server-search': serverSearch } },
  } = useAppConfig()

  const query = computed<GroupsSearchQuery>(() => normalizeGroupsQuery(route.query))
  const updateQuery = async (newQuery: Partial<GroupsSearchQuery>) => {
    await navigateTo({
      query: {
        ...route.query,
        ...newQuery,
      },
    })
  }

  const searchTerm = ref(query.value.q)
  const sortKey = computed(() => query.value.k)
  const sortOrder = computed(() => query.value.d)
  const pageNumber = ref(query.value.p)
  const pageSize = ref(query.value.l)

  const searchIdentityKey = computed(() => {
    // exclude pagination and sorting parameters
    const { k, d, p, l, ...filters } = query.value
    return JSON.stringify(filters)
  })

  const selectedMap = useState<Record<string, string | undefined>>(
    `selection-groups:${searchIdentityKey.value}`, () => ({}),
  )

  const selectedCount = computed(() => {
    return Object.values(selectedMap.value).filter(value => value !== undefined).length
  })
  /** Toggle the selection of a group */
  const toggleSelection = (event: Event | undefined, row: Row<GroupSummary>) => {
    selectedMap.value[row.original.id]
      = selectedMap.value[row.original.id] ? undefined : row.original.displayName
  }
  const toggleAllPageRows = (table: Table<GroupSummary>) => {
    const pageRows = table.getRowModel().rows
    const allSelected = pageRows.every(row => selectedMap.value[row.original.id] !== undefined)

    if (allSelected) {
      for (const row of pageRows) {
        selectedMap.value[row.original.id] = undefined
      }
    }
    else {
      for (const row of pageRows) {
        selectedMap.value[row.original.id] = row.original.displayName
      }
    }
  }
  const isAllPageRowsSelected = (table: Table<GroupSummary>) => {
    const pageRows = table.getRowModel().rows
    return pageRows.length > 0 && pageRows.every(
      row => selectedMap.value[row.original.id] !== undefined,
    )
  }
  const isSomePageRowsSelected = (table: Table<GroupSummary>) => {
    const pageRows = table.getRowModel().rows
    const selectedRows = pageRows.filter(row => selectedMap.value[row.original.id] !== undefined)
    return selectedRows.length > 0 && selectedRows.length < pageRows.length
  }

  const getSelected = (): { id: string, displayName: string }[] => {
    return Object.entries(selectedMap.value)
      .filter(([_, displayName]) => displayName !== undefined)
      .map(([id, displayName]) => ({ id, displayName: displayName! }))
  }
  const clearSelection = () => {
    selectedMap.value = {}
  }

  const modals = reactive({
    delete: false,
  })

  /** Column names with translations */
  const columnNames = computed<Record<keyof GroupSummary, string>>(() => ({
    id: '#',
    displayName: $t('groups.table.column.display-name'),
    public: $t('groups.table.column.public'),
    memberListVisibility: $t('groups.table.column.member-list-visibility'),
    usersCount: $t('groups.table.column.users-count'),
  }))

  const publicStatus = computed(() => ({
    true: $t('groups.table.cell.public.public'),
    false: $t('groups.table.cell.public.private'),
  }))

  const visibilityStatus = computed<Record<Visibility, string>>(() => ({
    Public: $t('groups.table.cell.visibility.public'),
    Private: $t('groups.table.cell.visibility.private'),
    Hidden: $t('groups.table.cell.visibility.hidden'),
  }))

  /** Returns action buttons for a group entity */
  const creationButtons = computed<[ButtonProps, ...ButtonProps[]]>(() => [
    {
      icon: 'i-lucide-plus',
      label: $t('button.create-new'),
      to: '/groups/new',
      color: 'primary',
      variant: 'solid',
    },
  ])

  /** Actions to display when the list is empty */
  const emptyActions = computed<[ButtonProps, ...ButtonProps[]]>(() => [
    {
      icon: 'i-lucide-refresh-cw',
      label: $t('button.reload'),
      color: 'neutral',
      variant: 'subtle',
      onClick: () => {}, // Placeholder for reload action
    },
  ])

  /** Actions for selected groups */
  const selectedGroupsActions = computed<[DropdownMenuItem, ...DropdownMenuItem[]]>(() => [
    {
      type: 'label' as const,
      label: $t('groups.selected-groups-actions'),
    },
    {
      icon: 'i-lucide-trash',
      label: $t('groups.delete-selected-button'),
      color: 'error',
      onSelect: () => modals.delete = true,
      disabled: selectedCount.value === 0,
    },
  ])

  type GroupsTableColumn = TableColumn<GroupSummary>
  const columns = computed<GroupsTableColumn[]>(() => [
    {
      id: 'select',
      header: ({ table }) =>
        h(UCheckbox, {
          'modelValue': isSomePageRowsSelected(table)
            ? 'indeterminate'
            : isAllPageRowsSelected(table),
          'onUpdate:modelValue': () => toggleAllPageRows(table),
          'aria-label': 'Select all',
        }),
      cell: ({ row }) =>
        h(UCheckbox, {
          'modelValue': selectedMap.value[row.original.id] !== undefined,
          'onUpdate:modelValue': () => toggleSelection(undefined, row),
          'aria-label': 'Select row',
        }),
      enableHiding: false,
    },
    {
      accessorKey: 'id',
      header: () => sortColumns
        ? sortableHeader('id')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.id),
    },
    {
      accessorKey: 'displayName',
      header: () => sortColumns
        ? sortableHeader('displayName')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.displayName),
      cell: ({ row }) => {
        const name: string = row.original.displayName
        return h(ULink, {
          to: `/groups/${row.original.id}`,
          class: 'font-bold hover:underline inline-flex items-center',
        }, () => [
          h('span', name),
        ])
      },
      enableHiding: false,
    },
    {
      accessorKey: 'public',
      header: () => sortColumns
        ? sortableHeader('public')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.public),
      cell: ({ row }) => (
        publicStatus.value[`${row.original.public}`]
      ),
    },
    {
      accessorKey: 'memberListVisibility',
      header: () => sortColumns
        ? sortableHeader('memberListVisibility')
        : h('span', { class: 'text-xs text-default font-medium' },
            columnNames.value.memberListVisibility),
      cell: ({ row }) => (
        visibilityStatus.value[row.original.memberListVisibility]
      ),
    },
    {
      accessorKey: 'usersCount',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' }, columnNames.value.usersCount,
      ),
      cell: ({ row }) => row.original.usersCount,
    },
    {
      id: 'actions',
      header: '',
      cell: ({ row }) =>
        h(
          'div',
          { class: 'text-right' },
          h(
            UDropdownMenu,
            {
              'content': { align: 'end' },
              'items': getActionItems(row),
              'aria-label': 'Actions dropdown',
            },
            () =>
              h(UButton, {
                'icon': 'i-lucide-ellipsis-vertical',
                'color': 'neutral',
                'variant': 'ghost',
                'size': 'sm',
                'class': 'ml-auto',
                'aria-label': 'Actions dropdown',
              }),
          ),
        ),
      enableHiding: false,
    },
  ],
  )

  function sortableHeader(key: GroupsSortableKeys) {
    const label = columnNames.value[key]
    const sortDirection = sortKey?.value === key ? sortOrder?.value : undefined
    const iconSet = {
      asc: 'i-lucide-arrow-down-a-z',
      desc: 'i-lucide-arrow-up-a-z',
      none: 'i-lucide-arrow-up-down',
    } as const

    return h(UButton, {
      color: sortDirection ? 'primary' : 'neutral',
      variant: 'ghost',
      size: 'xs',
      label,
      icon: sortDirection ? iconSet[sortDirection] : iconSet.none,
      class: 'font-medium cursor-pointer',
      onClick() {
        if (sortDirection === 'asc') updateQuery({ k: key, d: 'desc' }) // to desc
        else if (sortDirection === 'desc') updateQuery({ k: undefined, d: undefined }) // to default
        else updateQuery({ k: key, d: 'asc' }) // to asc
      },
    })
  }

  function getActionItems(row: TableRow<GroupSummary>): DropdownMenuItem[] {
    return [
      {
        type: 'label',
        label: $t('table.actions-label'),
      },
      {
        label: $t('groups.actions.copy-id'),
        onSelect() {
          copy(row.original.id)

          toast.add({
            title: $t('toast.success.title'),
            description: $t('toast.success.copy-group-id.description'),
            color: 'success',
            icon: 'i-lucide-circle-check',
          })
        },
        icon: 'i-lucide-clipboard-copy',
      },
      {
        type: 'separator',
      },
      {
        label: $t('table.actions.view-details'),
        to: `/groups/${row.original.id}`,
        icon: 'i-lucide-eye',
      },
      {
        label: $t('table.actions.delete'),
        onSelect: () => {},
        icon: 'i-lucide-trash',
        color: 'error',
      },
    ]
  }

  const columnVisibility = ref({ id: false })

  const makeAttributeFilters = (
    data: Ref<FilterOption[] | undefined>,
    {
      repositorySelect,
    }: { [key in 'repositorySelect']: { ref: Ref<unknown>, url: string } },
  ) => {
    const {
      items: repositoryItems,
      searchTerm: repoSearchTerm,
      status: repoSearchStatus,
      onOpen: onRepoOpen,
      setupInfiniteScroll: setupRepoScroll,
    } = useSelectMenuInfiniteScroll<RepositorySummary>({
      url: repositorySelect.url,
      limit: pageSizeConfig.repositories[0],
      server: serverSearch,
      transform: repository => ({
        label: repository.serviceName,
        value: repository.id,
      }),
    })
    setupRepoScroll(repositorySelect.ref)

    const options = computed(() => (
      Object.fromEntries(data.value?.map(option => [option.key, option]) ?? [],
      ) as Record<keyof GroupsSearchQuery, FilterOption>
    ))

    const repositoryFilter = computed(() => ({
      key: 'repositorySelect',
      placeholder: $t('repositories.title'),
      icon: 'i-lucide-folder',
      items: repositoryItems.value,
      multiple: options.value.r.multiple ?? false,
      searchTerm: repoSearchTerm,
      loading: repoSearchStatus.value === 'pending',
      onOpen: onRepoOpen,
      onUpdated: (values: unknown) => {
        updateQuery({ r: (values as { value: string }[]).map(v => v.value), p: 1 })
      },
    }))

    const filters = computed(() => [
      {
        key: 's',
        placeholder: $t('groups.table.column.public'),
        icon: '',
        items: options.value.s.items?.map(item => ({
          value: item.value,
          label: publicStatus.value[(item.value as 0 | 1 | undefined) === 0 ? 'true' : 'false'],
        })) ?? [],
        multiple: options.value.s.multiple ?? false,
        searchInput: false,
        onUpdated: (values: unknown) => {
          updateQuery({ s: (values as { value: 0 | 1 | undefined }).value, p: 1 })
        },
      },
      {
        key: 'v',
        placeholder: $t('groups.table.column.member-list-visibility'),
        icon: '',
        items: options.value.v.items?.map((item) => {
          const v = (item.value as 0 | 1 | 2 | undefined) === 0
            ? 'Public'
            : (item.value === 1 ? 'Private' : 'Hidden')

          return {
            value: item.value,
            label: visibilityStatus.value[v] }
        }) ?? [],
        multiple: options.value.v.multiple ?? false,
        searchInput: false,
        onUpdated: (values: unknown) => {
          updateQuery({ v: (values as { value: 0 | 1 | 2 | undefined }).value, p: 1 })
        },
      },
    ])

    return { repositoryFilter, filters }
  }

  const makePageInfo = (result: Ref<GroupsSearchResult | undefined>) => {
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
    /** Criteria for filtering and sorting groups */
    criteria: {
      /** Reactive object for the search term */
      searchTerm,
      /** Computed reference for the sort key */
      sortKey,
      /** Computed reference for the sort order */
      sortOrder,
      /** Reactive object for the current page number */
      pageNumber,
      /** Reactive object for the page size */
      pageSize,
    },
    /** Column names for the table with translations */
    columnNames,
    /** Reactive object for the selected groups */
    selectedMap,
    /** Computed reference for the count of selected groups */
    selectedCount,
    /** Toggle selection of a group */
    toggleSelection,
    /** Get selected groups as an array of id and displayName */
    getSelected,
    /** Clear all selections */
    clearSelection,
    /** Dropdown items of actions for the selected groups */
    selectedGroupsActions,
    /** Button properties for creating a new group */
    creationButtons,
    /** Button properties for empty actions */
    emptyActions,
    /** Column definitions for the table with translations */
    columns,
    /** Reactive object for the visibility of columns */
    columnVisibility,
    /** Make attribute filters for table columns */
    makeAttributeFilters,
    /** Make indicator for the page information */
    makePageInfo,
    /** Reactive object for the state of modals */
    modals,
  }
}

export { useGroupsTable }
