import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { endpoints } from '../config/api'
import './Wishlisted.css'

interface WishlistEntry {
  id: number
  email: string
  reason: string
  created_at: string
}

export function Wishlisted() {
  const navigate = useNavigate()
  const [apiKey, setApiKey] = useState('')
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [entries, setEntries] = useState<WishlistEntry[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(endpoints.wishlist, {
        method: 'GET',
        headers: {
          'X-API-Key': apiKey,
        },
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Invalid API key')
        }
        throw new Error('Error fetching wishlist entries')
      }

      const data = await response.json()
      setEntries(data)
      setIsAuthenticated(true)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
      console.error('Error fetching wishlist:', err)
    } finally {
      setLoading(false)
    }
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString('es-ES', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  }

  if (!isAuthenticated) {
    return (
      <div className="wishlisted-container">
        <div className="wishlisted-content">
          <button onClick={() => navigate('/')} className="back-button">
            ← Volver
          </button>
          <h1 className="wishlisted-title">Wishlist Admin</h1>
          <form onSubmit={handleSubmit} className="api-key-form">
            <div className="form-group">
              <label htmlFor="apiKey">API Key</label>
              <input
                type="password"
                id="apiKey"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Enter admin API key"
                required
                disabled={loading}
              />
            </div>
            {error && <div className="error-message">{error}</div>}
            <button type="submit" className="submit-button" disabled={loading}>
              {loading ? 'Authenticating...' : 'Access Wishlist'}
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="wishlisted-container">
      <div className="wishlisted-content">
        <div className="header-actions">
          <button onClick={() => navigate('/')} className="back-button">
            ← Volver
          </button>
          <button
            onClick={() => {
              setIsAuthenticated(false)
              setApiKey('')
              setEntries([])
            }}
            className="logout-button"
          >
            Logout
          </button>
        </div>
        <h1 className="wishlisted-title">Wishlist Entries ({entries.length})</h1>
        <div className="entries-container">
          {entries.length === 0 ? (
            <p className="no-entries">No entries yet</p>
          ) : (
            <div className="entries-grid">
              {entries.map((entry) => (
                <div key={entry.id} className="entry-card">
                  <div className="entry-header">
                    <span className="entry-id">#{entry.id}</span>
                    <span className="entry-date">{formatDate(entry.created_at)}</span>
                  </div>
                  <div className="entry-email">{entry.email}</div>
                  <div className="entry-reason">
                    <strong>Reason:</strong>
                    <p>{entry.reason}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
