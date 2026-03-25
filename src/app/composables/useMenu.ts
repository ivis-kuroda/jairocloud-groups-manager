/*
 * Copyright (C) 2026 National Institute of Informatics.
 */

/**
 * Composable to manage the application menu items
 */

import type { ButtonProps, FooterColumn, NavigationMenuItem } from '@nuxt/ui'

export function useMenu() {
  const route = useRoute()
  const { t: $t } = useI18n()
  const { header: { userManualURL } } = useAppConfig()
  const { currentUser, logout } = useAuth()

  const items = computed(() => ([
    {
      label: $t('menu.management'),
      children: [
        {
          label: $t('repositories.title'),
          to: '/repositories',
          icon: 'i-lucide-folder',
        },
        {
          label: $t('groups.title'),
          to: '/groups',
          icon: 'i-lucide-users',
        },
        {
          label: $t('users.title'),
          to: '/users',
          icon: 'i-lucide-user',
        },
      ],
    },
    {
      label: $t('menu.other'),
      children: [
        {
          label: $t('history.title'),
          to: '/history',
          icon: 'i-lucide-clock',

        },
        {
          label: $t('group-caches.title'),
          to: '/group-caches',
          icon: 'i-lucide-database',
          requiredSystemAdmin: true,
        },
      ],
    }]
  ))

  const navigation = computed<NavigationMenuItem[]>(() => items.value.map(section => ([
    { label: section.label, type: 'label' },
    ...section.children
      .filter(item => !item.requiredSystemAdmin || currentUser.value?.isSystemAdmin)
      .map(item => ({
        label: item.label,
        to: item.to,
        icon: item.icon,
        active: route.path.startsWith(item.to),
      })),
  ])))

  const footer = computed<FooterColumn[]>(() => items.value.map(section => ({
    label: section.label,
    children: section.children
      .filter(item => !item.requiredSystemAdmin || currentUser.value?.isSystemAdmin)
      .map(item => ({
        label: item.label,
        to: item.to,
      })),
  })))

  const submenu = computed(() => (
    [
      {
        id: 'profile',
        label: $t('submenu.profile'),
        to: `/users/${currentUser.value?.id}`,
        icon: 'i-lucide-user',
        color: 'neutral',
      },
      userManualURL && {
        id: 'manual',
        label: $t('submenu.manual'),
        target: '_blank',
        to: userManualURL,
        icon: 'i-lucide-book-open',
        color: 'neutral',
      },
      {
        id: 'logout',
        label: $t('submenu.logout'),
        icon: 'i-lucide-log-out',
        color: 'error',
        onClick: logout,
      },
    ] as (ButtonProps & { id: string })[]
  ).filter(Boolean))

  return { navigation, footer, submenu }
}
