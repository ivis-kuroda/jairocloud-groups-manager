import { getLocalTimeZone, parseDate } from '@internationalized/date'

import { UBadge, UButton, UDropdownMenu } from '#components'

import type { Row } from '@tanstack/table-core'
import type { DropdownMenuItem, TableColumn } from '@nuxt/ui'
import type { DateRange } from 'reka-ui'

const useHistory = () => {
  const toast = useToast()
  const route = useRoute()
  const { t: $t } = useI18n()
  const { $api } = useNuxtApp()
  const { currentUser } = useAuth()

  const query = computed<HistoryQuery>(() => normalizeHistoryQuery(route.query))
  const updateQuery = async (newQuery: Partial<HistoryQuery>) => {
    await navigateTo({
      query: {
        ...route.query,
        ...newQuery,
      },
    })
  }
  const tab = ref(query.value.tab ?? 'download')
  const sortOrder = computed(() => query.value.d)
  const pageNumber = ref(query.value.p)
  const pageSize = ref(query.value.l)
  const totalItems = ref<number>(0)

  const isFileAvailable = (data: DownloadHistoryData): boolean => {
    return data.fileExists
  }

  const uploadColumns = computed<TableColumn<UploadHistoryData>[]>(() => [
    {
      accessorKey: 'timestamp',
      header: () => sortableHeader('timestamp'),
      cell: ({ row }) => {
        const timestamp = new Date(row.original.timestamp)
        return datetimeFormatter.format(timestamp)
      },
    },
    {
      accessorKey: 'operator',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.operator')),
      cell: ({ row }) => row.original.operator.userName,
    },
    { accessorKey: 'users',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.user-count')),
      cell: ({ row }) => row.original.userCount,
    },
    { accessorKey: 'groups',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.group-count')),
      cell: ({ row }) => row.original.groupCount,
    },
    { accessorKey: 'status',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.status')),
      cell: ({ row }) => {
        const status = row.original.status
        switch (status) {
          case 'S': {
            return h(UBadge, { color: 'primary', variant: 'solid' }, () => $t('history.success'))
          }
          case 'F': {
            return h(UBadge, { color: 'error', variant: 'solid' }, () => $t('history.failed'))
          }
          case 'P': {
            return h(UBadge, { color: 'warning', variant: 'solid' }, () => $t('history.progress'))
          }
        }
      },
    },
    { accessorKey: 'actions',
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
    },
  ])

  const downloadColumns = computed<TableColumn<DownloadHistoryData>[]>(() => [
    {
      id: 'expand',
      cell: ({ row }) =>
        h(UButton, {
          'color': 'neutral',
          'variant': 'ghost',
          'icon': 'i-lucide-chevron-down',
          'square': true,
          'aria-label': 'Expand',
          'ui': {
            leadingIcon: [
              'transition-transform',
              row.getIsExpanded() ? 'duration-200 rotate-180' : '',
            ],
          },
          'onClick': () => { row.toggleExpanded() },
        }),
    },
    {
      accessorKey: 'timestamp',
      header: () => sortableHeader('timestamp'),
      cell: ({ row }) => {
        const timestamp = new Date(row.original.timestamp)
        return datetimeFormatter.format(timestamp)
      },
    },
    {
      accessorKey: 'operator',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.operator')),
      cell: ({ row }) => {
        const name = row.original.operator.userName
        const childrenCount = row.original.childrenCount
        if (childrenCount && childrenCount > 0) {
          return h('span', { class: 'inline-flex items-center gap-1' }, [
            name,
            h(UBadge, {
              color: 'info',
              variant: 'soft',
              class: 'ml-1',
            }, () => $t('history.re-download-count', { count: childrenCount })),
          ])
        }
        return name
      },
    },
    { accessorKey: 'users',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.user-count')),
      cell: ({ row }) => row.original.userCount,
    },
    { accessorKey: 'groups',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.group-count')),
      cell: ({ row }) => row.original.groupCount,
    },
    { accessorKey: 're-download',
      header: () => h(
        'span', { class: 'text-xs text-default font-medium' },
        $t('history.re-download')),
      cell: ({ row }) => {
        const data = row.original
        return isFileAvailable(data)
          ? h(UButton, {
              color: 'primary',
              variant: 'outline',
              size: 'sm',
              onClick: async () => {
                try {
                  await $api(`/api/history/files/${data.fileId}`, { method: 'GET' })
                }
                catch {
                  toast.add({
                    title: $t('history.file_not_available'),
                    color: 'error',
                    icon: 'i-lucide-circle-x',
                  })
                }
              },
            }, () => $t('history.re-download'))
          : h('span', { class: 'text-xs text-error' }, $t('history.expired'))
      },
    },
    { accessorKey: 'actions',
      header: '',
      cell: ({ row }) => {
        if (!currentUser.value?.isSystemAdmin) {
          return
        }
        return h(
          'div',
          { class: 'text-right' },
          h(
            UDropdownMenu,
            {
              'content': { align: 'end' },
              'items': getDownloadActionItems(row),
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
        )
      },
    },
  ])

  function sortableHeader(key: 'timestamp') {
    const label = key === 'timestamp'
      ? (tab.value === 'download'
          ? $t('history.table.column.download-date')
          : $t('history.table.column.upload-date'))
      : ''
    const iconSet = {
      asc: 'i-lucide-arrow-down-0-1',
      desc: 'i-lucide-arrow-up-0-1',
      none: 'i-lucide-arrow-up-down',
    } as const

    type SortDirection = keyof typeof iconSet
    const sortDirection = (sortOrder.value as SortDirection | undefined) ?? 'desc'

    return h(UButton, {
      color: sortDirection ? 'primary' : 'neutral',
      variant: 'ghost',
      size: 'xs',
      label,
      icon: sortDirection ? iconSet[sortDirection] : iconSet.none,
      class: 'font-medium cursor-pointer',
      onClick() {
        if (sortDirection === 'asc') updateQuery({ d: 'desc' })
        else updateQuery({ d: 'asc' })
      },
    })
  }

  function getActionItems(
    row: Row<UploadHistoryData>,
  ): DropdownMenuItem[] {
    const items: DropdownMenuItem[] = [
      {
        label: row.original.public ? $t('history.private') : $t('history.public'),
        onSelect: async () => {
          const data = row.original
          const id = data.id
          const currentPublic = data.public
          const updatedPublic = await togglePublicStatus(id, currentPublic)
          if (typeof updatedPublic === 'boolean') {
            data.public = updatedPublic
          }
        },
      },
      {
        label: $t('history.show-detail'),
        onSelect: () => {
          const data = row.original
          navigateTo(`/bulk/${data.id}`)
        },
      },
    ]
    return currentUser.value?.isSystemAdmin ? items : items.slice(1)
  }
  function getDownloadActionItems(
    row: Row<DownloadHistoryData>,
  ): DropdownMenuItem[] {
    return [
      {
        label: row.original.public ? $t('history.private') : $t('history.public'),
        onSelect: async () => {
          const data = row.original
          const id = data.id
          const currentPublic = data.public
          const updatedPublic = await togglePublicStatus(id, currentPublic)
          if (typeof updatedPublic === 'boolean') {
            data.public = updatedPublic
          }
        },
      },
    ]
  }

  const togglePublicStatus = async (
    id: string,
    currentPublic: boolean,
  ) => {
    const body = { public: !currentPublic }
    try {
      const result
        = await $api<PublicStatusUpdateRequest>(`/api/history/${tab.value}/${id}/public-status`,
          {
            method: 'PUT',
            body,
          })
      return result.public
    }
    catch {
      toast.add({
        title: $t('history.toggle_public_status_failed'),
        color: 'error',
        icon: 'i-lucide-circle-x',
      })
    }
  }

  const makePageInfo = (searchResult: Ref<DownloadApiModel | UploadApiModel | undefined>) => {
    return computed(() => {
      const start = searchResult.value?.offset ?? 1
      const total = searchResult.value?.total ?? 0
      const end = Math.min(start + pageSize.value!, total)

      return `${start} - ${end} / ${total}`
    })
  }

  return {
    tab,
    uploadColumns,
    downloadColumns,
    totalItems,
    sortOrder,
    pageNumber,
    pageSize,
    query,
    makePageInfo,
    updateQuery,
    togglePublicStatus,
    isFileAvailable,
  }
}

const useHistoryFilter = () => {
  const {
    table: { pageSize: pageSizeConfig },
    features: { repositories: { 'server-search': serverSearch } },
  } = useAppConfig()
  const { t: $t } = useI18n()

  const { query, updateQuery, tab } = useHistory()
  const specifiedIds = ref(query.value.i)
  const specifiedRepos = ref(query.value.r)
  const specifiedGroups = ref(query.value.g)
  const specifiedUsers = ref(query.value.u)
  const specifiedOperators = ref(query.value.o)
  const startDate = ref(query.value.s)
  const endDate = ref(query.value.e)
  const isFiltered = computed(() =>
    !!(query.value.r || query.value.g || query.value.u || query.value.o
      || query.value.s || query.value.e),
  )

  type FilterArguments = {
    [key in 'repositorySelect' | 'groupSelect' | 'userSelect' | 'operatorSelect']: {
      ref: Ref<unknown>
      url: string
    }
  }
  const makeHistoryFilters = (
    data: Ref<FilterOption[] | undefined>,
    { repositorySelect, groupSelect, userSelect, operatorSelect }: FilterArguments,
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

    const {
      items: groupItems,
      searchTerm: groupSearchTerm,
      status: groupSearchStatus,
      onOpen: onGroupOpen,
      setupInfiniteScroll: setupGroupScroll,
    } = useSelectMenuInfiniteScroll<GroupSummary>({
      url: groupSelect.url,
      limit: pageSizeConfig.groups[0],
      transform: group => ({
        label: group.displayName,
        value: group.id,
      }),
    })
    setupGroupScroll(groupSelect.ref)

    const {
      items: userItems,
      searchTerm: userSearchTerm,
      status: userSearchStatus,
      onOpen: onUserOpen,
      setupInfiniteScroll: setupUserScroll,
    } = useSelectMenuInfiniteScroll<UserSummary>({
      url: userSelect.url,
      limit: pageSizeConfig.users[0],
      transform: user => ({
        label: user.userName,
        value: user.id,
      }),
    })
    setupUserScroll(userSelect.ref)

    const {
      items: operatorItems,
      searchTerm: operatorSearchTerm,
      status: operatorSearchStatus,
      onOpen: onOperatorOpen,
      setupInfiniteScroll: setupOperatorScroll,
    } = useSelectMenuInfiniteScroll<Pick<UserSummary, 'id' | 'userName'>>({
      url: operatorSelect.url,
      limit: pageSizeConfig.history[0],
      transform: operator => ({
        label: operator.userName,
        value: operator.id,
      }),
    })
    setupOperatorScroll(operatorSelect.ref)

    const options = computed(() => (
      Object.fromEntries(data.value?.map(option => [option.key, option]) ?? [],
      ) as Record<keyof HistoryQuery, FilterOption>
    ))

    const repositoryFilter = computed(() => ({
      key: 'repositorySelect' as const,
      placeholder: $t('repositories.title'),
      icon: 'i-lucide-folder',
      items: repositoryItems.value,
      multiple: options.value.r?.multiple ?? false,
      searchTerm: repoSearchTerm,
      searchInput: true,
      loading: repoSearchStatus.value === 'pending',
      onOpen: onRepoOpen,
      onUpdated: (values: unknown) => {
        updateQuery({ r: (values as { value: string }[]).map(v => v.value), p: 1 })
      },
    }))
    const groupFilter = computed(() => ({
      key: 'groupSelect' as const,
      placeholder: $t('groups.title'),
      icon: 'i-lucide-users',
      items: groupItems.value,
      multiple: options.value.g?.multiple ?? false,
      searchTerm: groupSearchTerm,
      searchInput: true,
      loading: groupSearchStatus.value === 'pending',
      onOpen: onGroupOpen,
      onUpdated: (values: unknown) => {
        updateQuery({ g: (values as { value: string }[]).map(v => v.value), p: 1 })
      },
    }))
    const userFilter = computed(() => ({
      key: 'userSelect' as const,
      placeholder: $t('users.title'),
      icon: 'i-lucide-user',
      items: userItems.value,
      multiple: options.value.u?.multiple ?? false,
      searchTerm: userSearchTerm,
      searchInput: true,
      loading: userSearchStatus.value === 'pending',
      onOpen: onUserOpen,
      onUpdated: (values: unknown) => {
        updateQuery({ u: (values as { value: string }[]).map(v => v.value), p: 1 })
      },
    }))
    const operatorFilter = computed(() => ({
      key: 'operatorSelect' as const,
      placeholder: $t('history.operator'),
      icon: 'i-lucide-user-check',
      items: operatorItems.value,
      multiple: options.value.o?.multiple ?? false,
      searchTerm: operatorSearchTerm,
      searchInput: true,
      loading: operatorSearchStatus.value === 'pending',
      onOpen: onOperatorOpen,
      onUpdated: (values: unknown) => {
        updateQuery({ o: (values as { value: string }[]).map(v => v.value), p: 1 })
      },
    }))

    return {
      repositoryFilter,
      groupFilter,
      userFilter,
      operatorFilter,
    }
  }
  const dateRange = shallowRef<DateRange>({
    start: startDate.value ? parseDate(startDate.value) : undefined,
    end: endDate.value ? parseDate(endDate.value) : undefined,
  })

  const formattedDateRange = computed(() => {
    if (!dateRange.value.start) return $t('history.date')
    const from = dateFormatter.format(dateRange.value.start.toDate(getLocalTimeZone()))
    const to = dateRange.value.end
      ? dateFormatter.format(dateRange.value.end.toDate(getLocalTimeZone()))
      : undefined

    return to ? `${from} - ${to}` : from
  })

  const targetLabel = computed(() =>
    tab.value === 'download' ? $t('history.target', 1) : $t('history.target', 2),
  )

  return {
    query,
    tab,
    isFiltered,
    updateQuery,
    criteria: {
      specifiedIds,
      specifiedRepos,
      specifiedGroups,
      specifiedUsers,
      specifiedOperators,
      startDate,
      endDate,
    },
    dateFilter: {
      dateRange,
      formattedDateRange,
    },
    targetLabel,
    makeHistoryFilters,
  }
}

export { useHistory, useHistoryFilter }
