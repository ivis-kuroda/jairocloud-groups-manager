<script setup lang="ts" generic="T extends DownloadHistoryData | UploadHistoryData">
import type { TableColumn } from '@nuxt/ui'

interface Properties<T> {
  data: T[]
  total: number
  tableConfig?: {
    enableExpand?: boolean
    showStatus?: boolean
  }
  columns: TableColumn<T, unknown>[]
  childData?: DownloadHistoryData[]
  pageInfo: string
  offset: number
  status: string
  fileAvailabilityCheck?: (data: DownloadHistoryData) => boolean
  loadMoreChildren?: (row: DownloadHistoryData) => void
}
defineProps<Properties<T>>()

const { pageSize, pageNumber, updateQuery } = useHistory()
const { table: { pageSize: { history: pageOptions } } } = useAppConfig()
const isRowExpandable = (row: DownloadHistoryData) => row.childrenCount && row.childrenCount > 0
</script>

<template>
  <div class="flex items-center justify-between">
    <h2 class="text-xl font-semibold">
      {{ $t('history.table-title') }}
    </h2>
    <div class="flex items-center gap-2">
      <label class="text-sm text-gray-600 mr-1">{{ $t('table.page-size-label') }}</label>
      <USelect
        v-model="pageSize" :items="pageOptions"
        class="w-24"
        @update:model-value="() => updateQuery(
          { l: pageSize, p: Math.ceil(offset / pageSize!) },
        )"
      />
    </div>
  </div>

  <UTable
    :data="data"
    :columns="columns"
    row-key="id"
    :loading="status === 'loading'"
    :expandable="isRowExpandable"
    @expand="loadMoreChildren"
  >
    <template #empty>
      <UEmpty
        icon="i-lucide-search-x"
        :title="$t('history.empty-data')"
      />
    </template>
    <template #expanded>
      <div v-if="tableConfig?.enableExpand && childData">
        <div
          v-for="child in childData"
          :key="child.id"
          class="pl-8 py-2 border-b last:border-b-0 bg-gray-50"
        >
          <div>{{ child.timestamp }} ({{ child.operator }})</div>
        </div>
      </div>
    </template>
  </UTable>

  <div class="grid grid-cols-3 items-center">
    <div class="flex-1 text-gray-500 text-sm">
      {{ pageInfo }}
    </div>
    <div class="flex justify-center">
      <UPagination
        v-model:page="pageNumber"
        :items-per-page="pageSize"
        :total="total"
        @update:page="(value) => updateQuery({ p: value })"
      />
    </div>
  </div>
</template>
