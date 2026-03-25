<script setup lang="ts">
import { twMerge } from 'tailwind-merge'

interface Properties {
  title: string
  number: number
  color?: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
  icon: string
  to?: string
  ui?: {
    root?: string | string[]
    container?: string | string[]
    wrapper?: string | string[]
    body?: string | string[]
    title?: string | string[]
    description?: string | string[]
    iconWrapper?: string | string[]
    iconBody?: string | string[]
    icon?: string | string[]
  }
}
const properties = withDefaults(defineProps<Properties>(), {
  color: 'primary',
})

const ui = {
  root: '',
  container: 'flex lg:flex flex-row gap-6 md:gap-10 items-center',
  wrapper: 'flex-2',
  body: 'space-y-1',
  title: 'whitespace-nowrap',
  description: 'text-2xl font-bold text-highlighted m-0',
  iconWrapper: 'flex-1',
  iconBody: 'm-auto rounded-lg p-3 size-16',
  icon: `size-10 text-${properties.color}`,
}
const mergedUi = computed(() => {
  return {
    root: twMerge(ui.root, properties.ui?.root),
    container: twMerge(ui.container, properties.ui?.container),
    wrapper: twMerge(ui.wrapper, properties.ui?.wrapper),
    body: twMerge(ui.body, properties.ui?.body),
    title: twMerge(ui.title, properties.ui?.title),
    description: twMerge(ui.description, properties.ui?.description),
    iconWrapper: twMerge(ui.iconWrapper, properties.ui?.iconWrapper),
    iconBody: twMerge(ui.iconBody, properties.ui?.iconBody),
    icon: twMerge(ui.icon, properties.ui?.icon),
  }
})
</script>

<template>
  <UPageCard
    :title="title" :description="String(number)" :to="to"
    orientation="horizontal" reverse
    :ui="{
      root: mergedUi.root,
      container: mergedUi.container,
      wrapper: mergedUi.wrapper,
      body: mergedUi.body,
      title: mergedUi.title,
      description: mergedUi.description,
    }"
  >
    <div :class="mergedUi.iconWrapper">
      <div :class="`bg-${color}/10 ${mergedUi.iconBody}`">
        <UIcon :name="icon" :class="`${mergedUi.icon}`" />
      </div>
    </div>
  </UPageCard>
</template>
