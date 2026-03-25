<script setup lang="ts">
import type { FormErrorEvent, FormSubmitEvent } from '@nuxt/ui'

interface Properties {
  modelValue: UserForm | UserCreateForm | UserUpdateForm
  mode: FormMode
  onSubmit: (event: FormSubmitEvent<UserCreateForm | UserUpdateForm>) => Promise<void>
}
const properties = defineProps<Properties>()

const emit = defineEmits<{
  'update:modelValue': [value: UserForm | UserCreateForm | UserUpdateForm]
  'error': [event: FormErrorEvent]
  'cancel': []
}>()

const {
  table: { pageSize },
  features: { repositories: { 'server-search': serverSearch } },
} = useAppConfig()
const { currentUser } = useAuth()
const { schema } = useUserSchema(() => properties.mode)
const { preferredLanguageOptions, userRoleOptions } = useUserFormOptions()
const { handleFormError } = useFormError()

const state = computed({
  get: () => properties.modelValue,
  set: value => emit('update:modelValue', value),
})
const stateAsEdit = computed(() => properties.modelValue as UserForm)

const toast = useToast()
const { copy } = useClipboard()
const copyField = (value: string, key: 'id' | 'username' | 'emails' | 'eppns') => {
  copy(value)
  toast.add({
    title: $t('toast.success.title'),
    description: $t('toast.success.copy-field.description', { field: $t(`user.${key}`) }),
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

const groupSelect = useTemplateRef('groupSelect')
const {
  items: groupNames,
  searchTerm: groupSearchTerm,
  status: groupSearchStatus,
  onOpen: onGroupOpen,
  setupInfiniteScroll: setupGroupScroll,
} = useSelectMenuInfiniteScroll<GroupSummary>({
  url: '/api/groups',
  limit: pageSize.groups[0],
  transform: group => ({
    label: group.displayName,
    value: group.id,
  }),
})
setupGroupScroll(groupSelect)

const form = useTemplateRef('form')

type MultipleField<T> = { [K in keyof T]: T[K] extends string[] ? K : never }[keyof T]
const addField = (name: MultipleField<UserForm | UserCreateForm>) => {
  state.value[name].push('')
}
const removeField = (name: MultipleField<UserForm | UserCreateForm>, index: number) => {
  if (state.value[name].length > 1) {
    state.value[name].splice(index, 1)
  }
}

const addRepositoryRole = () => {
  state.value.repositoryRoles.push({ value: undefined, label: undefined, userRole: undefined })
}
const removeRepositoryRole = (index: number) => {
  if (state.value.repositoryRoles.length > 1) {
    state.value.repositoryRoles.splice(index, 1)
  }
  else {
    state.value.repositoryRoles[index] = { value: undefined, label: undefined, userRole: undefined }
  }
  form.value?.validate({ silent: false })
}

const addGroup = () => {
  state.value.groups.push({ value: undefined, label: undefined })
}
const removeGroup = (index: number) => {
  if (state.value.groups.length > 1) {
    state.value.groups.splice(index, 1)
  }
  else {
    state.value.groups[index] = { value: undefined, label: undefined }
  }
  form.value?.validate({ silent: false })
}

const onError = (event: FormErrorEvent) => {
  handleFormError(event)
  emit('error', event)
}
const onCancel = () => {
  form.value?.clear()
  emit('cancel')
}

const isSelf = computed(() =>
  properties.mode === 'new' ? false : currentUser.value?.id === stateAsEdit.value.id,
)
</script>

<template>
  <UForm
    ref="form"
    :schema="schema" :state="state" class="space-y-6"
    @submit="(event) => onSubmit(event as FormSubmitEvent<UserCreateForm | UserUpdateForm>)"
    @error="onError"
  >
    <h3 class="text-lg font-semibold">
      {{ $t('user.details-basic-section') }}
    </h3>

    <UFormField
      v-if="mode !== 'new'"
      :label="$t('user.id')" :ui="{ wrapper: 'mb-2' }"
    >
      <div class="mt-1 px-3 py-2 text-base">
        {{ stateAsEdit.id || '-' }}
        <UButton
          v-if="stateAsEdit.id"
          icon="i-lucide-copy" variant="ghost" color="neutral"
          :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
          @click="() => copyField(stateAsEdit.id, 'id')"
        />
      </div>
    </UFormField>

    <UFormField
      name="userName"
      :label="$t('user.username')"
      :description="$t('user.userName-description')"
      :ui="{ wrapper: 'mb-2' }" :required="mode !== 'view'"
    >
      <UInput
        v-if="mode !== 'view'"
        v-model="state.userName" size="xl"
        :placeholder="$t('user.placeholder.userName')"
        :ui="{ root: 'w-full' }"
      />
      <div
        v-else
        class="mt-1 px-3 py-2 text-base"
      >
        {{ stateAsEdit.userName || '-' }}
        <UButton
          v-if="stateAsEdit.userName"
          icon="i-lucide-copy" variant="ghost" color="neutral"
          :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
          @click="() => copyField(stateAsEdit.userName, 'username')"
        />
      </div>
    </UFormField>

    <UFormField
      name="eppns"
      :label="$t('user.eppns')" :error-pattern="/eppns\..*/"
      :description="$t('user.eppns-description')"
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
          @click="() => addField('eppns')"
        />
      </template>

      <template v-for="(eppn, index) in state.eppns" :key="index">
        <UInput
          v-if="mode !== 'view'"
          v-model="state.eppns[index]" size="xl"
          :placeholder="$t('user.placeholder.eppns')"
          :ui="{ root: 'w-full' }"
        >
          <template #trailing>
            <UButton
              icon="i-lucide-x" variant="ghost" color="neutral" size="sm"
              :ui="{ base: 'p-0' }"
              :disabled="state.eppns.length <= 1"
              @click="() => removeField('eppns', index)"
            />
          </template>
        </UInput>
        <div
          v-else
          class="mt-1 px-3 py-2 text-base"
        >
          {{ eppn || '-' }}
          <UButton
            v-if="eppn"
            icon="i-lucide-copy" variant="ghost" color="neutral"
            :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
            @click="() => copyField(eppn, 'eppns')"
          />
        </div>
      </template>
    </UFormField>

    <UFormField
      name="emails" :error-pattern="/emails\..*/"
      :label="$t('user.emails')"
      :description="$t('user.emails-description')"
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
          @click="() => addField('emails')"
        />
      </template>

      <template v-for="(email, index) in state.emails" :key="index">
        <UInput
          v-if="mode !== 'view'"
          v-model="state.emails[index]" size="xl"
          :placeholder="$t('user.placeholder.emails')"
          :ui="{ root: 'w-full' }"
        >
          <template #trailing>
            <UButton
              icon="i-lucide-x" variant="ghost" color="neutral" size="sm"
              :ui="{ base: 'p-0' }"
              :disabled="state.emails.length <= 1"
              @click="() => removeField('emails', index)"
            />
          </template>
        </UInput>
        <div
          v-else
          class="mt-1 px-3 py-2 text-base"
        >
          {{ email || '-' }}
          <UButton
            v-if="email"
            icon="i-lucide-copy" variant="ghost" color="neutral"
            :ui="{ base: 'p-0 ml-2', leadingIcon: 'size-3' }"
            @click="() => copyField(email, 'emails')"
          />
        </div>
      </template>
    </UFormField>

    <UFormField
      name="preferredLanguage"
      :label="$t('user.preferred-language')"
      class="w-full" :ui="{ label: 'text-lg' }"
    >
      <USelectMenu
        v-model="state.preferredLanguage" value-key="value"
        :items="preferredLanguageOptions" :search-input="false" size="xl" clear
        :placeholder="$t('user.placeholder.preferred-language')"
        :ui="{ base: 'w-full' }" :disabled="mode === 'view'"
      />
    </UFormField>

    <h3 class="text-lg font-semibold">
      {{ currentUser?.isSystemAdmin
        ? $t('user.details-affiliation-authority-section')
        : $t('user.details-affiliation-section')
      }}
    </h3>
    <UAlert
      v-if="isSelf"
      :title="$t('user.self-editing-warning')"
      icon="i-lucide-triangle-alert"
      variant="soft" color="warning" :ui="{ root: 'mb-4' }"
    />

    <UFormField
      v-if="currentUser?.isSystemAdmin"
      name="isSystemAdmin"
      :label="$t('user.privileged')"
      :description="$t('repository.suspended-description')"
      :ui="{ wrapper: 'mb-2' }"
    >
      <UCheckbox
        v-model="state.isSystemAdmin"
        variant="card" color="error" size="lg"
        :ui="{ root: 'py-2 px-3 w-fit', label: 'flex items-center gap-1.5' }"
        :disabled="!currentUser?.isSystemAdmin"
      >
        <template #label>
          <UIcon name="i-lucide-shield-check" size="20" />
          {{ $t('users.roles.system-admin') }}
        </template>
      </UCheckbox>
    </UFormField>

    <UFormField
      name="repositoryRoles" :error-pattern="/^repositoryRoles/"
      :label="$t('user.affiliated-repositories')"
      :description="$t('user.affiliated-repositories-description')"
      :ui="{
        wrapper: 'mb-2',
        hint: 'flex justify-end items-center px-2',
        container: 'space-y-3',
        error: 'mt-0',
      }" :required="!state.isSystemAdmin"
    >
      <template #hint>
        <UButton
          :label="$t('button.add')"
          icon="i-lucide-plus" variant="ghost" color="neutral" size="sm"
          :ui="{ base: 'p-0' }"
          @click="addRepositoryRole"
        />
      </template>

      <div
        v-for="(repository, index) in state.repositoryRoles " :key="index"
        class="flex gap-2.5 items-center"
      >
        <USelectMenu
          ref="repositorySelect"
          v-model="state.repositoryRoles[index] as { label: string, value: string }"
          v-model:search-term="repoSearchTerm" size="xl"
          :placeholder="$t('user.placeholder.repository-name')"
          :items="repositoryNames" :loading="repoSearchStatus === 'pending'"
          :ignore-filter="serverSearch"
          class="flex-2"
          @update:open="onRepoOpen"
        />
        <USelectMenu
          v-model="state.repositoryRoles[index]!.userRole" size="xl"
          :items="userRoleOptions" value-key="value" :search-input="false"
          :placeholder="$t('user.placeholder.role')"
          class="flex-1"
        />

        <UButton
          icon="i-lucide-x" variant="ghost" color="neutral" size="sm"
          :ui="{ base: 'p-0' }"
          @click="() => removeRepositoryRole(index)"
        />
      </div>
    </UFormField>

    <UFormField
      name="groups" :error-pattern="/groups\..*/"
      :label="$t('user.groups')"
      :description="$t('user.groups-description')"
      :ui="{
        wrapper: 'mb-2',
        hint: 'flex justify-end items-center px-2',
        container: 'space-y-3',
        error: 'mt-0',
      }"
    >
      <template #hint>
        <UButton
          :label="$t('button.add')"
          icon="i-lucide-plus" variant="ghost" color="neutral" size="sm"
          :ui="{ base: 'p-0' }"
          @click="addGroup"
        />
      </template>

      <div
        v-for="(group, index) in state.groups" :key="index"
        class="flex gap-2.5 items-center"
      >
        <USelectMenu
          ref="groupSelect"
          v-model="state.groups[index] as { label: string, value: string }"
          v-model:search-term="groupSearchTerm" size="xl"
          :placeholder="$t('user.placeholder.group-name')"
          :items="groupNames" :loading="groupSearchStatus === 'pending'" ignore-filter
          :ui="{ base: 'w-full' }"
          @update:open="onGroupOpen"
        />
        <UButton
          icon="i-lucide-x" variant="ghost" color="neutral" size="sm"
          :ui="{ base: 'p-0' }"
          @click="() => removeGroup(index)"
        />
      </div>
    </UFormField>

    <UFormField
      v-if="mode !== 'new'"
      :label="$t('user.created')" :ui="{ wrapper: 'mb-2' }"
    >
      <div class="mt-1 px-3 py-2 text-base">
        {{ stateAsEdit.created || '-' }}
      </div>
    </UFormField>

    <UFormField
      v-if="mode !== 'new'"
      :label="$t('user.last-modified')" :ui="{ wrapper: 'mb-2' }"
    >
      <div class="mt-1 px-3 py-2 text-base">
        {{ stateAsEdit.lastModified || '-' }}
      </div>
    </UFormField>

    <div class="flex justify-between items-center mt-2">
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
