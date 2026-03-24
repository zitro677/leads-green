import { useState } from 'react'
import { useWebhooks, useCreateWebhook, useDeleteWebhook } from '../hooks/useWebhooks'

interface WebhookForm {
  name: string
  url: string
  secret: string
  events: string[]
}

const EMPTY_FORM: WebhookForm = { name: '', url: '', secret: '', events: ['completed'] }

export default function Webhooks() {
  const { data: webhooks = [] } = useWebhooks()
  const createMutation = useCreateWebhook()
  const deleteMutation = useDeleteWebhook()
  const [form, setForm] = useState<WebhookForm>(EMPTY_FORM)
  const [showForm, setShowForm] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    await createMutation.mutateAsync(form)
    setForm(EMPTY_FORM)
    setShowForm(false)
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Webhooks</h1>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700"
        >
          {showForm ? 'Cancel' : 'Add Webhook'}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleSubmit} className="bg-white rounded-xl border border-gray-200 p-6 mb-6 space-y-4">
          {(['name', 'url', 'secret'] as const).map((field) => (
            <div key={field}>
              <label className="block text-sm font-medium text-gray-700 mb-1 capitalize">{field}</label>
              <input
                type={field === 'secret' ? 'password' : 'text'}
                value={form[field]}
                onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
          ))}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Events</label>
            {['completed', 'failed', 'all'].map((ev) => (
              <label key={ev} className="flex items-center gap-2 text-sm text-gray-700 mb-1">
                <input
                  type="checkbox"
                  checked={form.events.includes(ev)}
                  onChange={(e) =>
                    setForm((f) => ({
                      ...f,
                      events: e.target.checked ? [...f.events, ev] : f.events.filter((x) => x !== ev),
                    }))
                  }
                />
                {ev}
              </label>
            ))}
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating…' : 'Create Webhook'}
          </button>
        </form>
      )}

      <div className="space-y-3">
        {webhooks.length === 0 && (
          <p className="text-gray-500 text-sm">No webhooks configured yet.</p>
        )}
        {webhooks.map((wh: { id: string; name: string; url: string; events: string[]; is_active: boolean }) => (
          <div key={wh.id} className="bg-white rounded-xl border border-gray-200 p-5 flex items-center justify-between">
            <div>
              <p className="font-medium text-gray-900">{wh.name}</p>
              <p className="text-sm text-gray-500 mt-0.5">{wh.url}</p>
              <div className="flex gap-1 mt-2">
                {wh.events.map((ev) => (
                  <span key={ev} className="text-xs bg-blue-50 text-blue-700 rounded px-2 py-0.5">{ev}</span>
                ))}
                <span className={`text-xs rounded px-2 py-0.5 ${wh.is_active ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {wh.is_active ? 'active' : 'inactive'}
                </span>
              </div>
            </div>
            <button
              onClick={() => deleteMutation.mutate(wh.id)}
              className="text-sm text-red-600 hover:text-red-700 font-medium"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
