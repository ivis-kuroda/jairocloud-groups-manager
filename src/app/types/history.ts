/**
 * Types related to history
 */
interface DownloadHistoryData {
  id: string
  timestamp: string
  operator: UserSummary
  public: boolean
  parentId: string | undefined
  filePath: string
  fileId: string
  fileExists: boolean
  repositoryCount: number
  groupCount: number
  userCount: number
  childrenCount: number
}

interface UploadHistoryData {
  id: string
  timestamp: string
  endTimestamp?: string | undefined
  public: boolean
  operator: UserSummary
  status: 'S' | 'F' | 'P'
  filePath: string
  fileId: string
  repositoryCount: number
  groupCount: number
  userCount: number
}
interface DownloadApiModel {
  resources: DownloadHistoryData[]
  pageSize: number
  total: number
  offset: number
}

interface UploadApiModel {
  resources: UploadHistoryData[]
  pageSize: number
  total: number
  offset: number
}

interface HistoryQuery {
  tab?: 'download' | 'upload'
  p?: number
  l?: number
  d?: string
  s?: string
  e?: string
  o?: string[]
  r?: string[]
  g?: string[]
  u?: string[]
  i?: string[]
}

interface TableConfig {
  enableExpand?: boolean
  showStatus?: boolean
}

interface FilterOptionsResponse {
  operators: SelectOption[]
  target_repositories: SelectOption[]
  target_groups: SelectOption[]
  target_users: SelectOption[]
}

interface SelectOption {
  label: string
  value: string
}

interface StatusConfig {
  label: string
  color: 'success' | 'error' | 'warning' | 'info'
}

interface PublicStatusUpdateRequest {
  public: boolean
}

type ActionRow = DownloadHistoryData | UploadHistoryData

export type { DownloadHistoryData, UploadHistoryData, DownloadApiModel, UploadApiModel,
  HistoryQuery, TableConfig, FilterOptionsResponse, SelectOption, StatusConfig,
  PublicStatusUpdateRequest, ActionRow }
