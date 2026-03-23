<script setup lang="ts">
const toast = useToast()
const { $api } = useNuxtApp()

const { stateAsCreate: state } = useUserForm()
const { handleFetchError } = useErrorHandling()
const onSubmit = async (data: UserCreateForm) => {
  const { repositoryRoles, groups, ...remain } = data

  const payload: UserCreatePayload = {
    ...remain,
    repositoryRoles:
      remain.isSystemAdmin
        ? []
        : repositoryRoles.map(item =>
            ({ id: item.value!, userRole: item.userRole } as RepositoryRole),
          ),
    groups: groups.flatMap(item => item.value ? [{ id: item.value }] : []),
  }

  try {
    await $api('/api/users', {
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
              message: $t('error-page.forbidden.user-create'),
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
      description: $t('toast.success.user-created.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    await navigateTo('/users')
  }
  catch {
    // Already handled in onResponseError
  }
}
</script>

<template>
  <UPageHeader
    :title="$t('user.new-title')"
    :description="$t('user.new-description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div class="max-w-240 m-auto">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-2xl font-semibold">
            {{ $t('user.details-title') }}
          </h2>
          <div />
        </div>
      </template>

      <UserForm
        v-model="state" mode="new"
        @submit="(event) => onSubmit(event.data)"
        @cancel="() => navigateTo('/users')"
      />
    </UCard>
  </div>
</template>
