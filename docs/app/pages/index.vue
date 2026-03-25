<script setup lang="ts">
import type { Collections } from '@nuxt/content'

const categories: (Exclude<keyof Collections, 'index'>)[] = ['detailed', 'api',
  'db', 'manual']
const features = await Promise.all(
  categories.map(category =>
    useAsyncData(`feature-${category}`, () => {
      return queryCollection(category).first()
    }).then(result => ({
      title: result.data.value?.title,
      icon: result.data.value?.icon,
      to: `/${category}`,
    })),
  ),
)

const { data: page } = await useAsyncData('page-index', () => {
  return queryCollection('index').path('/').first()
})
</script>

<template>
  <UPageSection
    v-if="page"
    :title="page.title" :description="page.description"
    :features="features" :ui="{ container: 'max-w-250' }"
  />
</template>
