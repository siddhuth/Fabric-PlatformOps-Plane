import { useReducer, useEffect, useCallback } from 'react'
import { useProvisioningEvents } from '../hooks/useFixtureData'
import PlatformBadge from '../components/PlatformBadge'
import StatusBadge from '../components/StatusBadge'
import { platformColors } from '../lib/platformColors'

interface AnimState {
  selectedId: string | null
  visibleSteps: number
  playing: boolean
}

type AnimAction =
  | { type: 'select'; id: string }
  | { type: 'replay' }
  | { type: 'tick' }
  | { type: 'stop' }

function animReducer(state: AnimState, action: AnimAction): AnimState {
  switch (action.type) {
    case 'select':
      return { selectedId: action.id, visibleSteps: 0, playing: true }
    case 'replay':
      return { ...state, visibleSteps: 0, playing: true }
    case 'tick':
      return { ...state, visibleSteps: state.visibleSteps + 1 }
    case 'stop':
      return { ...state, playing: false }
  }
}

export default function ProvisionFlow() {
  const data = useProvisioningEvents()
  const [state, dispatch] = useReducer(animReducer, {
    selectedId: null,
    visibleSteps: 0,
    playing: false,
  })

  const trace = data?.traces.find((t) => t.trace_id === state.selectedId) ?? null

  const selectTrace = useCallback((id: string) => dispatch({ type: 'select', id }), [])
  const replay = useCallback(() => dispatch({ type: 'replay' }), [])

  useEffect(() => {
    if (!state.playing || !trace) return
    if (state.visibleSteps >= trace.steps.length) {
      dispatch({ type: 'stop' })
      return
    }
    const timer = setTimeout(() => dispatch({ type: 'tick' }), 400)
    return () => clearTimeout(timer)
  }, [state.playing, state.visibleSteps, trace])

  if (!data) return <p className="text-gray-500">Loading...</p>

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Provisioning Flow</h1>
        <p className="text-gray-500 mt-1">
          {data.total_traces} traces &middot; Select a trace to view step-by-step execution
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {data.traces.map((t) => (
          <button
            key={t.trace_id}
            onClick={() => selectTrace(t.trace_id)}
            className={`text-left p-4 rounded-lg border-2 transition-all ${
              state.selectedId === t.trace_id
                ? 'border-blue-500 bg-blue-50 shadow-sm'
                : 'border-gray-200 bg-white hover:border-gray-300'
            }`}
          >
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-mono text-gray-500">{t.trace_id}</span>
              <StatusBadge status={t.status} />
            </div>
            <p className="font-medium text-sm text-gray-900">{t.user.name}</p>
            <p className="text-xs text-gray-500 mt-0.5">{t.package}</p>
            <div className="flex items-center gap-1.5 mt-2">
              {t.platforms.map((p) => (
                <PlatformBadge key={p} platform={p} />
              ))}
            </div>
            <p className="text-xs text-gray-400 mt-2">
              {t.steps.length} steps &middot; {(t.duration_ms / 1000).toFixed(1)}s
            </p>
          </button>
        ))}
      </div>

      {trace && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                {trace.user.name} &mdash; {trace.package}
              </h2>
              <p className="text-sm text-gray-500 mt-0.5">
                Trigger: {trace.trigger} &middot; {new Date(trace.timestamp).toLocaleString()}
              </p>
            </div>
            <button
              onClick={replay}
              className="px-3 py-1.5 text-sm font-medium bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors"
            >
              Replay
            </button>
          </div>

          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-gray-200" />
            <div className="space-y-0">
              {trace.steps.map((step, i) => {
                const visible = i < state.visibleSteps
                const colors = platformColors[step.platform] ?? platformColors.all
                return (
                  <div
                    key={step.seq}
                    className={`relative pl-10 py-3 transition-all duration-300 ${
                      visible ? 'opacity-100 translate-x-0' : 'opacity-0 -translate-x-4'
                    }`}
                  >
                    <div className={`absolute left-2.5 top-4 w-3 h-3 rounded-full border-2 border-white shadow ${
                      step.status === 'success' ? 'bg-green-500' : step.status === 'failed' ? 'bg-red-500' : 'bg-gray-400'
                    }`} />

                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <PlatformBadge platform={step.platform} />
                          <span className={`text-xs font-medium px-2 py-0.5 rounded ${colors.bg} ${colors.text}`}>
                            {step.layer}
                          </span>
                          <span className="text-xs text-gray-500 font-mono">{step.duration_ms}ms</span>
                        </div>
                        <p className="text-sm font-medium text-gray-900">
                          {step.action}: {step.target}
                        </p>
                        <p className="text-xs text-gray-500 mt-0.5">{step.detail}</p>
                      </div>
                      <StatusBadge status={step.status} />
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
