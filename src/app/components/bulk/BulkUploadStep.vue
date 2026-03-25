<script setup lang="ts">
import type { FormError, FormErrorEvent, FormSubmitEvent } from '@nuxt/ui'

const emit = defineEmits<{
  next: [data: BulkProcessingStatus]
  error: [event: FormErrorEvent]
  update: [repositoryId: string]
}>()

const { $api } = useNuxtApp()
const { isProcessing } = useUserUpload()
const { table: { pageSize } } = useAppConfig()

const state = reactive<{
  repository: string | undefined
  file: File | undefined
}>({
  repository: undefined,
  file: undefined,
})

type Schema = typeof state

const validateFileFormat = (state: Partial<Schema>): FormError[] => {
  const errors: FormError[] = []
  if (!state.repository) {
    errors.push({ name: 'repository', message: $t('bulk.repository-required') })
  }

  if (state.file) {
    const fileName = state.file.name.toLowerCase()
    const allowedExtensions = ['.csv', '.tsv', '.xlsx']
    const allowedMimeTypes = [
      'text/csv',
      'text/tab-separated-values',
      'application/vnd.ms-excel',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    ]

    const hasValidExtension = allowedExtensions.some(extension => fileName.endsWith(extension))
    const hasValidMimeType = allowedMimeTypes.includes(state.file.type)

    if (!hasValidExtension && !hasValidMimeType) {
      errors.push({
        name: 'file',
        message: $t('bulk.file-format-error'),
      })
    }
  }
  else {
    errors.push({ name: 'file', message: $t('bulk.file-required') })
  }
  return errors
}

const { handleFetchError } = useErrorHandling()

const handleNext = async (event: FormSubmitEvent<Schema>) => {
  isProcessing.value = true

  const formData = new FormData()
  formData.append('bulk_file', event.data.file!)
  formData.append('repository_id', event.data.repository!)
  try {
    const data = await $api<BulkProcessingStatus>('/api/bulk/upload-file', {
      method: 'POST',
      body: formData,
      onResponseError({ response }) {
        switch (response.status) {
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
              message: $t('error-page.not-found.repository'),
            })
            break
          }
          default: {
            handleFetchError({ response })
            break
          }
        }
        isProcessing.value = false
      },
    })

    if (data) {
      emit('next', data)
    }
  }
  catch {
    // Already handled in onResponseError
  }
}

const repositorySelect = useTemplateRef('repositorySelect')
const {
  items: repositoryNames,
  searchTerm: repoSearchTerm,
  status: repoSearchStatus,
  onOpen: onRepoOpen,
  setupInfiniteScroll: setupRepoScroll,
} = useSelectMenuInfiniteScroll<RepositorySummary>({
  url: '/api/repositories',
  limit: pageSize.repositories[0],
  transform: (repository: RepositorySummary) => ({
    label: repository.serviceName,
    value: repository.id,
  }),
})
setupRepoScroll(repositorySelect)

const { handleFormError } = useFormError()
const onError = (event: FormErrorEvent) => {
  handleFormError(event)
  emit('error', event)
}
</script>

<template>
  <div class="space-y-4">
    <UAlert
      icon="i-lucide-info"
      color="warning"
      variant="subtle"
      :title="$t('bulk.about')"
      :ui="{
        title: 'text-black',
        description: 'text-black',
      }"
    >
      <template #description>
        <ul class="list-disc list-inside space-y-1 text-sm">
          <li>{{ $t('bulk.about-description') }}</li>
          <li>{{ $t('bulk.about-description2') }}</li>
          <li>{{ $t('bulk.about-description3') }}</li>
          <li>{{ $t('bulk.about-description4') }}</li>
        </ul>
      </template>
    </UAlert>
    <UForm
      class="space-y-6"
      :validate="validateFileFormat" :state="state"
      @submit="handleNext" @error="onError"
    >
      <UFormField
        :label="$t('bulk.select-repository')"
        name="repository"
      >
        <USelectMenu
          ref="repositorySelect"
          v-model="state.repository"
          :search-term="repoSearchTerm" value-key="value" size="xl"
          :placeholder="$t('group.placeholder.repository')"
          :items="repositoryNames" :loading="repoSearchStatus === 'pending'" ignore-filter
          :ui="{ base: 'w-full' }"
          @update:open="onRepoOpen" @update:model-value="emit('update', state.repository!)"
        />
      </UFormField>

      <UFormField
        :label="$t('bulk.upload-file')"
        name="file"
      >
        <UFileUpload
          v-model="state.file"
          accept=".csv,.tsv,.xlsx,text/csv,text/tab-separated-values,application/vnd.ms-excel,
          application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
          :label="$t('bulk.upload-field')"
          description="TSV, CSV, Excel"
          icon="i-lucide-file-up"
          layout="list"
          position="inside"
          color="primary"
        />
      </UFormField>

      <div class="flex justify-end">
        <UButton
          type="submit"
          :label="$t('button.next')"
          icon="i-lucide-arrow-right"
          trailing
          :loading="isProcessing"
        />
      </div>
    </UForm>
  </div>
</template>
