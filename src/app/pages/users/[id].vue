<script setup lang="ts">
import { camelCase } from 'scule'

const route = useRoute()
const toast = useToast()
const { $api } = useNuxtApp()

const userId = computed(() => route.params.id as string)
const mode = computed<'view' | 'edit'>(() => 'view')

const { currentUser, logout } = useAuth()
const { defaultData, defaultForm, state } = useUserForm()
const isSelf = computed(() => currentUser.value?.id === userId.value)

const { handleFetchError } = useErrorHandling()
const { data: user, refresh } = useApiFetch<UserDetail>(
  `/api/users/${userId.value}`, {
    method: 'GET',
    default: () => defaultData,
    onResponseError({ response }) {
      switch (response.status) {
        case 403: {
          showError({
            status: 403,
            statusText: 'Forbidden',
            message: $t('error-page.forbidden.user-access'),
          })
          break
        }
        case 404: {
          showError({
            status: 404,
            message: $t('error-page.not-found.user'),
          })
          break
        }
        default:{
          handleFetchError({ response })
          break
        }
      }
    },
  },
)

watch(user, (newUser: UserDetail) => {
  if (!newUser) return

  const created = newUser.created ? new Date(newUser.created) : undefined
  const lastModified = newUser.lastModified ? new Date(newUser.lastModified) : undefined
  Object.assign(state, {
    id: newUser.id,
    emails: newUser.emails?.length ? [...newUser.emails] : [...defaultForm.emails],
    eppns: newUser.eppns?.length ? [...newUser.eppns] : [...defaultForm.eppns],
    userName: newUser.userName || defaultForm.userName,
    preferredLanguage: newUser.preferredLanguage || defaultForm.preferredLanguage,
    isSystemAdmin: newUser.isSystemAdmin || defaultForm.isSystemAdmin,
    repositoryRoles: newUser.repositoryRoles?.length
      ? newUser.repositoryRoles?.map(role => ({
          value: role.id,
          label: role.serviceName,
          userRole: camelCase(role.userRole!),
        }))
      : structuredClone(defaultForm.repositoryRoles),
    groups: newUser.groups?.length
      ? newUser.groups?.map(group => ({ value: group.id, label: group.displayName }))
      : structuredClone(defaultForm.groups),
    created: created ? datetimeFormatter.format(created) : defaultForm.created,
    lastModified: lastModified ? datetimeFormatter.format(lastModified) : defaultForm.lastModified,
  } as UserForm)
}, { immediate: true })

const onSubmit = async (data: UserUpdateForm) => {
  const { repositoryRoles, groups, ...remain } = data
  const payload: UserUpdatePayload = {
    ...remain,
    emails: remain.emails.filter(email => email.trim() !== ''),
    repositoryRoles:
      remain.isSystemAdmin
        ? []
        : repositoryRoles.map(item =>
            ({ id: item.value!, userRole: item.userRole } as RepositoryRole),
          ),
    groups: groups.flatMap(item => item.value ? [{ id: item.value }] : []),
  }

  try {
    await $api(`/api/users/${userId.value}`, {
      method: 'PUT',
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
              message: $t('error-page.forbidden.user-edit'),
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
      description: $t('toast.success.user-updated.description'),
      color: 'success',
      icon: 'i-lucide-circle-check',
    })
    await navigateTo('/users')
    if (isSelf.value) {
      await logout()
    }
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
</script>

<template>
  <UPageHeader
    :title="user?.userName || ''"
    :description="$t('users.description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div class="max-w-240 m-auto">
    <UCard>
      <template #header>
        <div class="flex items-center justify-between">
          <h2 class="text-2xl font-semibold">
            {{ $t('user.details-title') }}
          </h2>
          <UButton
            v-if="mode === 'edit'"
            :label="$t('button.delete')"
            icon="i-lucide-trash"
            variant="subtle"
            color="error"
          />
        </div>
      </template>

      <UserForm
        v-model="state" :mode="mode"
        @submit="(event) => onSubmit(event.data as UserUpdateForm)"
        @cancel="onCancel"
      />
    </UCard>
  </div>
</template>
