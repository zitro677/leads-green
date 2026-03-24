import { BrowserRouter, Routes, Route, Navigate, NavLink } from 'react-router-dom'
import Upload from './pages/Upload'
import Results from './pages/Results'
import Dashboard from './pages/Dashboard'
import Webhooks from './pages/Webhooks'
import Login from './pages/Login'
import { useAuthStore } from './store/auth'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.accessToken)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  const token = useAuthStore((s) => s.accessToken)
  const clearToken = useAuthStore((s) => s.clearToken)

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-gray-50">
        {token && (
          <nav className="bg-white border-b border-gray-200 px-6 py-3 flex gap-6 items-center">
            <span className="font-semibold text-gray-900 mr-4">OCR Service</span>
            {[
              { to: '/upload', label: 'Upload' },
              { to: '/dashboard', label: 'Dashboard' },
              { to: '/webhooks', label: 'Webhooks' },
            ].map(({ to, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  isActive ? 'text-blue-600 font-medium' : 'text-gray-600 hover:text-gray-900'
                }
              >
                {label}
              </NavLink>
            ))}
            <button
              onClick={clearToken}
              className="ml-auto text-sm text-gray-500 hover:text-gray-700"
            >
              Sign out
            </button>
          </nav>
        )}
        <main className="max-w-5xl mx-auto px-6 py-8">
          <Routes>
            <Route path="/login" element={token ? <Navigate to="/upload" replace /> : <Login />} />
            <Route path="/" element={<Navigate to={token ? '/upload' : '/login'} replace />} />
            <Route path="/upload" element={<ProtectedRoute><Upload /></ProtectedRoute>} />
            <Route path="/results/:documentId" element={<ProtectedRoute><Results /></ProtectedRoute>} />
            <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
            <Route path="/webhooks" element={<ProtectedRoute><Webhooks /></ProtectedRoute>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
