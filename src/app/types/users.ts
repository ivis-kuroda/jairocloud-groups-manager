/**
 * Types related to user information
 */

/**
 * User role definitions and values
 */
const USER_ROLES = {
  systemAdmin: 0,
  repositoryAdmin: 1,
  communityAdmin: 2,
  contributor: 3,
  generalUser: 4,
} as const

/** User role type */
type UserRole = keyof typeof USER_ROLES

type UserRoleValue = typeof USER_ROLES[keyof typeof USER_ROLES]

/** User summary information */
interface UserSummary {
  id: string
  userName: string
  role?: UserRole
  emails?: string[]
  eppns?: [string, ...string[]]
  lastModified?: string
}

const PREFERRED_LANGUAGE = ['en', 'ja'] as const
type PreferredLanguage = (typeof PREFERRED_LANGUAGE)[number]

/** Repository affiliated with user including role */
interface RepositoryRole {
  id?: string
  serviceName?: string
  userRole?: UserRole
}

/** User detailed information */
interface UserDetail extends Omit<UserSummary, 'role'> {
  preferredLanguage?: PreferredLanguage
  isSystemAdmin?: boolean
  repositoryRoles?: RepositoryRole[]
  groups?: { id: string, displayName: string }[]
  created?: string
}

type UserForm = Omit<Required<UserDetail>, 'repositoryRoles' | 'groups'> & {
  repositoryRoles: { value?: string, label?: string, userRole?: UserRole }[]
  groups: { value?: string, label?: string }[]
}

type UserCreateForm = Omit<UserForm, 'id' | 'created' | 'lastModified'>
type UserCreatePayload = Omit<UserCreateForm, 'repositoryRoles' | 'groups'> & {
  repositoryRoles: RepositoryRole[]
  groups: { id: string }[]
}

type UserUpdateForm = UserCreateForm
type UserUpdatePayload = UserCreatePayload

export { USER_ROLES, PREFERRED_LANGUAGE }
export type {
  PreferredLanguage, UserRole, UserRoleValue, UserSummary, UserDetail,
  RepositoryRole, UserForm, UserCreateForm, UserCreatePayload,
  UserUpdateForm, UserUpdatePayload,
}
