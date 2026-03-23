<script setup lang="ts">
import type { FormSubmitEvent } from '@nuxt/ui'

const toast = useToast()
const { $api } = useNuxtApp()

const { table: { pageSize: { groups: groupPageSize } } } = useAppConfig()
const {
  query, updateQuery, criteria, creationButtons, emptyActions,
  toggleSelection, selectedCount, getSelected, clearSelection, selectedUsersActions,
  columns, columnNames, columnVisibility,
  makeAttributeFilters, dateFilter: { dateRange, formattedDateRange }, makePageInfo, modals,
  isRoleFilterActive, isGroupFilterActive,
} = useUsersTable()

const { searchTerm, pageNumber, pageSize } = criteria

const table = useTemplateRef('table')
const { table: { pageSize: { users: pageOptions } },
  features: { users: { 'filter-by-last-modified': filterByLastModified,
    'filter-by-both-role-group': filterByBoth,
    'search-only-username': sercheOnlyUserName },
  repositories: { 'server-search': serverSearch } },
} = useAppConfig()

const { handleFetchError } = useErrorHandling()
const { data: searchResult, status, refresh } = useApiFetch<UsersSearchResult>('/api/users', {
  method: 'GET',
  query,
  onResponseError({ response }) {
    switch (response.status) {
      case 400: {
        toast.add({
          title: $t('toast.error.failed-search.title'),
          description: $t('toast.error.invalid-search-query.description'),
          color: 'error',
        })
        break
      }
      default: {
        handleFetchError({ response })
        break
      }
    }
  },
  lazy: true,
})
const offset = computed(() => (searchResult.value?.offset ?? 1))
emptyActions.value[0].onClick = () => refresh()

const {
  data: filterOptions, status: filterOptionsStatus,
} = useApiFetch<FilterOption[]>('/api/users/filter-options', {
  method: 'GET',
  onResponseError: ({ response }) => handleFetchError({ response }),
  lazy: true,
})

const isFilterOpen = ref(false)
const repositorySelect = useTemplateRef('repositorySelect')
const groupSelect = useTemplateRef('groupSelect')
const { repositoryFilter, roleFilter, groupFilter } = makeAttributeFilters(filterOptions, {
  repositorySelect: { ref: repositorySelect, url: '/api/repositories' },
  groupSelect: { ref: groupSelect, url: '/api/groups' },
})
const pageInfo = makePageInfo(searchResult)

const addForm = useTemplateRef('addForm')
const removeForm = useTemplateRef('removeForm')
const userOpState = reactive({
  groupId: undefined as string | undefined,
  users: [] as { id: string, userName: string }[],
})

const groupOpSelect = useTemplateRef('groupOpSelect')
const {
  items: groupItems,
  searchTerm: groupSearchTerm,
  status: groupSearchStatus,
  onOpen: onGroupOpen,
  setupInfiniteScroll: setupGroupScroll,
} = useSelectMenuInfiniteScroll<GroupSummary>({
  url: '/api/groups',
  limit: groupPageSize[0],
  transform: group => ({
    label: group.displayName,
    value: group.id,
  }),
})
setupGroupScroll(groupOpSelect)

const onAdd = async (event: FormSubmitEvent<typeof userOpState>) => {
  try {
    await $api(`/api/groups/${event.data.groupId}`, {
      method: 'PATCH',
      body: {
        operations: [
          {
            op: 'add',
            path: 'members',
            value: event.data.users.map(user => user.id),
          },
        ],
      },
      onResponseError: ({ response }) => {
        switch (response.status) {
          case 403: {
            showError({
              status: 403,
              statusText: 'Forbidden',
              message: $t('error-page.forbidden.group-member-edit'),
            })
            break
          }
          default: {
            handleFetchError({ response })
            break
          }
        }
      },
    })

    modals.add = false
    toast.add({
      title: $t('toast.success.updated.title'),
      description: $t('toast.success.user-updated.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    clearSelection()
    await refresh()

    userOpState.groupId = undefined
    userOpState.users = []
  }
  catch {
    // Already handled in onResponseError
  }
}

const onRemove = async (event: FormSubmitEvent<typeof userOpState>) => {
  try {
    await $api(`/api/groups/${event.data.groupId}`, {
      method: 'PATCH',
      body: {
        operations: [
          {
            op: 'remove',
            path: 'members',
            value: event.data.users.map(user => user.id),
          },
        ],
      },
      onResponseError: ({ response }) => {
        switch (response.status) {
          case 403: {
            showError({
              status: 403,
              statusText: 'Forbidden',
              message: $t('error-page.forbidden.group-member-edit'),
            })
            break
          }
          default: {
            handleFetchError({ response })
            break
          }
        }
      },
    })

    modals.remove = false
    toast.add({
      title: $t('toast.success.updated.title'),
      description: $t('toast.success.user-updated.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    clearSelection()
    await refresh()

    userOpState.groupId = undefined
    userOpState.users = []
  }
  catch {
    // Already handled in onResponseError
  }
}
</script>

<template>
  <UPageHeader
    :title="$t('users.table.title')"
    :description="$t('users.description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div class="flex justify-between items-center my-4">
    <div class="flex space-x-2">
      <UButton
        v-for="(button, index) in creationButtons"
        :key="index"
        :icon="button.icon" :label="button.label"
        :to="button.to" :color="button.color" :variant="button.variant"
        :ui="{ base: 'gap-1' }"
      />
    </div>

    <UChip
      :text="selectedCount"
      :ui="{
        base: 'h-4 min-w-4 text-[12px]' + (selectedCount ? ' visible' : ' invisible'),
      }"
    >
      <UDropdownMenu :items="selectedUsersActions" :content="{ align: 'end' }">
        <UButton
          icon="i-lucide-wand" color="neutral" variant="outline"
          :ui="{ base: 'gap-1' }"
        />
      </UDropdownMenu>
    </UChip>
  </div>

  <div class="grid grid-cols-3 gap-4 my-4 h-8">
    <UInput
      v-model="searchTerm"
      :placeholder="
        sercheOnlyUserName
          ? $t('users.table.search-placeholder-username-only')
          : $t('users.table.search-placeholder')
      "
      icon="i-lucide-search" :ui="{ trailing: 'pe-1.5' }"
      @keydown.enter="() => updateQuery({ q: searchTerm, p: 1 })"
    >
      <template #trailing>
        <UButton
          variant="ghost" color="neutral"
          :ui="{ base: 'font-normal cursor-pointer p-1' }"
          @click="() => updateQuery({ q: searchTerm, p: 1 })"
        >
          <UKbd value="enter" />
        </UButton>
      </template>
    </UInput>

    <div class="col-span-2 flex gap-4">
      <UButton
        :label="$t('table.filter-button-label')"
        color="neutral" variant="outline" icon="i-lucide-filter"
        :trailing-icon="isFilterOpen ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        @click="isFilterOpen = !isFilterOpen"
      />

      <div class="flex flex-1 justify-end items-center space-x-4">
        <div class="flex items-center">
          <label class="text-sm text-gray-600 mr-1">{{ $t('table.page-size-label') }}</label>
          <USelect
            v-model="pageSize" :items="pageOptions"
            class="w-24"
            @update:model-value="() => updateQuery(
              { l: pageSize, p: Math.ceil(offset / pageSize!) },
            )"
          />
        </div>

        <UDropdownMenu
          :items="
            table?.tableApi
              ?.getAllColumns()
              .filter((column) => column.getCanHide())
              .map((column) => ({
                label: columnNames[column.id as keyof typeof columnNames],
                type: 'checkbox' as const,
                checked: column.getIsVisible(),
                onUpdateChecked(checked: boolean) {
                  table?.tableApi?.getColumn(column.id)?.toggleVisibility(!!checked)
                },
                onSelect(e: Event) {
                  e.preventDefault()
                },
              }))
          "
        >
          <UButton
            color="neutral" variant="outline"
            trailing-icon="i-lucide-chevron-down" :label="$t('table.display-columns-label')"
          />
        </UDropdownMenu>
      </div>
    </div>
  </div>

  <UCollapsible
    v-model:open="isFilterOpen"
    :ui="{ root: 'mb-4', content: 'grid grid-cols-3 gap-4' }"
  >
    <template #content>
      <USelectMenu
        ref="repositorySelect"
        v-model:search-term="repositoryFilter.searchTerm.value"
        :ignore-filter="serverSearch"
        :placeholder="repositoryFilter.placeholder"
        :icon="repositoryFilter.icon" :items="repositoryFilter.items"
        :multiple="repositoryFilter.multiple" :loading="repositoryFilter.loading"
        @update:open="repositoryFilter.onOpen" @update:model-value="repositoryFilter.onUpdated"
      />
      <UPopover
        :mode="filterByBoth ? undefined : 'hover'"
        :content="{
          align: 'center',
          side: 'bottom',
        }"
      >
        <USelectMenu
          :search-input="false"
          :placeholder="roleFilter.placeholder"
          :icon="roleFilter.icon" :items="roleFilter.items"
          :multiple="roleFilter.multiple" :loading="filterOptionsStatus === 'pending'"
          :disabled="isGroupFilterActive && !filterByBoth"
          @update:model-value="roleFilter.onUpdated"
        />
        <template #content>
          <UAlert
            v-if="isGroupFilterActive && !filterByBoth"
            :title="$t('users.alert.filter-by-both-role-group-disabled')"
            color="warning" variant="soft" class="w-full" icon="i-lucide-triangle-alert"
          />
        </template>
      </UPopover>
      <UPopover
        :mode="filterByBoth ? undefined : 'hover'"
        :content="{
          align: 'end',
          side: 'bottom',
        }"
      >
        <USelectMenu
          ref="groupSelect"
          v-model:search-term="groupFilter.searchTerm.value" ignore-filter
          :placeholder="groupFilter.placeholder"
          :icon="groupFilter.icon" :items="groupFilter.items"
          :multiple="groupFilter.multiple" :loading="groupFilter.loading"
          :disabled="isRoleFilterActive && !filterByBoth"
          @update:open="groupFilter.onOpen" @update:model-value="groupFilter.onUpdated"
        />
        <template #content>
          <UAlert
            v-if="isRoleFilterActive && !filterByBoth"
            :title="$t('users.alert.filter-by-both-role-group-disabled')"
            color="warning" variant="soft" class="w-full" icon="i-lucide-triangle-alert"
          />
        </template>
      </UPopover>

      <UPopover
        :mode="filterByLastModified ? undefined : 'hover'"
        :content="{
          align: 'start',
          side: 'bottom',
        }"
      >
        <UInput
          id="last-modefied" name="last-modefied"
          icon="i-lucide-calendar"
          :placeholder="$t('users.table.column.last-modified')"
          :model-value="formattedDateRange"
          :disabled="!filterByLastModified"
          :ui="{ base: `text-left ${dateRange.start ? '' : 'text-dimmed'}` }" readonly
        >
          <template #trailing>
            <UButton
              v-if="dateRange.start" variant="ghost"
              color="neutral" icon="i-lucide-x"
              :ui="{ base: 'text-dimmed p-0' }"
              @click="() => {
                dateRange = { start: undefined, end: undefined }
                updateQuery({ s: undefined, e: undefined, p: 1 })
              }"
            />
            <div v-else />
          </template>
        </UInput>
        <template #content>
          <UCalendar
            v-if="filterByLastModified"
            v-model="dateRange" :number-of-months="2" class="p-2" range
            @update:valid-model-value="() => updateQuery(
              { s: dateRange.start?.toString(), e: dateRange.end?.toString(), p: 1 },
            )"
          />
          <UAlert
            v-else
            :title="$t('users.alert.filter-by-last-modified-disabled')"
            color="warning" variant="soft" class="w-full" icon="i-lucide-triangle-alert"
          />
        </template>
      </UPopover>
    </template>
  </UCollapsible>

  <UTable
    ref="table"
    v-model:column-visibility="columnVisibility"
    :loading="status === 'pending'"
    :data="searchResult?.resources" :columns="columns" :ui="{ root: 'mb-8' }"
    @select="toggleSelection"
  >
    <template #empty>
      <UEmpty
        :title="$t('users.table.no-users-title')"
        :description="$t('users.table.no-users-description')"
        :actions="emptyActions"
      />
    </template>
  </UTable>

  <div class="flex justify-center mt-4">
    <div class="flex-1 text-gray-500 text-sm">
      {{ pageInfo }}
    </div>

    <div class="flex-2 flex justify-center">
      <UPagination
        v-model:page="pageNumber"
        :items-per-page="pageSize"
        :total="searchResult?.total"
        @update:page="(value) => updateQuery({ p: value })"
      />
    </div>

    <div class="flex-1" />
  </div>

  <UModal
    v-model:open="modals.add"
    :title="$t('modal.add-users-to-group.title')"
    :close="false" :ui="{ footer: 'justify-between', body: 'max-h-92 space-y-2' }"
  >
    <template #body>
      <UForm
        ref="addForm" :state="userOpState" :class="[
          'sticky -top-4 sm:-top-6 bg-default/75 backdrop-blur ',
          '-mx-4 sm:-mx-6 -mt-4 sm:-mt-6 mb-0 p-4 sm:p-6',
        ]"
        @submit="onAdd"
      >
        <UFormField
          name="groupId"
          :description="$t('modal.add-users-to-group.selection')"
          :ui="{ wrapper: 'mb-2' }"
        >
          <USelectMenu
            ref="groupOpSelect"
            v-model="userOpState.groupId"
            v-model:search-term="groupSearchTerm" ignore-filter clear
            :placeholder="$t('groups.title')"
            icon="i-lucide-users" :items="groupItems" value-key="value"
            :loading="groupSearchStatus === 'pending'"
            :ui="{ base: 'w-full' }"
            :content="{ side: 'bottom', align: 'start' }"
            @update:open="onGroupOpen"
          />
        </UFormField>
      </UForm>

      <div v-for="user in (userOpState.users = getSelected())" :key="user.id" class="group">
        <div class="text-lg font-semibold text-highlighted">
          {{ user.userName }}
        </div>
        <div class="text-xs text-muted mt-1">
          {{ user.id }}
        </div>

        <USeparator class="my-1 group-last:hidden" />
      </div>
    </template>

    <template #footer="{ close }">
      <UButton
        :label="$t('button.cancel')"
        icon="i-lucide-ban" color="neutral" variant="subtle"
        @click="() => { close(); userOpState.groupId = undefined; }"
      />
      <UButton
        :label="$t('button.add')"
        icon="i-lucide-user-plus" color="primary" variant="solid"
        :disabled="!userOpState.groupId"
        loading-auto
        @click="addForm!.submit()"
      />
    </template>
  </UModal>

  <UModal
    v-model:open="modals.remove"
    :title="$t('modal.remove-users-from-group.title')"
    :close="false" :ui="{ footer: 'justify-between', body: 'max-h-85 space-y-2' }"
  >
    <template #body>
      <UForm
        ref="removeForm" :state="userOpState" :class="[
          'sticky -top-4 sm:-top-6 bg-default/75 backdrop-blur ',
          '-mx-4 sm:-mx-6 -mt-4 sm:-mt-6 mb-0 p-4 sm:p-6',
        ]"
        @submit="onRemove"
      >
        <UFormField
          name="groupId"
          :description="$t('modal.remove-users-from-group.selection')"
          :ui="{ wrapper: 'mb-2' }"
        >
          <USelectMenu
            ref="groupOpSelect"
            v-model="userOpState.groupId"
            v-model:search-term="groupSearchTerm" ignore-filter clear
            :placeholder="$t('groups.title')"
            icon="i-lucide-users" :items="groupItems" value-key="value"
            :loading="groupSearchStatus === 'pending'"
            :ui="{ base: 'w-full' }"
            :content="{ side: 'bottom', align: 'start' }"
            @update:open="onGroupOpen"
          />
        </UFormField>
      </UForm>

      <div v-for="user in (userOpState.users = getSelected())" :key="user.id" class="group">
        <div class="text-lg font-semibold text-highlighted">
          {{ user.userName }}
        </div>
        <div class="text-xs text-muted mt-1">
          {{ user.id }}
        </div>

        <USeparator class="my-1 group-last:hidden" />
      </div>
    </template>

    <template #footer="{ close }">
      <UButton
        :label="$t('button.cancel')"
        icon="i-lucide-ban" color="neutral" variant="subtle"
        @click="() => { close(); userOpState.groupId = undefined; }"
      />
      <UButton
        :label="$t('button.remove')"
        icon="i-lucide-user-minus" color="error" variant="solid"
        :disabled="!userOpState.groupId"
        loading-auto
        @click="removeForm!.submit()"
      />
    </template>
  </UModal>
</template>
