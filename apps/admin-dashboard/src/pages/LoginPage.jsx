import { useState } from 'react'

export default function LoginPage({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  async function submit(event) {
    event.preventDefault(); setLoading(true); setError('')
    try { await onLogin(username, password); setPassword('') } catch { setError('Invalid username or password.') } finally { setLoading(false) }
  }
  return <main className="login-shell"><form className="login-card" onSubmit={submit}>
    <div className="login-mark">B</div><small>BRUD AI CONTROL CENTER</small><h1>Admin sign in</h1>
    <p>Use a local administrator account to manage training data.</p>
    {error && <div className="form-error" role="alert">{error}</div>}
    <label>Username<input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required /></label>
    <label>Password<input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
    <button disabled={loading}>{loading ? 'Signing in…' : 'Sign in'}</button>
  </form></main>
}
