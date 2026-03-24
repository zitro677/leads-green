import { useState } from 'react'
import SyntaxHighlighter from 'react-syntax-highlighter'
import { githubGist } from 'react-syntax-highlighter/dist/esm/styles/hljs'

interface Props {
  plainText: string
  jsonData: object
  onDownload: () => void
}

export default function TextViewer({ plainText, jsonData, onDownload }: Props) {
  const [tab, setTab] = useState<'text' | 'json'>('text')

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {(['text', 'json'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded text-sm font-medium ${
              tab === t ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {t === 'text' ? 'Plain Text' : 'JSON View'}
          </button>
        ))}
        <button
          onClick={onDownload}
          className="ml-auto px-4 py-1.5 rounded text-sm font-medium bg-green-600 text-white hover:bg-green-700"
        >
          Download JSON
        </button>
      </div>

      {tab === 'text' ? (
        <pre className="bg-gray-50 rounded-lg p-4 text-sm text-gray-800 whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
          {plainText}
        </pre>
      ) : (
        <div className="max-h-[60vh] overflow-y-auto rounded-lg">
          <SyntaxHighlighter language="json" style={githubGist} customStyle={{ borderRadius: '0.5rem', fontSize: '0.8rem' }}>
            {JSON.stringify(jsonData, null, 2)}
          </SyntaxHighlighter>
        </div>
      )}
    </div>
  )
}
