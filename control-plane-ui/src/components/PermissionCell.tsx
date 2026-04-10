import PlatformBadge from './PlatformBadge'
import type { MatrixEntry } from '../types'

interface PermissionCellProps {
  entry: MatrixEntry | undefined
  isSelected: boolean
  onClick: () => void
}

export default function PermissionCell({ entry, isSelected, onClick }: PermissionCellProps) {
  return (
    <td
      className={`px-2 py-2 border-b text-center transition-colors ${
        entry ? 'cursor-pointer hover:bg-blue-50' : ''
      } ${isSelected ? 'bg-blue-100 ring-2 ring-blue-400' : ''}`}
      onClick={() => entry && onClick()}
    >
      {entry ? (
        <span
          className={`inline-block w-3 h-3 rounded-full ${
            entry.platform === 'fabric' ? 'bg-blue-500' : 'bg-orange-500'
          }`}
          title={entry.permission || 'Per policy'}
        />
      ) : (
        <span className="text-gray-200">&mdash;</span>
      )}
    </td>
  )
}

interface GrantDetailProps {
  entry: MatrixEntry
  onClose: () => void
}

export function GrantDetail({ entry, onClose }: GrantDetailProps) {
  return (
    <div className="mb-6 p-4 rounded-lg bg-white border border-gray-200 shadow-sm">
      <div className="flex items-center justify-between mb-2">
        <h3 className="font-semibold text-gray-900">Grant Detail</h3>
        <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-sm">
          Close
        </button>
      </div>
      <dl className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div><dt className="text-gray-500">Principal</dt><dd className="font-medium">{entry.principal}</dd></div>
        <div><dt className="text-gray-500">Resource</dt><dd className="font-medium">{entry.resource_type}: {entry.resource || '(all)'}</dd></div>
        <div><dt className="text-gray-500">Permission</dt><dd className="font-medium">{entry.permission || 'Per policy'}</dd></div>
        <div><dt className="text-gray-500">Source Package</dt><dd className="font-medium">{entry.package}</dd></div>
        <div><dt className="text-gray-500">Group</dt><dd className="font-medium">{entry.group}</dd></div>
        <div><dt className="text-gray-500">Platform</dt><dd><PlatformBadge platform={entry.platform} /></dd></div>
      </dl>
    </div>
  )
}
