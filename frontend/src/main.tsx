import React from 'react'
import ReactDOM from 'react-dom/client'
import { Navigate, RouterProvider, createBrowserRouter } from 'react-router-dom'

import App from './App'
import AboutPage from './routes/AboutPage'
import ComparisonPage from './routes/ComparisonPage'
import HowToPage from './routes/HowToPage'
import PromptsPage from './routes/PromptsPage'
import RubricsPage from './routes/RubricsPage'
import ScoringPage from './routes/ScoringPage'
import './index.css'

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/prompts" replace /> },
      { path: 'prompts', element: <PromptsPage /> },
      { path: 'rubrics', element: <RubricsPage /> },
      { path: 'scoring', element: <ScoringPage /> },
      { path: 'comparison', element: <ComparisonPage /> },
      { path: 'how-to', element: <HowToPage /> },
      { path: 'about', element: <AboutPage /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
