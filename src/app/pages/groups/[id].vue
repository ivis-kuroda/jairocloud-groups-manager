<script setup lang="ts">
const route = useRoute()
const toast = useToast()
const { $api } = useNuxtApp()

const groupId = computed(() => route.params.id as string)
const mode = 'edit'

const { defaultData, defaultForm, state } = useGroupForm()

const { handleFetchError } = useErrorHandling()
const { data: group, refresh } = useApiFetch<GroupDetail>(
  `/api/groups/${groupId.value}`, {
    method: 'GET',
    default: () => defaultData,
    onResponseError({ response }) {
      switch (response.status) {
        case 403: {
          showError({
            status: 403,
            statusText: 'Forbidden',
            message: $t('error-page.forbidden.group-access'),
          })
          break
        }
        case 404: {
          showError({
            status: 404,
            message: $t('error-page.not-found.group'),
          })
          break
        }
        default: {
          handleFetchError({ response })
          break
        }
      }
    },
  },
)

const indicators = computed(() => [
  {
    title: $t('group.number-of-users'),
    count: group.value?.usersCount ?? defaultData.usersCount,
    color: 'primary' as const,
    icon: 'i-lucide-user',
    to: `/users?g=${groupId.value}`,
  },
])

watch(group, (newGroup: GroupDetail) => {
  if (!newGroup) return

  const created = newGroup.created ? new Date(newGroup.created) : undefined
  Object.assign(state, {
    id: newGroup.id,
    displayName: newGroup.displayName || defaultForm.displayName,
    description: newGroup.description || defaultForm.description,
    repository: newGroup.repository
      ? { value: newGroup.repository.id, label: newGroup.repository.serviceName }
      : structuredClone(defaultForm.repository),
    type: newGroup.type || defaultForm.type,
    public: newGroup.public ?? defaultForm.public,
    memberListVisibility: newGroup.memberListVisibility || defaultForm.memberListVisibility,
    created: created ? datetimeFormatter.format(created) : defaultForm.created,
  } as GroupUpdateForm)
}, { immediate: true })

const onSubmit = async (data: GroupUpdateForm) => {
  const { id, repository, type, created, ...payload } = data

  try {
    await $api(`/api/groups/${groupId.value}`, {
      method: 'PUT',
      body: payload as GroupUpdatePayload,
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
              message: $t('error-page.forbidden.group-edit'),
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
      title: $t('toast.success.updated.title'),
      description: $t('toast.success.group-updated.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    await navigateTo('/groups')
  }
  catch {
  // Already handled in onResponseError
  }
}

const onCancel = () => {
  refresh()

  if (import.meta.client) {
    nextTick(() => {
      window.scrollTo({ top: 0, behavior: 'smooth' })
    })
  }
}

const onDelete = async () => {
  try {
    await $api(`/api/groups/${groupId.value}`, {
      method: 'DELETE',
      onResponseError: ({ response }) => {
        switch (response.status) {
          case 403: {
            showError({
              status: 403,
              statusText: 'Forbidden',
              message: $t('error-page.forbidden.group-delete'),
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
      title: $t('toast.success.deleted.title'),
      description: $t('toast.success.group-deleted.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    await navigateTo('/groups')
  }
  catch {
    // Already handled in onResponseError
  }
}
</script>

<template>
  <UPageHeader
    :title="group?.displayName || ''"
    :description="$t('groups.description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div class="max-w-240 m-auto">
    <div class="grid grid-cols-2 gap-4 mb-6">
      <NumberIndicator
        v-for="(indicator, index) in indicators"
        :key="index" :title="indicator.title" :to="indicator.to"
        :number="indicator.count" :color="indicator.color" :icon="indicator.icon"
        :ui="{ container: 'lg:px-18 md:px-12' }"
      />
    </div>

    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-2xl font-semibold">
            {{ $t('group.details-title') }}
          </h2>

          <UModal
            :title="$t('modal.delete-group.title')"
            :description="$t('modal.delete-group.description')"
            :close="false" :ui="{ footer: 'justify-between' }"
          >
            <UButton
              :label="$t('button.delete')"
              icon="i-lucide-trash" variant="subtle" color="error"
              :disabled="group.type === 'role'"
            />

            <template #body>
              <div class="text-xl font-semibold text-highlighted">
                {{ group.displayName }}
              </div>
              <div class="text-xs text-muted mt-1">
                {{ group.id }}
              </div>
            </template>

            <template #footer="{ close }">
              <UButton
                :label="$t('button.cancel')"
                icon="i-lucide-ban" color="neutral" variant="subtle"
                @click="close"
              />
              <UButton
                :label="$t('button.delete')"
                icon="i-lucide-trash" color="error" variant="solid"
                :disabled="group.type === 'role'" loading-auto
                @click="async () => { await onDelete(); close(); }"
              />
            </template>
          </UModal>
        </div>
      </template>

      <GroupForm
        v-model="state" :mode="mode"
        @submit="(event) => onSubmit(event.data as GroupUpdateForm)" @cancel="onCancel"
      />
    </UCard>
  </div>
</template>
