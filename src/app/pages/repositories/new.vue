<script setup lang="ts">
const toast = useToast()
const { $api } = useNuxtApp()

const { currentUser } = useAuth()
const { stateAsCreate: state } = useRepositoryForm()

const { handleFetchError } = useErrorHandling()
const onSubmit = async (data: RepositoryCreateForm) => {
  const payload: RepositoryCreatePayload = {
    ...data,
    active: true,
  }
  try {
    await $api('/api/repositories', {
      method: 'POST',
      body: payload,
      onResponseError: ({ response }) => {
        switch (response.status) {
          case 400: {
            toast.add({
              title: $t('toast.error.validation.title'),
              description: $t('toast.error.validation.description'),
              color: 'error',
              icon: 'i-lucide-circle-x',
            })
            break
          }
          case 403: {
            showError({
              status: 403,
              statusText: 'Forbidden',
              message: $t('error-page.forbidden.repository-create'),
            })
            break
          }
          case 409: {
            toast.add({
              title: $t('toast.error.conflict.title'),
              description: $t('toast.error.conflict.description'),
              color: 'error',
              icon: 'i-lucide-circle-x',
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

    toast.add({
      title: $t('toast.success.created.title'),
      description: $t('toast.success.repository-created.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    await navigateTo('/repositories')
  }
  catch {
    // Already handled in onResponseError
  }
}

onMounted(() => {
  if (!currentUser.value?.isSystemAdmin) {
    showError({
      status: 403,
      statusText: 'Forbidden',
      message: $t('error-page.forbidden.repository-create'),
    })
  }
})
</script>

<template>
  <UPageHeader
    :title="$t('repository.new-title')"
    :description="$t('repository.new-description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div class="max-w-240 m-auto">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-2xl font-semibold">
            {{ $t('repository.details-title') }}
          </h2>
          <div />
        </div>
      </template>

      <RepositoryForm
        v-model="state"
        mode="new"
        @submit="(event) => onSubmit(event.data)"
        @cancel="() => navigateTo('/repositories')"
      />
    </UCard>
  </div>
</template>
