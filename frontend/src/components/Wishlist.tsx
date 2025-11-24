import { useState } from 'react'
import { ThemeToggle } from './ThemeToggle'
import { endpoints } from '../config/api'
import './Wishlist.css'

interface WishlistProps {
  onBack: () => void
}

export function Wishlist({ onBack }: WishlistProps) {
  const [formData, setFormData] = useState({
    email: '',
    reason: ''
  })
  const [submitted, setSubmitted] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      const response = await fetch(endpoints.wishlist, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      })

      if (!response.ok) {
        throw new Error('Error al enviar la solicitud')
      }

      setSubmitted(true)
    } catch (err) {
      setError('Hubo un error al enviar tu solicitud. Por favor intenta de nuevo.')
      console.error('Wishlist submission error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value
    })
  }

  if (submitted) {
    return (
      <div className="wishlist-overlay">
        <ThemeToggle />
        <div className="wishlist-content">
          <div className="logo">
            <div className="logo-t">
              <div className="t-horizontal"></div>
              <div className="t-vertical"></div>
              <span className="dot dot-left"></span>
              <span className="dot dot-right"></span>
              <span className="dot dot-center"></span>
              <span className="dot dot-bottom"></span>
            </div>
          </div>
          <h1 className="wishlist-title">Themis</h1>
          <div className="success-message">
            <h2>¡Gracias por tu interés!</h2>
            <p>Te contactaremos pronto con más información sobre Themis.</p>
            <button onClick={onBack} className="back-button-styled">
              ← Volver a explorar
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="wishlist-overlay">
      <ThemeToggle />
      <div className="wishlist-content">
        <div className="logo">
          <div className="logo-t">
            <div className="t-horizontal"></div>
            <div className="t-vertical"></div>
            <span className="dot dot-left"></span>
            <span className="dot dot-right"></span>
            <span className="dot dot-center"></span>
            <span className="dot dot-bottom"></span>
          </div>
        </div>
        <h1 className="wishlist-title">Themis</h1>
        <p className="wishlist-tagline">
          Únete a la lista de espera para acceder a nuestro sistema de auditoría de licitaciones públicas
        </p>

        <form onSubmit={handleSubmit} className="wishlist-form">
          <div className="form-group">
            <label htmlFor="email">Correo electrónico</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="reason">¿Por qué te interesa Themis?</label>
            <textarea
              id="reason"
              name="reason"
              value={formData.reason}
              onChange={handleChange}
              rows={4}
              required
              disabled={loading}
            />
          </div>

          {error && <div className="error-message">{error}</div>}

          <button type="submit" className="submit-button" disabled={loading}>
            {loading ? 'Enviando...' : 'Unirse a la lista de espera'}
          </button>

          <button type="button" onClick={onBack} className="cancel-button" disabled={loading}>
            Cancelar
          </button>
        </form>
      </div>
    </div>
  )
}
