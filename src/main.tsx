import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './styles.css'

const tg = window.Telegram?.WebApp
try {
  if (typeof tg?.ready === 'function') tg.ready()
  if (typeof tg?.expand === 'function') tg.expand()
  if (typeof tg?.setHeaderColor === 'function') tg.setHeaderColor('#090b10')
  if (typeof tg?.setBackgroundColor === 'function') tg.setBackgroundColor('#090b10')
} catch {}

class ErrorBoundary extends React.Component<{ children: React.ReactNode }, { error: string | null }> {
  state: { error: string | null } = { error: null }
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : String(e) }
  }
  render() {
    if (this.state.error) {
      return (
        <div className="app" style={{ padding: 24 }}>
          <h1 style={{ margin: '0 0 12px' }}>Ошибка интерфейса</h1>
          <p style={{ color: '#ff9b9b', margin: '0 0 16px' }}>{this.state.error}</p>
          <button onClick={() => this.setState({ error: null })} style={{ border: 0, borderRadius: 12, background: '#f5f7fb', color: '#0b0d12', padding: '12px 16px', fontWeight: 700 }}>Перезагрузить</button>
        </div>
      )
    }
    return this.props.children
  }
}

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')
createRoot(root).render(<React.StrictMode><ErrorBoundary><App /></ErrorBoundary></React.StrictMode>)

declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string
        initDataUnsafe?: { start_param?: string; user?: { id?: number; username?: string; first_name?: string; last_name?: string } }
        ready?: () => void
        expand?: () => void
        setHeaderColor?: (c: string) => void
        setBackgroundColor?: (c: string) => void
      }
    }
  }
}
