<!--
 Copyright (C) 2026 National Institute of Informatics.
-->
<script setup lang="ts">
import { description } from '@@/package.json'

definePageMeta({
  layout: 'unauth',
})
const route = useRoute()

let { next } = route.query
if (Array.isArray(next)) {
  next = next[0]
}
</script>

<template>
  <UPage>
    <UPageSection
      :title="$t('login.title')"
      :description="description" icon="i-lucide-user"
      :ui="{ leadingIcon: 'size-12' }"
    >
      <UAuthForm
        :ui="{
          title: 'text-2xl',
          body: 'flex flex-col justify-center items-center',
          providers: 'w-full max-w-200',
        }"
      >
        <template #providers>
          <EmbeddedDs :next="next as (string | undefined)" />
        </template>

        <template #footer>
          <DevOnly>
            <div class="flex flex-col justify-center items-center max-w-200 mx-auto">
              <USeparator :ui="{ root: 'h-px' }" />
              <DevLoginForm :next="next as (string | undefined)" />
            </div>
          </DevOnly>
        </template>
      </UAuthForm>
    </UPageSection>
  </UPage>
</template>
