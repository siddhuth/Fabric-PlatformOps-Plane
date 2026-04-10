import PlatformBadge from './PlatformBadge'
import { severityColors } from '../lib/platformColors'
import type { DriftFinding } from '../types'

const categoryLabels: Record<string, string> = {
  shadow_access: 'Shadow Access',
  over_provisioned: 'Over-Provisioned',
  under_provisioned: 'Under-Provisioned',
}

export default function DriftCard({ finding }: { finding: DriftFinding }) {
  const f = finding
  return (
    <div className={`rounded-lg border ${severityColors[f.severity]} p-4`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-bold">{f.id}</span>
          <PlatformBadge platform={f.platform} />
          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
            f.category === 'shadow_access'
              ? 'bg-red-200 text-red-800'
              : f.category === 'over_provisioned'
              ? 'bg-orange-200 text-orange-800'
              : 'bg-blue-200 text-blue-800'
          }`}>
            {categoryLabels[f.category] ?? f.category}
          </span>
        </div>
        <span className="text-xs text-gray-500">
          {new Date(f.detected_at).toLocaleString()}
        </span>
      </div>

      <p className="text-sm font-medium text-gray-900 mb-2">{f.detail}</p>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div>
          <span className="text-gray-500">Securable</span>
          <p className="font-medium text-gray-900 mt-0.5 break-all">{f.securable}</p>
        </div>
        <div>
          <span className="text-gray-500">Principal</span>
          <p className="font-medium text-gray-900 mt-0.5">{f.principal}</p>
        </div>
        <div>
          <span className="text-gray-500">Declared</span>
          <p className="font-mono font-medium text-green-700 mt-0.5">{f.declared}</p>
        </div>
        <div>
          <span className="text-gray-500">Actual</span>
          <p className="font-mono font-medium text-red-700 mt-0.5">{f.actual}</p>
        </div>
      </div>

      {f.package !== '\u2014' && (
        <p className="text-xs text-gray-500 mt-2">Source package: {f.package}</p>
      )}
    </div>
  )
}
