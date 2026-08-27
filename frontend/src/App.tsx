import { useEffect, useState } from 'react'

interface HealthResponse {
  status: string
  database: string
}

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetch(`${API_URL}/health`)
      .then((res) => res.json())
      .then((data: HealthResponse) => setHealth(data))
      .catch((err) => setError(String(err)))
  }, [])

  return (
    <div style={{ fontFamily: 'sans-serif', padding: '2rem' }}>
      <h1>AI Eval Tool</h1>
      <p>Skeleton is running. This page confirms the frontend can reach the backend and Postgres.</p>

      {error && <p style={{ color: 'red' }}>Error reaching API: {error}</p>}

      {health ? (
        <ul>
          <li>API status: {health.status}</li>
          <li>Database: {health.database}</li>
        </ul>
      ) : (
        !error && <p>Checking backend health...</p>
      )}
    </div>
  )
}

export default App
