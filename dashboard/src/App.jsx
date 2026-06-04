// dashboard/src/App.jsx
import { BrowserRouter, Routes, Route, NavLink } from "react-router-dom";
import LiveDemo from "./pages/LiveDemo";
import Results  from "./pages/Results";
import Slides   from "./pages/Slides";
import "./index.css";

function Nav() {
  return (
    <nav className="app-nav">
      <div className="nav-brand">🚦 Smart Traffic MARL</div>
      <div className="nav-links">
        {[
          { to: "/",        label: "Slides" },
          { to: "/demo",    label: "Live Demo" },
          { to: "/results", label: "Results" },
        ].map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) => `nav-link ${isActive ? "nav-link--active" : ""}`}
          >
            {label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-shell">
        <Nav />
        <main className="app-main">
          <Routes>
            <Route path="/"        element={<Slides />} />
            <Route path="/demo"    element={<LiveDemo />} />
            <Route path="/results" element={<Results />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
