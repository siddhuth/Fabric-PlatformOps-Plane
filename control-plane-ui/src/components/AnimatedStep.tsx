import PlatformBadge from './PlatformBadge'
import StatusBadge from './StatusBadge'
import { platformColors } from '../lib/platformColors'
import type { ProvisionStep } from '../types'

interface AnimatedStepProps {
  step: ProvisionStep
  visible: boolean
}

export default function AnimatedStep({ step, visible }: AnimatedStepProps) {
  const colors = platformColors[step.platform] ?? platformColors.all
  return (
    <div
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
}
