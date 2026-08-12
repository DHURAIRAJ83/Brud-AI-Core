import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const psSubTabs = [
  'Overview', 'External AI', 'OpenAI', 'Anthropic', 'Gemini', 'OpenRouter', 'Speech',
  'STT', 'TTS', 'Local Models', 'Connection Tests', 'Audit', 'Diagnostics',
]

export default function ProviderSettingsTab({
  psSubTab, setPsSubTab,
  psDiag,
  renderPsProviderCard,
  psTestResults,
  psAuditList,
}) {
  return (
    <>
      <p className="notice">
        MB-27 -- Secrets &amp; Provider Settings. Configuration only -- no inference, training,
        or deployment starts from this tab, and no outbound network call happens anywhere here
        except an explicit Test Connection press. API keys are encrypted with a local Fernet key
        (<code>BRUD_SECRET_ENCRYPTION_KEY</code>) before they are ever written to disk, and a
        stored key is never displayed again once saved -- only a masked indicator.
      </p>

      <div className="dataset-tabs">
        {psSubTabs.map((t) => (
          <Button key={t} className={psSubTab === t ? 'active' : ''} onClick={() => setPsSubTab(t)}>{t}</Button>
        ))}
      </div>

      {psSubTab === 'Overview' && (
        <>
          {psDiag && (
            <section className="metric-grid">
              <StatusCard label="Encryption available" value={String(psDiag.encryption_available)} tone={psDiag.encryption_available ? 'good' : 'warn'} />
              <StatusCard label="Configured providers" value={psDiag.configured_provider_count} tone="neutral" />
              <StatusCard label="Enabled providers" value={psDiag.enabled_provider_count} tone="good" />
              <StatusCard label="Unavailable providers" value={psDiag.unavailable_providers.length} tone="warn" />
            </section>
          )}
          {psDiag && psDiag.missing_encryption_key && (
            <div className="notice">
              BRUD_SECRET_ENCRYPTION_KEY is not configured in this environment -- secrets cannot
              be saved until an admin sets it. This is reported honestly, never silently worked
              around by generating a key.
            </div>
          )}
        </>
      )}

      {psSubTab === 'External AI' && (
        <>
          {renderPsProviderCard('openrouter')}
          {renderPsProviderCard('openai')}
          {renderPsProviderCard('anthropic')}
          {renderPsProviderCard('gemini')}
        </>
      )}

      {psSubTab === 'OpenAI' && renderPsProviderCard('openai')}
      {psSubTab === 'Anthropic' && renderPsProviderCard('anthropic')}
      {psSubTab === 'Gemini' && renderPsProviderCard('gemini')}
      {psSubTab === 'OpenRouter' && renderPsProviderCard('openrouter')}

      {psSubTab === 'Speech' && (
        <>
          {renderPsProviderCard('faster_whisper')}
          {renderPsProviderCard('coqui_tts')}
        </>
      )}
      {psSubTab === 'STT' && renderPsProviderCard('faster_whisper')}
      {psSubTab === 'TTS' && renderPsProviderCard('coqui_tts')}

      {psSubTab === 'Local Models' && renderPsProviderCard('local_llm')}

      {psSubTab === 'Connection Tests' && (
        <ul className="notice">
          {Object.entries(psTestResults).map(([providerId, result]) => (
            <li key={providerId}>{result.provider_key} -- {result.status} -- {result.latency_ms}ms{result.error_message ? ` -- ${result.error_message}` : ''}</li>
          ))}
          {!Object.keys(psTestResults).length && <li>No connection tests run yet this session.</li>}
        </ul>
      )}

      {psSubTab === 'Audit' && (
        <ul className="notice">
          {psAuditList.map((e) => (
            <li key={e.public_id}>{e.created_at} -- {e.provider_key} -- {e.action} -- admin: {e.admin_id} -- fields: {e.changed_fields.join(', ') || 'n/a'}</li>
          ))}
          {!psAuditList.length && <li>No audit events yet.</li>}
        </ul>
      )}

      {psSubTab === 'Diagnostics' && (
        <>
          {psDiag && <pre className="notice">{JSON.stringify(psDiag, null, 2)}</pre>}
          {!psDiag && <Skeleton lines={2} />}
        </>
      )}
    </>
  )
}
