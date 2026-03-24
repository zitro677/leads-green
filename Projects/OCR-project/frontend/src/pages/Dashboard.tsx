import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import { DocumentsOverTimeChart, FileTypeChart, OCREngineChart } from '../components/AnalyticsChart'

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
    </div>
  )
}

export default function Dashboard() {
  const { data: summary } = useQuery({
    queryKey: ['analytics-summary'],
    queryFn: () => api.get('/analytics/summary').then((r) => r.data),
  })

  const { data: overtime } = useQuery({
    queryKey: ['analytics-overtime'],
    queryFn: () => api.get('/analytics/usage-over-time?granularity=day').then((r) => r.data),
  })

  if (!summary) return <div className="text-gray-500">Loading analytics…</div>

  const fileTypeData = Object.entries(summary.by_file_type as Record<string, number>).map(([name, value]) => ({ name, value }))
  const engineData = Object.entries(summary.by_ocr_engine as Record<string, number>).map(([engine, count]) => ({ engine, count }))

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Dashboard</h1>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <StatCard label="Total Documents" value={summary.total_documents} />
        <StatCard label="Total Tokens" value={summary.total_tokens.toLocaleString()} />
        <StatCard label="Avg Processing" value={`${(summary.avg_processing_ms / 1000).toFixed(1)}s`} />
        <StatCard label="Error Rate" value={`${(summary.error_rate * 100).toFixed(1)}%`} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">Documents Over Time</h2>
          <DocumentsOverTimeChart data={overtime?.data ?? []} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">File Types</h2>
          <FileTypeChart data={fileTypeData} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-medium text-gray-700 mb-4">OCR Engines Used</h2>
          <OCREngineChart data={engineData} />
        </div>
      </div>
    </div>
  )
}
