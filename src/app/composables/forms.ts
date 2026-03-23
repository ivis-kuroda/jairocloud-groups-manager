import * as z from 'zod'

import type { MaybeRefOrGetter } from 'vue'
import type { FormErrorEvent } from '@nuxt/ui'

export type FormMode = 'new' | 'edit' | 'view'

const hasViewportReference = (
  object: unknown,
): object is { viewportRef: Ref<HTMLDivElement | null> } => {
  return (
    typeof object === 'object'
    && object !== null
    && 'viewportRef' in object
  )
}

/** Composable to make a select menu support infinite scroll */
const useSelectMenuInfiniteScroll = <T>(
  options: UseSelectMenuInfiniteScrollOptions<T>,
): UseSelectMenuInfiniteScrollReturn => {
  const {
    url,
    limit = 20,
    transform,
    debounce = 300,
    scrollDistance = 10,
    query = {},
    server = true,
  } = options

  const page = ref(1)
  const hasMore = ref(true)

  const searchTerm = ref('')
  const searchTermDebounced = refDebounced(searchTerm, debounce)

  const items = ref<Array<{ label: string, value: string }>>([])

  const { data, status, execute } = useApiFetch<SearchResult<T>>(url, {
    query: computed(() => ({
      ...query,
      q: searchTermDebounced.value || undefined,
      p: page.value,
      l: server ? limit : -1,
    })),
    lazy: true,
    immediate: false,
    watch: false,
  })

  watch(data, (newData) => {
    if (!newData) return

    const transformedItems = newData.resources.map(element => transform(element))
    items.value = page.value === 1 ? transformedItems : [...items.value, ...transformedItems]

    hasMore.value = items.value.length < newData.total
  })

  watch(searchTermDebounced, () => {
    if (!server) return
    page.value = 1
    hasMore.value = true
    execute()
  })

  const onOpen = (isOpen: boolean) => {
    if (isOpen && items.value.length === 0) {
      execute()
    }
  }

  const setupInfiniteScroll = (
    selectMenuReference: Ref<unknown>,
  ) => {
    const getViewportReference = () => {
      const reference = selectMenuReference.value
      if (Array.isArray(reference)) {
        return reference[0]?.viewportRef
      }
      if (hasViewportReference(reference)) {
        return reference.viewportRef
      }
      return
    }

    onMounted(() => {
      useInfiniteScroll(
        getViewportReference(),
        () => {
          if (hasMore.value && status.value !== 'pending') {
            page.value++
            execute()
          }
        },
        {
          distance: scrollDistance,
          canLoadMore: () => hasMore.value && status.value !== 'pending',
        },
      )
    })
  }

  return {
    /** Items for the select menu */
    items,
    /** Search term for filtering items */
    searchTerm,
    /** Status of the fetch request */
    status,
    /** Callback for when the select menu is opened */
    onOpen,
    /** Setup select menu infinite scroll */
    setupInfiniteScroll,
  }
}

/** Provides state and default data for repository forms */
const useRepositoryForm = () => {
  const defaultData: Required<RepositoryDetail> = {
    id: '',
    serviceName: '',
    serviceUrl: '',
    entityIds: [''],
    spConnectorId: '',
    active: false,
    created: '',
    groupsCount: 0,
    usersCount: 0,
  }
  const { groupsCount, usersCount, ...defaultForm } = defaultData
  const state = reactive<RepositoryForm>({ ...defaultForm })

  const { id, spConnectorId, created, ...defaultCreateForm } = defaultForm
  const stateAsCreate = reactive<RepositoryCreateForm>({ ...defaultCreateForm })

  return {
    /** Default data for repository forms */
    defaultData,
    /** Reactive state for repository forms */
    state,
    /** Reactive state for create repository forms */
    stateAsCreate,
  }
}

/** Provides schema for repository forms */
const useRepositorySchema = (mode?: MaybeRefOrGetter<FormMode>) => {
  const { t: $t } = useI18n()

  const { repositories: { maxUrlLength } } = useAppConfig()

  const createSchema = computed(() => z.object({
    serviceName: z.string().min(1, $t('repository.validation.serviceName.required')),
    serviceUrl: z.string()
      .min(1, $t('repository.validation.serviceUrl.required'))
      .max(maxUrlLength, $t('repository.validation.serviceUrl.max-length', { max: maxUrlLength }))
      .regex(
        /^(?!-)[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$/,
        $t('repository.validation.serviceUrl.invalid'),
      )
      .transform(value => `https://${value}`)
      .pipe(z.string().url($t('repository.validation.serviceUrl.invalid'))),
    entityIds: z.array(z.string().min(1, $t('repository.validation.entityIds.required')))
      .nonempty($t('repository.validation.entityIds.at-least-one')),
    active: z.boolean(),
  }))

  const updateSchema = computed(() => z.object({
    id: z.string(),
    serviceName: z.string().min(1, $t('repository.validation.serviceName.required')),
    serviceUrl: z.string(),
    entityIds: z.array(z.string().min(1, $t('repository.validation.entityIds.required')))
      .nonempty($t('repository.validation.entityIds.at-least-one')),
    active: z.boolean(),
  }))

  const getSchemaByMode = (m: FormMode) => {
    return m === 'new' ? createSchema.value : updateSchema.value
  }

  const schema = mode
    ? computed(() => {
        const currentMode = toValue(mode)
        return getSchemaByMode(currentMode)
      })
    : undefined

  return {
    /** Schema for repository forms */
    schema,
    /** Maximum URL length for repository forms */
    maxUrlLength,
  }
}

/** Provides state and default data for group forms */
const useGroupForm = () => {
  const defaultData: Required<GroupDetail> = {
    id: '',
    userDefinedId: '',
    displayName: '',
    description: '',
    repository: { id: '', serviceName: '' },
    type: 'group',
    public: false,
    memberListVisibility: 'Private',
    usersCount: 0,
    created: '',
  }

  const { usersCount, ..._defaultForm } = defaultData
  const defaultForm = {
    ..._defaultForm,
    repository: { value: undefined, label: undefined },
  }
  const state = reactive<Omit<GroupForm, 'usersCount'>>({ ...defaultForm })

  const defaultCreateForm: GroupCreateForm = {
    ..._defaultForm,
    repository: { value: undefined, label: undefined },
  }
  const stateAsCreate = reactive<GroupCreateForm>({ ...defaultCreateForm })

  return {
    /** Default data for group forms */
    defaultData,
    /** Default form state for group forms */
    defaultForm,
    /** Default create form state for group forms */
    defaultCreateForm,
    /** Reactive state for group forms */
    state,
    /** Reactive state for create group forms */
    stateAsCreate,
  }
}

/** Provides options for group forms */
const useGroupFormOptions = () => {
  const { t: $t } = useI18n()

  const publicStatusOptions = computed(() => [
    { label: $t('group.public-status.public'), value: true },
    { label: $t('group.public-status.private'), value: false },
  ])

  const visibilityOptions = computed(() =>
    VISIBILITY_OPTIONS.map((visibility) => {
      let label = ''
      switch (visibility) {
        case 'Public': {
          label = $t('group.member-list-visibility.public')
          break
        }
        case 'Private': {
          label = $t('group.member-list-visibility.private')
          break
        }
        case 'Hidden': {
          label = $t('group.member-list-visibility.hidden')
          break
        }
      }
      return { label, value: visibility }
    }))

  return {
    /** Select menu items for public status */
    publicStatusOptions,
    /** Select menu items for member list visibility */
    visibilityOptions,
  }
}

/** Provides schema for group forms */
const useGroupSchema = (mode?: MaybeRefOrGetter<FormMode>) => {
  const { t: $t } = useI18n()

  const { groups: { maxIdLength } } = useAppConfig()
  const getMaxIdLength = (repositoryId: string) => maxIdLength - repositoryId.length

  const createSchema = computed(() => z.object({
    userDefinedId: z.string()
      .min(1, $t('group.validation.groupId.required'))
      .regex(/^[a-zA-Z0-9._-]+$/, $t('group.validation.groupId.invalid-format')),
    displayName: z.string().min(1, $t('group.validation.displayName.required')),
    description: z.string().optional(),
    repository: z.object({
      value: z.string({
        // eslint-disable-next-line camelcase
        required_error: $t('group.validation.repository.id.required'),
      }).min(1, $t('group.validation.repository.id.required')),
    }),
    public: z.boolean().default(false),
    memberListVisibility: z.enum(VISIBILITY_OPTIONS, {
      errorMap: () => ({ message: $t('group.validation.memberListVisibility.invalid') }),
    }).default('Private'),
  }).superRefine((data, context) => {
    const maxIdLength = getMaxIdLength(data.repository?.value || '')
    if (data.userDefinedId && data.userDefinedId.length > maxIdLength) {
      context.addIssue({
        code: z.ZodIssueCode.too_big,
        maximum: maxIdLength,
        type: 'string',
        path: ['userDefinedId'],
        inclusive: true,
        message: $t('group.validation.groupId.max-length', { max: maxIdLength }),
      })
    }
  }))

  const updateSchema = computed(() => z.object({
    displayName: z.string().min(1, $t('group.validation.displayName.required')),
    description: z.string().optional(),
    public: z.boolean().default(false),
    memberListVisibility: z.enum(VISIBILITY_OPTIONS, {
      errorMap: () => ({ message: $t('group.validation.memberListVisibility.invalid') }),
    }).default('Private'),
  }))

  const getSchemaByMode = (m: FormMode) => {
    return m === 'new' ? createSchema.value : updateSchema.value
  }

  const schema = mode
    ? computed(() => {
        const currentMode = toValue(mode)
        return getSchemaByMode(currentMode)
      })
    : undefined

  return {
    /** Schema for group forms */
    schema,
    /** Get the maximum ID length based on the repository ID */
    getMaxIdLength,
  }
}

/** Provides reactive state and default data for user forms */
const useUserForm = () => {
  const defaultData: Required<UserDetail> = {
    id: '',
    eppns: [''],
    userName: '',
    emails: [''],
    preferredLanguage: undefined as unknown as PreferredLanguage,
    isSystemAdmin: false,
    repositoryRoles: [{ id: '', serviceName: '', userRole: undefined }],
    groups: [{ id: '', displayName: '' }],
    created: '',
    lastModified: '',
  }
  const { repositoryRoles, groups, ..._defaultForm } = defaultData
  const defaultForm: UserForm = {
    ..._defaultForm,
    repositoryRoles: [{ value: undefined, label: undefined, userRole: undefined }],
    groups: [{ value: undefined, label: undefined }],
  }
  const state = reactive<UserForm>({ ...defaultForm })

  const { id, created, lastModified, ...defaultCreateForm } = defaultForm
  const stateAsCreate = reactive<UserCreateForm>({ ...defaultCreateForm })

  return {
    /** Default data for user forms */
    defaultData,
    /** Default form state for user forms */
    defaultForm,
    /** Default create form state for user forms */
    defaultCreateForm,
    /** Reactive state for user forms */
    state,
    /** Reactive state for create user forms */
    stateAsCreate,
  }
}

/** Provides options for user forms */
const useUserFormOptions = () => {
  const { t: $t } = useI18n()

  const langLabel = computed(() => ({
    ja: $t('user.preferred-language-ja'),
    en: $t('user.preferred-language-en'),
  }))

  const preferredLanguageOptions = computed(() =>
    PREFERRED_LANGUAGE
      .filter(Boolean)
      .map(lang => ({
        label: lang ? langLabel.value[lang] : undefined,
        value: lang,
      })))

  const userRoleOptions = computed(() => {
    const roles = {
      repositoryAdmin: $t('users.roles.repository-admin'),
      communityAdmin: $t('users.roles.community-admin'),
      contributor: $t('users.roles.contributor'),
      generalUser: $t('users.roles.general-user'),
    }
    return Object.entries(roles).map(([key, label]) => ({
      label,
      value: key,
    }))
  })

  return {
    /** Select menu items for preferred language */
    preferredLanguageOptions,
    /** Select menu items for user roles */
    userRoleOptions,
  }
}

/**
 * Provides schema for user forms
 * @param mode form mode to return the corresponding schema.
 */
const useUserSchema = (mode?: MaybeRefOrGetter<FormMode>) => {
  const { t: $t } = useI18n()
  const userRoles = Object.keys(USER_ROLES) as [string, ...string[]]

  const createSchema = computed(() => z.object({
    eppns: z.array(z.string()
      .min(1, $t('user.validation.eppns.required')))
      .nonempty($t('user.validation.eppns.at-least-one')),
    userName: z.string().min(1, $t('user.validation.userName.required')),
    emails: z.array(z.string()
      .min(1, $t('user.validation.emails.required'))
      .email($t('user.validation.emails.invalid')),
    ).nonempty($t('user.validation.emails.at-least-one')),
    preferredLanguage: z.enum(PREFERRED_LANGUAGE, {
      errorMap: () => ({ message: $t('user.validation.preferredLanguage.invalid') }),
    }).optional().nullable(),
    isSystemAdmin: z.boolean().default(false),
    repositoryRoles: z.array(z.object({
      value: z.string().optional(),
      userRole: z.enum(userRoles).optional(),
    })),
    groups: z.array(z.object({ value: z.string().optional() })).optional(),
  }).superRefine((data, context) => {
    if (data.isSystemAdmin === true) {
      const hasFilledRole = data.repositoryRoles.some(role => role.value || role.userRole)
      if (hasFilledRole) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: $t('user.validation.repositoryRoles.must-be-empty-for-system-admin'),
          path: ['repositoryRoles'],
        })
      }
      if (data.groups && data.groups.some(group => group.value)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: $t('user.validation.groups.must-be-empty-for-system-admin'),
          path: ['groups'],
        })
      }
    }
    else {
      for (const [index, role] of data.repositoryRoles.entries()) {
        if (role.value || role.userRole) {
          if (!role.value || role.value.length === 0) {
            context.addIssue({
              code: z.ZodIssueCode.custom,
              message: $t('user.validation.repositoryRoles.id.required'),
              path: ['repositoryRoles', index, 'id'],
            })
          }
          if (!role.userRole) {
            context.addIssue({
              code: z.ZodIssueCode.custom,
              message: $t('user.validation.repositoryRoles.userRole.required'),
              path: ['repositoryRoles', index, 'userRole'],
            })
          }
        }
      }

      const hasValidRole = data.repositoryRoles.some(role => role.value && role.userRole)
      if (!hasValidRole) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: $t('user.validation.repositoryRoles.at-least-one'),
          path: ['repositoryRoles'],
        })
      }
    }
  }))

  const updateSchema = computed(() => z.object({
    eppns: z.array(z.string().optional()).optional(),
    userName: z.string().optional(),
    emails: z.array(z.string().optional()).optional(),
    preferredLanguage: z.string().optional().nullable(),
    isSystemAdmin: z.boolean().default(false),
    repositoryRoles: z.array(z.object({
      value: z.string().optional(),
      userRole: z.enum(userRoles).optional(),
    })),
    groups: z.array(z.object({ value: z.string().optional() })).optional(),
  }).superRefine((data, context) => {
    if (data.isSystemAdmin === true) {
      const hasFilledRole = data.repositoryRoles.some(role => role.value || role.userRole)
      if (hasFilledRole) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: $t('user.validation.repositoryRoles.must-be-empty-for-system-admin'),
          path: ['repositoryRoles'],
        })
      }
      if (data.groups && data.groups.some(group => group.value)) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: $t('user.validation.groups.must-be-empty-for-system-admin'),
          path: ['groups'],
        })
      }
    }
    else {
      for (const [index, role] of data.repositoryRoles.entries()) {
        if (role.value || role.userRole) {
          if (!role.value || role.value.length === 0) {
            context.addIssue({
              code: z.ZodIssueCode.custom,
              message: $t('user.validation.repositoryRoles.id.required'),
              path: ['repositoryRoles', index, 'id'],
            })
          }
          if (!role.userRole) {
            context.addIssue({
              code: z.ZodIssueCode.custom,
              message: $t('user.validation.repositoryRoles.userRole.required'),
              path: ['repositoryRoles', index, 'userRole'],
            })
          }
        }
      }

      const hasValidRole = data.repositoryRoles.some(role => role.value && role.userRole)
      if (!hasValidRole) {
        context.addIssue({
          code: z.ZodIssueCode.custom,
          message: $t('user.validation.repositoryRoles.at-least-one'),
          path: ['repositoryRoles'],
        })
      }
    }
  }))

  const getSchemaByMode = (m: FormMode) => {
    return m === 'new' ? createSchema.value : updateSchema.value
  }

  const schema = mode
    ? computed(() => {
        const currentMode = toValue(mode)
        return getSchemaByMode(currentMode)
      })
    : undefined

  return {
    /** Schema for user forms */
    schema,
  }
}

/** Provides form error handling */
const useFormError = () => {
  const { t: $t } = useI18n()
  const toast = useToast()

  const handleFormError = (event: FormErrorEvent) => {
    toast.add({
      title: $t('toast.error.validation.title'),
      description: $t('toast.error.validation.description'),
      color: 'error',
      icon: 'i-lucide-circle-x',
    })

    focusFirstError(event)
  }

  return {
    /** Show form error toast and focus the first error field */
    handleFormError,
  }
}

const focusFirstError = (event: FormErrorEvent) => {
  const errorId = event?.errors?.[0]?.id
  if (import.meta.client && errorId) {
    nextTick(() => {
      const id = CSS.escape(errorId)
      const element = document.querySelector(`#${id}`) as HTMLElement
      element?.focus()
      element?.scrollIntoView({ behavior: 'smooth', block: 'center' })
    })
  }
}

export {
  useRepositoryForm, useRepositorySchema,
  useGroupForm, useGroupSchema, useGroupFormOptions,
  useUserForm, useUserSchema, useUserFormOptions,
  useFormError, useSelectMenuInfiniteScroll,
}
