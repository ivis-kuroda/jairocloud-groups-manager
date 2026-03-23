<!-- eslint-disable unicorn/prevent-abbreviations -->
<script setup lang="ts">
import { ja } from '@nuxt/ui/locale'

const { navigation, collection } = await useNavigation()
provide('collection', collection)
provide('navigation', navigation)

const { data: files } = useLazyAsyncData(() => `search-${collection.value}`, () => {
  return queryCollectionSearchSections(collection.value)
}, {
  watch: [collection],
},
)

const { systemAdminVisible } = useSystemAdminVisibility()
</script>

<template>
  <UApp :locale="ja">
    <AppHeader />

    <UMain>
      <UContainer>
        <UPage>
          <template #left>
            <UPageAside>
              <template #top>
                <UContentSearchButton :collapsed="false" :kbds="['/']" />

                <div class="px-4 py-4">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-sm font-medium truncate">システム管理者</span>
                    <USwitch v-model="systemAdminVisible" size="sm" />
                  </div>
                </div>
              </template>

              <UContentNavigation :navigation="navigation" highlight />
            </UPageAside>
          </template>

          <slot />
        </UPage>
      </UContainer>
    </UMain>

    <LazyUContentSearch
      shortcut="/" :files="files" :navigation="navigation"
      :fuse="{ resultLimit: 42 }"
    />
  </UApp>
</template>
