<script setup lang="ts">
import type { CommandPaletteGroup } from '@nuxt/ui'

const toast = useToast()
const { $api } = useNuxtApp()
const { header: { globalSearch } } = useAppConfig()
const { searchTerm, previousSearchTerm, makeResultGroups } = useGlobalSearch()
const { handleFetchError } = useErrorHandling()

const result = ref<GlobalSearchResults | undefined>(undefined)
const status = ref<'idle' | 'pending' | 'success' | 'error'>('idle')

const groups = computed<CommandPaletteGroup[]>(() => {
  if (status.value !== 'success' || !result.value) return []

  return makeResultGroups(result.value)
})

const isOpen = ref(false)
defineShortcuts({
  '/': () => isOpen.value = !isOpen.value,
})
const onSelect = () => {
  isOpen.value = false
}
const onClose = () => {
  searchTerm.value = ''
  previousSearchTerm.value = ''
  result.value = undefined
  status.value = 'idle'
}

const executeSearch = async () => {
  if (!searchTerm.value) return
  previousSearchTerm.value = searchTerm.value
  status.value = 'pending'

  // Use $fetch instead of useFetch to avoid stale query params when component remounts via v-if.
  try {
    result.value = await $api<GlobalSearchResults>('/api/search', {
      method: 'GET',
      query: { q: searchTerm.value, limit: globalSearch.limit },
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
          default: {
            handleFetchError({ response })
          }
        }
      },
    })
    status.value = 'success'
  }
  catch {
    status.value = 'error'
  }
}
const handleKeydown = async (event: KeyboardEvent) => {
  if (!isOpen.value) return

  if (event.key === 'Enter' && searchTerm.value !== previousSearchTerm.value) {
    event.preventDefault()
    event.stopPropagation()
    await executeSearch()
  }
}

const emptyResultMessage = computed(() => {
  if (previousSearchTerm.value.length === 0) return $t('header.global-search.search-empty')
  if (status.value === 'pending') return $t('header.global-search.search-loading')
  return $t('header.global-search.no-results', { searchTerm: previousSearchTerm.value })
})
</script>

<template>
  <UInput
    ref="input" color="neutral"
    icon="i-lucide-search" variant="outline"
    :placeholder="$t('header.global-search.placeholder')" readonly
    :ui="{ root: 'w-60' }"
    @click="isOpen = true"
  >
    <template #trailing>
      <UKbd value="/" class="pointer-events-none" />
    </template>
  </UInput>

  <UModal
    v-model:open="isOpen"
    title="global search" description="search by name across resources"
    @after:leave="onClose"
  >
    <template #content>
      <UCommandPalette
        v-model:search-term="searchTerm"
        :loading="status === 'pending'" :groups="groups"
        :placeholder="$t('header.global-search.pallet-placeholder')"
        :ui="{ root: 'h-100 w-full' }"
        @update:model-value="onSelect"
        @keydown.capture="handleKeydown"
      >
        <template #empty>
          {{ emptyResultMessage }}
        </template>

        <template #close>
          <UButton
            variant="ghost" color="neutral" loading-auto
            :ui="{ leadingIcon: 'hidden' }"
            @click="executeSearch"
          >
            <UKbd value="enter" />
          </UButton>
        </template>
      </UCommandPalette>
    </template>
  </UModal>
</template>
