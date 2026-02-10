import { NavLink, Outlet } from "react-router-dom";

const nav = [
  { to: "/app/overview", label: "Overview" },
  { to: "/app/trades", label: "Trades" },
  { to: "/app/evaluate", label: "Evaluate" },
  { to: "/app/settings/brokers", label: "Brokers" },
];

export function AppShell() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">AnotherSet</div>
        <nav className="nav">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) => (isActive ? "nav-item active" : "nav-item")}
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">Trading Buddy</div>
          <div className="topbar-right">
            <span className="pill">Read-only</span>
            <span className="pill">Mock API</span>
          </div>
        </header>

        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
