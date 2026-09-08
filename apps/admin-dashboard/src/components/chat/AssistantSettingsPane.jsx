import { useEffect, useState, useCallback } from 'react'
import Button from '../Button.jsx'
import Skeleton from '../Skeleton.jsx'
import StatusCard from '../StatusCard.jsx'
import {
  psProviders,
  psDiagnostics,
  psCreateProvider,
  psEnableProvider,
  psDisableProvider,
  psSetSecret,
  psDeleteSecret,
  psTestConnection,
} from '../../services/api.js'

const SUPPORTED_PROVIDERS = [
  { key: 'openrouter', label: 'OpenRouter', type: 'external_ai', hasSecrets: true, secretName: 'api_key', desc: 'Gateway to Claude, Llama 3, DeepSeek, Mistral' },
  { key: 'openai', label: 'OpenAI', type: 'external_ai', hasSecrets: true, secretName: 'api_key', desc: 'GPT-4o, GPT-4o-mini' },
  { key: 'anthropic', label: 'Anthropic', type: 'external_ai', hasSecrets: true, secretName: 'api_key', desc: 'Claude 3.5 Sonnet, Claude 3 Haiku' },
  { key: 'gemini', label: 'Google Gemini', type: 'external_ai', hasSecrets: true, secretName: 'api_key', desc: 'Gemini 1.5 Pro, Gemini 1.5 Flash' },
  { key: 'local_llm', label: 'Local LLM / Ollama', type: 'local_model', hasSecrets: false, desc: 'Local llama.cpp / Ollama runtime endpoint' },
  { key: 'faster_whisper', label: 'Faster Whisper (STT)', type: 'speech_stt', hasSecrets: false, desc: 'Local Tamil / English Speech-to-Text' },
  { key: 'coqui_tts', label: 'Coqui TTS (TTS)', type: 'speech_tts', hasSecrets: false, desc: 'Local Tamil Text-to-Speech synthesis' },
]

export default function AssistantSettingsPane({ toast, onNavigate }) {
  const [providers, setProviders] = useState([])
  const [diagnostics, setDiagnostics] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [secretInputs, setSecretInputs] = useState({})
  const [testResults, setTestResults] = useState({})
  const [error, setError] = useState('')

  const loadData = useCallback(async () => {
    try {
      const [provRes, diagRes] = await Promise.all([
        psProviders(),
        psDiagnostics().catch(() => null),
      ])
      setProviders(provRes?.items || [])
      setDiagnostics(diagRes)
    } catch (err) {
      setError(err.message || 'Failed to load provider settings')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadData()
  }, [loadData])

  async function handleCreate(providerKey) {
    setBusy(true)
    setError('')
    try {
      await psCreateProvider(providerKey, true, {})
      toast?.success(`Initialized ${providerKey} provider.`)
      await loadData()
    } catch (err) {
      setError(err.message)
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleToggle(id, currentEnabled) {
    setBusy(true)
    setError('')
    try {
      if (currentEnabled) {
        await psDisableProvider(id)
        toast?.success('Provider disabled.')
      } else {
        await psEnableProvider(id)
        toast?.success('Provider enabled.')
      }
      await loadData()
    } catch (err) {
      setError(err.message)
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleSaveSecret(id, secretName) {
    const inputKey = `${id}:${secretName}`
    const rawValue = (secretInputs[inputKey] || '').trim()
    if (!rawValue) return
    setBusy(true)
    setError('')
    try {
      await psSetSecret(id, secretName, rawValue)
      // Never store plaintext in state or storage; clear input immediately
      setSecretInputs((prev) => ({ ...prev, [inputKey]: '' }))
      toast?.success(`API key encrypted and saved securely.`)
      await loadData()
    } catch (err) {
      setError(err.message)
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleDeleteSecret(id, secretName) {
    setBusy(true)
    setError('')
    try {
      await psDeleteSecret(id, secretName)
      toast?.success('API key removed.')
      await loadData()
    } catch (err) {
      setError(err.message)
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function handleTest(id, secretName) {
    setBusy(true)
    setError('')
    try {
      const res = await psTestConnection(id, secretName || 'api_key')
      setTestResults((prev) => ({ ...prev, [id]: res }))
      if (res.status === 'healthy' || res.status === 'success') {
        toast?.success(`Connection successful (${res.latency_ms}ms)`)
      } else {
        toast?.error(`Connection check: ${res.status} - ${res.error_message || ''}`)
      }
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { status: 'failed', error_message: err.message, latency_ms: 0 },
      }))
      toast?.error(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (loading) {
    return (
      <div className="assistant-settings-pane">
        <Skeleton lines={4} />
      </div>
    )
  }

  return (
    <div className="assistant-settings-pane">
      <div className="assistant-pane-header">
        <div>
          <h3>Assistant &amp; Provider Settings</h3>
          <p className="subtext">
            Configure external AI providers &amp; local models for synthetic dataset generation and assistant reasoning.
          </p>
        </div>
        {onNavigate && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => onNavigate('Mini Brain')}
            title="Open Provider Settings tab in Mini Brain dashboard"
          >
            Dashboard Settings
          </Button>
        )}
      </div>

      {diagnostics && (
        <div className="metric-grid" style={{ marginBottom: 'var(--space-3)' }}>
          <StatusCard
            label="Encryption"
            value={diagnostics.encryption_available ? 'Active (Fernet)' : 'Missing Key'}
            tone={diagnostics.encryption_available ? 'good' : 'warn'}
          />
          <StatusCard
            label="Configured"
            value={diagnostics.configured_provider_count}
            tone="neutral"
          />
          <StatusCard
            label="Enabled"
            value={diagnostics.enabled_provider_count}
            tone="good"
          />
        </div>
      )}

      {error && <div className="notice error-notice">{error}</div>}

      <div className="provider-cards-list">
        {SUPPORTED_PROVIDERS.map((meta) => {
          const configured = providers.find((p) => p.provider_key === meta.key)
          const testRes = configured ? testResults[configured.public_id] : null
          const inputKey = configured ? `${configured.public_id}:${meta.secretName}` : ''
          const secretObj = configured?.secrets?.find((s) => s.secret_name === meta.secretName)

          return (
            <div key={meta.key} className="provider-card">
              <div className="provider-card-head">
                <div>
                  <h4 style={{ margin: 0 }}>
                    {meta.label}{' '}
                    <span
                      className={`badge ${
                        !configured
                          ? 'neutral'
                          : configured.health === 'healthy'
                          ? 'good'
                          : 'warn'
                      }`}
                    >
                      {!configured ? 'Not Configured' : configured.health}
                    </span>
                  </h4>
                  <small className="subtext">{meta.desc}</small>
                </div>
                {configured && (
                  <label className="toggle-label" style={{ fontSize: '0.85rem' }}>
                    <input
                      type="checkbox"
                      checked={configured.enabled}
                      disabled={busy}
                      onChange={() => handleToggle(configured.public_id, configured.enabled)}
                    />
                    {' '}Enabled
                  </label>
                )}
              </div>

              {!configured ? (
                <div style={{ marginTop: 'var(--space-2)' }}>
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={busy}
                    onClick={() => handleCreate(meta.key)}
                  >
                    Setup {meta.label}
                  </Button>
                </div>
              ) : (
                <div className="provider-card-body">
                  {meta.hasSecrets && (
                    <div className="secret-section">
                      <div className="secret-input-row">
                        <input
                          type="password"
                          autoComplete="new-password"
                          placeholder="Enter API key (stored encrypted)"
                          value={secretInputs[inputKey] || ''}
                          onChange={(e) =>
                            setSecretInputs((prev) => ({
                              ...prev,
                              [inputKey]: e.target.value,
                            }))
                          }
                          aria-label={`${meta.label} API Key`}
                        />
                        <Button
                          size="sm"
                          variant="primary"
                          disabled={busy || !(secretInputs[inputKey] || '').trim()}
                          onClick={() => handleSaveSecret(configured.public_id, meta.secretName)}
                        >
                          Save Key
                        </Button>
                      </div>

                      {secretObj && secretObj.is_set && (
                        <div className="secret-status-row">
                          <span className="badge good" style={{ fontSize: '0.75rem' }}>
                            Encrypted &amp; Masked ({secretObj.masked_indicator})
                          </span>
                          <Button
                            size="sm"
                            variant="ghost"
                            disabled={busy}
                            onClick={() => handleDeleteSecret(configured.public_id, meta.secretName)}
                          >
                            Remove
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  <div className="provider-actions-row">
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy}
                      onClick={() => handleTest(configured.public_id, meta.secretName)}
                    >
                      Test Connection
                    </Button>
                    {testRes && (
                      <span
                        className={`test-result-indicator ${
                          testRes.status === 'healthy' || testRes.status === 'success'
                            ? 'text-good'
                            : 'text-warn'
                        }`}
                        style={{ fontSize: '0.85rem' }}
                      >
                        {testRes.status} ({testRes.latency_ms}ms)
                        {testRes.error_message ? `: ${testRes.error_message}` : ''}
                      </span>
                    )}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
