import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api'

interface UploadState {
  progress: number
  uploading: boolean
  error: string | null
}

export function useUpload() {
  const navigate = useNavigate()
  const [state, setState] = useState<UploadState>({ progress: 0, uploading: false, error: null })

  async function upload(file: File) {
    setState({ progress: 0, uploading: true, error: null })
    const formData = new FormData()
    formData.append('file', file)

    try {
      const { data } = await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setState((s) => ({ ...s, progress: Math.round((e.loaded / e.total!) * 100) }))
        },
      })
      navigate(`/results/${data.document_id}`)
    } catch (err: any) {
      setState({ progress: 0, uploading: false, error: err.response?.data?.detail ?? 'Upload failed' })
    }
  }

  return { ...state, upload }
}
