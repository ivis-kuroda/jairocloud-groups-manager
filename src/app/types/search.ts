/**
 * Types related to recourse search
 */

/** Filter option for search queries */
interface FilterOption {
  key: string
  description?: string
  type: 'string' | 'number' | 'date'
  multiple: boolean
  items?: { value: string | number, label: string }[]
}

/** Repositories query parameters */
interface RepositoriesSearchQuery {
  q?: string
  i?: string[]
  k?: RepositoriesSortableKeys
  d?: SortOrder
  p?: number
  l?: number
}

/** Groups query parameters */
interface GroupsSearchQuery {
  q?: string
  i?: string[]
  r?: string[]
  u?: string[]
  s?: 0 | 1
  v?: 0 | 1 | 2
  k?: GroupsSortableKeys
  d?: SortOrder
  p?: number
  l?: number
}

/** Users query parameters */
interface UsersSearchQuery {
  q?: string
  i?: string[]
  r?: string[]
  g?: string[]
  a?: UserRoleValue[]
  s?: string
  e?: string
  k?: UsersSortableKeys
  d?: SortOrder
  p?: number
  l?: number
}

interface CacheGroupsSearchQuery {
  q?: string
  f?: GroupCacheStatus[]
  p?: number
  l?: number
}

type RepositoriesSortableKeys = 'id' | 'serviceName' | 'serviceUrl' | 'entityIds'

type GroupsSortableKeys = 'id' | 'displayName' | 'public' | 'memberListVisibility'

type UsersSortableKeys = 'id' | 'userName' | 'emails' | 'eppns' | 'lastModified'

type SortOrder = 'asc' | 'desc'

/** General search result structure */
interface SearchResult<T> {
  total: number
  pageSize: number
  offset: number
  resources: T[]
}

/** Repository search result structure */
type RepositoriesSearchResult = SearchResult<RepositorySummary>

/** Group search result structure */
type GroupsSearchResult = SearchResult<GroupSummary>

/** User search result structure */
type UsersSearchResult = SearchResult<UserSummary>

/** Global search result structure */
type GlobalSearchResults = (
  RepositoriesSearchResult & { type: 'repositories' }
  | GroupsSearchResult & { type: 'groups' }
  | UsersSearchResult & { type: 'users' }
)[]

type GroupCachesSearchResult = SearchResult<RepositoryCache>

export type {
  FilterOption,
  RepositoriesSearchQuery, RepositoriesSortableKeys,
  GroupsSearchQuery, GroupsSortableKeys,
  UsersSearchQuery, UsersSortableKeys,
  SortOrder,
  SearchResult, UsersSearchResult, GroupsSearchResult, RepositoriesSearchResult,
  GlobalSearchResults,
  CacheGroupsSearchQuery, GroupCachesSearchResult,
}
