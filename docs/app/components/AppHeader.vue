<!-- eslint-disable unicorn/prevent-abbreviations -->
<script setup lang="ts">
import type { Collections, ContentNavigationItem } from '@nuxt/content'
import type { NavigationMenuItem } from '@nuxt/ui'

const route = useRoute()
const categories: (Exclude<keyof Collections, 'index'>)[] = ['detailed', 'api', 'db',
  'manual']
const categoryData = await Promise.all(
  categories.map(category =>
    useAsyncData(`links-${category}`, () => {
      return queryCollection(category).first()
    }),
  ),
)
const items = computed(() =>
  categoryData.map((result, index) => ({
    label: result.data.value!.title,
    icon: result.data.value?.icon,
    to: `/${categories[index]}`,
    active: route.path.startsWith(`/${categories[index]}`),
  } as NavigationMenuItem)),
)

const navigation = inject<Ref<ContentNavigationItem[] | undefined>>('navigation')
</script>

<template>
  <UHeader
    toggle-side="left" mode="slideover"
    :toggle="{ class: route.path !== '/' }" :menu="{ side: 'left' }"
  >
    <template #title>
      <img src="/logo.png" alt="Logo" class="h-8 object-cover rounded-full">
    </template>

    <UNavigationMenu
      v-if="route.path !== '/'"
      :items="items" variant="pill" highlight
    />

    <template #body>
      <UContentSearchButton
        :collapsed="false" :kbds="['/']"
        :ui="{ base: 'container mt-2' }"
      />
      <div class="w-full h-8" />

      <UNavigationMenu
        v-if="route.path !== '/'"
        :items="items" variant="pill" highlight orientation="vertical"
      />
      <div class="w-full h-6" />

      <UContentNavigation :navigation="navigation" highlight :ui="{ root: 'px-2.5' }" />
    </template>
  </UHeader>
</template>
