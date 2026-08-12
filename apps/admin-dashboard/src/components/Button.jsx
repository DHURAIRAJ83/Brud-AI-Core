export default function Button({
  variant = 'secondary',
  size = 'md',
  as = 'button',
  loading = false,
  disabled = false,
  children,
  className = '',
  ...rest
}) {
  const Component = as
  const classes = ['btn', `btn-${variant}`, `btn-${size}`, loading ? 'btn-loading' : '', className]
    .filter(Boolean)
    .join(' ')
  return (
    <Component
      className={classes}
      disabled={as === 'button' ? (disabled || loading) : undefined}
      aria-busy={loading || undefined}
      {...rest}
    >
      {children}
    </Component>
  )
}
