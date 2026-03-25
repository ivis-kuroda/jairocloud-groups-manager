<!--
 Copyright (C) 2026 National Institute of Informatics.
-->

<script setup lang="ts">
const { setLocale } = useI18n()
const { currentUser, isAuthenticated } = useAuth()
const { currentLocale: locale, locales } = useAvailableLocales()

const { navigation: items, submenu } = useMenu()
</script>

<template>
  <UHeader
    toggle-side="left" mode="slideover"
    :toggle="{ class: isAuthenticated ? '' : 'invisible' }" :menu="{ side: 'left' }"
    :ui="{ header: '[&>div:last-child]:hidden' }"
  >
    <template #title>
      <AppLogo />
    </template>

    <AppSearch v-if="isAuthenticated" />

    <template #right>
      <UColorModeButton />
      <ULocaleSelect
        v-model="locale" :locales="locales" :ui="{ base: 'h-8 w-30 my-auto' }"
        @update:model-value="setLocale($event as AvailableLocaleCode)"
      />

      <UPopover
        v-if="isAuthenticated" arrow
        :content="{ align: 'end' }"
        :ui="{ content: 'p-4 min-w-40' }"
      >
        <UButton
          :label="currentUser?.userName"
          icon="i-lucide-user-circle" color="neutral" variant="subtle"
        />
        <template #content="{ close }">
          <div class="text-xl font-semibold text-highlighted">
            {{ currentUser?.userName }}
          </div>
          <div class="text-xs text-muted mt-1">
            {{ currentUser?.eppn }}
          </div>

          <USeparator class="my-3" />

          <UButton
            v-for="item in submenu" :key="item.id"
            :label="item.label" :to="item.to" :icon="item.icon" :target="item.target"
            :color="item.color" variant="ghost"
            class="w-full justify-start" block
            @click="(event) => { [item.onClick].flat().forEach(fn => fn?.(event)); close(); }"
          />
        </template>
      </UPopover>
    </template>

    <template
      v-if="isAuthenticated"
      #body
    >
      <UBadge
        v-if="currentUser?.isSystemAdmin"
        variant="subtle" color="error" :ui="{ base: 'mb-8 w-45' }"
      >
        {{ $t('users.roles.system-admin') }}
      </UBadge>
      <UNavigationMenu :items="items" orientation="vertical" />
    </template>
  </UHeader>
</template>
