interface FilterBarProps {
  platforms: string[]
  activePlatform: string
  onPlatformChange: (p: string) => void
  searchValue?: string
  onSearchChange?: (v: string) => void
  searchPlaceholder?: string
  showSnowflake?: boolean
}

const labels: Record<string, string> = {
  all: 'All',
  fabric: 'Fabric',
  databricks: 'Databricks',
  snowflake: 'Snowflake',
}

export default function FilterBar({
  platforms,
  activePlatform,
  onPlatformChange,
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search...',
  showSnowflake = true,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3 mb-6">
      <div className="flex rounded-lg bg-gray-100 p-1">
        {['all', ...platforms].map((p) => (
          <button
            key={p}
            onClick={() => onPlatformChange(p)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              activePlatform === p
                ? 'bg-white text-gray-900 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {labels[p] ?? p}
          </button>
        ))}
        {showSnowflake && !platforms.includes('snowflake') && (
          <span className="px-3 py-1.5 text-sm font-medium text-cyan-400 cursor-default" title="Phase 3 — Q3 2026">
            Snowflake
            <span className="ml-1 text-[10px] align-super">soon</span>
          </span>
        )}
      </div>
      {onSearchChange && (
        <input
          type="text"
          value={searchValue ?? ''}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder={searchPlaceholder}
          className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      )}
    </div>
  )
}
