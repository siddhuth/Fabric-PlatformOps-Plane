export const platformColors: Record<string, { bg: string; border: string; text: string; badge: string }> = {
  fabric: {
    bg: 'bg-blue-50',
    border: 'border-blue-400',
    text: 'text-blue-700',
    badge: 'bg-blue-100 text-blue-800',
  },
  databricks: {
    bg: 'bg-orange-50',
    border: 'border-orange-400',
    text: 'text-orange-700',
    badge: 'bg-orange-100 text-orange-800',
  },
  snowflake: {
    bg: 'bg-cyan-50',
    border: 'border-cyan-300',
    text: 'text-cyan-600',
    badge: 'bg-cyan-100 text-cyan-700',
  },
  all: {
    bg: 'bg-gray-50',
    border: 'border-gray-400',
    text: 'text-gray-700',
    badge: 'bg-gray-100 text-gray-800',
  },
}

export const severityColors: Record<string, string> = {
  high: 'bg-red-100 text-red-800 border-red-300',
  medium: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  low: 'bg-green-100 text-green-800 border-green-300',
}

export const statusColors: Record<string, string> = {
  success: 'bg-green-100 text-green-800',
  partial: 'bg-yellow-100 text-yellow-800',
  failed: 'bg-red-100 text-red-800',
  warning: 'bg-yellow-100 text-yellow-800',
}
