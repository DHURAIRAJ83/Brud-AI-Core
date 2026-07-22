export default function Topbar({ title, onMenu, admin, onLogout }) {
  return <header className="topbar"><button className="menu" onClick={onMenu} aria-label="Open menu">☰</button><div><small>ADMIN DASHBOARD</small><h1>{title}</h1></div><div className="admin-actions"><span>{admin?.display_name}</span><button onClick={onLogout}>Log out</button></div></header>
}
