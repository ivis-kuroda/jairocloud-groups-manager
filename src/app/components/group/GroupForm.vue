<script setup lang="ts">
import type { FormErrorEvent, FormSubmitEvent } from '@nuxt/ui'

interface Properties {
  modelValue: GroupCreateForm | GroupUpdateForm
  mode: FormMode
  onSubmit: (event: FormSubmitEvent<GroupCreateForm | GroupUpdateForm>) => Promise<void>
}
const properties = defineProps<Properties>()

const emit = defineEmits<{
  'update:modelValue': [value: GroupCreateForm | GroupUpdateForm]
  'error': [event: FormErrorEvent]
  'cancel': []
}>()

const {
  table: { pageSize },
  features: { repositories: { 'server-search': serverSearch } },
} = useAppConfig()
const { schema, getMaxIdLength } = useGroupSchema(() => properties.mode)
const { handleFormError } = useFormError()

const state = computed({
  get: () => properties.modelValue,
  set: value => emit('update:modelValue', value),
})
const stateAsCreate = computed(() => properties.modelValue as GroupCreateForm)
const stateAsEdit = computed(() => properties.modelValue as GroupUpdateForm)

const toast = useToast()
const { copy } = useClipboard()
const copyId = (id: string) => {
  copy(id)
  toast.add({
    title: $t('toast.success.title'),
    description: $t('toast.success.copy-group-id.description'),
    color: 'success',
    icon: 'i-lucide-circle-check',
  })
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
  transform: repository => ({
    label: repository.serviceName,
    value: repository.id,
  }),
  server: serverSearch,
})
setupRepoScroll(repositorySelect)

const maxIdLength = computed(() =>
  stateAsCreate.value.repository.value
    ? getMaxIdLength(state.value.repository.value || '')
    : 0,
)

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
    :schema="schema" :state="state" class="space-y-6" :novalidate="true"
    @submit="(event) => onSubmit(
      event as FormSubmitEvent<GroupCreateForm | GroupUpdateForm>,
    )"
    @error="onError"
  >
    <h3 class="text-lg font-semibold">
      {{ $t('group.details-basic-section') }}
    </h3>

    <UFormField
      name="repository" :error-pattern="/repository\..*/"
      :label="$t('group.repository')"
      :description="mode === 'new' ? $t('group.repository-description') : ''"
      :ui="{ wrapper: 'mb-2' }" :required="mode === 'new'"
    >
      <USelectMenu
        v-if="mode === 'new'"
        ref="repositorySelect"
        v-model="state.repository as { label: string, value: string }"
        v-model:search-term="repoSearchTerm" size="xl"
        :placeholder="$t('group.placeholder.repository')"
        :items="repositoryNames" :loading="repoSearchStatus === 'pending'"
        :ignore-filter="serverSearch"
        :ui="{ base: 'w-full' }" :disabled="mode !== 'new'"
        @update:open="onRepoOpen"
      />
      <div
        v-else
        class="mt-1 px-3 py-2 text-base"
      >
        <ULink
          :to="`/repositories/${state.repository.value}`"
          class="font-bold hover:underline inline-flex items-center"
        >
          {{ state.repository.label || '-' }}
        </ULink>
      </div>
    </UFormField>

    <UFormField
      name="userDefinedId"
      :label="$t('group.id')"
      :description="mode === 'new' ? $t('group.id-description') : ''"
      :ui="{ wrapper: 'mb-2' }"
      :required="mode === 'new'"
    >
      <!-- eslint-disable vue/attribute-hyphenation -->
      <UInput
        v-if="mode === 'new'"
        v-model="stateAsCreate.userDefinedId" size="xl"
        :ui="{ root: 'w-full' }"
        :placeholder="$t('group.placeholder.id')"
        :maxLength="maxIdLength"
      >
        <!-- eslint-enable vue/attribute-hyphenation -->
        <template #trailing>
          {{ stateAsCreate.userDefinedId.length }} / {{ maxIdLength }}
        </template>
      </UInput>

      <div
        v-else
        class="mt-1 px-3 py-2 text-base"
      >
        <UBadge
          v-if="stateAsEdit.type === 'role'"
          :label="$t('group.type-role')" color="warning" variant="outline"
          :ui="{ base: 'mr-2' }"
        />
        {{ stateAsEdit.id || '-' }}
        <UButton
          icon="i-lucide-copy" variant="ghost" color="neutral"
          :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
          @click="() => copyId(stateAsEdit.id)"
        />
      </div>
    </UFormField>

    <UFormField
      name="displayName"
      :label="$t('group.display-name')"
      :description="$t('group.display-name-description')"
      :ui="{ wrapper: 'mb-2' }" :required="mode !== 'view'"
    >
      <UInput
        v-model="state.displayName" size="xl"
        :placeholder="$t('group.placeholder.display-name')"
        :ui="{ root: 'w-full' }" :disabled="mode === 'view'"
      />
    </UFormField>

    <UFormField
      name="description"
      :label="$t('group.description')"
      :description="$t('group.description-description')"
      :ui="{ wrapper: 'mb-2' }"
    >
      <UTextarea
        v-model="state.description" size="xl"
        :ui="{ root: 'w-full' }" :disabled="mode === 'view'" autoresize
      />
    </UFormField>

    <UFormField
      v-if="mode !== 'new'"
      :label="$t('user.created')" :ui="{ wrapper: 'mb-2' }"
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
