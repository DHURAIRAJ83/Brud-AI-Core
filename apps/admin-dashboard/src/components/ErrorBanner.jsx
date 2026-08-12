import Button from './Button.jsx'

export default function ErrorBanner({ title = 'Something went wrong', message, onRetry }) {
  return (
    <div className="error-banner" role="alert">
      <div>
        <strong>{title}</strong>
        <p>{message}</p>
      </div>
      {onRetry && <Button variant="danger" size="sm" onClick={onRetry}>Retry</Button>}
    </div>
  )
}
