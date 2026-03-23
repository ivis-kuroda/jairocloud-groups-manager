<!--
 Copyright (C) 2026 National Institute of Informatics.
-->

<script setup lang="ts">
import { author } from '@@/package.json'

const { footer: { links } } = useAppConfig()

const { isAuthenticated } = useAuth()
const { footer: columns } = useMenu()
</script>

<template>
  <USeparator icon="i-lucide-ellipsis" :ui="{ root: 'h-px' }" />

  <UFooter :ui="{ top: 'border-b border-default' }">
    <template
      v-if="isAuthenticated"
      #top
    >
      <UContainer>
        <UPage>
          <template #left>
            <UPageAside />
          </template>

          <UPageBody class="pb-0 px-10">
            <UFooterColumns :columns="columns" :ui="{ root: 'xl:grid-cols-2' }" />
          </UPageBody>
        </UPage>
      </UContainer>
    </template>

    <template #left>
      <p class="text-muted text-sm">
        &copy; {{ new Date().getFullYear() }} {{ author.name }}
      </p>
    </template>

    <template #right>
      <ULink
        :to="links['privacy-policy']"
        class="text-sm hover:underline inline-flex items-center gap-1"
      >
        {{ $t('footer.privacy-policy') }}
        <UIcon name="i-lucide-external-link" class="size-3 shrink-0" /></ULink>
      |
      <ULink
        :to="links['terms-of-service']"
        class="text-sm hover:underline inline-flex items-center gap-1"
      >
        {{ $t('footer.terms-of-use') }}
        <UIcon name="i-lucide-external-link" class="size-3 shrink-0" /></ULink>
    </template>
  </UFooter>
</template>
