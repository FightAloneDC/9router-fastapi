import { useState, useEffect, useCallback } from 'react'
import {
  Terminal,
  Settings,
  ExternalLink,
  Copy,
  Check,
  ChevronDown,
  ChevronUp,
  Shield,
} from 'lucide-react'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Toggle from '../components/ui/Toggle'
import Loading from '../components/ui/Loading'
import { getCliTools, updateCliTool } from '../api/cliTools'
import { CLI_TOOLS } from '../constants/cliTools'

// Config type badge variants
const CONFIG_TYPE_VARIANTS = {
  env: 'info',
  guide: 'primary',
  custom: 'default',
  mitm: 'warning',
}

const CONFIG_TYPE_LABELS = {
  env: 'Environment',
  guide: 'Guide',
  custom: 'Custom',
  mitm: 'MITM',
}

export default function CLIToolsPage() {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [expandedTool, setExpandedTool] = useState(null)
  const [togglingId, setTogglingId] = useState(null)
  const [copiedValue, setCopiedValue] = useState(null)

  // Fetch tool configs from API
  const fetchTools = useCallback(async () => {
    try {
      const res = await getCliTools()
      setTools(res.data)
    } catch (err) {
      console.error('Failed to fetch CLI tools:', err)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTools()
  }, [fetchTools])

  // Get config state for a tool (from API or defaults)
  const getToolState = (toolId) => {
    const serverConfig = tools.find((t) => t.id === toolId)
    return serverConfig || { id: toolId, enabled: false, config_data: {} }
  }

  // Toggle enabled state
  const handleToggle = async (toolId) => {
    setTogglingId(toolId)
    try {
      const current = getToolState(toolId)
      await updateCliTool(toolId, { enabled: !current.enabled })
      await fetchTools()
    } catch (err) {
      console.error('Failed to toggle tool:', err)
    } finally {
      setTogglingId(null)
    }
  }

  // Copy text to clipboard
  const handleCopy = async (text) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopiedValue(text)
      setTimeout(() => setCopiedValue(null), 2000)
    } catch {
      // Fallback for non-HTTPS contexts
      console.warn('Clipboard API unavailable')
    }
  }

  // Get tool icon initials from CLI_TOOLS constant
  const getToolIcon = (toolId) => {
    return CLI_TOOLS[toolId]?.icon || toolId.slice(0, 2).toUpperCase()
  }

  // Get tool color
  const getToolColor = (toolId) => {
    return CLI_TOOLS[toolId]?.color || '#71717a'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh]">
        <Loading size="lg" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-zinc-100">CLI Tools</h1>
          <p className="text-sm text-zinc-500 mt-1">
            Configure AI coding tools to route through 9Router
          </p>
        </div>
        <Badge variant="default" size="md">
          {Object.keys(CLI_TOOLS).length} tools
        </Badge>
      </div>

      {/* Tool Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(CLI_TOOLS).map(([key, tool]) => {
          const state = getToolState(key)
          const isEnabled = state.enabled || false
          const isExpanded = expandedTool === key
          const color = tool.color
          const iconBg = color === '#000000' ? '#ffffff' : color

          return (
            <Card
              key={key}
              className={`hover:border-zinc-600/80 transition-colors ${
                isEnabled ? 'border-emerald-600/30' : ''
              }`}
            >
              {/* Card body */}
              <div className="p-4">
                {/* Tool header */}
                <div className="flex items-center gap-3 mb-3">
                  <div
                    className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold shrink-0"
                    style={{
                      backgroundColor: iconBg + '20',
                      color: color === '#000000' ? '#e4e4e7' : color,
                    }}
                  >
                    {getToolIcon(key)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold text-zinc-100 truncate">
                      {tool.name}
                    </h3>
                    <p className="text-xs text-zinc-500 truncate">
                      {tool.description}
                    </p>
                  </div>
                  <Badge
                    variant={CONFIG_TYPE_VARIANTS[tool.configType] || 'default'}
                    size="sm"
                  >
                    {CONFIG_TYPE_LABELS[tool.configType] || tool.configType}
                  </Badge>
                </div>

                {/* Enable toggle */}
                <div className="flex items-center justify-between mb-3 py-2 px-3 rounded-lg bg-zinc-800/40">
                  <span className="text-xs text-zinc-400">
                    {isEnabled ? 'Enabled' : 'Disabled'}
                  </span>
                  <Toggle
                    checked={isEnabled}
                    onChange={() => handleToggle(key)}
                    disabled={togglingId === key}
                  />
                </div>

                {/* Configure button */}
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => setExpandedTool(isExpanded ? null : key)}
                >
                  <Settings size={14} />
                  Configure
                  {isExpanded ? (
                    <ChevronUp size={14} />
                  ) : (
                    <ChevronDown size={14} />
                  )}
                </Button>

                {/* Expanded configuration panel */}
                {isExpanded && (
                  <div className="mt-3 pt-3 border-t border-zinc-800">
                    {/* env config type: show environment variables */}
                    {tool.configType === 'env' && (
                      <EnvConfigPanel
                        tool={tool}
                        copiedValue={copiedValue}
                        onCopy={handleCopy}
                      />
                    )}

                    {/* guide config type: show step-by-step */}
                    {tool.configType === 'guide' && (
                      <GuideConfigPanel
                        tool={tool}
                        copiedValue={copiedValue}
                        onCopy={handleCopy}
                      />
                    )}

                    {/* custom config type: generic OpenAI-compatible */}
                    {tool.configType === 'custom' && (
                      <CustomConfigPanel
                        tool={tool}
                        copiedValue={copiedValue}
                        onCopy={handleCopy}
                      />
                    )}

                    {/* mitm config type: link to MITM page */}
                    {tool.configType === 'mitm' && (
                      <MitmConfigPanel tool={tool} />
                    )}
                  </div>
                )}
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}

// --- Sub-components for config panels ---

function EnvConfigPanel({ tool, copiedValue, onCopy }) {
  const envVars = tool.envVars || {}

  return (
    <div className="space-y-3">
      <p className="text-xs text-zinc-400">
        Set these environment variables before running {tool.name}:
      </p>
      <div className="space-y-2">
        {Object.entries(envVars).map(([key, varName]) => (
          <div
            key={key}
            className="flex items-center justify-between rounded-lg bg-zinc-800/60 px-3 py-2"
          >
            <code className="text-xs text-emerald-400 font-mono truncate">
              {varName}
            </code>
            <button
              onClick={() => onCopy(varName)}
              className="p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors shrink-0 ml-2"
              title="Copy variable name"
            >
              {copiedValue === varName ? (
                <Check size={12} className="text-emerald-400" />
              ) : (
                <Copy size={12} />
              )}
            </button>
          </div>
        ))}
      </div>

      {/* Default models */}
      {tool.defaultModels && tool.defaultModels.length > 0 && (
        <div>
          <p className="text-xs text-zinc-500 mb-1.5">Default models:</p>
          <div className="flex flex-wrap gap-1.5">
            {tool.defaultModels.map((m) => (
              <Badge key={m.id} variant="default" size="sm">
                {m.name}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Example shell snippet */}
      <div className="rounded-lg bg-zinc-950 border border-zinc-800 p-3">
        <p className="text-[11px] text-zinc-500 mb-1">Example:</p>
        <code className="text-xs text-zinc-300 font-mono leading-relaxed block">
          <span className="text-zinc-500">$</span>{' '}
          export ANTHROPIC_BASE_URL="http://localhost:20128"
        </code>
      </div>
    </div>
  )
}

function GuideConfigPanel({ tool, copiedValue, onCopy }) {
  const steps = tool.guideSteps || []

  if (steps.length === 0) {
    return (
      <div className="text-center py-3">
        <p className="text-xs text-zinc-500">
          Configuration guide coming soon.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <p className="text-xs text-zinc-400">
        Follow these steps to connect {tool.name}:
      </p>
      <div className="space-y-2">
        {steps.map((step) => (
          <div
            key={step.step}
            className="flex items-start gap-3 rounded-lg bg-zinc-800/40 px-3 py-2.5"
          >
            {/* Step number */}
            <div className="w-5 h-5 rounded-full bg-zinc-700 flex items-center justify-center text-[10px] font-bold text-zinc-300 shrink-0 mt-0.5">
              {step.step}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-xs font-medium text-zinc-200">{step.title}</p>
              {step.desc && (
                <p className="text-[11px] text-zinc-500 mt-0.5">{step.desc}</p>
              )}
              {step.value && (
                <div className="flex items-center gap-2 mt-1.5">
                  <code className="text-xs text-emerald-400 font-mono bg-zinc-900 px-2 py-1 rounded">
                    {step.value}
                  </code>
                  {step.copyable && (
                    <button
                      onClick={() => onCopy(step.value)}
                      className="p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors"
                      title="Copy"
                    >
                      {copiedValue === step.value ? (
                        <Check size={12} className="text-emerald-400" />
                      ) : (
                        <Copy size={12} />
                      )}
                    </button>
                  )}
                </div>
              )}
              {step.type === 'apiKeySelector' && (
                <p className="text-[11px] text-amber-400/80 mt-1">
                  Use your 9Router API key
                </p>
              )}
              {step.type === 'modelSelector' && (
                <p className="text-[11px] text-blue-400/80 mt-1">
                  Select your preferred model
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function CustomConfigPanel({ tool, copiedValue, onCopy }) {
  const exampleConfig = `{
  "api_base": "http://localhost:20128",
  "model": "your-model-name"
}`

  return (
    <div className="space-y-3">
      <p className="text-xs text-zinc-400">
        Configure {tool.name} to use the OpenAI-compatible API endpoint:
      </p>
      <div className="space-y-2">
        <div className="flex items-center justify-between rounded-lg bg-zinc-800/60 px-3 py-2">
          <div>
            <p className="text-xs font-medium text-zinc-200">Base URL</p>
            <code className="text-xs text-emerald-400 font-mono">
              http://localhost:20128
            </code>
          </div>
          <button
            onClick={() => onCopy('http://localhost:20128')}
            className="p-1 rounded hover:bg-zinc-700 text-zinc-500 hover:text-zinc-300 transition-colors shrink-0"
            title="Copy"
          >
            {copiedValue === 'http://localhost:20128' ? (
              <Check size={12} className="text-emerald-400" />
            ) : (
              <Copy size={12} />
            )}
          </button>
        </div>
        <div className="flex items-center justify-between rounded-lg bg-zinc-800/60 px-3 py-2">
          <div>
            <p className="text-xs font-medium text-zinc-200">API Format</p>
            <p className="text-xs text-zinc-500">OpenAI-compatible</p>
          </div>
          <Badge variant="default" size="sm">
            /v1
          </Badge>
        </div>
      </div>
      <div className="rounded-lg bg-zinc-950 border border-zinc-800 p-3">
        <p className="text-[11px] text-zinc-500 mb-1">Example config:</p>
        <pre className="text-xs text-zinc-300 font-mono leading-relaxed whitespace-pre-wrap">
          {exampleConfig}
        </pre>
      </div>
    </div>
  )
}

function MitmConfigPanel({ tool }) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2 rounded-lg bg-amber-600/10 border border-amber-500/20 px-3 py-2.5">
        <Shield size={14} className="text-amber-400 shrink-0 mt-0.5" />
        <p className="text-xs text-amber-200/90">
          {tool.name} uses MITM proxy interception. Configure it from the MITM
          page.
        </p>
      </div>
      <a
        href="/mitm"
        className="flex items-center justify-center gap-2 w-full py-2 rounded-lg border border-zinc-700 text-xs text-zinc-400 hover:text-zinc-200 hover:border-zinc-600 transition-colors"
      >
        <Shield size={12} />
        Go to MITM Settings
        <ExternalLink size={10} />
      </a>
    </div>
  )
}
