import { useState, useMemo } from 'react'
import { useDriftResults } from '../hooks/useFixtureData'
import FilterBar from '../components/FilterBar'
import DriftCard from '../components/DriftCard'
import SnowflakeComingSoon from '../components/SnowflakeComingSoon'

export default function DriftDashboard() {
  const data = useDriftResults()
  const [platform, setPlatform] = useState('all')
  const [severity, setSeverity] = useState('all')

  const filtered = useMemo(() => {
    if (!data) return []
    return data.findings.filter((f) => {
      if (platform !== 'all' && f.platform !== platform) return false
      if (severity !== 'all' && f.severity !== severity) return false
      return true
    })
  }, [data, platform, severity])

  if (!data) return <p className="text-gray-500">Loading...</p>

  const categoryLabels: Record<string, string> = {
    shadow_access: 'Shadow Access',
    over_provisioned: 'Over-Provisioned',
    under_provisioned: 'Under-Provisioned',
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Drift Dashboard</h1>
        <p className="text-gray-500 mt-1">
          Last scan: {new Date(data.scan_timestamp).toLocaleString()} &middot;{' '}
          {data.total_findings} findings
        </p>
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <SummaryCard label="Total" value={data.total_findings} color="bg-gray-100 text-gray-900" />
        <SummaryCard label="High" value={data.summary.high} color="bg-red-50 text-red-700" />
        <SummaryCard label="Medium" value={data.summary.medium} color="bg-yellow-50 text-yellow-700" />
        <SummaryCard label="Low" value={data.summary.low} color="bg-green-50 text-green-700" />
        <div className="rounded-lg bg-white border border-gray-200 p-4">
          <p className="text-xs text-gray-500 mb-2">By Category</p>
          {Object.entries(data.summary.by_category).map(([cat, count]) => (
            <div key={cat} className="flex items-center justify-between text-xs mb-1">
              <span className="text-gray-600">{categoryLabels[cat] ?? cat}</span>
              <span className="font-medium text-gray-900">{count}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-6">
        <FilterBar
          platforms={['fabric', 'databricks']}
          activePlatform={platform}
          onPlatformChange={setPlatform}
        />
        <div className="flex gap-2">
          {['all', 'high', 'medium', 'low'].map((s) => (
            <button
              key={s}
              onClick={() => setSeverity(s)}
              className={`px-3 py-1 text-xs font-medium rounded-full transition-colors ${
                severity === s
                  ? 'bg-gray-900 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {s === 'all' ? 'All Severities' : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-4">
        {filtered.map((f) => (
          <DriftCard key={f.id} finding={f} />
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-gray-400 py-12">No drift findings match filters.</p>
      )}

      <div className="mt-6">
        <SnowflakeComingSoon />
      </div>
    </div>
  )
}

function SummaryCard({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className={`rounded-lg p-4 ${color}`}>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-xs mt-1">{label}</p>
    </div>
  )
}
