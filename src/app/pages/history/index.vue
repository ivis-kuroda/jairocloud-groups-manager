<script setup lang="ts">
import type { TabsItem } from '@nuxt/ui'

const {
  query, makePageInfo, updateQuery,
  tab, uploadColumns, downloadColumns, isFileAvailable,
} = useHistory()

const childData = ref<DownloadApiModel>()
const { features: { history: { upload: fileUpload } } } = useAppConfig()

const tabItems = computed<TabsItem[]>(() => fileUpload
  ? [
      { label: $t('history.tab.download'), icon: 'i-lucide-download', slot: 'download',
        value: 'download' },
      { label: $t('history.tab.upload'), icon: 'i-lucide-upload', slot: 'upload', value: 'upload' },
    ]
  : [
      { label: $t('history.tab.download'), icon: 'i-lucide-download', slot: 'download',
        value: 'download' },
    ])

const { handleFetchError } = useErrorHandling()
const { data, execute, status } = useApiFetch<DownloadApiModel | UploadApiModel>(
  `/api/history/${tab.value}`, {
    method: 'GET',
    query,
    onResponseError: async ({ response }) => {
      handleFetchError({ response })
    },
    lazy: true,
  })
const pageInfo = computed(() => makePageInfo(data))
const offset = computed(() => (data.value?.offset ?? 1))
const activeTab = computed<'download' | 'upload'>({
  get() {
    return (query.value.tab) || 'download'
  },
  set(tab) {
    updateQuery({ tab: tab })
    execute()
  },
})

const toggleSort = () => {
  updateQuery({ d: query.value.d === 'asc' ? 'desc' : 'asc' })
}

const handleLoadMoreChildren = async (row: DownloadHistoryData) => {
  const { data } = await useApiFetch<DownloadApiModel>('/api/history/download', {
    method: 'GET',
    query: {
      i: [row.id],
    },
    onResponseError({ response }) {
      switch (response.status) {
        case 400: {
          showError({
            status: 400,
            statusText: 'Bad Request',
            message: $t('error-page.failed.load-more'),
          })
          break
        }
        default:{
          handleFetchError({ response })
          break
        }
      }
    },
  })
  childData.value = data.value
}
</script>

<template>
  <UPageHeader
    :title="$t('history.title')"
    :description="$t('history.description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-2' }"
  />
  <UTabs
    v-model="activeTab"
    :items="tabItems"
    class="w-full"
    variant="link"
    :ui="{ trigger: 'min-w-50' }"
  >
    <template #download>
      <div class="container mx-auto px-4  space-y-4">
        <HistoryFilter target="download" />

        <div>
          <HistoryTable
            key="download-table" :data="(data?.resources ?? []) as DownloadHistoryData[]"
            :total="data?.total ?? 0"
            :table-config="{ enableExpand: true, showStatus: false }"
            :file-availability-check="isFileAvailable"
            :page-info="pageInfo.value" :offset="offset"
            :child-data="childData?.resources ?? []"
            :columns="downloadColumns"
            :status="status"
            @sort-change="toggleSort"
            @load-more-children="handleLoadMoreChildren"
          />
        </div>
      </div>
    </template>

    <template #upload>
      <div class="container mx-auto px-4  space-y-4">
        <HistoryFilter target="upload" />

        <div>
          <HistoryTable
            key="upload-table" :data="(data?.resources ?? []) as UploadHistoryData[]"
            :total="data?.total ?? 0"
            :table-config="{ enableExpand: false, showStatus: true }"
            :page-info="pageInfo.value" :offset="offset"
            :columns="uploadColumns"
            :status="status"
            @sort-change="toggleSort"
          />
        </div>
      </div>
    </template>
  </UTabs>
</template>
