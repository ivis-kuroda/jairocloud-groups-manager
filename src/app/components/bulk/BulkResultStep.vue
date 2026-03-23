<script setup lang="ts">
const toast = useToast()

const properties = defineProps<{
  historyId: string
  taskId?: string
}>()

const { query, makePageInfo, makeIndicators } = useBulk()
const { handleFetchError } = useErrorHandling()
const { data: status, refresh: refreshStatus }
  = await useApiFetch<BulkProcessingStatus>(`/api/bulk/execute/status/${properties.taskId}`, {
    method: 'GET',
    lazy: true,
    onResponseError({ response }) {
      switch (response.status) {
        case 404: {
          break
        }
        default:{
          handleFetchError({ response })
          break
        }
      }
    },
  })

const { polling: { interval, maxAttempts } } = useAppConfig()
const isPolling = ref(false)
const pollExecuteStatus = async () => {
  isPolling.value = true
  for (let index = 0; index < maxAttempts; index++) {
    await refreshStatus()
    const st = (status.value?.status)
    if (st === 'SUCCESS') {
      isPolling.value = false
      return
    }
    if (st === 'FAILURE') {
      toast.add({
        title: $t('bulk.status.error'),
        description: $t('bulk.execute.failed'),
        color: 'error',
        icon: 'i-lucide-circle-x',
      })
      isPolling.value = false
      return
    }
    await new Promise(r => setTimeout(r, interval))
  }
  toast.add({
    title: $t('bulk.status.error'),
    description: $t('bulk.execute.timeout'),
    color: 'error',
    icon: 'i-lucide-circle-x',
  })
  isPolling.value = false
}

const { data: executeResult, refresh: refreshExecuteResult, status: getResultStatus }
  = await useApiFetch<ExecuteResults>(`/api/bulk/result/${properties.historyId}`, {
    method: 'GET',
    query,
    lazy: true,
    onResponseError({ response }) {
      switch (response.status) {
        case 403: {
          showError({
            status: 403,
            statusText: 'Forbidden',
            message: $t('error-page.forbidden.bulk-result'),
          })
          break
        }
        case 404: {
          showError({
            status: 404,
            statusText: 'Not Found',
            message: $t('error-page.not-found.bulk-result'),
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

onMounted(async () => {
  if (properties.taskId)
    await pollExecuteStatus()
  await refreshExecuteResult()
})

const indicators = computed(() => makeIndicators(executeResult.value))
const fileInfo = computed(() => executeResult.value!.fileInfo)
const pageInfo = computed(() => makePageInfo(executeResult))
</script>

<template>
  <div class="space-y-4">
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <NumberIndicator
        v-for="indicator in indicators"
        :key="indicator.key"
        :title="indicator.title"
        :icon="indicator.icon"
        :number="indicator.number"
        :color="indicator.color"
      />
    </div>

    <div class="flex items-center justify-between">
      <h3 class="text-lg font-semibold">
        {{ $t('bulk.upload-file-info') }}
      </h3>
    </div>

    <div class="grid grid-cols-2 gap-x-8 gap-y-3 text-sm">
      <div class="flex justify-between">
        <span class="text-muted">{{ $t('bulk.upload-file') }}:</span>
        <span class="font-medium">{{ fileInfo.fileName || '-' }}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-muted">{{ $t('bulk.start-at') }}:</span>
        <span class="font-medium">
          {{ fileInfo.startedAt ? new Date(fileInfo.startedAt).toLocaleString('ja-JP') : '-' }}
        </span>
      </div>
      <div class="flex justify-between">
        <span class="text-muted">{{ $t('bulk.operator') }}:</span>
        <span class="font-medium">{{ fileInfo.executedBy || '-' }}</span>
      </div>
      <div class="flex justify-between">
        <span class="text-muted">{{ $t('bulk.completed-at') }}:</span>
        <span class="font-medium">
          {{ fileInfo.completedAt ? new Date(fileInfo.completedAt).toLocaleString('ja-JP')
            : '-' }}
        </span>
      </div>
    </div>

    <BulkUserTable
      :data="executeResult!.results"
      :total-count="executeResult!.total"
      :page-info="pageInfo"
      :offset="executeResult!.offset"
      :title="$t('bulk.import-results')"
      :status="isPolling ? 'loading' : getResultStatus "
    />
  </div>
</template>
