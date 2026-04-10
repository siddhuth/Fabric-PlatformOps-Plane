import { Routes, Route, NavLink } from 'react-router-dom'
import PlatformOverview from './pages/PlatformOverview'
import AccessMatrix from './pages/AccessMatrix'
import ProvisionFlow from './pages/ProvisionFlow'
import AuditLog from './pages/AuditLog'
import DriftDashboard from './pages/DriftDashboard'

const navItems = [
  { to: '/', label: 'Platforms' },
  { to: '/access-matrix', label: 'Access Matrix' },
  { to: '/provisioning', label: 'Provisioning' },
  { to: '/audit-log', label: 'Audit Log' },
  { to: '/drift', label: 'Drift' },
]

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-gray-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
                FA
              </div>
              <span className="font-semibold text-gray-900 hidden sm:block">
                Fabric Access Platform
              </span>
            </div>
            <nav className="flex gap-1">
              {navItems.map(({ to, label }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                      isActive
                        ? 'bg-gray-100 text-gray-900'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`
                  }
                >
                  {label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        <Routes>
          <Route path="/" element={<PlatformOverview />} />
          <Route path="/access-matrix" element={<AccessMatrix />} />
          <Route path="/provisioning" element={<ProvisionFlow />} />
          <Route path="/audit-log" element={<AuditLog />} />
          <Route path="/drift" element={<DriftDashboard />} />
        </Routes>
      </main>
    </div>
  )
}
