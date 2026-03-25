<script setup lang="ts">
import type { FormErrorEvent, FormSubmitEvent } from '@nuxt/ui'

interface Properties {
  modelValue: RepositoryForm | RepositoryCreateForm
  mode: FormMode
  onSubmit: (event: FormSubmitEvent<RepositoryForm | RepositoryCreateForm>) => Promise<void>
}
const properties = defineProps<Properties>()

const emit = defineEmits<{
  'update:modelValue': [value: RepositoryForm | RepositoryCreateForm]
  'error': [event: FormErrorEvent]
  'cancel': []
}>()

const { currentUser } = useAuth()
const { schema, maxUrlLength } = useRepositorySchema(() => properties.mode)
const { handleFormError } = useFormError()

const state = computed({
  get: () => properties.modelValue,
  set: value => emit('update:modelValue', value),
})
const stateAsEdit = computed(() => properties.modelValue as RepositoryForm)

const toast = useToast()
const { copy } = useClipboard()
const copyUrl = (url: string) => {
  copy(url)
  toast.add({
    title: $t('toast.success.title'),
    description: $t('toast.success.copy-service-url.description'),
    color: 'success',
    icon: 'i-lucide-circle-check',
  })
}
const copyEntityId = (id: string) => {
  copy(id)
  toast.add({
    title: $t('toast.success.title'),
    description: $t('toast.success.copy-entity-id.description'),
    color: 'success',
    icon: 'i-lucide-circle-check',
  })
}

const addEntityId = () => {
  state.value.entityIds.push('')
}
const removeEntityId = (index: number) => {
  if (state.value.entityIds.length > 1) {
    state.value.entityIds.splice(index, 1)
  }
}

const form = useTemplateRef('form')
const onError = (event: FormErrorEvent) => {
  handleFormError(event)
  emit('error', event)
}
const onCancel = () => {
  form.value?.clear()
  emit('cancel')
}
</script>

<template>
  <UForm
    ref="form"
    :schema="schema" :state="state" class="space-y-6"
    @submit="onSubmit" @error="onError"
  >
    <h3 class="text-lg font-semibold">
      {{ $t('repository.details-basic-section') }}
    </h3>

    <UFormField
      name="serviceName"
      :label="$t('repository.service-name')"
      :description="$t('repository.service-name-description')"
      :ui="{ wrapper: 'mb-2' }" :required="mode !== 'view'"
    >
      <UInput
        v-if="mode !== 'view'"
        v-model="state.serviceName" size="xl"
        :placeholder="$t('repository.placeholders.service-name')"
        :ui="{ root: 'w-full' }"
      />
      <div
        v-else
        class="mt-1 px-3 py-2 text-base"
      >
        {{ state.serviceName || '-' }}
      </div>
    </UFormField>

    <UFormField
      name="serviceUrl"
      :label="$t('repository.service-url')"
      :description="$t('repository.service-url-description')"
      :ui="{ wrapper: 'mb-2' }" :required="mode === 'new'"
    >
      <UInput
        v-if="mode === 'new'"
        v-model="state.serviceUrl" size="xl"
        :placeholder="$t('repository.placeholders.service-url')"
        :maxlength="maxUrlLength"
        :ui="{ root: 'w-full', base: 'pl-17' }"
      >
        <template #leading>
          <span class="text-base">https://</span>
        </template>

        <template #trailing>
          {{ state.serviceUrl.length }} / {{ maxUrlLength }}
        </template>
      </UInput>
      <div
        v-else
        class="mt-1 px-3 py-2 text-base"
      >
        https://{{ state.serviceUrl || '-' }}
        <UButton
          v-if="state.serviceUrl"
          icon="i-lucide-copy" variant="ghost" color="neutral"
          :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
          @click="copyUrl('https://' + state.serviceUrl)"
        />
      </div>
    </UFormField>

    <UFormField
      name="entityIds" :error-pattern="/entityIds\..*/"
      :label="$t('repository.entity-ids')"
      :description="$t('repository.entity-ids-description')"
      :ui="{
        wrapper: 'mb-2',
        hint: 'flex justify-end items-center px-2',
        container: 'space-y-3',
        error: 'mt-0',
      }" :required="mode !== 'view'"
    >
      <template v-if="mode !== 'view'" #hint>
        <UButton
          :label="$t('button.add')"
          icon="i-lucide-plus" variant="ghost" color="neutral" size="sm"
          :ui="{ base: 'p-0' }"
          @click="addEntityId"
        />
      </template>

      <template v-for="(entityId, index) in state.entityIds" :key="index">
        <UInput
          v-if="mode !== 'view'"
          v-model="state.entityIds[index]" size="xl"
          :placeholder="$t('repository.placeholders.entity-ids')"
          :ui="{ root: 'w-full' }"
        >
          <template #trailing>
            <UButton
              icon="i-lucide-x" variant="ghost" color="neutral" size="sm"
              :ui="{ base: 'p-0' }"
              :disabled="state.entityIds.length <= 1"
              @click="removeEntityId(index)"
            />
          </template>
        </UInput>
        <div
          v-else
          class="mt-1 px-3 py-2 text-base"
        >
          {{ entityId }}
          <UButton
            icon="i-lucide-copy" variant="ghost" color="neutral"
            :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
            @click="copyEntityId(entityId)"
          />
        </div>
      </template>
    </UFormField>

    <h3 v-if="mode !== 'new'" class="text-lg font-semibold mt-2">
      {{ $t('repository.details-sp-connector-section') }}
    </h3>

    <UFormField
      v-if="mode !== 'new'"
      :label="$t('repository.sp-connector')"
      :description="$t('repository.sp-connector-description')"
      :ui="{ wrapper: 'mb-2' }"
    >
      <div class="mt-1 px-3 py-2 text-base">
        {{ stateAsEdit.spConnectorId }}
      </div>
    </UFormField>

    <UFormField
      v-if="mode !== 'new' && currentUser?.isSystemAdmin"
      name="active"
      :label="$t('repository.suspended')"
      :description="$t('repository.suspended-description')"
    >
      <USwitch
        v-model="state.active"
        size="xl"
        :label="
          state.active ? $t('repository.suspended-active') : $t('repository.suspended-inactive')
        "
        :ui="{ root: 'py-2 px-3' }"
        :disabled="mode === 'view'"
      />
    </UFormField>

    <UFormField
      v-if="mode !== 'new'"
      :label="$t('repository.created')" :ui="{ wrapper: 'mb-2' }"
    >
      <div class="mt-1 px-3 py-2 text-base">
        {{ stateAsEdit.created || '-' }}
      </div>
    </UFormField>

    <div v-if="mode !== 'view'" class="flex justify-between items-center mt-2">
      <UButton
        :label="$t('button.cancel')"
        icon="i-lucide-ban" color="neutral" variant="subtle"
        @click="onCancel"
      />
      <UButton
        v-if="mode === 'new'"
        :label="$t('button.save')"
        type="submit" icon="i-lucide-save" color="info" variant="subtle"
        loading-auto
      />
      <UButton
        v-else
        :label="$t('button.update')"
        type="submit" icon="i-lucide-save" color="info" variant="subtle"
        loading-auto
      />
    </div>
  </UForm>
</template>
