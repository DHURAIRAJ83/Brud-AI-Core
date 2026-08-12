import Button from '../../components/Button.jsx'

export default function SettingsTab({ settings, logLevel, setLogLevel, saveSettings }) {
  if (!settings) return null
  return (
    <form className="inline-form training-form" onSubmit={saveSettings}>
      <h3>Configuration</h3>
      <label>Log level
        <select value={logLevel} onChange={(e) => setLogLevel(e.target.value)}>
          <option value="debug">debug</option>
          <option value="info">info</option>
          <option value="warning">warning</option>
          <option value="error">error</option>
        </select>
      </label>
      <p className="notice">Runtime backend: <strong>{settings.config?.runtime_backend ?? 'none'}</strong> -- MB-01 supports no other value; no model is downloaded or loaded in this phase.</p>
      <Button type="submit">Save configuration</Button>
    </form>
  )
}
