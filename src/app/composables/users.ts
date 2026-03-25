/**
 * Composable for user-related operations
 */

import { DateFormatter, getLocalTimeZone, parseDate } from '@internationalized/date'
import { camelCase } from 'scule'

import { UButton, UCheckbox, UDropdownMenu, UIcon, ULink, UTooltip } from '#components'

import type { Row, Table } from '@tanstack/table-core'
import type { ButtonProps, DropdownMenuItem, TableColumn, TableRow } from '@nuxt/ui'
import type { DateRange } from 'reka-ui'

const useUsersTable = () => {
  const route = useRoute()

  const toast = useToast()
  const { t: $t } = useI18n()
  const { copy } = useClipboard()

  const {
    table: { pageSize: pageSizeConfig },
    features: { users: { 'sort-columns': sortColumns, 'file-upload': fileUpload },
      repositories: { 'server-search': serverSearch } },
  } = useAppConfig()

  /** Reactive query object */
  const query = computed<UsersSearchQuery>(() => normalizeUsersQuery(route.query))
  /** Update query parameters and push to router */
  const updateQuery = async (newQuery: Partial<UsersSearchQuery>) => {
    await navigateTo({
      query: {
        ...route.query,
        ...newQuery,
      },
    })
  }

  const searchTerm = ref(query.value.q)
  const specifiedIds = ref(query.value.i)
  const specifiedRepos = ref(query.value.r)
  const specifiedGroups = computed(() => query.value.g)
  const specifiedRoles = computed(() => query.value.a)
  const startDate = ref(query.value.s)
  const endDate = ref(query.value.e)
  const sortKey = computed(() => query.value.k)
  const sortOrder = computed(() => query.value.d)
  const pageNumber = ref(query.value.p)
  const pageSize = ref(query.value.l)

  const searchIdentityKey = computed(() => {
    const { k, d, p, l, ...filters } = query.value
    return JSON.stringify(filters)
  })

  const selectedMap = useState<Record<string, string | undefined>>(
    `selection-users:${searchIdentityKey.value}`, () => ({}),
  )

  /** Number of selected users */
  const selectedCount = computed(() => {
    return Object.values(selectedMap.value).filter(value => value !== undefined).length
  })
  const toggleSelection = (event: Event | undefined, row: Row<UserSummary>) => {
    selectedMap.value[row.original.id]
      = selectedMap.value[row.original.id] ? undefined : row.original.userName
  }
  const toggleAllPageRows = (table: Table<UserSummary>) => {
    const pageRows = table.getRowModel().rows
    const allSelected = pageRows.every(row => selectedMap.value[row.original.id] !== undefined)

    if (allSelected) {
      for (const row of pageRows) {
        selectedMap.value[row.original.id] = undefined
      }
    }
    else {
      for (const row of pageRows) {
        selectedMap.value[row.original.id] = row.original.userName
      }
    }
  }
  const isAllPageRowsSelected = (table: Table<UserSummary>) => {
    const pageRows = table.getRowModel().rows
    return pageRows.length > 0 && pageRows.every(
      row => selectedMap.value[row.original.id] !== undefined,
    )
  }
  const isSomePageRowsSelected = (table: Table<UserSummary>) => {
    const pageRows = table.getRowModel().rows
    const selectedRows = pageRows.filter(row => selectedMap.value[row.original.id] !== undefined)
    return selectedRows.length > 0 && selectedRows.length < pageRows.length
  }

  const getSelected = (): { id: string, userName: string }[] => {
    return Object.entries(selectedMap.value)
      .filter(([_, userName]) => userName !== undefined)
      .map(([id, userName]) => ({ id, userName: userName! }))
  }
  const clearSelection = () => {
    selectedMap.value = {}
  }

  const modals = reactive({
    add: false,
    remove: false,
  })

  /** Column names with translations */
  const columnNames = computed<Record<keyof UserSummary, string>>(() => ({
    id: '#',
    userName: $t('users.table.column.user-name'),
    role: $t('users.table.column.role'),
    emails: $t('users.table.column.emails'),
    eppns: $t('users.table.column.eppns'),
    lastModified: $t('users.table.column.last-modified'),
  }))

  /** Returns action buttons for a user entry */
  const creationButtons = computed<[ButtonProps, ...ButtonProps[]]>(() => fileUpload
    ? [
        {
          icon: 'i-lucide-user-plus',
          label: $t('button.create-new'),
          to: '/users/new',
          color: 'primary',
          variant: 'solid',
        },
        {
          icon: 'i-lucide-file-up',
          label: $t('button.upload'),
          to: '/bulk',
          color: 'primary',
          variant: 'solid',
        },
      ]
    : [
        {
          icon: 'i-lucide-user-plus',
          label: $t('button.create-new'),
          to: '/users/new',
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

  /** Actions for selected users */
  const selectedUsersActions = computed<[DropdownMenuItem, ...DropdownMenuItem[]]>(() => [
    {
      type: 'label' as const,
      label: $t('users.all-users-actions'),
    },
    {
      icon: 'i-lucide-download',
      label: $t('users.button.all-users-download'),
      onSelect() {}, // Placeholder for download action
    },
    {
      type: 'separator' as const,
    },
    {
      type: 'label' as const,
      label: $t('users.selected-users-actions'),
    },
    {
      icon: 'i-lucide-download',
      label: $t('users.button.selected-users-download'),
      onSelect() {}, // Placeholder for download action
      disabled: selectedCount.value === 0,
    },
    {
      icon: 'i-lucide-user-plus',
      label: $t('users.button.selected-users-add-to-group'),
      color: 'neutral',
      onSelect: () => modals.add = true,
      disabled: selectedCount.value === 0,
    },
    {
      icon: 'i-lucide-user-minus',
      label: $t('users.button.selected-users-remove-from-group'),
      color: 'error',
      onSelect: () => modals.remove = true,
      disabled: selectedCount.value === 0,
    },
  ])

  const badgableRoles = ['systemAdmin', 'repositoryAdmin', 'communityAdmin', 'contributor'] as const
  type BadgableRoles = (typeof badgableRoles)[number]
  const hasBadge = (role: UserRole | undefined): role is BadgableRoles => {
    const roles = new Set<string>(badgableRoles)
    return role ? roles.has(role) : false
  }

  type UserTableColumn = TableColumn<UserSummary>
  const columns = computed<UserTableColumn[]>(() => [
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
      accessorKey: 'userName',
      header: () => sortColumns
        ? sortableHeader('userName')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.userName),
      cell: ({ row }) => {
        const name = row.original.userName
        const role = camelCase(row.original.role!)
        const labelMap: Record<BadgableRoles, { label: string, icon: string, color: string }> = {
          systemAdmin: {
            label: $t('users.roles.system-admin'),
            icon: 'i-lucide-shield-check',
            color: 'error',
          },
          repositoryAdmin: {
            label: $t('users.roles.repository-admin'),
            icon: 'i-lucide-shield-check',
            color: 'secondary',
          },
          communityAdmin: {
            label: $t('users.roles.community-admin'),
            icon: 'i-lucide-badge-check',
            color: 'warning',
          },
          contributor: {
            label: $t('users.roles.contributor'),
            icon: 'i-lucide-user-check',
            color: 'neutral',
          },
        }

        return h(ULink,
          {
            to: (`/users/${row.original.id}`),
            class: 'font-bold inline-flex items-center group text-neutral space-x-2',
          },
          () => [
            hasBadge(role)
              ? h(UTooltip, {
                  text: labelMap[role].label,
                  arrow: true,
                }, () => h(
                  UIcon, {
                    name: labelMap[role].icon,
                    class: ['size-4.5', 'shrink-0', `text-${labelMap[role].color}`],
                  },
                ))
              : h('span', { class: 'size-4.5' }),
            h('span', { class: 'group-hover:underline' }, name),
          ].filter(Boolean),
        )
      },
      enableHiding: false,
    },
    {
      accessorKey: 'emails',
      header: () => sortColumns
        ? sortableHeader('emails')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.emails),
      cell: ({ row }) => row.original.emails?.[0] ?? '',
    },
    {
      accessorKey: 'eppns',
      header: () => sortColumns
        ? sortableHeader('eppns')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.eppns),
      cell: ({ row }) => row.original.eppns?.[0] ?? '',
    },
    {
      accessorKey: 'lastModified',
      header: () => sortColumns
        ? sortableHeader('lastModified')
        : h('span', { class: 'text-xs text-default font-medium' }, columnNames.value.lastModified),
      cell: ({ row }) =>
        row.original.lastModified
          ? datetimeFormatter.format(new Date(row.original.lastModified))
          : undefined,
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

  function sortableHeader(key: UsersSortableKeys) {
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

  function getActionItems(row: TableRow<UserSummary>): DropdownMenuItem[] {
    return [
      {
        type: 'label',
        label: $t('table.actions-label'),
      },
      {
        label: $t('user.actions.copy-id'),
        onSelect() {
          copy(row.original.id)

          toast.add({
            title: $t('toast.success.title'),
            description: $t('toast.success.copy-user-id.description'),
            color: 'success',
            icon: 'i-lucide-circle-check',
          })
        },
        icon: 'i-lucide-clipboard-copy',
      },
      {
        label: $t('user.actions.copy-eppn'),
        onSelect() {
          copy(row.original.eppns?.[0] || '')

          toast.add({
            title: $t('toast.success.title'),
            description: $t('toast.success.copy-user-eppn.description'),
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
        to: `/users/${row.original.id}`,
        icon: 'i-lucide-eye',
      },
    ]
  }

  const columnVisibility = ref({ id: false })

  const UserRoleNames = computed(() => ({
    systemAdmin: $t('users.roles.system-admin'),
    repositoryAdmin: $t('users.roles.repository-admin'),
    communityAdmin: $t('users.roles.community-admin'),
    contributor: $t('users.roles.contributor'),
    generalUser: $t('users.roles.general-user'),
  }))

  const makeAttributeFilters = (
    data: Ref<FilterOption[] | undefined>,
    {
      repositorySelect, groupSelect,
    }: { [key in 'repositorySelect' | 'groupSelect']: { ref: Ref<unknown>, url: string } },
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

    const options = computed(() => (
      Object.fromEntries(data.value?.map(option => [option.key, option]) ?? [],
      ) as Record<keyof UsersSearchQuery, FilterOption>
    ))

    const repositoryFilter = computed(() => ({
      key: 'repositorySelect' as const,
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
    const roleFilter = computed(() => ({
      key: 'roleSelect' as const,
      placeholder: $t('user.roles-title'),
      icon: 'i-lucide-shield-check',
      items: options.value.a.items?.map(item => ({
        value: item.value,
        label: UserRoleNames.value[item.label as UserRole],
      })) ?? [],
      multiple: options.value.a.multiple ?? false,
      onUpdated: (values: unknown) => {
        updateQuery({ a: (values as { value: UserRoleValue }[]).map(v => v.value), p: 1 })
      },
    }))
    const groupFilter = computed(() => ({
      key: 'groupSelect' as const,
      placeholder: $t('groups.title'),
      icon: 'i-lucide-users',
      items: groupItems.value,
      multiple: options.value.g.multiple ?? false,
      searchTerm: groupSearchTerm,
      loading: groupSearchStatus.value === 'pending',
      onOpen: onGroupOpen,
      onUpdated: (values: unknown) => {
        updateQuery({ g: (values as { value: string }[]).map(v => v.value), p: 1 })
      },
    }))

    return { repositoryFilter, roleFilter, groupFilter }
  }

  const dateRange = shallowRef<DateRange>({
    start: startDate.value ? parseDate(startDate.value) : undefined,
    end: endDate.value ? parseDate(endDate.value) : undefined,
  })
  const df = new DateFormatter('ja-JP', {
    dateStyle: 'medium',
  })
  const formattedDateRange = computed(() => {
    if (!dateRange.value.start) return $t('users.table.column.last-modified')

    const from = df.format(dateRange.value.start.toDate(getLocalTimeZone()))
    const to = dateRange.value.end
      ? df.format(dateRange.value.end.toDate(getLocalTimeZone()))
      : undefined

    return to ? `${from} - ${to}` : from
  })

  const makePageInfo = (result: Ref<UsersSearchResult | undefined>) => {
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

  const isRoleFilterActive = computed(() => {
    return specifiedRoles.value && specifiedRoles.value.length > 0
  })

  const isGroupFilterActive = computed(() => {
    return specifiedGroups.value && specifiedGroups.value.length > 0
  })

  return {
    /** Computed reference for the current query */
    query,
    /** Update query parameters and push to router */
    updateQuery,
    /** Criteria for filtering and sorting users */
    criteria: {
      /** Reactive object for the search term */
      searchTerm,
      /** Reactive object for the specified IDs */
      specifiedIds,
      /** Reactive object for the specified repositories */
      specifiedRepos,
      /** Reactive object for the specified groups */
      specifiedGroups,
      /** Reactive object for the specified roles */
      specifiedRoles,
      /** Reactive object for the start date */
      startDate,
      /** Reactive object for the end date */
      endDate,
      /** Computed reference for the sort key */
      sortKey,
      /** Computed reference for the sort order */
      sortOrder,
      /** Reactive object for the current page number */
      pageNumber,
      /** Reactive object for the number of items per page */
      pageSize,
    },
    /** Button properties for creating a new user */
    creationButtons,
    /** Button properties for actions when the list is empty */
    emptyActions,
    /** Count of selected users */
    selectedCount,
    /** Toggle selection of a user */
    toggleSelection,
    /** Get selected users as an array of objects with id and userName */
    getSelected,
    /** Clear all selections */
    clearSelection,
    /** Dropdown items of actions for the selected users */
    selectedUsersActions,
    /** Column definitions for the table with translations */
    columns,
    /** Column names for the table with translations */
    columnNames,
    /** Reactive object for the visibility of columns */
    columnVisibility,
    /** Mapping of user role names with translations */
    UserRoleNames,
    /** Make attribute filters for table columns */
    makeAttributeFilters,
    /** Date range for filtering */
    dateFilter: {
      /** Reactive object for the date range */
      dateRange,
      /** Computed reference for the formatted date range */
      formattedDateRange,
    },
    /** Make indicator for the page information */
    makePageInfo,
    /** Indicator for whether the group filter is active */
    isGroupFilterActive,
    /** Indicator for whether the role filter is active */
    isRoleFilterActive,
    /** Reactive object for the state of modals */
    modals,
  }
}

export { useUsersTable }
