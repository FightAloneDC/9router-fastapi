import { Routes, Route, Navigate } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import DashboardPage from './pages/DashboardPage'
import PlaceholderPage from './pages/PlaceholderPage'
import SettingsLayout from './pages/settings/SettingsLayout'
import GeneralSettingsPage from './pages/settings/GeneralSettingsPage'
import SecuritySettingsPage from './pages/settings/SecuritySettingsPage'
import BackupSettingsPage from './pages/settings/BackupSettingsPage'
import RoutingSettingsPage from './pages/settings/RoutingSettingsPage'
import ObservabilitySettingsPage from './pages/settings/ObservabilitySettingsPage'
import NetworkSettingsPage from './pages/settings/NetworkSettingsPage'
import ExperimentalSettingsPage from './pages/settings/ExperimentalSettingsPage'
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

function ProtectedRoute({ children }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated)
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }
  return children
}

function App() {
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
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <DashboardLayout>
              <SettingsLayout />
            </DashboardLayout>
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="general" replace />} />
        <Route path="general" element={<GeneralSettingsPage />} />
        <Route path="security" element={<SecuritySettingsPage />} />
        <Route path="backup" element={<BackupSettingsPage />} />
        <Route path="routing" element={<RoutingSettingsPage />} />
        <Route path="observability" element={<ObservabilitySettingsPage />} />
        <Route path="network" element={<NetworkSettingsPage />} />
        <Route path="experimental" element={<ExperimentalSettingsPage />} />
      </Route>

      {/* OAuth Callback */}
      <Route path="/callback" element={<CallbackPage />} />

      {/* Catch-all redirect */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default App
