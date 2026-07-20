import { Routes, Route } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { LoginPage } from './pages/LoginPage'
import { DashboardLayout } from './layouts/DashboardLayout'
import { DashboardPage } from './pages/DashboardPage'
import { OrganizationsPage } from './pages/OrganizationsPage'
import { PlansPage } from './pages/PlansPage'
import { UsersPage } from './pages/UsersPage'
import { OnboardingPage } from './pages/OnboardingPage'
import { api } from './lib/api'

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null)

  useEffect(() => {
    // Check if user is authenticated
    const checkAuth = async () => {
      try {
        const response = await api.get('/auth/me')
        setIsAuthenticated(true)
      } catch (error) {
        setIsAuthenticated(false)
      }
    }
    checkAuth()
  }, [])

  if (isAuthenticated === null) {
    return <div className="flex h-screen w-screen items-center justify-center">Loading...</div>
  }

  return (
    <Routes>
      <Route path="/login" element={<LoginPage onLogin={() => setIsAuthenticated(true)} />} />
      <Route path="/onboarding" element={<OnboardingPage onComplete={() => setIsAuthenticated(true)} />} />
      
      <Route
        path="/"
        element={
          isAuthenticated ? (
            <DashboardLayout>
              <DashboardPage />
            </DashboardLayout>
          ) : (
            <LoginPage onLogin={() => setIsAuthenticated(true)} />
          )
        }
      />
      
      <Route
        path="/organizations"
        element={
          isAuthenticated ? (
            <DashboardLayout>
              <OrganizationsPage />
            </DashboardLayout>
          ) : (
            <LoginPage onLogin={() => setIsAuthenticated(true)} />
          )
        }
      />
      
      <Route
        path="/plans"
        element={
          isAuthenticated ? (
            <DashboardLayout>
              <PlansPage />
            </DashboardLayout>
          ) : (
            <LoginPage onLogin={() => setIsAuthenticated(true)} />
          )
        }
      />
      
      <Route
        path="/users"
        element={
          isAuthenticated ? (
            <DashboardLayout>
              <UsersPage />
            </DashboardLayout>
          ) : (
            <LoginPage onLogin={() => setIsAuthenticated(true)} />
          )
        }
      />
    </Routes>
  )
}

export default App
