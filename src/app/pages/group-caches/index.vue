<script setup lang="ts">
const toast = useToast()
const { $api } = useNuxtApp()
const {
  table: { pageSize: { cacheGroups: pageOptions } },
  polling: { interval },
} = useAppConfig()

const {
  query, updateQuery, criteria,
  selectedCount, toggleSelection, getSelected, clearSelection, selectedRepositoriesAction,
  filterItems, columns, makePageInfo, modals, isUpdating,
} = useCacheGroups()
const { searchTerm, filter, pageNumber, pageSize } = criteria

const { handleFetchError } = useErrorHandling()
const {
  data: searchResult, status, refresh: refreshSearchResult,
} = await useApiFetch<GroupCachesSearchResult>('/api/group-caches', {
  method: 'GET',
  query,
  onResponseError({ response }) {
    switch (response.status) {
      case 400: {
        toast.add({
          title: $t('toast.error.failed-search.title'),
          description: $t('toast.error.invalid-search-query.description'),
          color: 'error',
        })
        break
      }
      case 403: {
        showError({
          status: 403,
          statusText: 'Forbidden',
          message: $t('error-page.forbidden.group-caches'),
        })
        break
      }
      default: {
        handleFetchError({ response })
        break
      }
    }
  },
  lazy: true,
})
const offset = computed(() => (searchResult.value?.offset ?? 1))
const pageInfo = makePageInfo(searchResult)

const selectedRepositories = ref<{ id: string, serviceName: string, serviceUrl: string }[]>([])
const {
  data: updatingData, refresh: refreshStatus,
} = await useApiFetch<TaskDetail>('/api/group-caches/status', {
  method: 'GET',
  onResponse({ response }) {
    if (response.ok) isUpdating.value = true
  },
  onResponseError({ response }) {
    switch (response.status) {
      case 400: {
        isUpdating.value = false
        break
      }
      default: {
        handleFetchError({ response })
        break
      }
    }
  },
  lazy: true,
})

const progress = computed(() => updatingData.value?.done ?? 0)
const progressCount = computed(() => `${progress.value} / ${updatingData.value?.total ?? 0}`)

const pllProgressData = async () => {
  while (isUpdating.value) {
    await refreshStatus()
    await refreshSearchResult()
    await new Promise(resolve => setTimeout(resolve, interval))
  }
}

const onExecute = async (op: GroupCacheUpdateAction) => {
  isUpdating.value = true
  try {
    await $api('/api/group-caches', {
      method: 'post',
      body: {
        ids: op === 'id-specified' ? selectedRepositories.value.map(item => item.id) : undefined,
        op: op,
      },
      onResponseError: ({ response }) => {
        switch (response.status) {
          case 403: {
            showError({
              status: 403,
              statusText: 'Forbidden',
              message: $t('error-page.forbidden.group-caches'),
            })
            break
          }
          case 409: {
            toast.add({
              title: $t('toast.error.conflict.title'),
              description: $t('toast.error.cache-update-in-progress.description'),
              color: 'error',
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
  }
  catch {
    isUpdating.value = false
    return
  }

  toast.add({
    title: $t('toast.success.title'),
    description: $t('toast.success.group-cache-update-started.description'),
    color: 'success',
  })
  clearSelection()

  pllProgressData()
}

onUnmounted(() => {
  isUpdating.value = false
})
</script>

<template>
  <UPageHeader
    :title="$t('group-caches.title')"
    :description="$t('group-caches.description')"
    :ui="{ root: 'py-2 mb-6', description: 'mt-4' }"
  />

  <div v-if="isUpdating" class="flex flex-col items-center space-y-4 mb-4">
    <span class="text-lg font-medium text-gray-700">
      {{ $t('group-caches.updating') }}
    </span>
    <span class="text-sm text-green-500">{{ progressCount }}</span>
    <UProgress v-model="progress" />
  </div>

  <div class="flex justify-between items-center my-4">
    <div />
    <UChip
      :text="selectedCount"
      :ui="{
        base: 'h-4 min-w-4 text-[12px]' + (selectedCount ? ' visible' : ' invisible'),
      }"
    >
      <UDropdownMenu :items="selectedRepositoriesAction" :content="{ align: 'end' }">
        <UButton
          icon="i-lucide-wand" color="neutral" variant="outline"
          :ui="{ base: 'gap-1' }"
        />
      </UDropdownMenu>
    </UChip>
  </div>

  <div class="grid grid-cols-3 gap-4 my-4 h-8">
    <UInput
      v-model="searchTerm" :placeholder="$t('group-caches.search-placeholder')"
      icon="i-lucide-search" :ui="{ base: 'w-full', trailing: 'pe-1.5' }"
      @keydown.enter="updateQuery({ q: searchTerm, p: 1 })"
    >
      <template #trailing>
        <UButton
          variant="ghost" color="neutral"
          :ui="{ base: 'font-normal cursor-pointer p-1' }"
          @click="() => updateQuery({ q: searchTerm, p: 1 })"
        >
          <UKbd value="enter" />
        </UButton>
      </template>
    </UInput>

    <div class="col-span-2 flex justify-between items-center">
      <USelect
        v-model="filter"
        :placeholder="$t('table.filter-button-label')"
        icon="i-lucide-filter"
        :items="filterItems" :disabled="isUpdating" multiple
        @change="updateQuery({ f: filter, p: 1 })"
      />

      <div class="flex justify-end items-center">
        <span class="text-sm text-gray-600">{{ $t('table.page-size-label') }}</span>
        <USelect
          v-model="pageSize"
          :items="pageOptions"
          :disabled="isUpdating"
          class="w-24"
          @change="updateQuery(
            { l: pageSize, p: Math.ceil(offset / pageSize!) },
          )"
        />
      </div>
    </div>
  </div>

  <UTable
    :loading="status === 'pending'"
    :data="searchResult?.resources" :columns="columns" :ui="{ root: 'mb-8' }"
    @select="toggleSelection"
  >
    <template #empty>
      <UEmpty
        :title="$t('repositories.table.no-repositories-title')"
        :description="$t('repositories.table.no-repositories-description')"
      />
    </template>
  </UTable>

  <div class="flex justify-center mt-4">
    <div class="flex-1 text-gray-500 text-sm">
      {{ pageInfo }}
    </div>
    <div class="flex-2 flex justify-center">
      <UPagination
        v-model:page="pageNumber"
        :items-per-page="pageSize"
        :total="searchResult?.total"
        @update:page="(value) => updateQuery({ p: value })"
      />
    </div>
    <div class="flex-1" />
  </div>

  <UModal
    v-model:open="modals['id-specified']"
    :title="$t('cache-groups.confirm-update-selected-repositories', { count: selectedCount })"
    :close="false" :ui="{ footer: 'justify-between', body: 'max-h-85 space-y-2' }"
  >
    <template #body>
      <div v-for="(repo, id) in (selectedRepositories = getSelected())" :key="id" class="group">
        <div class="text-lg font-semibold text-highlighted">
          {{ repo.serviceName }}
        </div>
        <div class="text-xs text-muted mt-1">
          {{ repo.serviceUrl }}
        </div>

        <USeparator class="my-1 group-last:hidden" />
      </div>
    </template>

    <template #footer="{ close }">
      <UButton
        :label="$t('button.cancel')"
        icon="i-lucide-ban" color="neutral" variant="soft"
        @click="close"
      />
      <UButton
        :label="$t('button.update')"
        icon="i-lucide-refresh-cw" color="primary" variant="solid"
        :disabled="isUpdating" loading-auto
        @click="async() => { close(); await onExecute('id-specified'); }"
      />
    </template>
  </UModal>

  <UModal
    v-model:open="modals.all"
    :title="$t('modal.update-all-repositories-cache.title')"
    :close="false" :ui="{ footer: 'justify-between', body: 'max-h-85 space-y-2' }"
  >
    <template #body>
      <UAlert
        :title="$t('modal.update-all-repositories-cache.alert')"
        icon="i-lucide-alert-triangle" color="warning" variant="subtle"
      />
    </template>
    <template #footer="{ close }">
      <UButton
        :label="$t('button.cancel')"
        icon="i-lucide-ban" color="neutral" variant="soft"
        @click="close"
      />
      <UButton
        :label="$t('button.update')"
        icon="i-lucide-refresh-cw" color="primary" variant="solid"
        :disabled="isUpdating" loading-auto
        @click="async() => { close(); await onExecute('all'); }"
      />
    </template>
  </UModal>
</template>
