import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'

interface JobStatus {
  status: string
  progress_pct: number | null
  queued_at: string
  started_at: string | null
}

export function useJobStatus(documentId: string) {
  return useQuery<JobStatus>({
    queryKey: ['job-status', documentId],
    queryFn: () => api.get(`/documents/${documentId}/status`).then((r) => r.data),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      return status === 'completed' || status === 'failed' ? false : 2000
    },
  })
}

export function useDocumentResult(documentId: string, enabled: boolean) {
  return useQuery({
    queryKey: ['doc-result', documentId],
    queryFn: () => api.get(`/documents/${documentId}/result`).then((r) => r.data),
    enabled,
  })
}
