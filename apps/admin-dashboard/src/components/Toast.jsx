import { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react'

const ToastContext = createContext(null)

function ToastViewport({ toasts, onDismiss }) {
  if (toasts.length === 0) return null
  return (
    <div className="toast-viewport" role="region" aria-label="Notifications">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.variant}`} role="status">
          <span>{toast.message}</span>
          <button
            type="button"
            className="toast-dismiss"
            aria-label="Dismiss notification"
            onClick={() => onDismiss(toast.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  )
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const nextId = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((previous) => previous.filter((toast) => toast.id !== id))
  }, [])

  const addToast = useCallback((message, { variant = 'info', duration = 5000 } = {}) => {
    const id = ++nextId.current
    setToasts((previous) => [...previous, { id, message, variant }])
    if (duration) setTimeout(() => dismiss(id), duration)
    return id
  }, [dismiss])

  const value = useMemo(() => ({
    addToast,
    success: (message, options) => addToast(message, { ...options, variant: 'success' }),
    error: (message, options) => addToast(message, { ...options, variant: 'error' }),
    dismiss,
  }), [addToast, dismiss])

  return (
    <ToastContext.Provider value={value}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismiss} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used within a ToastProvider')
  return context
}
