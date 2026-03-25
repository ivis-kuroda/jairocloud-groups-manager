/**
 * Types related to user-defined groups
 */

/** Member list visibility options */
const VISIBILITY_OPTIONS = ['Public', 'Private', 'Hidden'] as const
type Visibility = typeof VISIBILITY_OPTIONS[number]

/** Group summary information */
interface GroupSummary {
  id: string
  displayName: string
  public: boolean
  memberListVisibility: Visibility
  usersCount: number
}

/** Group detailed information */
interface GroupDetail extends GroupSummary {
  type: 'group' | 'role'
  userDefinedId?: string
  description: string
  repository: { id: string, serviceName: string }
  created?: string
}

type GroupForm = Omit<Required<GroupDetail>, 'repository'> & {
  repository: { value?: string, label?: string }
}

type GroupCreateForm = Omit<GroupForm, 'id' | 'created' | 'usersCount'>
type GroupCreatePayload = Omit<GroupCreateForm, 'repository' | 'type'> & {
  repository: { id: string }
}

type GroupUpdateForm = Omit<GroupForm, 'userDefinedId' | 'usersCount'>
type GroupUpdatePayload = Omit<GroupCreatePayload, 'id' | 'userDefinedId' | 'repository'>

export { VISIBILITY_OPTIONS }
export type {
  Visibility,
  GroupSummary, GroupDetail,
  GroupForm, GroupCreateForm, GroupCreatePayload,
  GroupUpdateForm, GroupUpdatePayload,
}
