<!-- eslint-disable unicorn/prevent-abbreviations -->
<script setup lang="ts">
import type { FormSubmitEvent } from '@nuxt/ui'

const { next } = defineProps<{ next?: string }>()
const { $api } = useNuxtApp()

const { data: accounts } = useApiFetch<{ eppns: string[] }>('/api/dev/accounts', {
  method: 'GET',
  default: () => ({ eppns: [] }),
})

const state = ref({ eppn: '' },
)
const form = useTemplateRef('form')

const onSubmit = (payload: FormSubmitEvent<{ eppn: string }>) => {
  $api('/api/dev/login', {
    method: 'POST',
    query: { next },
    body: {
      eppn: payload.data.eppn,
    },
  }).then(() => {
    navigateTo(decodeURIComponent(next || '/'))
  }).catch(() => {
    form.value?.setErrors([{
      name: 'eppn', message: $t('login.dev-login-error'),
    }])
  })
}
</script>

<template>
  <UForm ref="form" :state="state" class="p-4 space-y-2" @submit="onSubmit">
    <h3 class="text-lg font-semibold my-2">
      {{ $t('login.dev-login-title') }}
    </h3>

    <UFormField
      name="eppn"
      :label="$t('login.dev-account')" :ui="{ root: 'w-100', wrapper: 'mb-2' }"
    >
      <USelectMenu
        v-model="state.eppn" :items="accounts.eppns"
        :ui="{ base: 'w-full' }"
      />
    </UFormField>

    <UButton type="submit" class="mt-4">
      {{ $t('login.dev-login-button') }}
    </UButton>
  </UForm>
</template>
