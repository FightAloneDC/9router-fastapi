import { useMemo, useState, useEffect, useCallback, useRef } from 'react'
import {
  ReactFlow,
  Handle,
  Position,
  Controls,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import useCatalogStore from '../stores/catalogStore'

// Normalize provider ID: lowercase, strip spaces/special chars
function normalizeId(id) {
  return (id || '').toLowerCase().replace(/[^a-z0-9-]/g, '')
}

function getProviderConfig(providerId) {
  const id = normalizeId(providerId)
  // Try exact, lowercase, and alias match
  return useCatalogStore.getState().providers[providerId] || useCatalogStore.getState().providers[id] || { color: '#6b7280', name: providerId }
}

// Try multiple image path variations
function getProviderImageUrls(providerId) {
  const id = normalizeId(providerId)
  const raw = providerId || ''
  // Deduplicate while preserving order
  const seen = new Set()
  const paths = []
  for (const candidate of [raw, id]) {
    if (candidate && !seen.has(candidate)) {
      seen.add(candidate)
      paths.push(`/providers/${candidate}.png`)
    }
  }
  return paths
}

function ProviderNode({ data }) {
  const { label, color, imageUrls, textIcon, active } = data
  const [imgIndex, setImgIndex] = useState(0)
  const [imgFailed, setImgFailed] = useState(false)

  const handleImgError = () => {
    if (imgIndex < imageUrls.length - 1) {
      setImgIndex((i) => i + 1)
    } else {
      setImgFailed(true)
    }
  }

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 rounded-lg border-2 transition-all duration-300 bg-zinc-900"
      style={{
        borderColor: active ? color : '#3f3f46',
        boxShadow: active ? `0 0 16px ${color}40` : 'none',
        minWidth: '150px',
      }}
    >
      <Handle type="target" position={Position.Top} id="top" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Bottom} id="bottom" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Left} id="left" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="target" position={Position.Right} id="right" className="!bg-transparent !border-0 !w-0 !h-0" />

      <div
        className="w-8 h-8 rounded-md flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${color}15` }}
      >
        {!imgFailed && imageUrls.length > 0 ? (
          <img src={imageUrls[imgIndex]} alt={label} className="w-6 h-6 rounded-sm object-contain" onError={handleImgError} />
        ) : (
          <span className="text-sm font-bold" style={{ color }}>{textIcon}</span>
        )}
      </div>

      <span
        className="text-sm font-medium truncate"
        style={{ color: active ? color : '#e4e4e7' }}
      >
        {label}
      </span>

      {active && (
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: color }} />
          <span className="relative inline-flex rounded-full h-2 w-2" style={{ backgroundColor: color }} />
        </span>
      )}
    </div>
  )
}

function RouterNode({ data }) {
  return (
    <div className="flex items-center justify-center px-5 py-3 rounded-xl border-2 border-blue-500 bg-blue-500/5 shadow-md min-w-[130px]">
      <Handle type="source" position={Position.Top} id="top" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Bottom} id="bottom" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Left} id="left" className="!bg-transparent !border-0 !w-0 !h-0" />
      <Handle type="source" position={Position.Right} id="right" className="!bg-transparent !border-0 !w-0 !h-0" />

      <span className="text-sm font-bold text-blue-400">9Router</span>
      {data.activeCount > 0 && (
        <span className="ml-2 px-1.5 py-0.5 rounded-full bg-blue-500 text-white text-xs font-bold">
          {data.activeCount}
        </span>
      )}
    </div>
  )
}

const nodeTypes = { provider: ProviderNode, router: RouterNode }

function buildLayout(providers, activeSet, lastSet, errorSet) {
  const nodeW = 180
  const nodeH = 30
  const routerW = 120
  const routerH = 44
  const nodeGap = 24
  // Filter out providers with no name to avoid duplicate keys
  // stats.byProvider uses "name" field, connections use "provider" field
  const validProviders = providers.filter((p) => p.name || p.provider)
  const count = validProviders.length

  const minRx = ((nodeW + nodeGap) * count) / (2 * Math.PI)
  const rx = Math.max(320, minRx)
  const ry = Math.max(200, rx * 0.55)

  if (count === 0) {
    return {
      nodes: [{ id: 'router', type: 'router', position: { x: 0, y: 0 }, data: { activeCount: 0 }, draggable: false }],
      edges: [],
    }
  }

  const nodes = []
  const edges = []

  nodes.push({
    id: 'router',
    type: 'router',
    position: { x: -routerW / 2, y: -routerH / 2 },
    data: { activeCount: activeSet.size },
    draggable: false,
  })

  const edgeStyle = (active, last, error) => {
    if (error) return { stroke: '#f87171', strokeWidth: 2.5, opacity: 1 }
    if (active) return { stroke: '#4ade80', strokeWidth: 2.5, opacity: 1 }
    if (last) return { stroke: '#fbbf24', strokeWidth: 2, opacity: 0.9 }
    return { stroke: '#71717a', strokeWidth: 1.5, opacity: 0.6 }
  }

  validProviders.forEach((p, i) => {
    // stats.byProvider uses "name", connections use "provider"
    const pid = p.provider || p.name
    const config = getProviderConfig(pid)
    const active = activeSet.has(pid?.toLowerCase())
    const last = !active && lastSet.has(pid?.toLowerCase())
    const error = !active && errorSet.has(pid?.toLowerCase())
    const nodeId = `provider-${pid}`

    const angle = -Math.PI / 2 + (2 * Math.PI * i) / count
    const cx = rx * Math.cos(angle)
    const cy = ry * Math.sin(angle)

    let sourceHandle, targetHandle
    if (Math.abs(angle + Math.PI / 2) < Math.PI / 4 || Math.abs(angle - 3 * Math.PI / 2) < Math.PI / 4) {
      sourceHandle = 'top'; targetHandle = 'bottom'
    } else if (Math.abs(angle - Math.PI / 2) < Math.PI / 4) {
      sourceHandle = 'bottom'; targetHandle = 'top'
    } else if (cx > 0) {
      sourceHandle = 'right'; targetHandle = 'left'
    } else {
      sourceHandle = 'left'; targetHandle = 'right'
    }

    nodes.push({
      id: nodeId,
      type: 'provider',
      position: { x: cx - nodeW / 2, y: cy - nodeH / 2 },
      data: {
        label: (config.name !== pid ? config.name : null) || p.name || pid,
        color: config.color || '#6b7280',
        imageUrls: getProviderImageUrls(pid),
        textIcon: config.textIcon || (pid || '?').slice(0, 2).toUpperCase(),
        active,
      },
      draggable: false,
    })

    edges.push({
      id: `e-${nodeId}`,
      source: 'router',
      sourceHandle,
      target: nodeId,
      targetHandle,
      animated: active,
      style: edgeStyle(active, last, error),
    })
  })

  return { nodes, edges }
}

export default function ProviderTopology({ providers = [], activeRequests = [], lastProvider = '', errorProvider = '' }) {
  const activeKey = useMemo(
    () => activeRequests.map((r) => r.provider?.toLowerCase()).filter(Boolean).sort().join(','),
    [activeRequests]
  )
  const lastKey = lastProvider?.toLowerCase() || ''
  const errorKey = errorProvider?.toLowerCase() || ''

  const activeSet = useMemo(() => new Set(activeKey ? activeKey.split(',') : []), [activeKey])
  const lastSet = useMemo(() => new Set(lastKey ? [lastKey] : []), [lastKey])
  const errorSet = useMemo(() => new Set(errorKey ? [errorKey] : []), [errorKey])

  const { nodes, edges } = useMemo(
    () => buildLayout(providers, activeSet, lastSet, errorSet),
    [providers, activeSet, lastKey, errorKey]
  )

  const providersKey = useMemo(
    () => providers.map((p) => p.provider).sort().join(','),
    [providers]
  )

  const rfInstance = useRef(null)
  const containerRef = useRef(null)
  const fitOpts = { padding: 0.2, duration: 200 }

  const onInit = useCallback((instance) => {
    rfInstance.current = instance
    setTimeout(() => instance.fitView(fitOpts), 50)
  }, [])

  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const ro = new ResizeObserver(() => {
      if (rfInstance.current) rfInstance.current.fitView(fitOpts)
    })
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  useEffect(() => {
    if (rfInstance.current) {
      const id = setTimeout(() => rfInstance.current.fitView(fitOpts), 50)
      return () => clearTimeout(id)
    }
  }, [nodes.length])

  return (
    <div ref={containerRef} className="h-[320px] w-full min-w-0 rounded-lg border border-zinc-800 bg-zinc-900/30 sm:h-[480px]">
      <style>{`
        .react-flow__controls {
          background: transparent !important;
          border: none !important;
          box-shadow: none !important;
        }
        .react-flow__controls button {
          background: #27272a !important;
          border: 1px solid #3f3f46 !important;
          color: #a1a1aa !important;
          width: 28px !important;
          height: 28px !important;
        }
        .react-flow__controls button:hover {
          background: #3f3f46 !important;
          color: #e4e4e7 !important;
        }
        .react-flow__controls button svg {
          fill: currentColor !important;
        }
      `}</style>
      {providers.length === 0 ? (
        <div className="h-full flex items-center justify-center text-zinc-500 text-sm">
          No providers connected
        </div>
      ) : (
        <ReactFlow
          key={providersKey}
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={fitOpts}
          minZoom={0.1}
          maxZoom={2}
          onInit={onInit}
          proOptions={{ hideAttribution: true }}
          panOnDrag
          zoomOnScroll
          zoomOnPinch
          zoomOnDoubleClick
          preventScrolling={false}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
        >
          <Controls showInteractive={false} />
        </ReactFlow>
      )}
    </div>
  )
}
