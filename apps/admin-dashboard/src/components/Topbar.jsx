export default function Topbar({ title, onMenu }) {
  return <header className="topbar"><button className="menu" onClick={onMenu} aria-label="Open menu">☰</button><div><small>ADMIN DASHBOARD</small><h1>{title}</h1></div><span className="environment">Development</span></header>
}
