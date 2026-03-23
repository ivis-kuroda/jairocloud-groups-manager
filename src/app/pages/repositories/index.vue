<script setup lang="ts">
const toast = useToast()
const { currentUser } = useAuth()
const tableView = ref(currentUser.value?.isSystemAdmin)

const {
  query, updateQuery, criteria, creationButtons, emptyActions,
  columns, columnNames, columnVisibility, makePageInfo,
} = useRepositoriesTable()

const { searchTerm, pageNumber, pageSize } = criteria

const table = useTemplateRef('table')
const {
  table: { pageSize: { repositories: pageOptions } },
  features: { repositories: { 'server-search': serverSearch } },
} = useAppConfig()
const serverQuery = computed(() => {
  if (serverSearch) return query.value

  const { q, l, ...remain } = query.value
  return {
    ...remain,
    l: -1,
  }
})
const { handleFetchError } = useErrorHandling()
const {
  data: searchResult, status, refresh,
} = useApiFetch<RepositoriesSearchResult>('/api/repositories', {
  method: 'GET',
  query: serverQuery,
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

const pageInfo = makePageInfo(searchResult)
</script>

<template>
  <UPageHeader
    :title="$t('repositories.table.title')"
    :description="$t('repositories.description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div class="flex justify-between items-center my-4">
    <div v-if="currentUser?.isSystemAdmin" class="flex space-x-2">
      <UButton
        v-for="(button, index) in creationButtons"
        :key="index"
        :icon="button.icon" :label="button.label"
        :to="button.to" :color="button.color" :variant="button.variant"
        :ui="{ base: 'gap-1' }"
      />
    </div>
    <div v-else />

    <UButton
      color="neutral" variant="soft"
      :label="tableView ? $t('table.switch-to-card-view') : $t('table.switch-to-table-view')"
      :ui="{ base: 'gap-1' }"
      :icon="tableView ? 'i-lucide-layout-grid' : 'i-lucide-list'"
      @click="tableView = !tableView"
    />
  </div>

  <div class="grid grid-cols-3 gap-4 my-4 h-8">
    <UInput
      v-model="searchTerm"
      :placeholder="
        serverSearch || tableView
          ? $t('repositories.table.search-placeholder')
          : $t('repositories.table.search-placeholder-service-name-only')
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
          v-if="tableView"
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

  <div v-if="tableView">
    <UTable
      ref="table"
      v-model:column-visibility="columnVisibility" v-model:global-filter="searchTerm"
      :loading="status === 'pending'"
      :data="searchResult?.resources" :columns="columns" :ui="{ root: 'mb-8' }"
    >
      <template #empty>
        <UEmpty
          :title="$t('repositories.table.no-repositories-title')"
          :description="$t('repositories.table.no-repositories-description')"
          :actions="emptyActions"
        />
      </template>
    </UTable>
  </div>
  <div v-else class="grid grid-cols-3 gap-4">
    <UPageCard
      v-for="
        item in searchResult?.resources.filter(
          repo => serverSearch
            || !searchTerm
            || repo.serviceName.toLowerCase().includes(searchTerm.toLowerCase()),
        )
      " :key="item.id"
      :ui="{ root: 'p-4 cursor-pointer', title: 'hover:underline' }"
    >
      <template #title>
        <ULink
          :to="`/repositories/${item.id}`" class="font-bold hover:underline"
          @click.stop
        >
          {{ item.serviceName }}
        </ULink>
      </template>

      <template #description>
        <p class="text-sm mb-1">
          {{ $t('repositories.url-label') }}
          <ULink
            v-if="item.serviceUrl"
            :to="item.serviceUrl" target="_blank" class="hover:underline" external
            @click.stop
          >
            {{ item.serviceUrl }}
            <UIcon name="i-lucide-external-link" size="3" class="size-3 shrink-0" />
          </ULink>
        </p>
        <p class="text-sm mb-1">
          {{ $t('repositories.entity-id-label') }} {{ item.entityIds?.[0] }}
        </p>
      </template>
    </UPageCard>

    <UEmpty
      v-if="!searchResult?.resources.length"
      :title="$t('repositories.table.no-repositories-title')"
      :description="$t('repositories.table.no-repositories-description')"
      :actions="emptyActions" :ui="{ root: 'col-span-3' }"
    />
  </div>

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
</template>
