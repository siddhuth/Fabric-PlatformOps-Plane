import { statusColors } from '../lib/platformColors'

export default function StatusBadge({ status }: { status: string }) {
  const color = statusColors[status] ?? 'bg-gray-100 text-gray-800'
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${color}`}>
      {status}
    </span>
  )
}
