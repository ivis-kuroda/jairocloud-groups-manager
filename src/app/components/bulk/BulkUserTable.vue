<script setup lang="ts">
defineProps<{
  data: EachResult[]
  totalCount: number
  title?: string
  pageInfo?: string
  offset?: number
  status: string
}>()

const { updateQuery, pageNumber, pageSize, makeStatusFilters, columns } = useBulk()
const { table: { pageSize: { bulks: pageOptions } } } = useAppConfig()

const filterSelects = makeStatusFilters()
</script>

<template>
  <div class="flex items-center justify-between mb-4">
    <div>
      <h3 class="text-lg font-semibold">
        {{ title }}
      </h3>
    </div>
    <div class="flex items-center gap-2">
      <USelectMenu
        v-for="filter in filterSelects"
        :key="filter.key"
        :items="filter.items" :multiple="filter.multiple"
        :search-input="false"
        :ui="{ base: 'w-40' }"
        :placeholder="$t('table.filter-button-label')"
        @update:model-value="filter.onUpdated"
      />
      <USelect
        v-model="pageSize" :items="pageOptions"
        class="w-24"
        @update:model-value="() => updateQuery(
          { l: pageSize, p: Math.ceil((offset ?? 1) / pageSize!) },
        )"
      />
    </div>
  </div>

  <UTable
    :data="data"
    :columns="columns"
    :loading="status === 'loading'"
    sticky
  >
    <template #empty>
      <UEmpty
        icon="i-lucide-search-x"
        :title="$t('bulk.no-results')"
      />
    </template>
  </UTable>

  <div class="flex items-center">
    <div class="flex items-center gap-4 flex-1">
      <span class="text-sm text-muted">
        {{ pageInfo }}
      </span>
    </div>

    <UPagination
      v-model:page="pageNumber"
      :items-per-page="pageSize"
      :total="totalCount"
      @update:page="(value) => updateQuery({ p: value })"
    />

    <div class="flex-1" />
  </div>
</template>
