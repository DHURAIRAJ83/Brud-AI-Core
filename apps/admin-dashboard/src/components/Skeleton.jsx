export default function Skeleton({ lines = 1, height = '1rem', width = '100%', className = '' }) {
  return (
    <div className={`skeleton-group ${className}`} role="status" aria-label="Loading">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          className="skeleton-line"
          style={{ height, width: typeof width === 'string' ? width : `${width}px` }}
        />
      ))}
    </div>
  )
}
