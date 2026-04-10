import { usePlatformSummary } from '../hooks/useFixtureData'
import { platformColors } from '../lib/platformColors'

export default function PlatformOverview() {
  const data = usePlatformSummary()
  if (!data) return <p className="text-gray-500">Loading...</p>

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">Platform Overview</h1>
        <p className="text-gray-500 mt-1">
          {data.totals.platforms_active} active platforms &middot;{' '}
          {data.totals.total_access_packages} access packages &middot;{' '}
          {data.totals.total_active_users} active users
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {data.platforms.map((p) => {
          const colors = platformColors[p.id] ?? platformColors.all
          const isComingSoon = p.status === 'coming_soon'
          return (
            <div
              key={p.id}
              className={`rounded-xl border-2 ${colors.border} ${colors.bg} p-6 ${
                isComingSoon ? 'opacity-60' : ''
              }`}
            >
              <div className="flex items-center justify-between mb-4">
                <h2 className={`text-lg font-semibold ${colors.text}`}>{p.name}</h2>
                {isComingSoon ? (
                  <span className="text-xs font-medium bg-gray-200 text-gray-600 rounded-full px-2.5 py-0.5">
                    Coming Soon
                  </span>
                ) : (
                  <span className="text-xs font-medium bg-green-100 text-green-800 rounded-full px-2.5 py-0.5">
                    {p.version}
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 gap-3 mb-4">
                <Stat label="Packages" value={p.stats.access_packages} />
                <Stat label="Users" value={p.stats.active_users} />
                {p.stats.drift_findings != null && (
                  <Stat label="Drift Findings" value={p.stats.drift_findings} warn={p.stats.drift_findings > 0} />
                )}
                {p.stats.uc_grants_active != null && (
                  <Stat label="UC Grants" value={p.stats.uc_grants_active} />
                )}
                {p.stats.sql_grants_active != null && (
                  <Stat label="SQL Grants" value={p.stats.sql_grants_active} />
                )}
                {p.stats.scim_groups_synced != null && (
                  <Stat label="SCIM Groups" value={p.stats.scim_groups_synced} />
                )}
              </div>

              {p.stats.last_provision && (
                <p className="text-xs text-gray-500 mb-3">
                  Last provisioned: {new Date(p.stats.last_provision).toLocaleDateString()}
                </p>
              )}
              {p.eta && (
                <p className="text-xs text-gray-500">{p.eta}</p>
              )}

              <div className="mt-4 pt-4 border-t border-gray-200/60">
                <p className="text-xs font-medium text-gray-600 mb-2">Capabilities</p>
                <ul className="space-y-1">
                  {p.capabilities.slice(0, 4).map((c) => (
                    <li key={c} className="text-xs text-gray-500 flex items-start gap-1.5">
                      <span className={`mt-1 w-1.5 h-1.5 rounded-full shrink-0 ${isComingSoon ? 'bg-gray-300' : 'bg-green-500'}`} />
                      {c}
                    </li>
                  ))}
                  {p.capabilities.length > 4 && (
                    <li className="text-xs text-gray-400">+{p.capabilities.length - 4} more</li>
                  )}
                </ul>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function Stat({ label, value, warn }: { label: string; value: number; warn?: boolean }) {
  return (
    <div>
      <p className={`text-xl font-bold ${warn ? 'text-red-600' : 'text-gray-900'}`}>{value}</p>
      <p className="text-xs text-gray-500">{label}</p>
    </div>
  )
}
