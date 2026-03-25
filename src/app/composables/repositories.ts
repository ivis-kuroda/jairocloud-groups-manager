/**
 * Composable for repository-related operations
 */

import { UButton, UDropdownMenu, UIcon, ULink } from '#components'

import type { ButtonProps, DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'

const { features: { repositories: { 'sort-columns': sortColumns } } } = useAppConfig()

/** Composable for managing repositories table */
const useRepositoriesTable = () => {
  const route = useRoute()

  const toast = useToast()
  const { t: $t } = useI18n()
  const { copy } = useClipboard()

  /** Reactive query object */
  const query = computed<RepositoriesSearchQuery>(() => normalizeRepositoriesQuery(route.query))
  /** Update query parameters and push to router */
  const updateQuery = async (newQuery: Partial<RepositoriesSearchQuery>) => {
    await navigateTo({
      query: {
        ...route.query,
        ...newQuery,
      },
    })
  }

  const searchTerm = ref(query.value.q)
  const spConnectorId = ref(query.value.i)
  const sortKey = computed(() => query.value.k)
  const sortOrder = computed(() => query.value.d)
  const pageNumber = ref(query.value.p)
  const pageSize = ref(query.value.l)

  /** Column names with translations */
  const columnNames = computed<Record<RepositoriesSortableKeys, string>>(() => ({
    id: '#',
    serviceName: $t('repositories.table.column.service-name'),
    serviceUrl: $t('repositories.table.column.service-url'),
    spConnectorId: $t('repositories.table.column.sp-connector-id'),
    entityIds: $t('repositories.table.column.entity-ids'),
  }))

  /** Returns action buttons for a repository entry */
  const creationButtons = computed<[ButtonProps, ...ButtonProps[]]>(() => [
    {
      icon: 'i-lucide-plus',
      label: $t('button.create-new'),
      to: '/repositories/new',
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

  type RepositoryTableColumn = TableColumn<RepositorySummary>
  const columns = computed<RepositoryTableColumn[]>(() => [
    {
      accessorKey: 'id',
      header: () => sortColumns
        ? sortableHeader('id')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.id),
      cell: ({ row }) => row.original.spConnectorId,
      enableGlobalFilter: false,
    },
    {
      accessorKey: 'serviceName',
      header: () => sortColumns
        ? sortableHeader('serviceName')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.serviceName),
      cell: ({ row }) => {
        const name: string = row.original.serviceName
        return h(ULink, {
          to: `/repositories/${row.original.id}`,
          class: 'font-bold hover:underline inline-flex items-center',
        }, () => [
          h('span', name),
        ])
      },
      enableHiding: false,
    },
    {
      accessorKey: 'serviceUrl',
      header: () => sortColumns
        ? sortableHeader('serviceUrl')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.serviceUrl),
      cell: ({ row }) => {
        const url: string = row.original.serviceUrl
        return url
          ? h(ULink, {
              to: url,
              target: '_blank',
              class: 'hover:underline inline-flex items-center gap-1 w-full',
            }, () => [
              h('span', { class: 'truncate' }, url),
              h(UIcon, { name: 'i-lucide-external-link', class: 'size-3 shrink-0' }),
            ])
          : undefined
      },
      meta: {
        class: {
          td: 'max-w-xs',
        },
      },
    },
    {
      accessorKey: 'entityIds',
      accessorFn: row => row.entityIds?.[0],
      header: () => sortColumns
        ? sortableHeader('entityIds')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.entityIds),
      cell: ({ row }) => row.original.entityIds?.[0],
      meta: {
        class: {
          td: 'max-w-xs truncate',
        },
      },
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
  ])

  function sortableHeader(key: RepositoriesSortableKeys) {
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

  function getActionItems(row: TableRow<RepositorySummary>): DropdownMenuItem[] {
    return [
      {
        type: 'label',
        label: $t('table.actions-label'),
      },
      {
        label: $t('repository.actions.copy-url'),
        onSelect() {
          copy(row.original.serviceUrl)

          toast.add({
            title: $t('toast.success.title'),
            description: $t('toast.success.copy-url.description'),
            color: 'success',
            icon: 'i-lucide-circle-check',
          })
        },
        icon: 'i-lucide-clipboard-copy',
      },
      {
        label: $t('repositories.actions.copy-sp-connector-id'),
        onSelect() {
          copy(row.original.spConnectorId!)

          toast.add({
            title: $t('toast.success.title'),
            description: $t('toast.success.copy-sp-connector-id.description'),
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
        to: `/repositories/${row.original.id}`,
        icon: 'i-lucide-eye',
      },
    ]
  }

  const columnVisibility = ref({ id: false })

  const makePageInfo = (result: Ref<RepositoriesSearchResult | undefined>) => {
    return computed(() => {
      const start = result.value?.offset ?? 1
      const total = result.value?.total ?? 0
      const end = Math.min(start + pageSize.value!, total)

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
      /** Reactive object for the SP connector ID */
      spConnectorId,
      /** Computed reference for the sort key */
      sortKey,
      /** Computed reference for the sort order */
      sortOrder,
      /** Reactive object for the current page number */
      pageNumber,
      /** Reactive object for the number of items per page */
      pageSize,
    },
    /** Button properties for creating new repositories */
    creationButtons,
    /** Button properties for actions when the list is empty */
    emptyActions,
    /** Column definitions for the table with translations */
    columns,
    /** Column names for the table with translations */
    columnNames,
    /** Reactive object for the visibility of columns */
    columnVisibility,
    /** Make indicator for the page information */
    makePageInfo,
  }
}

export { useRepositoriesTable }
