type StatusType = 'create' | 'update' | 'delete' | 'skip' | 'error'

interface EachResult {
  row: number
  id: string
  status: StatusType
  userName: string
  eppn: string[]
  emails: string[]
  groups: string[]
  code?: string
}

interface MissingUser {
  id: string
  name: string
  eppn: string[]
  groups: string[]
}

interface ValidationResults {
  results: EachResult[]
  summary: Summary
  missingUsers: MissingUser[]
  total: number
  offset: number
  pageSize: number
}

interface Summary {
  create: number
  update: number
  delete: number
  skip: number
  error: number
}

interface ExecuteResults {
  results: EachResult[]
  summary: Summary
  fileInfo: {
    fileName: string
    startedAt: string
    completedAt: string
    executedBy: string
  }
  total: number
  offset: number
  pageSize: number
}

interface BulkProcessingStatus {
  status: 'PENDING' | 'STARTED' | 'SUCCESS' | 'FAILURE'
  taskId: string
  historyId?: string
  tempFileId?: string
}
interface ExcuteRequest {
  taskId: string
  repositoryId: string
  tempFileId: string
  deleteUsers: string[]
}

interface UploadQuery {
  f?: string[]
  p?: number
  l?: number
  d?: 'asc' | 'desc'
}

interface ExcuteResponse {
  taskId: string
  historyId: string
}

interface BulkIndicator {
  title: string
  number: number
  color: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info'
  icon: string
  key: StatusType
}
export type { StatusType, EachResult, MissingUser, Summary, ExcuteResponse,
  BulkProcessingStatus, ValidationResults, ExecuteResults, ExcuteRequest,
  UploadQuery, BulkIndicator,
}
