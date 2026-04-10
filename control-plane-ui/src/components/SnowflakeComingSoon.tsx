export default function SnowflakeComingSoon() {
  return (
    <div className="rounded-lg border-2 border-dashed border-cyan-200 bg-cyan-50/50 p-4 flex items-center gap-3 opacity-60">
      <div className="w-8 h-8 rounded-lg bg-cyan-100 flex items-center justify-center text-cyan-600 font-bold text-xs shrink-0">
        SF
      </div>
      <div>
        <p className="text-sm font-medium text-cyan-700">
          Snowflake
          <span className="ml-2 text-xs font-medium bg-cyan-100 text-cyan-600 rounded-full px-2 py-0.5">
            Coming Soon
          </span>
        </p>
        <p className="text-xs text-cyan-500 mt-0.5">Phase 3 — Q3 2026</p>
      </div>
    </div>
  )
}
