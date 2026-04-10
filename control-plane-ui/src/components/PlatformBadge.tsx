import { platformColors } from '../lib/platformColors'

const labels: Record<string, string> = {
  fabric: 'Fabric',
  databricks: 'Databricks',
  snowflake: 'Snowflake',
  all: 'All Platforms',
}

export default function PlatformBadge({ platform }: { platform: string }) {
  const colors = platformColors[platform] ?? platformColors.all
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${colors.badge}`}>
      {labels[platform] ?? platform}
    </span>
  )
}
