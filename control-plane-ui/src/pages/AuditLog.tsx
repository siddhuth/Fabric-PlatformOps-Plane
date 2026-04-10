import { useState, useMemo } from 'react'
import { useAuditLog } from '../hooks/useFixtureData'
import PlatformBadge from '../components/PlatformBadge'
import StatusBadge from '../components/StatusBadge'
import FilterBar from '../components/FilterBar'
import SnowflakeComingSoon from '../components/SnowflakeComingSoon'
import { platformColors } from '../lib/platformColors'

const actionLabels: Record<string, string> = {
  provision: 'Provision',
  revoke: 'Revoke',
  drift_scan: 'Drift Scan',
  recertification: 'Recertification',
}

export default function AuditLog() {
  const data = useAuditLog()
  const [platform, setPlatform] = useState('all')
  const [search, setSearch] = useState('')
  const [actionFilter, setActionFilter] = useState('all')

  const filtered = useMemo(() => {
    if (!data) return []
    return data.events.filter((e) => {
      if (platform !== 'all' && e.platform !== platform) return false
      if (actionFilter !== 'all' && e.action !== actionFilter) return false
      if (search) {
        const q = search.toLowerCase()
        return (
          e.user_name.toLowerCase().includes(q) ||
          e.details.toLowerCase().includes(q) ||
          e.package.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [data, platform, search, actionFilter])

  if (!data) return <p className="text-gray-500">Loading...</p>

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Audit Log</h1>
        <p className="text-gray-500 mt-1">
          {data.total_events} events over {data.period_days} days
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <FilterBar
          platforms={['fabric', 'databricks']}
          activePlatform={platform}
          onPlatformChange={setPlatform}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder="Search events..."
        />
      </div>

      <div className="flex gap-2 mb-6">
        {['all', 'provision', 'revoke', 'drift_scan', 'recertification'].map((a) => (
          <button
            key={a}
            onClick={() => setActionFilter(a)}
            className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
              actionFilter === a
                ? 'bg-gray-900 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {a === 'all' ? 'All Actions' : actionLabels[a] ?? a}
          </button>
        ))}
      </div>

      <div className="space-y-0">
        {filtered.map((event) => {
          const colors = platformColors[event.platform] ?? platformColors.all
          return (
            <div
              key={event.event_id}
              className={`flex items-start gap-4 p-4 border-l-4 ${colors.border} bg-white border-b border-r border-t border-gray-100 first:rounded-t-lg last:rounded-b-lg`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <PlatformBadge platform={event.platform} />
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    event.action === 'revoke'
                      ? 'bg-red-100 text-red-700'
                      : event.action === 'drift_scan'
                      ? 'bg-purple-100 text-purple-700'
                      : event.action === 'recertification'
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'bg-blue-100 text-blue-700'
                  }`}>
                    {actionLabels[event.action] ?? event.action}
                  </span>
                  <StatusBadge status={event.status} />
                </div>
                <p className="text-sm font-medium text-gray-900">{event.user_name}</p>
                <p className="text-sm text-gray-600 mt-0.5">{event.details}</p>
                <p className="text-xs text-gray-400 mt-1">
                  {event.package !== '\u2014' && <span>Package: {event.package} &middot; </span>}
                  Initiated by: {event.initiated_by}
                </p>
              </div>
              <div className="text-right shrink-0">
                <p className="text-xs font-mono text-gray-500">
                  {new Date(event.timestamp).toLocaleDateString()}
                </p>
                <p className="text-xs font-mono text-gray-400">
                  {new Date(event.timestamp).toLocaleTimeString()}
                </p>
                <p className="text-xs text-gray-300 mt-1">{event.event_id}</p>
              </div>
            </div>
          )
        })}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-gray-400 py-12">No events match filters.</p>
      )}

      <div className="mt-6">
        <SnowflakeComingSoon />
      </div>
    </div>
  )
}
