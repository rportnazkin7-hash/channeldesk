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

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')
createRoot(root).render(<React.StrictMode><App /></React.StrictMode>)

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
