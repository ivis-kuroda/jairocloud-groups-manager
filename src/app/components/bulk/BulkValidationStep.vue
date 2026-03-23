<script setup lang="ts">
import { UCheckbox, UIcon } from '#components'

const properties = defineProps<{ onPrevious?: () => void
  onNext?: (data: ExcuteResponse) => void }>()

const { $api } = useNuxtApp()
const toast = useToast()

const taskId = inject<Ref<string | undefined>>('taskId', ref(undefined))
const temporaryFileId = inject<Ref<string | undefined>>('temporaryFileId', ref(undefined))
const selectedRepository = inject<Ref<string | undefined>>('selectedRepository', ref(undefined))
const {
  query,
  selectedMissingUsers,
  selectedCount,
  toggleSelection,
} = useValidation({ taskId, selectedRepository })

const { makePageInfo, makeIndicators } = useBulk()
const { polling: { interval, maxAttempts } } = useAppConfig()
const { handleFetchError } = useErrorHandling()
const { data: status, refresh: refreshValidateStatus }
  = await useApiFetch<BulkProcessingStatus>(`/api/bulk/validate/status/${taskId.value}`,
    {
      method: 'GET',
      lazy: true,
      onResponseError({ response }) {
        switch (response.status) {
          case 404: {
            showError({
              status: 404,
              statusText: 'Not Found',
              message: $t('bulk.validation.fetch_failed'),
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
const isPolling = ref(false)
const pollValidationStatus = async () => {
  isPolling.value = true
  for (let index = 0; index < maxAttempts; index++) {
    await refreshValidateStatus()
    const st = (status.value?.status)
    if (st === 'SUCCESS') {
      isPolling.value = false
      return
    }
    if (st === 'FAILURE') {
      toast.add({
        title: $t('bulk.status.error'),
        description: $t('bulk.validation.failed'),
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
    description: $t('bulk.validation.timeout'),
    color: 'error',
    icon: 'i-lucide-circle-x',
  })
  isPolling.value = false
}

const { data: validationResults, refresh: refreshValidateResult, status: getResultStatus }
  = await useApiFetch<ValidationResults>(`/api/bulk/validate/result/${taskId.value}`, {
    method: 'GET',
    query,
    lazy: true,
    onResponseError({ response }) {
      switch (response.status) {
        case 400: {
          toast.add({
            title: $t('bulk.status.error'),
            description: $t('bulk.validation.failed'),
            color: 'error',
            icon: 'i-lucide-circle-x',
          })
          break
        }
        case 403: {
          showError({
            status: 403,
            statusText: 'Forbidden',
            message: $t('error-page.forbidden.bulk-edit'),
          })
          break
        }
        case 404: {
          showError({
            status: 404,
            statusText: 'Not Found',
            message: $t('error-page.not-found.bulk-validation'),
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

onMounted(async () => {
  await pollValidationStatus()
  refreshValidateResult()
})

const offset = computed(() => (validationResults.value?.offset ?? 1))
const canProceed = computed(() => validationResults.value?.summary.error === 0)
const totalCount = computed(() => validationResults.value?.total)
const indicators = makeIndicators(validationResults.value)
const pageInfo = computed(() => makePageInfo(validationResults))

const handleNext = async () => {
  if (!canProceed.value) return

  if (!taskId || !selectedRepository.value) {
    throw new Error('Missing required data')
  }
  try {
    const { taskId, historyId } = await $api<BulkProcessingStatus>(`/api/bulk/execute`, {
      method: 'POST',
      body: {
        tempFileId: temporaryFileId.value,
        repositoryId: selectedRepository.value,
        deleteUsers:
          Object.keys(selectedMissingUsers.value).filter(key => selectedMissingUsers.value[key]),
      } as ExcuteRequest,
      onResponseError({ response }) {
        switch (response.status) {
          case 400: {
            toast.add({
              title: $t('bulk.status.error'),
              description: $t('bulk.execute.failed'),
              color: 'error',
              icon: 'i-lucide-circle-x',
            })
            break
          }
          case 403: {
            showError({
              status: 403,
              statusText: 'Forbidden',
              message: $t('error-page.forbidden.bulk-edit'),
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
    if (historyId && taskId) {
      properties.onNext?.({ taskId, historyId })
    }
  }
  catch {
    // Already handled in onResponseError
  }
}

const handlePrevious = () => {
  properties.onPrevious?.()
}

const selectAllMissingUsers = () => {
  selectedMissingUsers.value = Object.fromEntries(
    validationResults.value?.missingUsers.map(user => [user.id, true]) ?? [],
  )
}

const deselectAllMissingUsers = () => {
  selectedMissingUsers.value = {}
}

const indicatorWrapper = useTemplateRef('indicatorWrapper')
const { isStuck } = useSticky(indicatorWrapper,
  { baseElementSelector: 'header', spaceRem: 1, fallbackPosition: 64 },
)
</script>

<template>
  <div class="space-y-6">
    <UAlert
      v-if="validationResults?.summary && validationResults.summary.error > 0"
      color="error" icon="i-lucide-alert-circle"
      :as="$t('bulk.validation.error')" :description="$t('bulk.validation.error-detail')"
    />

    <div
      ref="indicatorWrapper" :data-stuck="isStuck || undefined"
      :class="[
        'sticky top-[calc(var(--ui-header-height)+1rem)] z-10',
        'flex items-center justify-between gap-4 rounded group',
        'transition-all data-stuck:bg-default/25 data-stuck:backdrop-blur',
        'data-stuck:justify-start data-stuck:ring  data-stuck:ring-default',
      ]"
    >
      <NumberIndicator
        v-for="indicator in indicators" :key="indicator.key"
        :title="indicator.title" :icon="indicator.icon" :number="indicator.number"
        :color="indicator.color"
        :ui="{
          root: [
            'w-full',
            'group-data-stuck:w-fit', 'group-data-stuck:ring-0 group-data-stuck:bg-transparent',
          ],
          container: [
            'md:px-4 gap-4 md:gap-4',
            'group-data-stuck:p-2 group-data-stuck:gap-2 group-data-stuck:width-auto',
          ],
          wrapper: 'flex-3',
          body: 'group-data-stuck:flex group-data-stuck:gap-2',
          iconWrapper: 'flex-2',
          iconBody: 'transition-all p-1.5 size-10 group-data-stuck:p-1 group-data-stuck:size-8',
          icon: 'transition-all size-7 group-data-stuck:size-6',
          title: 'group-data-stuck:text-sm',
          description: 'group-data-stuck:text-sm',
        }"
      />
    </div>

    <BulkUserTable
      :data="validationResults?.results ?? []" :total-count="totalCount ?? 0"
      :page-info="pageInfo" :offset="offset"
      :title="$t('bulk.validation.results')" :status="isPolling ? 'loading' : getResultStatus"
    />

    <div v-if="validationResults?.missingUsers.length ?? 0 > 0" variant="outline">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2">
          <h3 class="font-semibold">
            {{ $t('bulk.missing_user') }} ({{ validationResults?.missingUsers.length ?? 0 }})
          </h3>
        </div>
        <div class="flex items-center gap-2">
          <UButton
            :label="$t('bulk.select_all')" size="xs" color="neutral" variant="outline"
            @click="selectAllMissingUsers"
          />
          <UButton
            :label="$t('bulk.deselect_all')" size="xs" color="neutral" variant="outline"
            @click="deselectAllMissingUsers"
          />
        </div>
      </div>
      <p class="text-sm text-muted">
        {{ $t('bulk.missing-user.select') }}
      </p>

      <UAlert
        v-if="selectedCount > 0" color="error" icon="i-lucide-alert-triangle"
        :title="$t('bulk.missing-user.confirm')"
        :description="
          $t('bulk.missing-user.confirm_desc', { count: selectedCount })
        "
        class="mb-4" variant="solid"
      />

      <div class="space-y-2">
        <div
          v-for="user in validationResults?.missingUsers" :key="user.id"
          class="flex items-center gap-3 p-3
            rounded-lg border cursor-pointer hover:bg-elevated/50 transition-colors"
          :class="selectedMissingUsers[user.id]
            ? 'border-error bg-error/5' : 'border-default'"
          @click="toggleSelection(user.id)"
        >
          <UCheckbox
            :model-value="selectedMissingUsers[user.id]"
            @update:model-value="toggleSelection(user.id)"
          />
          <div class="flex-1">
            <p class="font-medium">
              {{ user.name }}
            </p>
            <p class="text-sm text-muted font-mono">
              {{ user.eppn }}
            </p>
          </div>
          <div class="flex flex-col text-sm">
            <div v-for="group in user.groups" :key="group">
              <span class="font-mono text-sm">{{ group }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="flex justify-between">
      <UButton
        :label="$t('button.back')" color="neutral" variant="outline" icon="i-lucide-arrow-left"
        loading-auto @click="handlePrevious"
      />
      <UButton
        :label="$t('bulk.upload.execute')" icon="i-lucide-arrow-right" trailing
        loading-auto :disabled="!canProceed" @click="handleNext"
      >
        <template v-if="!canProceed" #trailing>
          <UTooltip :text="$t('bulk.validation.fix_error')">
            <UIcon name="i-lucide-alert-circle" class="size-4" />
          </UTooltip>
        </template>
      </UButton>
    </div>
  </div>
</template>
