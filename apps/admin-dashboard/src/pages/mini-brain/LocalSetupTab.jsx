import Button from '../../components/Button.jsx'
import Skeleton from '../../components/Skeleton.jsx'
import StatusCard from '../../components/StatusCard.jsx'

const lcSubTabs = [
  'Hardware', 'Local Models', 'Recommendations', 'Local Configuration', 'External Providers',
  'Diagnostics', 'Setup Guide', 'Help',
]

export default function LocalSetupTab({
  lcSubTab, setLcSubTab,
  lcHardwareData,
  lcSetupBusy, runLcScan, lcScannedModels, selectLcScannedModel,
  loadLcRecommendations, lcRecommendationsData,
  lcLocalForm, setLcLocalForm, saveLcLocalModel, testLcLocalModel,
  lcCatalog, lcProviderForm, updateLcProviderForm, saveLcProvider,
  lcDiag,
  loadLcGuide, lcGuide,
}) {
  return (
    <>
      <p className="notice">
        MB-29 -- Local Model Auto-Setup &amp; Provider Configuration Center. Detects hardware, scans
        admin-approved directories for GGUF files, and recommends a model -- nothing is ever
        downloaded automatically. / வன்பொருளைக் கண்டறிந்து, GGUF கோப்புகளை ஸ்கேன் செய்து, மாடலைப்
        பரிந்துரைக்கிறது -- எதுவும் தானாக பதிவிறக்கப்படாது.
      </p>

      <div className="dataset-tabs">
        {lcSubTabs.map((t) => (
          <Button key={t} className={lcSubTab === t ? 'active' : ''} onClick={() => setLcSubTab(t)}>{t}</Button>
        ))}
      </div>

      {lcSubTab === 'Hardware' && (
        <>
          {lcHardwareData && (
            <section className="metric-grid">
              <StatusCard label="Total RAM" value={`${lcHardwareData.total_ram_gb} GB`} tone="neutral" />
              <StatusCard label="Available RAM" value={`${lcHardwareData.available_ram_gb} GB`} tone="neutral" />
              <StatusCard label="CPU cores / threads" value={`${lcHardwareData.cpu_cores} / ${lcHardwareData.cpu_threads}`} tone="neutral" />
              <StatusCard label="Disk free" value={`${lcHardwareData.disk_free_gb} GB`} tone="neutral" />
              <StatusCard label="RAM tier" value={lcHardwareData.recommended_ram_tier} tone="neutral" />
              <StatusCard label="Health" value={lcHardwareData.health?.health} tone={lcHardwareData.health?.health === 'healthy' ? 'good' : (lcHardwareData.health?.health === 'unconfigured' ? 'neutral' : 'waiting')} />
            </section>
          )}
          {lcHardwareData && !lcHardwareData.psutil_available && (
            <p className="notice">psutil is not installed -- using the standard-library fallback for hardware figures.</p>
          )}
          {!lcHardwareData && <Skeleton lines={2} />}
        </>
      )}

      {lcSubTab === 'Local Models' && (
        <div className="card">
          <Button disabled={lcSetupBusy} onClick={runLcScan}>Scan for local models</Button>
          <table>
            <thead><tr><th>Filename</th><th>Family</th><th>Quant</th><th>Size (GB)</th><th /></tr></thead>
            <tbody>
              {lcScannedModels.map((m) => (
                <tr key={m.absolute_path}>
                  <td>{m.filename}</td><td>{m.inferred_family || '—'}</td><td>{m.inferred_quantization || '—'}</td>
                  <td>{m.size_gb}</td>
                  <td><Button onClick={() => selectLcScannedModel(m.absolute_path)}>Select</Button></td>
                </tr>
              ))}
              {!lcScannedModels.length && <tr><td colSpan={5}>No scan run yet, or no GGUF files found.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {lcSubTab === 'Recommendations' && (
        <div className="card">
          <Button disabled={lcSetupBusy} onClick={loadLcRecommendations}>Get recommendations</Button>
          {lcRecommendationsData && lcRecommendationsData.top_recommendation && (
            <div className="notice">
              <strong>Best for this machine / இந்த கணினிக்கு சிறந்தது:</strong>{' '}
              {lcRecommendationsData.top_recommendation.model_name} ({lcRecommendationsData.top_recommendation.quantization})
              — ~{lcRecommendationsData.top_recommendation.expected_ram_usage_gb}GB RAM,
              {' '}{lcRecommendationsData.top_recommendation.expected_speed.en} / {lcRecommendationsData.top_recommendation.expected_speed.ta}
            </div>
          )}
          <table>
            <thead><tr><th>Model</th><th>RAM (GB)</th><th>Speed</th><th>Tamil</th><th>Coding</th><th>Brud Admin</th></tr></thead>
            <tbody>
              {(lcRecommendationsData?.models || []).map((m) => (
                <tr key={m.model_name}>
                  <td>{m.model_name} ({m.quantization})</td><td>{m.expected_ram_usage_gb}</td>
                  <td>{m.expected_speed.en} / {m.expected_speed.ta}</td>
                  <td>{m.tamil_support.en} / {m.tamil_support.ta}</td>
                  <td>{m.coding_support.en} / {m.coding_support.ta}</td>
                  <td>{m.recommended_for_brud_admin.en} / {m.recommended_for_brud_admin.ta}</td>
                </tr>
              ))}
              {!(lcRecommendationsData?.models || []).length && <tr><td colSpan={6}>Press "Get recommendations" above.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {lcSubTab === 'Local Configuration' && (
        <div className="card">
          <label>Model path</label>
          <input value={lcLocalForm.model_path} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, model_path: e.target.value }))} placeholder="e.g. qwen2.5-1.5b-instruct-q4_k_m.gguf" />
          <label>Context length</label>
          <input type="number" value={lcLocalForm.context_length} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, context_length: e.target.value }))} />
          <label>Max tokens</label>
          <input type="number" value={lcLocalForm.max_tokens} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, max_tokens: e.target.value }))} />
          <label>Temperature</label>
          <input type="number" step="0.05" value={lcLocalForm.temperature} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, temperature: e.target.value }))} />
          <label>Threads</label>
          <input type="number" value={lcLocalForm.threads} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, threads: e.target.value }))} />
          <label>Additional model directories (one per line, optional)</label>
          <textarea rows={3} value={lcLocalForm.additional_model_dirs} onChange={(e) => setLcLocalForm((prev) => ({ ...prev, additional_model_dirs: e.target.value }))} />
          <div>
            <Button disabled={lcSetupBusy} onClick={saveLcLocalModel}>Save</Button>
            <Button disabled={lcSetupBusy || !lcLocalForm.model_path} onClick={testLcLocalModel}>Test local model</Button>
          </div>
        </div>
      )}

      {lcSubTab === 'External Providers' && (
        <>
          {lcCatalog.map((p) => {
            const form = lcProviderForm(p.provider_key)
            return (
              <div className="card" key={p.provider_key}>
                <h4>{p.provider_key}</h4>
                <p className="notice">Context window: {p.context_window} -- Reasoning: {p.reasoning_level.en} / {p.reasoning_level.ta} -- Cost: {p.cost_hint.en} / {p.cost_hint.ta}</p>
                <label>API Key</label>
                <input type="password" value={form.api_key} onChange={(e) => updateLcProviderForm(p.provider_key, { api_key: e.target.value })} placeholder="API Key / API விசையை உள்ளிடவும்" />
                <label>Model</label>
                <select value={form.model} onChange={(e) => updateLcProviderForm(p.provider_key, { model: e.target.value })}>
                  <option value="">-- select --</option>
                  {p.recommended_models.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
                <label>
                  <input type="checkbox" checked={form.enabled} onChange={(e) => updateLcProviderForm(p.provider_key, { enabled: e.target.checked })} />
                  {' '}Enabled / இயக்கப்பட்டது
                </label>
                <div>
                  <Button disabled={lcSetupBusy} onClick={() => saveLcProvider(p.provider_key)}>Save</Button>
                </div>
              </div>
            )
          })}
          {!lcCatalog.length && <Skeleton lines={2} />}
        </>
      )}

      {lcSubTab === 'Diagnostics' && (
        <>
          {lcDiag && <pre className="notice">{JSON.stringify(lcDiag, null, 2)}</pre>}
          {!lcDiag && <Skeleton lines={2} />}
        </>
      )}

      {lcSubTab === 'Setup Guide' && (
        <div className="card">
          <Button disabled={lcSetupBusy} onClick={loadLcGuide}>Build setup guide</Button>
          <ol>
            {(lcGuide?.steps || []).map((s) => (
              <li key={s.step}>
                <strong>{s.title_en} / {s.title_ta}</strong>
                <p>{s.body_en}</p>
                <p>{s.body_ta}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {lcSubTab === 'Help' && (
        <ul className="clean-list">
          <li><strong>Hardware / வன்பொருள்:</strong> Shows RAM, CPU, disk, and a health badge. / RAM, CPU, வட்டு மற்றும் ஆரோக்கிய பதக்கத்தைக் காட்டுகிறது.</li>
          <li><strong>Local Models / உள்ளூர் மாடல்கள்:</strong> Scans admin-approved directories for .gguf files. / அனுமதிக்கப்பட்ட அடைவுகளில் .gguf கோப்புகளை ஸ்கேன் செய்கிறது.</li>
          <li><strong>Recommendations / பரிந்துரைகள்:</strong> Suggests the best model for your machine -- nothing downloads automatically. / உங்கள் கணினிக்கு சிறந்த மாடலைப் பரிந்துரைக்கிறது -- எதுவும் தானாக பதிவிறக்கப்படாது.</li>
          <li><strong>Local Configuration / உள்ளூர் அமைப்பு:</strong> Set the model path and runtime parameters. / மாடல் பாதை மற்றும் இயக்க அளவுருக்களை அமைக்கவும்.</li>
          <li><strong>External Providers / வெளிப்புற வழங்குநர்கள்:</strong> Optional cloud fallback providers. / விருப்பமான cloud மாற்று வழங்குநர்கள்.</li>
        </ul>
      )}
    </>
  )
}
