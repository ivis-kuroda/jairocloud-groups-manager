<script setup lang="ts">
import { description, name as title } from '@@/package.json'

definePageMeta({
  layout: 'unauth',
})
</script>

<template>
  <div>
    <UPageHero
      :title="title"
      :description="description"
    />
  </div>
</template>
