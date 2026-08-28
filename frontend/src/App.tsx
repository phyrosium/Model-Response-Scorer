import { NavLink, Outlet } from 'react-router-dom'
import { useEffect, useState } from 'react'

import { api } from './api/client'

function HealthBadge() {
  const [label, setLabel] = useState('checking...')

  useEffect(() => {
    api
      .health()
      .then((h) => setLabel(`api ${h.status} · db ${h.database}`))
      .catch(() => setLabel('api unreachable'))
  }, [])

  return <span className="pill">{label}</span>
}

export default function App() {
  return (
    <>
      <header className="top">
        <div className="inner">
          <h1>Model Response Scorer</h1>
          <nav>
            <NavLink to="/prompts">Prompts</NavLink>
            <NavLink to="/rubrics">Rubrics</NavLink>
            <NavLink to="/scoring">Scoring</NavLink>
            <NavLink to="/comparison">Comparison</NavLink>
            <NavLink to="/how-to">How-to</NavLink>
            <NavLink to="/about">About</NavLink>
          </nav>
          <div style={{ marginLeft: 'auto' }}>
            <HealthBadge />
          </div>
        </div>
      </header>
      <div className="shell">
        <Outlet />
      </div>
    </>
  )
}
