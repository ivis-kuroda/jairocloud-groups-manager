/**
 * Utility functions for resource search
 */

import { camelCase } from 'scule'

import type { LocationQuery } from 'vue-router'

const pickSingle = <T = string>(
  value: unknown, { camel }: { camel?: boolean } = {},
): T | undefined => {
  const _ = Array.isArray(value) ? value[0]?.toString() : value?.toString()
  return camel ? camelCase(_ as string) as T : _ as T
}

const toArray = (value: unknown): string[] => (
  Array.isArray(value) ? value : (value ? [value.toString()] : [])
)

/**
 * Normalize location query to repositories search query
 */
const normalizeRepositoriesQuery = (query: LocationQuery): RepositoriesSearchQuery => {
  const { table: { pageSize } } = useAppConfig()
  return {
    q: query.q ? pickSingle(query.q) : undefined,
    i: query.i ? toArray(query.i) : undefined,
    k: query.k ? pickSingle(query.k, { camel: true }) : undefined,
    d: query.d ? pickSingle(query.d) as SortOrder : undefined,
    p: Number(query.p) || 1,
    l: Number(query.l) || pageSize.repositories[0],
  }
}

/** Normalize location query to groups search query */
const normalizeGroupsQuery = (query: LocationQuery): GroupsSearchQuery => {
  const { table: { pageSize } } = useAppConfig()
  return {
    q: query.q ? pickSingle(query.q) : undefined,
    i: query.i ? toArray(query.i) : undefined,
    r: query.r ? toArray(query.r) : undefined,
    u: query.u ? toArray(query.u) : undefined,
    s: query.s === undefined ? undefined : Number(pickSingle(query.s)) as 0 | 1,
    v: query.v === undefined ? undefined : Number(pickSingle(query.v)) as 0 | 1 | 2,
    k: query.k ? pickSingle(query.k, { camel: true }) : undefined,
    d: query.d ? pickSingle(query.d) as SortOrder : undefined,
    p: Number(query.p) || 1,
    l: Number(query.l) || pageSize.groups[0],
  }
}

/**
 * Normalize location query to users search query
 */
const normalizeUsersQuery = (query: LocationQuery): UsersSearchQuery => {
  const { table: { pageSize } } = useAppConfig()
  return {
    q: query.q ? pickSingle(query.q) : undefined,
    i: query.i ? toArray(query.i) : undefined,
    r: query.r ? toArray(query.r) : undefined,
    g: query.g ? toArray(query.g) : undefined,
    a: query.a ? toArray(query.a).map(Number) as UserRoleValue[] : undefined,
    s: query.s?.toString() || undefined,
    e: query.e?.toString() || undefined,
    k: query.k ? pickSingle(query.k, { camel: true }) : undefined,
    d: query.d ? pickSingle(query.d) as SortOrder : undefined,
    p: Number(query.p) || 1,
    l: Number(query.l) || pageSize.users[0],
  }
}

/**
  * Normalize location query to cache groups search query
 */
const normalizeCacheGroupsQuery = (query: LocationQuery): CacheGroupsSearchQuery => {
  const { table: { pageSize } } = useAppConfig()
  return {
    q: query.q ? pickSingle(query.q) : undefined,
    f: query.f ? toArray(query.f) as GroupCacheStatus[] : undefined,
    p: Number(query.p) || 1,
    l: Number(query.l) || pageSize.cacheGroups?.[0],
  }
}

/**
 * Normalize location query to history
 */
const normalizeHistoryQuery = (query: LocationQuery): HistoryQuery => {
  const { table: { pageSize } } = useAppConfig()
  return {
    tab: query.tab ? pickSingle(query.tab) : 'download',
    p: Number(query.p) || 1,
    l: Number(query.l) || pageSize.history?.[0],
    d: query.d ? pickSingle(query.d) : undefined,
    s: query.s?.toString() || undefined,
    e: query.e?.toString() || undefined,
    o: query.o ? toArray(query.o) : undefined,
    r: query.r ? toArray(query.r) : undefined,
    g: query.g ? toArray(query.g) : undefined,
    u: query.u ? toArray(query.u) : undefined,
    i: query.i ? pickSingle(query.i) : undefined,
  }
}

const normalizeUploadQuery = (query: LocationQuery): UploadQuery => {
  const { table: { pageSize } } = useAppConfig()
  return {
    f: query.f ? toArray(query.f) : undefined,
    p: Number(query.p) || 1,
    l: Number(query.l) || pageSize.bulks?.[0],
  }
}

export {
  normalizeRepositoriesQuery, normalizeGroupsQuery, normalizeUsersQuery,
  normalizeHistoryQuery, normalizeUploadQuery,
  normalizeCacheGroupsQuery,
}
