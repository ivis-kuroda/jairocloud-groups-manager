<script setup lang="ts">
const { features: { repositories: { 'server-search': serverSearch } } } = useAppConfig()

const {
  tab,
  criteria: {
    specifiedRepos,
    specifiedGroups,
    specifiedUsers,
    specifiedOperators,
  },
  dateFilter: {
    dateRange,
    formattedDateRange,
  },
  updateQuery,
  isFiltered,
  makeHistoryFilters,
} = useHistoryFilter()

const { handleFetchError } = useErrorHandling()

const {
  data: filterOptions,
} = useApiFetch<FilterOption[]>('/api/history/filter-options', {
  method: 'GET',
  onResponseError: ({ response }) => handleFetchError({ response }),
  lazy: true,
})
const repositorySelect = useTemplateRef('repositorySelect')
const groupSelect = useTemplateRef('groupSelect')
const userSelect = useTemplateRef('userSelect')
const operatorSelect = useTemplateRef('operatorSelect')
const {
  repositoryFilter, groupFilter, userFilter, operatorFilter,
} = makeHistoryFilters(filterOptions, {
  repositorySelect: { ref: repositorySelect, url: '/api/repositories' },
  groupSelect: { ref: groupSelect, url: '/api/groups' },
  userSelect: { ref: userSelect, url: '/api/users' },
  operatorSelect: {
    ref: operatorSelect,
    url: `/api/history/${tab.value}/filter-options/operators`,
  },
})
</script>

<template>
  <div class="flex items-center justify-between space-y-2">
    <h2 class="text-lg font-semibold">
      {{ $t('history.filter.title') }}
    </h2>
    <UButton
      :label="$t('history.reset')" icon="i-lucide-rotate-ccw" color="neutral" variant="ghost"
      size="xs" :disabled="!isFiltered"
      @click="() => {
        updateQuery({
          tab: tab,
          s: undefined,
          e: undefined,
          r: undefined,
          g: undefined,
          u: undefined,
          o: undefined,
          p: 1,
        })
        specifiedRepos = []
        specifiedGroups = []
        specifiedUsers = []
        specifiedOperators = []
        dateRange.start = undefined
        dateRange.end = undefined
      }"
    />
  </div>

  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
    <UPopover :popper="{ placement: 'bottom-start' }">
      <UInput
        icon="i-lucide-calendar"
        :model-value="formattedDateRange"
        readonly
        :ui="{ base: `text-left ${dateRange.start ? '' : 'text-dimmed'}` }"
        class="w-full"
      />
      <template #content>
        <UCalendar
          v-model="dateRange" :number-of-months="2" class="p-2" range
          @update:valid-model-value="() => updateQuery(
            { s: dateRange.start?.toString(), e: dateRange.end?.toString(), p: 1 },
          )"
        />
      </template>
    </UPopover>

    <USelectMenu
      ref="operatorSelect"
      v-model:search-term="operatorFilter.searchTerm.value" ignore-filter
      :placeholder="operatorFilter.placeholder"
      :icon="operatorFilter.icon" :items="operatorFilter.items"
      :multiple="operatorFilter.multiple" :loading="operatorFilter.loading" clear
      @update:open="operatorFilter.onOpen" @update:model-value="operatorFilter.onUpdated"
    />
  </div>

  <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mt-4">
    <USelectMenu
      ref="repositorySelect"
      v-model:search-term="repositoryFilter.searchTerm.value"
      :ignore-filter="serverSearch"
      :placeholder="repositoryFilter.placeholder"
      :icon="repositoryFilter.icon" :items="repositoryFilter.items"
      :multiple="repositoryFilter.multiple" :loading="repositoryFilter.loading" clear
      @update:open="repositoryFilter.onOpen" @update:model-value="repositoryFilter.onUpdated"
    />
    <USelectMenu
      ref="groupSelect"
      v-model:search-term="groupFilter.searchTerm.value" ignore-filter
      :placeholder="groupFilter.placeholder"
      :icon="groupFilter.icon" :items="groupFilter.items"
      :multiple="groupFilter.multiple" :loading="groupFilter.loading" clear
      @update:open="groupFilter.onOpen" @update:model-value="groupFilter.onUpdated"
    />
    <USelectMenu
      ref="userSelect"
      v-model:search-term="userFilter.searchTerm.value" ignore-filter
      :placeholder="userFilter.placeholder"
      :icon="userFilter.icon" :items="userFilter.items"
      :multiple="userFilter.multiple" :loading="userFilter.loading" clear
      @update:open="userFilter.onOpen" @update:model-value="userFilter.onUpdated"
    />
  </div>
</template>
