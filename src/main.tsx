import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import App from './App.tsx'
import { LandingPage } from './pages/LandingPage.tsx'
import { PricingPage } from './pages/PricingPage.tsx'
import { PipelinePage } from './pages/PipelinePage.tsx'
import { SignInForm } from './components/auth/SignInForm'
import { SignUpForm } from './components/auth/SignUpForm'
import { AdminDashboard } from './pages/AdminDashboard'
import { AuthGuard } from './components/auth/AuthGuard'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        {/* Public Landing Page */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/signin" element={<SignInForm />} />
        <Route path="/signup" element={<SignUpForm />} />
        
        {/* Authenticated App Routes */}
        <Route
          path="/app"
          element={
            <AuthGuard>
              <App />
            </AuthGuard>
          }
        />
        <Route
          path="/pipeline"
          element={
            <AuthGuard>
              <PipelinePage />
            </AuthGuard>
          }
        />
        <Route
          path="/admin"
          element={
            <AuthGuard requireRole="admin">
              <AdminDashboard />
            </AuthGuard>
          }
        />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
)