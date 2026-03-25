<script setup lang="ts">
import type { Collections, ContentNavigationItem } from '@nuxt/content'

definePageMeta({
  layout: 'docs',
})

const route = useRoute()
const category = inject<ComputedRef<Exclude<keyof Collections, 'index'>>>('collection')

if (!category) {
  throw new Error('Category not provided')
}

const { data: page } = await useAsyncData(`page-${route.path}`, () => {
  return queryCollection(category.value).path(route.path).first()
})

if (!page.value) {
  throw createError({ statusCode: 404, statusMessage: 'Page not found', fatal: true })
}

const navigation = inject<Ref<ContentNavigationItem[] | undefined>>('navigation')

const findParent
  = (nav: ContentNavigationItem[], currentPath: string): ContentNavigationItem | undefined => {
    for (const item of nav) {
      if (item.children) {
        const hasCurrentPage = item.children.some(child => child.path === currentPath)
        if (hasCurrentPage) return item

        const foundInChildren = findParent(item.children, currentPath)
        if (foundInChildren) return foundInChildren
      }
    }
    return
  }

const headline = computed(() => {
  if (page?.value?.headline) return page.value.headline
  if (!navigation?.value) return
  return findParent(navigation.value, route.path)?.title
})

const { data: surround } = await useAsyncData(`${route.path}-surround`, () => {
  return queryCollectionItemSurroundings(category.value, route.path, {
    fields: ['description'],
  })
})
</script>

<template>
  <UPage v-if="page">
    <UPageHeader :title="page.title" :description="page.description" :headline="headline" />

    <UPageBody>
      <ContentRenderer v-if="page.body" :value="page" />

      <USeparator v-if="surround?.length" />
      <UContentSurround :surround="surround" />
    </UPageBody>

    <template
      v-if="page?.body?.toc?.links?.length"
      #right
    >
      <UContentToc :links="page.body.toc.links" />
    </template>
  </UPage>
</template>
