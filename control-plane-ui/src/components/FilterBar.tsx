interface FilterBarProps {
  platforms: string[]
  activePlatform: string
  onPlatformChange: (p: string) => void
  searchValue?: string
  onSearchChange?: (v: string) => void
  searchPlaceholder?: string
}

const labels: Record<string, string> = {
  all: 'All',
  fabric: 'Fabric',
  databricks: 'Databricks',
}

export default function FilterBar({
  platforms,
  activePlatform,
  onPlatformChange,
  searchValue,
  onSearchChange,
  searchPlaceholder = 'Search...',
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
