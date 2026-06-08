import { useEffect } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import PlaceholderPage from './pages/PlaceholderPage'
import SettingsPage from './pages/SettingsPage'
import QuotaTrackerPage from './pages/QuotaTrackerPage'
import UsagePage from './pages/UsagePage'
import EndpointPage from './pages/EndpointPage'
import ProvidersPage from './pages/ProvidersPage'
import ProviderDetailPage from './pages/ProviderDetailPage'
import ErrorBoundary from './components/ErrorBoundary'
import MitmPage from './pages/MitmPage'
import CLIToolsPage from './pages/CLIToolsPage'
import ProxyPoolsPage from './pages/ProxyPoolsPage'
import SkillsPage from './pages/SkillsPage'
import MediaProvidersPage from './pages/MediaProvidersPage'
import MediaProviderDetailPage from './pages/MediaProviderDetailPage'
import CombosPage from './pages/CombosPage'
import ConsoleLogPage from './pages/ConsoleLogPage'
import ChatPage from './pages/ChatPage'
import CallbackPage from './pages/CallbackPage'
import AuthLayout from './components/layouts/AuthLayout'
import DashboardLayout from './components/layouts/DashboardLayout'
import { useAuthStore } from './stores/authStore'
import useCatalogStore from './stores/catalogStore'

function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  const fetchCatalog = useCatalogStore((s) => s.fetchCatalog)
  const catalogLoaded = useCatalogStore((s) => s.loaded)

  useEffect(() => {
    if (isAuthenticated && !catalogLoaded) {
      fetchCatalog()
    }
  }, [isAuthenticated, catalogLoaded, fetchCatalog])
  return (
    <Routes>
      <Route path="/login" element={<AuthLayout><LoginPage /></AuthLayout>} />

      {/* Dashboard routes */}
      <Route path="/" element={<ProtectedRoute><DashboardLayout><DashboardPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/endpoints" element={<ProtectedRoute><DashboardLayout><EndpointPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/providers" element={<ProtectedRoute><DashboardLayout><ProvidersPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/providers/:providerId" element={<ProtectedRoute><DashboardLayout><ErrorBoundary fallbackMessage="Provider detail page crashed. This may be due to incompatible provider data."><ProviderDetailPage /></ErrorBoundary></DashboardLayout></ProtectedRoute>} />
      <Route path="/usage" element={<ProtectedRoute><DashboardLayout><UsagePage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/quota-tracker" element={<ProtectedRoute><DashboardLayout><QuotaTrackerPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/mitm" element={<ProtectedRoute><DashboardLayout><MitmPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/cli-tools" element={<ProtectedRoute><DashboardLayout><CLIToolsPage /></DashboardLayout></ProtectedRoute>} />

      {/* Media Providers */}
      <Route path="/media-providers" element={<ProtectedRoute><DashboardLayout><MediaProvidersPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/media-providers/:kind" element={<ProtectedRoute><DashboardLayout><MediaProvidersPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/media-providers/:kind/:providerId" element={<ProtectedRoute><DashboardLayout><MediaProviderDetailPage /></DashboardLayout></ProtectedRoute>} />

      {/* System */}
      <Route path="/combos" element={<ProtectedRoute><DashboardLayout><CombosPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/proxy-pools" element={<ProtectedRoute><DashboardLayout><ProxyPoolsPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/skills" element={<ProtectedRoute><DashboardLayout><SkillsPage /></DashboardLayout></ProtectedRoute>} />

      {/* Debug */}
      <Route path="/console-log" element={<ProtectedRoute><DashboardLayout><ConsoleLogPage /></DashboardLayout></ProtectedRoute>} />
      <Route path="/chat" element={<ProtectedRoute><DashboardLayout><ChatPage /></DashboardLayout></ProtectedRoute>} />

      {/* Settings */}
      <Route path="/settings" element={<ProtectedRoute><DashboardLayout><SettingsPage /></DashboardLayout></ProtectedRoute>} />

      {/* OAuth Callback */}
      <Route path="/callback" element={<CallbackPage />} />

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
