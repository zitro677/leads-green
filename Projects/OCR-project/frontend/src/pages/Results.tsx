import { useParams } from 'react-router-dom'
import { useJobStatus, useDocumentResult } from '../hooks/useJobStatus'
import TextViewer from '../components/TextViewer'
import { api } from '../lib/api'

export default function Results() {
  const { documentId } = useParams<{ documentId: string }>()
  const { data: status } = useJobStatus(documentId!)
  const isDone = status?.status === 'completed'
  const isFailed = status?.status === 'failed'
  const { data: result } = useDocumentResult(documentId!, isDone)

  function downloadJson() {
    window.open(`/api/v1/documents/${documentId}/result/download`, '_blank')
  }

  if (isFailed) {
    return <p className="text-red-600">Processing failed. Please try uploading again.</p>
  }

  if (!isDone || !result) {
    return (
      <div className="max-w-2xl mx-auto text-center py-16">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600 mx-auto mb-4" />
        <p className="text-gray-600 capitalize">{status?.status ?? 'Loading'}…</p>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="flex items-center gap-4 mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Result</h1>
        <div className="flex gap-3 text-sm text-gray-500">
          <span>Engine: <strong>{result.ocr_engine}</strong></span>
          {result.confidence_avg && <span>Confidence: <strong>{result.confidence_avg.toFixed(1)}%</strong></span>}
          <span>Tokens: <strong>{result.tokens_used.toLocaleString()}</strong></span>
          <span>Time: <strong>{(result.processing_ms / 1000).toFixed(1)}s</strong></span>
        </div>
      </div>

      <TextViewer plainText={result.extracted_text} jsonData={result} onDownload={downloadJson} />

      <details className="mt-6">
        <summary className="cursor-pointer text-sm font-medium text-gray-700 mb-2">
          Page breakdown ({result.pages.length} pages)
        </summary>
        <div className="space-y-3 mt-3">
          {result.pages.map((p: { page: number; text: string; confidence: number | null }) => (
            <div key={p.page} className="bg-gray-50 rounded-lg p-4">
              <div className="flex justify-between text-xs text-gray-500 mb-2">
                <span>Page {p.page}</span>
                {p.confidence && <span>Confidence: {p.confidence}%</span>}
              </div>
              <p className="text-sm text-gray-800 whitespace-pre-wrap">{p.text}</p>
            </div>
          ))}
        </div>
      </details>
    </div>
  )
}
