/**
 * Types related to cache groups
 */

/** Cache group summary information */
interface RepositoryCache extends RepositorySummary {
  updated?: string
  status?: 'success' | 'failed'
}

/** Detail information of a cache groups update task */
interface TaskDetail {
  results: RepositoryCache[]
  current: string
  done: number
  total: number
}

/** Group cache status for filtering */
type GroupCacheStatus = 'e' | 'n'

/** Group cache update action */
type GroupCacheUpdateAction = 'all' | 'id-specified'

export type {
  RepositoryCache, TaskDetail,
  GroupCacheStatus, GroupCacheUpdateAction,
}
