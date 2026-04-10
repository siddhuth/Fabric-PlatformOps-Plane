import { useState, useMemo } from 'react'
import { useAccessMatrix } from '../hooks/useFixtureData'
import FilterBar from '../components/FilterBar'
import PermissionCell, { GrantDetail } from '../components/PermissionCell'
import SnowflakeComingSoon from '../components/SnowflakeComingSoon'

export default function AccessMatrix() {
  const data = useAccessMatrix()
  const [platform, setPlatform] = useState('all')
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<{ principal: string; resource: string } | null>(null)

  const filtered = useMemo(() => {
    if (!data) return []
    return data.matrix.filter((e) => {
      if (platform !== 'all' && e.platform !== platform) return false
      if (search) {
        const q = search.toLowerCase()
        return (
          e.principal.toLowerCase().includes(q) ||
          e.resource.toLowerCase().includes(q) ||
          e.resource_type.toLowerCase().includes(q) ||
          e.package.toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [data, platform, search])

  const principals = useMemo(() => [...new Set(filtered.map((e) => e.principal))], [filtered])

  const resources = useMemo(() => {
    const seen = new Set<string>()
    return filtered
      .map((e) => `${e.resource_type}:${e.resource}`)
      .filter((r) => {
        if (seen.has(r)) return false
        seen.add(r)
        return true
      })
  }, [filtered])

  const cellMap = useMemo(() => {
    const m = new Map<string, typeof filtered[0]>()
    for (const e of filtered) {
      m.set(`${e.principal}||${e.resource_type}:${e.resource}`, e)
    }
    return m
  }, [filtered])

  if (!data) return <p className="text-gray-500">Loading...</p>

  const selectedEntry = selected
    ? cellMap.get(`${selected.principal}||${selected.resource}`)
    : null

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Access Matrix</h1>
        <p className="text-gray-500 mt-1">
          {data.unique_principals} principals &middot; {data.total_entries} grants
        </p>
      </div>

      <FilterBar
        platforms={data.platforms}
        activePlatform={platform}
        onPlatformChange={setPlatform}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Filter by principal, resource, or package..."
      />

      {selectedEntry && (
        <GrantDetail entry={selectedEntry} onClose={() => setSelected(null)} />
      )}

      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="bg-gray-50">
              <th className="sticky left-0 z-10 bg-gray-50 px-3 py-2 text-left font-medium text-gray-600 border-b">
                Principal
              </th>
              {resources.map((r) => (
                <th key={r} className="px-2 py-2 text-left font-medium text-gray-600 border-b whitespace-nowrap max-w-[120px] truncate" title={r}>
                  {r.split(':')[0]}
                  <br />
                  <span className="font-normal text-gray-400">{r.split(':').slice(1).join(':') || '(all)'}</span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {principals.map((p) => (
              <tr key={p} className="hover:bg-gray-50">
                <td className="sticky left-0 z-10 bg-white px-3 py-2 font-medium text-gray-900 border-b whitespace-nowrap">
                  {p.split('@')[0]}
                </td>
                {resources.map((r) => {
                  const entry = cellMap.get(`${p}||${r}`)
                  return (
                    <PermissionCell
                      key={r}
                      entry={entry}
                      isSelected={selected?.principal === p && selected?.resource === r}
                      onClick={() => setSelected({ principal: p, resource: r })}
                    />
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="mt-6">
        <SnowflakeComingSoon />
      </div>
    </div>
  )
}
